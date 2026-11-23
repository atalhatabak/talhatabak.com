---
title: "NGINX Configuration"
description: "Turning the NGINX setup that iRedMail installed into one that can serve many services and virtual hosts."
date: 2026-11-21T00:08:00+03:00
chapter: "3"
tags: ["nginx"]
---
> [!abstract] Requirements
> - [2 Mail Server Setup](/self-hosting/mail-server/) and [2.1 Setting Up SSL for the Mail Server](/self-hosting/mail-server-ssl/) must be done.
>
> **Assumptions**
> - NGINX was installed and configured by iRedMail (version 1.26 from the Rocky Linux 10 repository).
> - `A` and `AAAA` records exist for `mail.xenonly.com` and `iredadmin.xenonly.com`.
> - Commands are run on the server with root rights (`sudo`).

## Understanding the Current Configuration

### iRedMail's Default Layout

The NGINX on the system was installed by [iRedMail](term:iredmail), and iRedMail changed its configuration.

> [!note]
> On a normal [RHEL](term:rhel) installation, the `include` directive in `/etc/nginx/nginx.conf` includes the `conf.d` directory. iRedMail uses the same directory layout on every distribution, so during the installation it rewrites `nginx.conf` and includes the `sites-enabled` and `conf-enabled` directories.

In the steps part, I'll change this layout like this:

- `conf.d` for configuration files
- `vhost.d` for [virtual host](term:virtual-host) definitions

### Templates (/etc/nginx/templates)

Under `/etc/nginx/templates` there are the default templates iRedMail brought. The `netdata.tmpl`, `netdata-subdomain.tmpl`, `sogo.tmpl`, `sogo-subdomain.tmpl` and `adminer.tmpl` templates won't be used; we'll delete them in the steps part.

Let's look at the other templates.

#### fastcgi_php.tmpl

> Has the shared settings for passing PHP requests to [PHP-FPM](term:php-fpm) (`php_workers` → `127.0.0.1:9999`). [Roundcube](term:roundcube) and the other PHP blocks include this file.

#### hsts.tmpl

> Sends the `Strict-Transport-Security` header to the browser. A browser that gets this header connects to the site only over HTTPS for 1 year.

The current NGINX version (1.26) doesn't support the `add_header_inherit` directive. So if `add_header` is defined in a virtual host or a location block, the headers in `conf.d/headers.conf` are not applied in that block.

The `hsts.tmpl` template is included from the `roundcube-subdomain.tmpl`, `roundcube.tmpl` and `iredadmin-subdomain.tmpl` templates.

So in the steps part we'll add the definition in `hsts.tmpl` to `headers.conf`, remove the include lines from these three templates and delete `hsts.tmpl`.

#### iredadmin-subdomain.tmpl

> A ready configuration for serving the admin panel that comes with iRedMail on a subdomain. This is what we'll use on our system too.

#### iredadmin.tmpl

> For the admin panel that comes with iRedMail; it passes requests for the `/iredadmin` path to [iRedAdmin](term:iredadmin).

We'll serve iRedAdmin on a subdomain, so we'll delete this one in the steps part.

#### misc.tmpl

- Handles `.well-known` requests that come over HTTPS
- Blocks access to hidden files
- Turns off logging for `favicon.ico` and `robots.txt` requests

#### php-catchall.tmpl

> Passes every `.php` request not caught by the earlier templates to PHP-FPM.

This is not what we want; we'll decide ourselves what runs where. So we don't need it, and we'll delete it in the steps part.

#### redirect_to_https.tmpl

> Redirects requests for the `sogo`, `iredadmin` and `mail` paths to HTTPS.

In the current setup every request is already redirected to HTTPS. We don't need it; we'll delete it in the steps part.

#### roundcube-subdomain.tmpl

> A ready configuration for serving Roundcube webmail on a subdomain.

#### roundcube.tmpl

> Used for Roundcube webmail; passes requests for the `/mail` path to Roundcube.

On this system Roundcube will be served on a subdomain, but for other domains we may need to serve it on the `/mail` path. So I won't delete it.

