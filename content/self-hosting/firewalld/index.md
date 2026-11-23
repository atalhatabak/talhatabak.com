---
title: "Firewalld Configuration"
description: "Configuring and turning on Firewalld, which we kept off during the setup, and blocking containers and VPN clients from sending out on port 25."
date: 2026-11-21T00:11:00+03:00
chapter: "5"
tags: ["firewalld"]
---
> [!abstract] Requirements
> - [2 Mail Server Setup](/self-hosting/mail-server/), [3 NGINX Configuration](/self-hosting/nginx/) and [4 Docker Setup](/self-hosting/docker/) must be done.
>
> **Assumptions**
> - Firewalld was turned off in [1 Post-Install Configuration](/self-hosting/post-install-configuration/), and iRedMail's Firewalld configuration was not applied during the installation.
> - The outside network interface is `eth0`, and SSH runs on the default port, 22.
> - Commands are run on the server with root rights (`sudo`).

## Which Ports We'll Open

| Service | Port | Why |
| --- | --- | --- |
| ssh | 22/tcp | The default port for SSH. If SSH runs on another port, add it with `--add-port=<PORT>/tcp` |
| http / https | 80/tcp, 443/tcp | NGINX |
| smtp | 25/tcp | Mail coming from other servers |
| smtp-submission | 587/tcp | Clients sending mail ([STARTTLS](term:starttls)) |
| smtps | 465/tcp | Clients sending mail ([TLS](term:tls)) |
| imap / imaps | 143/tcp, 993/tcp | Reading mail |

## Starting Point

Let's check the starting point:

```bash
sudo systemctl is-active firewalld
sudo firewall-offline-cmd --get-default-zone
sudo firewall-offline-cmd --zone=public --list-all
```

The output should look like this:

```text
inactive
public
public (default)
 target: default
 ingress-priority: 0
 egress-priority: 0
 icmp-block-inversion: no
 interfaces:
 sources:
 services: cockpit dhcpv6-client ssh
 ports:
 protocols:
 forward: yes
 masquerade: no
 forward-ports:
 source-ports:
 icmp-blocks:
 rich rules:
```

This is the default Firewalld configuration. Firewalld is off right now; we'll keep it that way for now.

## Public Zone Configuration

Cockpit is allowed by default; we won't use it, so let's remove it. Firewalld is off, so we'll use `firewall-offline-cmd` instead of `firewall-cmd`.

```bash
sudo firewall-offline-cmd --zone=public --remove-service-from-zone=cockpit
```

We add the services we use:

```bash
sudo firewall-offline-cmd --zone=public \
 --add-service=ssh --add-service=http --add-service=https \
 --add-service=smtp --add-service=smtp-submission --add-service=smtps \
 --add-service=imap --add-service=imaps
```

`ssh` is on by default, so the warning `Warning: ALREADY_ENABLED: ssh` is normal. After it, a `success` output follows.

The services we added are `http` and `https` for NGINX, and the ones the mail service needs. I won't use POP3, so I didn't add it.

Let's check the changes:

```bash
sudo firewall-offline-cmd --zone=public --list-all
```

The output should look like this:

```text
public (default)
 target: default
 ingress-priority: 0
 egress-priority: 0
 icmp-block-inversion: no
 interfaces:
 sources:
 services: dhcpv6-client http https imap imaps smtp smtp-submission smtps ssh
 ports:
 protocols:
 forward: yes
 masquerade: no
 forward-ports:
 source-ports:
 icmp-blocks:
 rich rules:
```

## Rescue Timer and Start

In case something goes wrong after Firewalld is on and we can't connect over SSH, let's set up a timer that stops Firewalld after 10 minutes:

```bash
sudo systemd-run --on-active=10min --unit=fw-rescue systemctl stop firewalld
```

Then we can enable and start Firewalld:

```bash
sudo systemctl enable --now firewalld
sudo firewall-cmd --get-active-zones
```

When Firewalld starts, the current SSH session doesn't drop, because connections that are already open are still allowed. So let's do the test by opening **a new SSH connection from a new terminal**. If the connection works, we can cancel the timer:

```bash
sudo systemctl stop fw-rescue.timer
```

## Docker Integration

We installed Docker before configuring Firewalld, so Docker couldn't create its own Firewalld settings (the `docker` [zone](term:firewalld-zone) and the `docker-forwarding` [policy](term:firewalld-policy)). Restarting Docker is enough for this:

```bash
sudo systemctl restart docker
```

### Check

