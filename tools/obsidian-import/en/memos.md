> **Requirements**
> - [4.1 A Ready Template for Docker Containers](/self-hosting/docker-template/) and [7.2 Putting Services Behind the VPN](/self-hosting/services-behind-vpn/) must be done.
>
> **Assumptions**
> - Memos is reached at `memos.xenonly.com`. `A` and `AAAA` records exist for this domain.
> - The Memos container uses port `127.0.0.1:8001`.
> - Commands are run on the server with root rights (`sudo`).

## What It Is

[Memos](https://usememos.com/) is a light note app that you use in the browser and can host yourself.

## Installation

We'll install it with Docker Compose.

@@code@@

Let's create `/opt/docker/memos/compose.yaml` like this:

@@code@@

Let's start the container:

@@code@@

## Certificate and NGINX Reverse Proxy

Let's get the certificate:

@@code@@

Let's create `/etc/nginx/vhost.d/vhost_memos.xenonly.com.conf` like this:

@@code@@

> `client_max_body_size 40m`: For files attached to notes. The 12m limit iRedMail sets is too small.

> `vpn-only.tmpl`: In Memos, the first user who signs up becomes the admin. On a public address, if someone else creates the first account, they become the admin. So until the first account is created, Memos will be reachable only over the VPN.

Let's test the NGINX configuration and reload it:

@@code@@

## First Account and Closing Sign-Ups

1. Let's connect to the VPN with the full tunnel and create our own account at `https://memos.xenonly.com`.
2. With the admin account, let's close new user sign-ups by turning on **Settings → System → Disallow user registration**.
3. Let's delete the `include /etc/nginx/templates/vpn-only.tmpl;` line in the virtual host and reload NGINX with `sudo nginx -t && sudo systemctl reload nginx`.

> With a split tunnel, the domain resolves to the server's public IP, so the request doesn't go through the VPN and gets a 403 (see [7.3 Possible Problems](/self-hosting/wireguard-troubleshooting/)).

## Check

@@code@@

## Backup and Updates

All of Memos' data (the SQLite database and the uploaded files) is in the `/opt/docker/memos/data` directory; it is the only place that needs a backup.

To update:

@@code@@
