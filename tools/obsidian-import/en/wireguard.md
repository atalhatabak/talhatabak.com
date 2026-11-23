> **Requirements**
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
3. Making some services on the server (for example the iRedAdmin panel) reachable only over the VPN instead of by everyone

## Installation

@@code@@

> The WireGuard kernel module is already in the Rocky Linux 10 kernel, so we only install the tools. `qrencode` is for showing the phone configuration as a QR code.

## Creating the Key Pair

Let's create the key pair the WireGuard service will use:

@@code@@

> `cd` and `umask` are commands of the shell itself, so running them as `sudo cd` or `sudo umask` doesn't affect the current shell. That's why we run the commands in a single root shell with `sudo sh -c`. `umask 077` makes sure only root can read the key files we create.

## Permanent IP Forwarding

> We turn on IP forwarding so that packets can be passed from one interface to another (in practice, so that traffic from the VPN interface can go out to the internet).

> Docker already turns forwarding on, but only when its own service starts. This file turns forwarding on at boot, independent of Docker.

### Check IPv6 First

On Linux, once IPv6 forwarding is on, the kernel no longer accepts Router Advertisements (RA). If the VPS gets its IPv6 address through RA (SLAAC), the IPv6 connection may drop the moment we turn forwarding on. So before turning forwarding on, let's check the default IPv6 route:

@@code@@

The output should look similar to this:

@@code@@

On this server IPv6 is static (`proto static`) and RA is not used, so turning forwarding on doesn't affect the IPv6 connection. If the output shows `proto ra`, you also need to add the line `net.ipv6.conf.eth0.accept_ra = 2` to the file below.

### Turning On Forwarding

Let's create the file `/etc/sysctl.d/90-wireguard.conf` with the content below:

@@code@@

Let's apply the settings:

@@code@@

## WireGuard Configuration

Let's create `/etc/wireguard/wg0.conf` like this:

@@code@@

> `<server.key>`: The contents of the file `/etc/wireguard/server.key` (`sudo cat /etc/wireguard/server.key`).

Let's set the file's permissions so only root can read it:

@@code@@

## Firewalld Configuration

### Binding the Outside Interface to the Public Zone Explicitly

> `eth0` is in the default zone right now, so it is already in the public zone. This step makes sure `eth0` stays in the public zone even if the default zone changes later, so the VPN policy we'll define below (its outgoing zone is public) keeps working.

@@code@@

> `<CONNECTION_NAME>`: The name of the connection that belongs to `eth0` in the output of the first command.

### Opening the WireGuard Port

@@code@@

### Creating a Zone for the VPN in Firewalld

@@code@@

> Why we allow the services that are already allowed in the public zone again in the VPN zone: when a client is connected to the VPN, its traffic to the server (with a full tunnel, even the traffic to the server's public IP) comes in through `wg0`. If we don't allow these services in the VPN zone, the client can't reach them while it is connected to the VPN.

### From the VPN to the Internet

> A **zone** manages traffic that comes to the server itself. For example: "Can someone coming from the VPN connect to SSH on the server?"

> A **policy** manages traffic that goes through the server, so packets forwarded from one zone to another.

In Firewalld, forwarding between zones is off by default. So for the VPN clients to reach the internet, we need to define a policy explicitly.

@@code@@

Let's apply the rules we added to Firewalld:

@@code@@

Let's check the zone and the policy:

@@code@@

@@code@@

@@code@@

@@code@@

> The `no-smtp-out` policy we created in [5 Firewalld Configuration](/self-hosting/firewalld/) uses `ANY` as the ingress zone, so it applies to the VPN clients too. Its priority (`-10`) is smaller than that of `vpn-internet` (`-1`), so it is checked first. After adding a client ([7.1](/self-hosting/wireguard-clients/)), while it is connected with the full tunnel profile, the command `nc -v -w 5 gmail-smtp-in.l.google.com 25 </dev/null` on the client should give a connection error. On Windows, `Test-NetConnection gmail-smtp-in.l.google.com -Port 25` should return `TcpTestSucceeded : False`.

## Docker's FORWARD DROP Policy

Docker sets the default policy of the FORWARD chain in iptables to DROP. Even if Firewalld allows the VPN traffic, the packet also passes through Docker's table, and the DROP policy drops it.

Let's check whether this policy is in place:

@@code@@

If the output shows `-P FORWARD DROP`, the policy is in place.

Let's stop Docker from setting the DROP policy by adding the line below to `/etc/docker/daemon.json`:

@@code@@

The file should look like this:

@@code@@

Let's check the Docker configuration:

@@code@@

If we got the `configuration OK` output, let's restart Docker and fix the FORWARD policy:

@@code@@

> Restarting Docker doesn't change the current DROP policy. The `ip-forward-no-drop` setting stops Docker from setting the policy to DROP from now on. The policy that is DROP right now doesn't fix itself, so we set it to ACCEPT by hand once.

> This doesn't mean forwarded traffic is no longer filtered. Firewalld keeps filtering forwarded traffic with the zone and policy rules in its own nftables table. The ACCEPT policy in iptables only removes the second block Docker put there.

## Starting WireGuard

Let's enable and start the service with the commands below:

@@code@@

The output should show `interface: wg0` and `listening port: 51820`.