#### ssl.tmpl

> The standard SSL settings for HTTPS, and the definition of the SSL certificate that iRedMail, which set up our mail server, uses.

We'll use this server for many services and virtual hosts, so in the steps part we'll remove the certificate definition from here.

Also, the settings in `ssl.tmpl` can be set at the http level, and we'll use them for every virtual host. So instead of including it in every virtual host configuration, we'll move it to the `conf.d` directory.

#### stub_status.tmpl

> Serves the NGINX (`/stub_status`) and PHP-FPM (`/status`) status pages for monitoring tools, reachable only from `localhost`.

I don't plan to use it, so I'll delete it in the steps part.

### Configuration Files (/etc/nginx/conf-available → conf.d)

> Applied at the http {} level; unless something else is set in a virtual host or location block, they apply to every request.

I'll only look at the ones that need to change.

#### What We'll Change

##### cache.conf

We'll add the current JavaScript [MIME](term:mime) types (`application/javascript`, `text/javascript`).

##### headers.conf

We'll remove the outdated `X-XSS-Protection` and `X-Download-Options` headers and add the `Strict-Transport-Security` definition from `hsts.tmpl` here. We'll also remove the `Content-Security-Policy` header iRedMail set.

### Virtual Hosts (/etc/nginx/sites-available → vhost.d)

> The current configuration has only the default virtual host definitions and the templates included in them.

#### 00-default.conf

Its default version roughly does this:

- Listens on port 80 (HTTP)
- Serves `.well-known/acme-challenge` requests for SSL from the `/opt/www/well_known` directory
- Redirects all other requests to HTTPS

#### 00-default-ssl.conf

Its default version roughly does this:

- Listens on port 443 (HTTPS)
- Has `/var/www/html` as the root directory and `index.php` as the index
- Then includes a set of templates from the `templates` directory

By default these files are included:

```text
misc.tmpl         → Will be included in the vhosts that need it
ssl.tmpl          → Will be moved to conf.d
iredadmin.tmpl    → Will be served on a subdomain
roundcube.tmpl    → Will be served on a subdomain
php-catchall.tmpl → Not used
stub_status.tmpl  → Not used
```

### The Layout We Want

Every request that comes to port 80 (HTTP), except the `acme challenge`, should be redirected to 443 (HTTPS). The `conf.d` directory should hold the default settings for every request, and the `vhost.d` directory the configuration of each virtual host.

## Steps

### Directory Layout

As we said in the understanding part, we'll use the `conf.d` directory for configuration files and `vhost.d` for virtual host definitions.

The whole `conf-available` directory becomes `conf.d`, so if there is a file there with no link in `conf-enabled` (so a file not in use right now), it will start being loaded too. Let's compare the two directories before the move:

```bash
ls /etc/nginx/conf-available
ls -l /etc/nginx/conf-enabled
```

Then let's rearrange the directories:

```bash
cd /etc/nginx
sudo rm -rf conf.d # If it exists; it isn't used right now anyway
sudo mv conf-available conf.d
sudo mv sites-available vhost.d
sudo rm -rf sites-enabled conf-enabled
```

and change the `conf-enabled` and `sites-enabled` include lines in `nginx.conf` like this:

```nginx {title="/etc/nginx/nginx.conf"}
http {
    ...
    # Requires Nginx 1.25.1+.
    # http2 on;
    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/vhost.d/*.conf;
}
```

### Templates

#### hsts.tmpl

As we said in the understanding part, the `hsts.tmpl` template is included from three templates:

```bash
sudo grep -rn hsts.tmpl /etc/nginx/templates
```

```text
/etc/nginx/templates/iredadmin-subdomain.tmpl:4:include /etc/nginx/templates/hsts.tmpl;
/etc/nginx/templates/roundcube-subdomain.tmpl:19:    include /etc/nginx/templates/hsts.tmpl;
/etc/nginx/templates/roundcube-subdomain.tmpl:23:    include /etc/nginx/templates/hsts.tmpl;
/etc/nginx/templates/roundcube-subdomain.tmpl:28:    include /etc/nginx/templates/hsts.tmpl;
/etc/nginx/templates/roundcube.tmpl:27:    include /etc/nginx/templates/hsts.tmpl;
/etc/nginx/templates/roundcube.tmpl:32:    include /etc/nginx/templates/hsts.tmpl;
```

