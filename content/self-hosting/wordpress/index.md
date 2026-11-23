---
title: "WordPress Setup"
description: "A WordPress setup where every site runs in its own container and all sites share one MariaDB container."
date: 2026-11-21T00:19:00+03:00
chapter: "10"
tags: ["wordpress", "docker", "mariadb"]
---
> [!abstract] Requirements
> - [3 NGINX Configuration](/self-hosting/nginx/), [4 Docker Setup](/self-hosting/docker/) and [4.1 A Ready Template for Docker Containers](/self-hosting/docker-template/) must be done.
> - For the sites to send mail, [2 Mail Server Setup](/self-hosting/mail-server/) must be done.
> - To finish the setup wizard behind the VPN, [7.2 Putting Services Behind the VPN](/self-hosting/services-behind-vpn/) must be done.
>
> **Assumptions**
> - The example site is `example.com`, and the site's short name is `example`. The short name is used in directory, container and database names; for each site, replace every `example` with the site's name.
> - `A` and `AAAA` records exist for `example.com` and `www.example.com`.
> - The port range `8030`–`8049` is set aside for WordPress sites; the first site uses port `8030`.
> - Commands are run on the server with root rights (`sudo`).

We'll install the WordPress sites with Docker. Each site will run in its own [container](term:container), and all sites will use one shared MariaDB container.

## Architecture

```text
                      ┌→ 127.0.0.1:8030 → wp-example ──┐
Internet → NGINX:443 ─┤                                ├─ db network (internal) → mariadb
                      └→ 127.0.0.1:8031 → wp-other ────┘
```

- Each site runs in its own container with the official `wordpress` [image](term:image) (Apache + PHP).
- All sites use a single MariaDB container. Each site has its own database and its own user that has rights only on that database.
- MariaDB is on an `internal` Docker network named `db`. Only the WordPress containers are on this network; MariaDB can't be reached from the host or from the internet, and MariaDB can't reach the internet either.
- The site files are on the host, in the `/opt/docker/wp-<site>/html` directory.
- Like the other services, the WordPress containers open ports only on `127.0.0.1` and are served to the outside with NGINX.

> [!note]
> Why a single MariaDB: a separate MariaDB container for each site means spending RAM for each of them. At this scale one MariaDB is enough; we keep the sites apart by giving each site its own database user.

> [!note]
> The shared `db` network also connects the WordPress containers to each other; a compromised site can reach the other sites directly on port 80, skipping NGINX. The sites are already open to the internet, so this gives no extra access; the only difference is that the restrictions in NGINX (`vpn-only`, Fail2Ban) are skipped. If you want full separation, you can create a separate internal network for each site and connect MariaDB to all of them.

> [!note]
> We don't use the MariaDB on the host (the one [iRedMail](term:iredmail) installed). The mail server's database and the websites' databases should stay apart.

## MariaDB Container

This part is done once, for all sites.

Let's create the directory, generate a random root password and write it to the `.env` file:

```bash
sudo mkdir -p /opt/docker/mariadb
cd /opt/docker/mariadb
sudo sh -c 'umask 077; echo "MARIADB_ROOT_PASSWORD=$(openssl rand -hex 24)" > .env'
```

> [!note]
> `cd` and redirection (`>`) are done by the shell itself, so written as `sudo cd` or `sudo echo ... > .env` they don't run with root rights. That's why we create the file in a single root shell with `sudo sh -c`; `umask 077` makes sure only root can read the file.

Let's create `/opt/docker/mariadb/compose.yaml` like this:

```yaml {title="/opt/docker/mariadb/compose.yaml"}
services:
  mariadb:
    image: mariadb:11.4
    container_name: mariadb
    restart: unless-stopped
    environment:
      MARIADB_ROOT_PASSWORD: ${MARIADB_ROOT_PASSWORD}
      MARIADB_AUTO_UPGRADE: "1"
      MARIADB_ROOT_HOST: localhost
    volumes:
      - ./data:/var/lib/mysql
    networks:
      - db

networks:
  db:
    name: db
    internal: true
```

Why each line is there:

1. **No `ports`:** Only the containers on the `db` network will reach MariaDB; we don't open a port on the host.
2. **`${MARIADB_ROOT_PASSWORD}`:** [Docker Compose](term:docker-compose) reads this value from the `.env` file in the same directory; the password doesn't sit in the open in the compose file.
3. **`MARIADB_AUTO_UPGRADE: "1"`:** When the image is updated, the database files are upgraded to the new version automatically.
4. **`MARIADB_ROOT_HOST: localhost`:** We don't need root access over the network, so we stop the `root@'%'` user from being created. Root access will be possible only from inside the container.
5. **`name: db`:** We fix the network's name. Compose normally puts the project name in front of the network name (`mariadb_db`); from the WordPress compose files we'll connect to this network with the name `db`.
6. **`internal: true`:** The containers on this network can't reach the internet. MariaDB doesn't need the internet, and the WordPress containers will reach the internet through their own networks.

