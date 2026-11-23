> **Requirements**
> - [2 Mail Server Setup](/self-hosting/mail-server/), [4.1 A Ready Template for Docker Containers](/self-hosting/docker-template/), [6 Fail2Ban Configuration](/self-hosting/fail2ban/) and [7.2 Putting Services Behind the VPN](/self-hosting/services-behind-vpn/) must be done.
>
> **Assumptions**
> - Vaultwarden is reached at `password.xenonly.com`. `A` and `AAAA` records exist for this domain.
> - The Vaultwarden container uses port `127.0.0.1:8004`.
> - Commands are run on the server with root rights (`sudo`).

## What It Is

Vaultwarden is a light version of the Bitwarden server, written in Rust. It works with the official Bitwarden clients (browser extension, desktop, mobile). Self-hosting the official Bitwarden needs several containers, MSSQL and gigabytes of RAM; Vaultwarden runs in a single container with a few dozen MB of RAM.

The vault is encrypted on the client. The server never sees the master password, it only stores the encrypted data. This is also what drives the access decision below.

## Decisions Before Installing

**Subdomain:** I'll use `password.xenonly.com` for Vaultwarden.

**Port:** Vaultwarden will be served on port `8004`.

**Database:** Vaultwarden supports SQLite, MariaDB and PostgreSQL. We could use the MariaDB container we'll set up for WordPress in [10 WordPress Setup](/self-hosting/wordpress/), but for a single user SQLite is enough. All the data sits in a single `data` directory, it is easy to back up, and the service doesn't depend on MariaDB.

**Access:** It will be public.

- For autofill and sync on the phone, the server must be reachable all the time. The `hosts` file method we chose for the services behind the VPN can't be done on mobile devices without root access; if Vaultwarden were reachable only over the VPN, the full tunnel would have to stay on all the time on the phone.
- The clients keep a copy of the vault on the device. When the server can't be reached, the vault can still be read, but new entries don't sync.
- The data is encrypted on the client, so even if the server is compromised, the vault can't be opened without the master password.

Since it will be public, we'll close sign-ups, put the admin panel behind the VPN, turn on 2FA and add a Fail2Ban jail.

## Installation

### Mail Account

Vaultwarden sends mail for 2FA, new device notifications and invitations. Let's create the account `vaultwarden@xenonly.com` in iRedAdmin.

### Admin Token

@@code@@

The command asks for a password twice and prints a line like `ADMIN_TOKEN='$argon2id$v=19$...'`. Let's add this line as it is to the file `/opt/docker/vaultwarden/.env`:

@@code@@

> `<SMTP_PASSWORD>`: The password of the `vaultwarden@xenonly.com` account.

@@code@@

> The single quotes matter. The hash contains `$` characters; without the quotes, Docker Compose reads them as variables and removes them.

> You log in to the admin panel with the password you entered in the command, not with the hash.

### Compose

Let's create `/opt/docker/vaultwarden/compose.yaml` like this:

@@code@@

Why each line is there:

1. **`DOMAIN`:** The links in the mails, WebSocket and WebAuthn use this address. Write the full address, with `https://`.
2. **`SIGNUPS_ALLOWED: "true"`:** Only to create the first account. After the account is created, it will be set to `false`.
3. **`INVITATIONS_ALLOWED: "false"`:** When it is on, new accounts can be opened with organization invitations even if sign-ups are closed. There will be a single user, so we turn it off.
4. **`PASSWORD_HINTS_ALLOWED: "false"`:** A password hint leaks information about the master password.
5. **`SMTP_FROM` and `SMTP_USERNAME` are the same:** iRedMail rejects mail sent with a sender address different from the account that logged in.
6. **`TZ`:** So the log times are written in local time.

> By default, Vaultwarden reads the visitor's IP address from the `X-Real-IP` header; `proxy.tmpl` sends this header. Fail2Ban depends on this; without the header, every request looks like it comes from a 172.20.x.x address.

Let's start the container:

@@code@@

> **Careful:** If a setting is changed and saved in the admin panel, Vaultwarden creates the file `data/config.json`, and the values in this file override the environment variables in the compose file. After that, changes made in the compose file are silently ignored. So we'll manage the settings only from the compose file; we'll use the admin panel for user management and diagnostics, not for saving settings.

