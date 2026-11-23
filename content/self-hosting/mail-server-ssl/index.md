---
title: "Setting Up SSL for the Mail Server"
description: "Getting a Let's Encrypt certificate for mail.xenonly.com and renewing it automatically."
date: 2026-11-21T00:03:00+03:00
chapter: "2.1"
tags: ["mail", "ssl", "certbot"]
---
> [!abstract] Requirements
> - [2 Mail Server Setup](/self-hosting/mail-server/) must be done.
>
> **Assumptions**
> - The `A` and `AAAA` records of `mail.xenonly.com` point to the server.
> - Port 80 (HTTP) of the server is reachable from the internet (Firewalld is still off).
> - Commands are run on the server with root rights (`sudo`).

We finished setting up the mail server. Right now the system uses the [self-signed certificate](term:self-signed) created during the [iRedMail](term:iredmail) installation. Instead, we'll get a [Let's Encrypt](term:lets-encrypt) certificate for `mail.xenonly.com` and make the system use it.

## Getting a Certificate from Let's Encrypt

`certbot` was installed in [1 Post-Install Configuration](/self-hosting/post-install-configuration/). We'll get the certificate with the `webroot` method. For this method, the domain's `A` record must point to the server and the server must listen on port 80 (HTTP).

NGINX was installed during the iRedMail installation and is already configured for the Let's Encrypt ([ACME](term:acme)) check:

```bash
sudo grep well_known /etc/nginx/sites-enabled/00-default.conf   # root /opt/www/well_known;
```

To get the certificate, running the command below is enough.

> [!note]
> On the first run it asks for an email address and for accepting the terms of service.

```bash
sudo certbot certonly --webroot -w /opt/www/well_known -d mail.xenonly.com
```

```text
Certificate is saved at: /etc/letsencrypt/live/mail.xenonly.com/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/mail.xenonly.com/privkey.pem
```

The self-signed certificates iRedMail uses are at these paths:

```text
SSL cert keys (size: 4096):
    - /etc/pki/tls/certs/iRedMail.crt
    - /etc/pki/tls/private/iRedMail.key
```

Let's back up the old certificates:

```bash
sudo mv /etc/pki/tls/certs/iRedMail.crt /etc/pki/tls/certs/iRedMail.crt.bak

sudo mv /etc/pki/tls/private/iRedMail.key /etc/pki/tls/private/iRedMail.key.bak
```

Then let's create symbolic links for the new certificate with the commands below:

```bash
sudo ln -s /etc/letsencrypt/live/mail.xenonly.com/fullchain.pem \
  /etc/pki/tls/certs/iRedMail.crt

sudo ln -s /etc/letsencrypt/live/mail.xenonly.com/privkey.pem \
  /etc/pki/tls/private/iRedMail.key
```

and restart the related services:

```bash
sudo systemctl restart postfix dovecot nginx
```

## Certificate Renewal

Let's Encrypt certificates are valid for 90 days. The [certbot](term:certbot) package comes with a [systemd](term:systemd) timer for renewal (`certbot-renew.timer`). Let's make sure the timer is enabled:

```bash
sudo systemctl enable --now certbot-renew.timer
sudo systemctl is-enabled certbot-renew.timer   # enabled
```

We'll also create a hook that reloads the services when the certificate is renewed. Let's create the file `/etc/letsencrypt/renewal-hooks/deploy/reload-mail.sh` with the content below:

```bash {title="/etc/letsencrypt/renewal-hooks/deploy/reload-mail.sh"}
#!/bin/bash
set -e

systemctl reload postfix dovecot

if nginx -t; then
    systemctl reload nginx
else
    echo "Nginx config test failed, reload skipped" >&2
    exit 1
fi
```

> [!note]
> The hooks under `renewal-hooks/deploy/` run for **every renewed certificate**, not only for the mail certificate. This is useful for us: when the other certificates we'll get in the next parts (for example `iredadmin.xenonly.com`) are renewed, this hook also reloads NGINX. If you want [Postfix](term:postfix) and [Dovecot](term:dovecot) to reload only when the mail certificate is renewed, you can check the `$RENEWED_DOMAINS` variable that certbot passes to the hook.

Let's make the hook executable:

```bash
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-mail.sh
```

Let's test that the renewal and the hook work:

```bash
sudo certbot renew --dry-run
sudo /etc/letsencrypt/renewal-hooks/deploy/reload-mail.sh
```

> [!note]
> `--dry-run` doesn't run the deploy hooks, so we test the hook by running it by hand.
