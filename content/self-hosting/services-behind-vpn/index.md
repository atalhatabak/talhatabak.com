---
title: "Putting Services Behind the VPN"
description: "Making SSH and NGINX virtual hosts reachable only over the VPN."
date: 2026-11-21T00:15:00+03:00
chapter: "7.2"
tags: ["wireguard", "vpn", "nginx", "ssh"]
---
> [!abstract] Requirements
> - [7 WireGuard Setup](/self-hosting/wireguard/) and [7.1 Adding WireGuard Clients](/self-hosting/wireguard-clients/) must be done; you must be able to connect to the VPN from your personal computer.
> - For the NGINX part, [3 NGINX Configuration](/self-hosting/nginx/) must be done.
>
> **Assumptions**
> - The VPN networks are `10.8.0.0/24` and `fd42:8::/64`, and the server's VPN address is `10.8.0.1`.
> - SSH is allowed in the `vpn` zone ([7 WireGuard Setup](/self-hosting/wireguard/)).
> - Server commands are run on the server with root rights (`sudo`). The tests with `ssh` and `curl` are done from a personal computer.

We'll make the services on the server that only we want to reach (the [iRedAdmin](term:iredadmin) panel, vault, SSH and so on) reachable only while there is a VPN connection.

Roughly, what we need to do is allow, in the configuration of each service, only the requests that come from these addresses:

- `10.8.0.0/24` (IPv4) and `fd42:8::/64` (IPv6)

## Reaching SSH Only Over the VPN

What we need to do is remove SSH from the public [zone](term:firewalld-zone) in the firewall; it is already allowed in the VPN zone.

### Checks Before We Start

#### Firewalld

```bash
sudo firewall-cmd --zone=vpn --list-all
```

With this command, let's make sure SSH is in the VPN zone.

> [!warning]
> Also make sure root or the normal user has a password, and that you know it. If something goes wrong with the VPN, the only way into the server will be the [VNC](term:vnc) console of the provider, and you'll need to log in there with a username and password.

#### VPN Connection

Let's connect to the VPN (split or [full tunnel](term:full-tunnel)) from our personal computer and make sure we can open an SSH connection over the VPN with the command below:

```bash
ssh <USER>@10.8.0.1
```

#### Rescue Timer and a Temporary (Runtime) Change

In case something goes wrong and we can't open an SSH connection, let's set up a timer that undoes the change:

```bash
sudo systemd-run --on-active=10min --unit=ssh-rescue firewall-cmd --reload
```

We won't use `--permanent` for the changes we make in Firewalld, so if we don't cancel the timer, it runs after 10 minutes, reloads Firewalld and loads the permanent (old) settings again.

### Steps

Let's remove the SSH service from the public zone with the command below:

```bash
sudo firewall-cmd --zone=public --remove-service=ssh
```

#### Checking

From our personal computer, with the **[split tunnel](term:split-tunnel)** profile connected, let's test:

```bash
ssh <USER>@10.8.0.1                              # should connect, goes through the VPN
ssh -o ConnectTimeout=5 <USER>@<SERVER_IPV4>     # over the internet, should not connect
ssh -o ConnectTimeout=5 <USER>@<SERVER_IPV6>     # IPv6, should not connect
```

> [!warning]
> If you do this test with the full tunnel connected, the result is misleading: the traffic to the server's public IP also goes through the tunnel and comes in through `wg0`, so the VPN zone's rules apply and the connection works.

#### Making It Permanent

If there is no problem, let's make the change permanent with the commands below before the 10 minutes are up:

```bash
sudo firewall-cmd --permanent --zone=public --remove-service=ssh
sudo systemctl stop ssh-rescue.timer
sudo firewall-cmd --reload
```

```bash
sudo firewall-cmd --zone=public --list-services   # ssh should not be in the list
```

### Editing the SSH Configuration

We'll always connect to SSH over the VPN, and the server's IP address on the VPN network doesn't change, so for convenience we can edit the `~/.ssh/config` file on our personal computer like this:

```ssh-config {title="~/.ssh/config"}
Host <SERVER_NAME>
    HostName 10.8.0.1
    User <USER>
    IdentityFile ~/.ssh/<SSH_KEY>
    IdentitiesOnly yes
```