## Certificate and NGINX Reverse Proxy

Let's get the certificate:

@@code@@

Let's create `/etc/nginx/vhost.d/vhost_password.xenonly.com.conf` like this:

@@code@@

- **`add_header Strict-Transport-Security`:** Vaultwarden sends its own CSP and security headers; if the headers from `headers.conf` were added too, some of them would appear twice in the response. When a single `add_header` is defined in a virtual host, the headers in `headers.conf` are not inherited by that virtual host (see [3 NGINX Configuration](/self-hosting/nginx/)). We add HSTS ourselves, and Vaultwarden sends the rest.
- **`client_max_body_size 128m`:** For file attachments and Send. The 12m iRedMail sets is not enough.
- **WebSocket:** Live sync to the other devices goes over WebSocket through `/notifications/hub`. Since version 1.29 no separate port is needed; the `Upgrade` and `Connection` headers in `proxy.tmpl` are enough.
- **`location /admin`:** Keeps the admin panel behind the VPN even after the `vpn-only` line in the server block is removed. To reach it with a split tunnel, add the entry `10.8.0.1 password.xenonly.com` to the `hosts` file on your personal computer (see [7.3 Possible Problems](/self-hosting/wireguard-troubleshooting/)).

Let's test the NGINX configuration and reload it:

@@code@@

## First Account and Closing Sign-Ups

1. Let's connect to the VPN with the full tunnel and create our account at `https://password.xenonly.com`.
2. Let's turn on 2FA from **Settings → Security → Two-step login → Authenticator app**. Let's save the recovery code somewhere outside the server.
3. In the compose file, let's set `SIGNUPS_ALLOWED: "false"` and recreate the container with `sudo docker compose up -d`.
4. In the virtual host, let's delete the server-level `include /etc/nginx/templates/vpn-only.tmpl;` line and reload NGINX with `sudo nginx -t && sudo systemctl reload nginx`.

> **Careful:** If the master password is forgotten, there is no way to recover it; it can't be reset on the server side. Learn it by heart and keep it on paper in a safe place.

### Clients

In the Bitwarden apps, choose **Self-hosted** from the region selection on the login screen and enter `https://password.xenonly.com` as the Server URL.

## Check

From our personal computer, while not connected to the VPN:

@@code@@

- Over the VPN, the `https://password.xenonly.com/admin/diagnostics` page should show no errors in the domain, time and WebSocket checks.
- You can test SMTP with **Send test email** in the admin panel; this button doesn't save any settings.
- If an entry added on one device shows up on another device within a few seconds while the vault is open on both, WebSocket works.

## Extra Settings

### Fail2Ban

The Docker logs go to journald, so we'll define the jail with the `systemd` backend.

Let's create the file `/etc/fail2ban/filter.d/vaultwarden.local` with the content below:

@@code@@

Let's create the file `/etc/fail2ban/jail.d/vaultwarden.local` with the content below:

@@code@@

After trying to log in once with a wrong password, let's test the filter and restart the service:

@@code@@

> The ban works because NGINX runs on the host; the request comes to port 443 on the host. If the container port were open to the internet directly, the traffic would go through Docker's FORWARD chain and the ban rules on the host wouldn't catch it.

> I didn't add a jail for the admin panel; the panel is behind the VPN, and the VPN network is already in `ignoreip`.

> If you get a backend error, install the package for journald support with `sudo dnf install fail2ban-systemd`.

### Backup

Everything that needs a backup is under `/opt/docker/vaultwarden/data`:

| File | Note |
| --- | --- |
| `db.sqlite3` | A plain copy while the service is running can give an inconsistent backup; take it with `.backup` |
| `attachments/`, `sends/` | File attachments and Send files |
| `config.json` | If it exists |
| `rsa_key.pem` | Signs the sessions. If it is lost, all devices are logged out; no data is lost |

@@code@@

> The vault data is encrypted with the master password; when you restore from a backup, you need the master password too.

> For the worst case, take an export from the web vault now and then with **Tools → Export → Encrypted JSON** and keep it outside the server.

### Updates

@@code@@

Bitwarden clients update themselves, and an old Vaultwarden version can have problems with new clients. So keeping Vaultwarden up to date matters more than for the other services; it should be one of the first services to get automatic updates.