```bash
sudo firewall-cmd --get-active-zones
```

```text
docker
 interfaces: docker0
public (default)
 interfaces: eth0
```

```bash
sudo firewall-cmd --zone=docker --list-all
```

```text
docker (active)
 target: ACCEPT
 ingress-priority: 0
 egress-priority: 0
 icmp-block-inversion: no
 interfaces: docker0
 sources:
 services:
 ports:
 protocols:
 forward: yes
 masquerade: no
 forward-ports:
 source-ports:
 icmp-blocks:
 rich rules:
```

```bash
sudo firewall-cmd --get-policies
```

```text
allow-host-ipv6 docker-forwarding gateway-dmz-to-HOST gateway-lan-to-HOST gateway-lan-to-work gateway-lan-to-world gateway-world-to-HOST
```

If the outputs show the `docker` zone and the `docker-forwarding` policy, Docker's Firewalld configuration was done.

## Blocking Outgoing Port 25

Everything that goes out to the internet through the server, so the [containers](term:container) and the VPN clients we'll set up in [7 WireGuard Setup](/self-hosting/wireguard/), uses the same IP addresses as the mail server. The [PTR record](term:ptr-record) of these addresses points to `mail.xenonly.com`. If a compromised container or a device on the VPN sends spam directly out on port 25, our mail server's IP gets on a [blocklist](term:dnsbl).

Mail servers talk to each other on port 25, and only [Postfix](term:postfix) on the host needs to go out on this port. The containers send their mail to our own mail server on port 587, with a login. That connection is not forwarded, it comes straight to the host, so the block doesn't affect it.

First let's see the problem. Let's try to connect from a container to Gmail's mail server on port 25:

```bash
sudo docker run --rm alpine nc -v -w 5 gmail-smtp-in.l.google.com 25
```

```text
gmail-smtp-in.l.google.com (64.233.167.26:25) open
```

The `open` line shows that the container can connect directly to a mail server outside on port 25.

Let's create a policy that rejects traffic that goes through the server (is forwarded) to port 25 outside:

```bash
# Creates a new, empty policy named no-smtp-out.
sudo firewall-cmd --permanent --new-policy=no-smtp-out

# Applies to traffic forwarded from any zone (ANY) to the public zone (the internet).
# ANY doesn't include the server's own traffic (HOST), so Postfix is not affected.
sudo firewall-cmd --permanent --policy=no-smtp-out --add-ingress-zone=ANY
sudo firewall-cmd --permanent --policy=no-smtp-out --add-egress-zone=public

# Makes the policy run before the zone rules and the other policies.
sudo firewall-cmd --permanent --policy=no-smtp-out --set-priority=-10

# Rejects connections to port 25. Logs at most 3 lines per minute.
sudo firewall-cmd --permanent --policy=no-smtp-out \
    --add-rich-rule='rule port port="25" protocol="tcp" log prefix="SMTP-OUT-BLOCK: " level="warning" limit value="3/m" reject'

sudo firewall-cmd --reload
```

> [!note]
> Policies are checked in order of their `priority` value; the smaller value comes first. Policies with a negative priority run before the zone rules. `-10` makes this policy run before the ACCEPT target of the `docker` zone and before the `vpn-internet` policy (`-1`) we'll create in part 7.

> [!note]
> We didn't change the policy's target; the default is `CONTINUE`. Traffic to ports other than 25 moves on to the next rule and works as before. We didn't set `family` in the [rich rule](term:rich-rule), so the rule applies to both IPv4 and IPv6.

> [!note]
> We used `ANY` as the ingress zone, so the rule also applies by itself to zones added later (for example the `vpn` zone in part 7).

Let's check the policy:

```bash
sudo firewall-cmd --info-policy=no-smtp-out
```

The output should show `priority: -10`, `ingress-zones: ANY`, `egress-zones: public` and the rich rule we added.

Let's run the test again:

```bash
sudo docker run --rm alpine nc -v -w 5 gmail-smtp-in.l.google.com 25
```

This time the `open` line should not show up; `nc` should print a connection error. The blocked attempts go to the kernel log:

```bash
sudo journalctl -k -g SMTP-OUT-BLOCK
```

> [!note]
> The `SRC=` field in the log shows the IP address of the container or VPN client that tried to go out on port 25. If there is an unexpected entry here, that container or device may be compromised.

To see that Postfix is not affected, let's send a mail to a Gmail address and look for the `status=sent` line in Postfix's log:

```bash
sudo journalctl -t postfix/smtp -n 20
```