Let's start the service:

```bash
sudo docker compose up -d
sudo docker logs mariadb 2>&1 | tail -3
```

If the output shows `ready for connections`, MariaDB is ready.

> [!note]
> `MARIADB_ROOT_PASSWORD` is used only on the first run, while the `data` directory is empty. Changing the password in the `.env` file later doesn't change the root password. To change it, first change it in MariaDB with `ALTER USER`, then in the `.env` file.

To connect to MariaDB as root:

```bash
sudo docker exec -it mariadb sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD"'
```

> [!note]
> The password is read from the `MARIADB_ROOT_PASSWORD` variable inside the container, so we don't need to type it. The single quotes matter; the variable must be expanded inside the container, not on the host.

## Setting Up a New Site

This part is repeated for every new site. For the first site I'll use port `8030`.

### Database and User

Let's create a database password for the site:

```bash
openssl rand -hex 24
```

> [!note]
> We'll use the password from the output wherever `<DB_PASSWORD>` is written below.

Let's connect to MariaDB:

```bash
sudo docker exec -it mariadb sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD"'
```

and create the site's database and user:

```sql
CREATE DATABASE wp_example CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'wp_example'@'%' IDENTIFIED BY '<DB_PASSWORD>';
GRANT ALL PRIVILEGES ON wp_example.* TO 'wp_example'@'%';
exit
```

> [!note]
> `'%'` means it can connect from any address. MariaDB can be reached only from the `db` network, so this is not a problem.

> [!note]
> The user has rights only on its own database. Even if one site is compromised, the databases of the other sites can't be reached.

### Site Directory

```bash
sudo mkdir -p /opt/docker/wp-example
cd /opt/docker/wp-example
```

Let's create the file `/opt/docker/wp-example/.env` with the content below:

```ini {title="/opt/docker/wp-example/.env"}
DB_PASSWORD=<DB_PASSWORD>
```

```bash
sudo chmod 600 .env
```

### PHP Settings

In the image's default PHP settings the upload limit is 2 MB. This limit causes problems when uploading themes, plugins or large images; let's add our own settings.

Let's create the file `/opt/docker/wp-example/php.ini` with the content below:

```ini {title="/opt/docker/wp-example/php.ini"}
upload_max_filesize = 64M
post_max_size = 64M
memory_limit = 256M
max_execution_time = 300
```

### Compose

Let's create `/opt/docker/wp-example/compose.yaml` like this:

```yaml {title="/opt/docker/wp-example/compose.yaml"}
services:
  wordpress:
    image: wordpress:php8.4-apache
    container_name: wp-example
    restart: unless-stopped
    ports:
      - "127.0.0.1:8030:80"
    environment:
      WORDPRESS_DB_HOST: mariadb
      WORDPRESS_DB_NAME: wp_example
      WORDPRESS_DB_USER: wp_example
      WORDPRESS_DB_PASSWORD: ${DB_PASSWORD}
    volumes:
      - ./html:/var/www/html
      - ./php.ini:/usr/local/etc/php/conf.d/custom.ini:ro
    networks:
      - default
      - db

networks:
  db:
    external: true
```

Why each line is there:

1. **`wordpress:php8.4-apache`:** The image only provides PHP and Apache. We pin the PHP version so it doesn't change before we check that the plugins work with it.
2. **`WORDPRESS_DB_HOST: mariadb`:** The name of the MariaDB container; it resolves by this name on the `db` network.
3. **`./html:/var/www/html`:** The WordPress files (core, themes, plugins, uploads) are kept on the host. If the directory is empty, the image copies WordPress here on the first run.
4. **`./php.ini`:** Our own PHP settings. With `:ro` the container can only read this file.
5. **`networks: default, db`:** Through the `default` network it reaches the internet (updates, plugins) and publishes its port; through the `db` network it reaches MariaDB.
6. **`external: true`:** The `db` network is not created in this compose file; we connect to the network that MariaDB's compose file created. So the MariaDB container must be set up first.

Let's start the container:

```bash
sudo docker compose up -d
sudo ls html
sudo docker logs wp-example 2>&1 | tail -5
```

The `html` directory should now have files like `wp-admin`, `wp-content` and `wp-config.php`.