> [!note]
> The reason we write `10.8.0.1` instead of the domain as the `HostName` is the split tunnel: the domain resolves to the server's public IP, so the traffic goes over the internet, and since SSH is closed in the public zone, the connection fails. With the full tunnel this problem doesn't happen.

> [!note]
> We could also set sshd to listen only on `10.8.0.1` with `ListenAddress`. But the firewall already blocks connections from outside, and that would make the SSH service depend on WireGuard, so I didn't see the need. The only risk we accept with this choice is that SSH becomes open to the internet if the firewall goes down.

## Putting NGINX Virtual Hosts Behind the VPN

Web services like iRedAdmin already run behind NGINX. So we'll put a restriction in the NGINX configuration only for the services we want to reach over the VPN.

The `/etc/nginx/templates` directory already has the templates we use. Let's add the template `/etc/nginx/templates/vpn-only.tmpl` to them with the content below:

```nginx {title="/etc/nginx/templates/vpn-only.tmpl"}
allow 10.8.0.0/24;
allow fd42:8::/64;
deny  all;
```

From now on, all we need to do is add the line `include /etc/nginx/templates/vpn-only.tmpl;` to the `server` block of the [virtual hosts](term:virtual-host) we want to reach only over the VPN.

### Putting the iRedAdmin Panel Behind the VPN

Let's open `/etc/nginx/vhost.d/vhost_iredadmin.xenonly.com.conf` and include the `vpn-only` template in the `server` block. The file will look like this:

```nginx {title="/etc/nginx/vhost.d/vhost_iredadmin.xenonly.com.conf"}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name iredadmin.xenonly.com;

    ssl_certificate     /etc/letsencrypt/live/iredadmin.xenonly.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/iredadmin.xenonly.com/privkey.pem;
    include /etc/nginx/templates/vpn-only.tmpl;
    include /etc/nginx/templates/misc.tmpl;
    include /etc/nginx/templates/iredadmin-subdomain.tmpl;
}
```

Let's test the NGINX configuration and reload it:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

#### Checking

From our personal computer, while not connected to the VPN:

```bash
curl -sI https://iredadmin.xenonly.com | head -1   # HTTP/2 403
```

While connected to the VPN (with the full tunnel, or with the split tunnel and the `hosts` entry from [7.3 Possible Problems](/self-hosting/wireguard-troubleshooting/)), the same command should return something other than `403` (for example `200` or a redirect).

#### NGINX Location Inheritance

> [!note]
> It doesn't matter in which part of the `server` block the `vpn-only` template is added.

The point to watch here is how NGINX location blocks behave.

In NGINX, settings are defined in nested blocks: http → server → location. A child block inherits the settings of its parent block. But there is a rule:

> [!important]
> If a child block defines even one directive of a kind, all the directives of that kind from the parent block stop working for that child block.

By adding the `vpn-only` template to the `server` block, we allow requests from the VPN network and reject the rest. But if a separate location block (maybe one that comes from an include) has an `allow` or `deny` rule, our rules don't work for that location.

Also, the `return` and `rewrite` directives run at a stage of request processing that comes before access control (`allow`/`deny`). A location that answers with `return` (or redirects with `rewrite`) sends its response without ever reaching the `deny` rule.

So let's check our current configuration:

```bash
sudo grep -RnE 'allow|deny|return|rewrite' /etc/nginx
```

- `roundcube-subdomain.tmpl` has `deny all` for many locations; this doesn't cause a problem.
- The `return 301` in `00-default.conf` only redirects HTTP requests on port 80 to HTTPS; the restriction applies when the real request reaches the virtual host on port 443.
- The `allow all` directives in `misc.tmpl` and `00-default.conf` are in the `.well-known` location. They override our rule, but that is what we want: the `.well-known` directory holds the temporary files [Let's Encrypt](term:lets-encrypt) creates while it checks the certificate.

> [!note]
> Certificate renewal is not affected by this restriction: the Let's Encrypt check is done through `00-default.conf` on port 80, and there is no VPN restriction there.
