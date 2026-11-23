---
title: "Usememos Setup"
description: "Installing Memos, a note app you can host yourself."
date: 2026-11-21T00:21:00+03:00
chapter: "11"
tags: ["memos", "docker"]
---
> [!abstract] Requirements
> - [4.1 A Ready Template for Docker Containers](/self-hosting/docker-template/) and [7.2 Putting Services Behind the VPN](/self-hosting/services-behind-vpn/) must be done.
>
> **Assumptions**
> - Memos is reached at `memos.xenonly.com`. `A` and `AAAA` records exist for this domain.
> - The Memos container uses port `127.0.0.1:8001`.
> - Commands are run on the server with root rights (`sudo`).

## What It Is

[Memos](https://usememos.com/) is a light note app that you use in the browser and can host yourself.

## Installation

We'll install it with [Docker Compose](term:docker-compose).

```bash
sudo mkdir /opt/docker/memos
```

Let's create `/opt/docker/memos/compose.yaml` like this:

```yaml {title="/opt/docker/memos/compose.yaml"}
services:
  memos:
    image: neosmemo/memos:stable
    container_name: memos
    restart: unless-stopped
    ports:
      - "127.0.0.1:8001:5230"
    volumes:
      - ./data:/var/opt/memos
    environment:
      MEMOS_PORT: 5230
      MEMOS_DRIVER: sqlite
      MEMOS_INSTANCE_URL: "https://memos.xenonly.com"
      MEMOS_TRUSTED_PROXIES: "172.20.0.0/16"
```

Let's start the [container](term:container):

```bash
cd /opt/docker/memos
sudo docker compose up -d
```

## Certificate and NGINX Reverse Proxy

Let's get the certificate:

```bash
sudo certbot certonly --webroot -w /opt/www/well_known -d memos.xenonly.com
```

Let's create `/etc/nginx/vhost.d/vhost_memos.xenonly.com.conf` like this:

```nginx {title="/etc/nginx/vhost.d/vhost_memos.xenonly.com.conf"}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name memos.xenonly.com;

    ssl_certificate     /etc/letsencrypt/live/memos.xenonly.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/memos.xenonly.com/privkey.pem;

    client_max_body_size 40m;

    # Until the first account is created, remove afterwards
    include /etc/nginx/templates/vpn-only.tmpl;

    location / {
        proxy_pass http://127.0.0.1:8001;
        include /etc/nginx/templates/proxy.tmpl;
    }
}
```

> [!note]
> `client_max_body_size 40m`: For files attached to notes. The 12m limit [iRedMail](term:iredmail) sets is too small.

> [!note]
> `vpn-only.tmpl`: In Memos, the first user who signs up becomes the admin. On a public address, if someone else creates the first account, they become the admin. So until the first account is created, Memos will be reachable only over the VPN.

Let's test the NGINX configuration and reload it:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## First Account and Closing Sign-Ups

1. Let's connect to the VPN with the [full tunnel](term:full-tunnel) and create our own account at `https://memos.xenonly.com`.
2. With the admin account, let's close new user sign-ups by turning on **Settings → System → Disallow user registration**.
3. Let's delete the `include /etc/nginx/templates/vpn-only.tmpl;` line in the [virtual host](term:virtual-host) and reload NGINX with `sudo nginx -t && sudo systemctl reload nginx`.

> [!note]
> With a [split tunnel](term:split-tunnel), the domain resolves to the server's public IP, so the request doesn't go through the VPN and gets a 403 (see [7.3 Possible Problems](/self-hosting/wireguard-troubleshooting/)).

## Check

```bash
curl -sI https://memos.xenonly.com | head -1   # HTTP/2 200
```

## Backup and Updates

All of Memos' data (the [SQLite](term:sqlite) database and the uploaded files) is in the `/opt/docker/memos/data` directory; it is the only place that needs a backup.

To update:

```bash
cd /opt/docker/memos && sudo docker compose pull && sudo docker compose up -d
```