Let's delete the `include /etc/nginx/templates/hsts.tmpl;` lines in these three templates:

```bash
sudo sed -i '/hsts.tmpl/d' /etc/nginx/templates/{iredadmin-subdomain,roundcube-subdomain,roundcube}.tmpl
```

We'll add the definition in `hsts.tmpl` to `headers.conf` below, and delete the template itself together with the unused templates.

#### ssl.tmpl

Let's delete the lines starting with `ssl_certificate` and `ssl_certificate_key` in `/etc/nginx/templates/ssl.tmpl` and move the file to the `conf.d` directory:

```bash
sudo sed -i '/^\s*ssl_certificate/d' /etc/nginx/templates/ssl.tmpl
sudo mv /etc/nginx/templates/ssl.tmpl /etc/nginx/conf.d/ssl.conf
```

### Configuration Files

#### cache.conf

`/etc/nginx/conf.d/cache.conf` will look like this:

```nginx {title="/etc/nginx/conf.d/cache.conf"}
map $sent_http_content_type $expires {
    default                     off;
    application/javascript      1d;
    text/javascript             1d;
    application/x-javascript    1d;
    text/css                    1d;
    ~image/                     1d;
}

expires $expires;
```

> [!note]
> `map` only defines the `$expires` variable. For the variable to be used, the `expires $expires;` line at the bottom is needed; without it the map has no effect.

#### headers.conf

Let's edit `/etc/nginx/conf.d/headers.conf` like this:

```nginx {title="/etc/nginx/conf.d/headers.conf"}
add_header Strict-Transport-Security "max-age=31536000" always;
add_header X-Frame-Options sameorigin always;
add_header X-Content-Type-Options nosniff always;
add_header X-Permitted-Cross-Domain-Policies none always;
add_header Referrer-Policy strict-origin always;
```

> [!note]
> Without the `always` parameter, NGINX adds the headers only to successful and redirect responses (200, 301, 304 and so on); it doesn't send them with 403, 404 and 5xx responses.

> [!note]
> We removed the `Content-Security-Policy` header iRedMail set. Its value, `default-src https: data: 'unsafe-inline' 'unsafe-eval'`, allows every HTTPS source, inline scripts and `eval`, so it gives almost no protection against [XSS](term:xss). On the other hand, because it is set at the http level, it goes to every application behind NGINX, and since it blocks `blob:` and `wss:` sources it can break applications. Applications that need a [CSP](term:csp) (for example Vaultwarden) send their own header.

### Virtual Hosts

#### 00-default.conf

> Expected behavior: redirect every request except the `acme challenge` to 443/HTTPS.

We add the `default_server` parameter to the `listen 80` and `listen [::]:80` directives in the current configuration:

```nginx {title="/etc/nginx/vhost.d/00-default.conf"}
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    # Allow ACME challenge to be served over HTTP (don't redirect to HTTPS).
    location ~* ^/.well-known/acme-challenge/ {
        root /opt/www/well_known;
        try_files $uri =404;
        allow all;
    }

    # Redirect all insecure http requests to https
    location / {
        return 301 https://$host$request_uri;
    }
}
```

#### 00-default-ssl.conf

> Expected behavior: there will be a separate definition for each virtual host, so this one takes the requests that no virtual host catches.

We edit `/etc/nginx/vhost.d/00-default-ssl.conf` like this:

```nginx {title="/etc/nginx/vhost.d/00-default-ssl.conf"}
server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;

    ssl_reject_handshake on;
}
```

If no `server_name` ([SNI](term:sni)) matches an incoming request, the [TLS](term:tls) handshake is rejected.

As we said in the understanding part, the templates that used to be included here are no longer used.