> [!note]
> The image creates `wp-config.php` from its own template. It reads the database details from the environment variables and generates the security keys ([salts](term:salt)) at random. The same template looks at the `X-Forwarded-Proto` header coming from NGINX to understand that it runs behind HTTPS; no extra setting is needed.

> [!note]
> Apache's `remoteip` module is on in the image; the logs and WordPress show the visitor's real IP address (`X-Forwarded-For`).

> [!note]
> If the WordPress container comes up before MariaDB when the server restarts, it may show "Error establishing a database connection" for a few seconds; it fixes itself once MariaDB is up.

### Certificate and NGINX Reverse Proxy

Let's get the certificate:

```bash
sudo certbot certonly --webroot -w /opt/www/well_known -d example.com -d www.example.com
```

Let's create `/etc/nginx/vhost.d/vhost_example.com.conf` like this:

```nginx {title="/etc/nginx/vhost.d/vhost_example.com.conf"}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name example.com www.example.com;

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    client_max_body_size 64m;

    # Until the setup wizard is finished, remove afterwards
    include /etc/nginx/templates/vpn-only.tmpl;

    location = /xmlrpc.php {
        deny all;
    }

    location / {
        proxy_pass http://127.0.0.1:8030;
        include /etc/nginx/templates/proxy.tmpl;
    }
}
```

- **`client_max_body_size 64m`:** The same as the upload limit in `php.ini`. The iRedMail installation sets 12m and rejects bigger uploads before they reach PHP.
- **`vpn-only.tmpl`:** [Let's Encrypt](term:lets-encrypt) writes every certificate we get to the public [Certificate Transparency](term:certificate-transparency) logs. Some bots watch these logs for new domains and look for half-finished WordPress installations; whoever finishes the wizard first becomes the admin. So until the wizard is finished, the site will be reachable only over the VPN.
- **`xmlrpc.php`:** An old remote access API; a common target for [brute force](term:brute-force) and [DDoS](term:ddos) attacks. If you'll use Jetpack or the WordPress mobile app, remove this block.
- WordPress itself redirects requests for `www.example.com` to the site address (`example.com`).

Let's test the NGINX configuration and reload it:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### Setup Wizard

Let's connect to the VPN with the [full tunnel](term:full-tunnel), go to `https://example.com` and finish the setup wizard:

- Let's not use `admin` as the admin username; it is the first username brute force attempts try.
- Let's pick a strong password and save it in the password manager.

> [!note]
> With a [split tunnel](term:split-tunnel), the domain resolves to the server's public IP, so the request doesn't go through the VPN and gets a 403 (see [7.3 Possible Problems](/self-hosting/wireguard-troubleshooting/)).

After the wizard is finished, let's delete the `include /etc/nginx/templates/vpn-only.tmpl;` line in the [virtual host](term:virtual-host) and reload NGINX:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### Check

```bash
curl -I https://example.com   # HTTP/2 200
```

In the admin panel, the **Tools → Site Health** page should show no critical problems.

## Extra Settings

### Sending Mail

There is no mail server in the WordPress container, so PHP's `mail()` function doesn't work. Password reset, new user and contact form mails won't go out. Let's install an [SMTP](term:smtp) plugin (WP Mail SMTP or similar) and use our own mail server:

| Setting | Value |
| --- | --- |
| SMTP server | `mail.xenonly.com` |
| Port | 587 ([STARTTLS](term:starttls)) |
| User | The mail account opened for the site in [iRedAdmin](term:iredadmin) |

> [!note]
> The container resolves `mail.xenonly.com` to the server's public IP, and the connection comes to the host over the Docker network. In Firewalld the target of the `docker` [zone](term:firewalld-zone) is ACCEPT, so no extra rule is needed.

> [!note]
> If the mail will be sent from an `@example.com` address, the domain must be added to iRedAdmin and its [SPF](term:spf), [DKIM](term:dkim) and [DMARC](term:dmarc) records must be added in DNS (see [2.2 Adding a New Domain to the Mail Server](/self-hosting/mail-server-new-domain/)). Or you can send from an account under `xenonly.com`.

### Updates

- **WordPress, themes and plugins:** The files are in the `html` directory; they are updated from the admin panel or with automatic updates. Updating the image doesn't update WordPress.
- **PHP and Apache:** `sudo docker compose pull && sudo docker compose up -d` in the site directory.
- **Upgrading the PHP version:** Changing the image tag in the compose file is enough (for example `php8.4-apache` → `php8.5-apache`). Check first that the plugins work with the new version.
- **MariaDB:** `sudo docker compose pull && sudo docker compose up -d` in the MariaDB directory. The image tag is `11.4`, so it stays within version 11.4.
