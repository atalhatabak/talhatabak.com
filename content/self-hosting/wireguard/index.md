---
title: "WireGuard Setup"
description: "A VPN server: sending clients to the internet through the VPN, letting clients talk to each other and making some services reachable only over the VPN."
date: 2026-11-21T00:13:00+03:00
chapter: "7"
tags: ["wireguard", "vpn", "firewalld"]
---
> [!abstract] Requirements
> - [4 Docker Setup](/self-hosting/docker/) and [5 Firewalld Configuration](/self-hosting/firewalld/) must be done (this part changes the configuration of both).
>
> **Assumptions**
> - The outside network interface is `eth0`, it is managed by NetworkManager, and its IPv6 address is set statically.
> - The VPN networks are `10.8.0.0/24` (IPv4) and `fd42:8::/64` (IPv6); the server's VPN address is `10.8.0.1` / `fd42:8::1`.
> - WireGuard listens on port `51820/udp`.
> - Commands are run on the server with root rights (`sudo`).

We'll use WireGuard for these things:

1. Sending clients to the internet through the VPN
2. Letting clients talk to each other (for example a laptop and a phone)
3. Making some services on the server (for example the [iRedAdmin](term:iredadmin) panel) reachable only over the VPN instead of by everyone

## Installation

```bash
sudo dnf install wireguard-tools qrencode
```

> [!note]
> The WireGuard kernel module is already in the Rocky Linux 10 kernel, so we only install the tools. `qrencode` is for showing the phone configuration as a QR code.

## Creating the Key Pair

Let's create the key pair the WireGuard service will use:

```bash
sudo sh -c 'cd /etc/wireguard && umask 077 && wg genkey | tee server.key | wg pubkey > server.pub'
```

> [!note]
> `cd` and `umask` are commands of the shell itself, so running them as `sudo cd` or `sudo umask` doesn't affect the current shell. That's why we run the commands in a single root shell with `sudo sh -c`. `umask 077` makes sure only root can read the key files we create.

## Permanent IP Forwarding

> [!note]
> We turn on [IP forwarding](term:ip-forwarding) so that packets can be passed from one interface to another (in practice, so that traffic from the VPN interface can go out to the internet).

> [!note]
> Docker already turns forwarding on, but only when its own service starts. This file turns forwarding on at boot, independent of Docker.

### Check IPv6 First

On Linux, once IPv6 forwarding is on, the kernel no longer accepts [Router Advertisements](term:slaac) (RA). If the [VPS](term:vps) gets its IPv6 address through RA (SLAAC), the IPv6 connection may drop the moment we turn forwarding on. So before turning forwarding on, let's check the default IPv6 route:

```bash
ip -6 route show default
```

The output should look similar to this:

```text
default via fe80::1 dev eth0 proto static metric 100 pref medium
```

On this server IPv6 is static (`proto static`) and RA is not used, so turning forwarding on doesn't affect the IPv6 connection. If the output shows `proto ra`, you also need to add the line `net.ipv6.conf.eth0.accept_ra = 2` to the file below.

### Turning On Forwarding

Let's create the file `/etc/sysctl.d/90-wireguard.conf` with the content below:

```ini {title="/etc/sysctl.d/90-wireguard.conf"}
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
```

Let's apply the settings:

```bash
sudo sysctl --system
```

## WireGuard Configuration

Let's create `/etc/wireguard/wg0.conf` like this:

```ini {title="/etc/wireguard/wg0.conf"}
[Interface]
Address    = 10.8.0.1/24, fd42:8::1/64
ListenPort = 51820
PrivateKey = <server.key>
```

> [!note]
> `<server.key>`: The contents of the file `/etc/wireguard/server.key` (`sudo cat /etc/wireguard/server.key`).

Let's set the file's permissions so only root can read it:

```bash
sudo chmod 600 /etc/wireguard/wg0.conf
```

## Firewalld Configuration

### Binding the Outside Interface to the Public Zone Explicitly

> [!note]
> `eth0` is in the default [zone](term:firewalld-zone) right now, so it is already in the public zone. This step makes sure `eth0` stays in the public zone even if the default zone changes later, so the VPN [policy](term:firewalld-policy) we'll define below (its outgoing zone is public) keeps working.

```bash
sudo nmcli -t -f NAME,DEVICE con show --active
sudo nmcli con modify "<CONNECTION_NAME>" connection.zone public
```

> [!note]
> `<CONNECTION_NAME>`: The name of the connection that belongs to `eth0` in the output of the first command.

### Opening the WireGuard Port

```bash
sudo firewall-cmd --permanent --zone=public --add-service=wireguard
```

### Creating a Zone for the VPN in Firewalld

```bash
# Creates a new, empty zone named vpn
sudo firewall-cmd --permanent --new-zone=vpn

# Binds the wg0 interface to this zone. From now on, all traffic from the WireGuard tunnel is checked against the rules of the vpn zone, not the public zone.
sudo firewall-cmd --permanent --zone=vpn --add-interface=wg0

# Sets which services on the server the traffic from the VPN may reach:
sudo firewall-cmd --permanent --zone=vpn \
  --add-service=ssh --add-service=http --add-service=https \
  --add-service=smtp-submission --add-service=smtps \
  --add-service=imap --add-service=imaps

# Allows forwarding inside the same zone, so clients can talk to each other.
sudo firewall-cmd --permanent --zone=vpn --add-forward
```