> [!warning]
> After this configuration, HTTPS requests to names that have no virtual host (for example `https://xenonly.com`, or straight to the IP address) are rejected. The `/mail` and `/iredadmin` addresses from [2 Mail Server Setup](/self-hosting/mail-server/) are now used through the subdomains below.

#### vhost_mail.xenonly.com.conf

We'll use it to serve Roundcube Webmail. Let's create `/etc/nginx/vhost.d/vhost_mail.xenonly.com.conf` like this:

```nginx {title="/etc/nginx/vhost.d/vhost_mail.xenonly.com.conf"}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name mail.xenonly.com;

    ssl_certificate     /etc/letsencrypt/live/mail.xenonly.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mail.xenonly.com/privkey.pem;

    include /etc/nginx/templates/misc.tmpl;
    include /etc/nginx/templates/roundcube-subdomain.tmpl;
}
```

> [!note]
> We got the certificate in [2.1 Setting Up SSL for the Mail Server](/self-hosting/mail-server-ssl/), so we don't get it again.

> [!tip]
> Using a subdomain is purely a personal choice; it can also be served on a path like `/mail`.

> [!note]
> If we need to serve the webmail for more than one domain, each domain will have its own certificate, so we need to create a separate virtual host or add a new `server` block to this file.

#### vhost_iredadmin.xenonly.com.conf

First let's get the certificate:

```bash
sudo certbot certonly --webroot -w /opt/www/well_known -d iredadmin.xenonly.com
```

> [!note]
> The deploy hook we created in [2.1 Setting Up SSL for the Mail Server](/self-hosting/mail-server-ssl/) reloads NGINX when the certificate is renewed.

Then let's create `/etc/nginx/vhost.d/vhost_iredadmin.xenonly.com.conf` like this:

```nginx {title="/etc/nginx/vhost.d/vhost_iredadmin.xenonly.com.conf"}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name iredadmin.xenonly.com;

    ssl_certificate     /etc/letsencrypt/live/iredadmin.xenonly.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/iredadmin.xenonly.com/privkey.pem;

    include /etc/nginx/templates/misc.tmpl;
    include /etc/nginx/templates/iredadmin-subdomain.tmpl;
}
```

> [!tip]
> Using a subdomain is purely a personal choice; it can also be served on the `/iredadmin` path.

> [!note]
> It is an admin panel and doesn't need to be reached from outside, so it can be made reachable only over the VPN. We'll do that in [7.2 Putting Services Behind the VPN](/self-hosting/services-behind-vpn/).

### Deleting the Unused Templates

The templates we said won't be used in the understanding part:

- netdata.tmpl
- netdata-subdomain.tmpl
- sogo.tmpl
- sogo-subdomain.tmpl
- adminer.tmpl
- stub_status.tmpl
- redirect_to_https.tmpl
- php-catchall.tmpl
- iredadmin.tmpl
- hsts.tmpl

```bash
cd /etc/nginx/templates
sudo rm -f netdata.tmpl netdata-subdomain.tmpl sogo.tmpl sogo-subdomain.tmpl adminer.tmpl
sudo rm -f stub_status.tmpl redirect_to_https.tmpl php-catchall.tmpl iredadmin.tmpl hsts.tmpl
```

> [!note]
> Right now NGINX serves only Roundcube webmail and the iRedAdmin panel. More sites will come later and we'll add their definitions too. That's it for now.

### Checking

Let's check the configuration and restart the service:

```bash
sudo nginx -t
sudo systemctl restart nginx
```

## Troubleshooting

If `nginx -t` gives an error, the problem is most likely invisible or formatted characters that got mixed into the configuration text while copying it from the document.

```bash
sudo cat -A /etc/nginx/vhost.d/<FILE>.conf | head
```

With this command we can check whether the problem comes from character formatting. Non-breaking space (NBSP) characters show up as `M-BM-` in the lines.

```bash
sudo sed -i 's/\xC2\xA0/ /g' /etc/nginx/vhost.d/<FILE>.conf
```

And with this command we can fix it.
