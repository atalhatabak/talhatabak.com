---
title: "Fail2Ban Configuration"
description: "Adding longer and longer ban times for repeat attackers to the Fail2Ban that comes with iRedMail."
date: 2026-11-21T00:12:00+03:00
chapter: "6"
tags: ["fail2ban"]
---
> [!abstract] Requirements
> - [2 Mail Server Setup](/self-hosting/mail-server/) must be done (Fail2Ban is installed together with iRedMail).
>
> **Assumptions**
> - The VPN networks are `10.8.0.0/24` and `fd42:8::/64` from [7 WireGuard Setup](/self-hosting/wireguard/); these networks are never banned.
> - Commands are run on the server with root rights (`sudo`).

Fail2Ban was installed together with [iRedMail](term:iredmail). Let's add a few useful settings on top of it.

## Longer Bans for Repeat Offenders

Let's create the file `/etc/fail2ban/jail.d/99-local.local` with the content below.

> [!note]
> Fail2Ban reads the files in this order: `jail.conf` → `jail.d/*.conf` → `jail.local` → `jail.d/*.local` (alphabetical). `99-local.local` is read last, so its `[DEFAULT]` settings override the `[DEFAULT]` settings in the earlier files. But settings defined in [jail](term:jail) sections (for example `[sshd]`) win over `[DEFAULT]`; this file doesn't change them.

```ini {title="/etc/fail2ban/jail.d/99-local.local"}
[DEFAULT]
bantime.increment = true
bantime.factor    = 2
bantime.maxtime   = 1w
ignoreip = 127.0.0.1/8 ::1 10.8.0.0/24 fd42:8::/64
```

> [!note]
> `ignoreip`: Only localhost and the VPN network are never banned. We can't leave out localhost; [Roundcube](term:roundcube) and [iRedAdmin](term:iredadmin) connect to [Dovecot](term:dovecot) and [Postfix](term:postfix) from 127.0.0.1. The VPN network is never banned because after [7.2 Putting Services Behind the VPN](/self-hosting/services-behind-vpn/) SSH is reachable only over the VPN; if our VPN address gets banned, we lose access to the server.

> [!note]
> We leave the Docker network (`172.20.0.0/16`) out of `ignoreip` on purpose. [Containers](term:container) connect to the ports on the host from 172.20.x.x addresses; if a compromised container tries mail passwords, it should be banned. The ban only affects that container. A container with a wrong [SMTP](term:smtp) password can get banned too; then fixing the password and lifting the ban with `sudo fail2ban-client unban <IP>` is enough.

`fail2ban.conf` has `dbpurgeage = 1d`, so Fail2Ban remembers an IP in its database for at most 1 day. The longer bans work by reading an IP's earlier bans from this database, so `dbpurgeage` must not be shorter than `bantime.maxtime`. Otherwise bans older than 1 day are forgotten and the ban time doesn't grow.

Without changing `fail2ban.conf`, let's create the file `/etc/fail2ban/fail2ban.local` with the content below (if the file already exists, add the `dbpurgeage` line to its `[Definition]` section):

```ini {title="/etc/fail2ban/fail2ban.local"}
[Definition]
dbpurgeage = 1w
```

## Apply and Check

```bash
sudo fail2ban-client -t                  # OK: configuration test is successful
sudo systemctl restart fail2ban
sudo fail2ban-client get sshd bantime    # 3600
sudo fail2ban-client get dbpurgeage      # 604800 (1 week)
```