> [!note]
> Why we allow the services that are already allowed in the public zone again in the VPN zone: when a client is connected to the VPN, its traffic to the server (with a [full tunnel](term:full-tunnel), even the traffic to the server's public IP) comes in through `wg0`. If we don't allow these services in the VPN zone, the client can't reach them while it is connected to the VPN.

### From the VPN to the Internet

> [!note]
> A **zone** manages traffic that comes to the server itself. For example: "Can someone coming from the VPN connect to SSH on the server?"

> [!note]
> A **policy** manages traffic that goes through the server, so packets forwarded from one zone to another.

In Firewalld, forwarding between zones is off by default. So for the VPN clients to reach the internet, we need to define a policy explicitly.

```bash
# Creates a new, empty policy named vpn-internet.
sudo firewall-cmd --permanent --new-policy=vpn-internet

# Sets the direction of the policy. It applies when traffic comes from the vpn zone (wg0) and goes to the public zone (the outside interface, so the internet).
sudo firewall-cmd --permanent --policy=vpn-internet --add-ingress-zone=vpn
sudo firewall-cmd --permanent --policy=vpn-internet --add-egress-zone=public

# Accepts traffic in this direction. A VPN client can go to any address on the internet; port 25 is blocked by the no-smtp-out policy from part 5.
sudo firewall-cmd --permanent --policy=vpn-internet --set-target=ACCEPT

# Turns on NAT.
sudo firewall-cmd --permanent --policy=vpn-internet --add-masquerade

# --add-masquerade only applies to IPv4, IPv6 needs a separate rich rule
sudo firewall-cmd --permanent --policy=vpn-internet \
    --add-rich-rule='rule family="ipv6" source address="fd42:8::/64" masquerade'
```

Let's apply the rules we added to Firewalld:

```bash
sudo firewall-cmd --reload
```

Let's check the zone and the policy:

```bash
# Shows which interface is in which zone
sudo firewall-cmd --get-active-zones
```

```text
docker
 interfaces: docker0
public (default)
 interfaces: eth0
vpn
 interfaces: wg0
```

```bash
# Shows the settings of the policy
sudo firewall-cmd --info-policy=vpn-internet
```

```text
vpn-internet (active)  
 disable: no  
 priority: -1  
 target: ACCEPT  
 ingress-zones: vpn  
 egress-zones: public  
 services:    
 ports:    
 protocols:    
 masquerade: yes  
 forward-ports:    
 source-ports:    
 icmp-blocks:    
 rich rules:    
       rule family="ipv6" source address="fd42:8::/64" masquerade
```

> [!note]
> The `no-smtp-out` policy we created in [5 Firewalld Configuration](/self-hosting/firewalld/) uses `ANY` as the ingress zone, so it applies to the VPN clients too. Its priority (`-10`) is smaller than that of `vpn-internet` (`-1`), so it is checked first. After adding a client ([7.1](/self-hosting/wireguard-clients/)), while it is connected with the full tunnel profile, the command `nc -v -w 5 gmail-smtp-in.l.google.com 25 </dev/null` on the client should give a connection error. On Windows, `Test-NetConnection gmail-smtp-in.l.google.com -Port 25` should return `TcpTestSucceeded : False`.

## Docker's FORWARD DROP Policy

Docker sets the default policy of the FORWARD chain in [iptables](term:iptables) to DROP. Even if Firewalld allows the VPN traffic, the packet also passes through Docker's table, and the DROP policy drops it.

Let's check whether this policy is in place:

```bash
sudo iptables -S FORWARD | head -1
sudo ip6tables -S FORWARD | head -1
```

If the output shows `-P FORWARD DROP`, the policy is in place.

Let's stop Docker from setting the DROP policy by adding the line below to `/etc/docker/daemon.json`:

```json {title="/etc/docker/daemon.json"}
"ip-forward-no-drop": true
```

The file should look like this:

```json {title="/etc/docker/daemon.json"}
{
  "ip": "127.0.0.1",
  "default-network-opts": {
    "bridge": { "com.docker.network.bridge.host_binding_ipv4": "127.0.0.1" }
  },
  "log-driver": "journald",
  "live-restore": true,
  "ip-forward-no-drop": true,
  "default-address-pools": [
    { "base": "172.20.0.0/16", "size": 24 }
  ]
}
```

Let's check the Docker configuration:

```bash
sudo dockerd --validate --config-file /etc/docker/daemon.json
```

If we got the `configuration OK` output, let's restart Docker and fix the FORWARD policy:

```bash
sudo systemctl restart docker
sudo iptables -P FORWARD ACCEPT && sudo ip6tables -P FORWARD ACCEPT
```

> [!note]
> Restarting Docker doesn't change the current DROP policy. The `ip-forward-no-drop` setting stops Docker from setting the policy to DROP from now on. The policy that is DROP right now doesn't fix itself, so we set it to ACCEPT by hand once.

> [!note]
> This doesn't mean forwarded traffic is no longer filtered. Firewalld keeps filtering forwarded traffic with the zone and policy rules in its own nftables table. The ACCEPT policy in iptables only removes the second block Docker put there.

## Starting WireGuard

Let's enable and start the service with the commands below:

```bash
sudo systemctl enable --now wg-quick@wg0
sudo wg show
```

The output should show `interface: wg0` and `listening port: 51820`.
