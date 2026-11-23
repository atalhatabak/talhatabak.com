---
title: "Syncthing Setup"
description: "Syncthing for syncing files between devices; the server is the shared peer that is always on."
date: 2026-11-21T00:22:00+03:00
chapter: "12"
tags: ["syncthing"]
---
> [!abstract] Requirements
> - [1 Post-Install Configuration](/self-hosting/post-install-configuration/) (the EPEL repository), [5 Firewalld Configuration](/self-hosting/firewalld/) and [7.2 Putting Services Behind the VPN](/self-hosting/services-behind-vpn/) must be done.
>
> **Assumptions**
> - The Syncthing web UI is reached at `sync.xenonly.com`, only over the VPN. `A` and `AAAA` records exist for this domain.
> - Devices connect to the server at `xenonly.com:22000`.
> - Syncthing runs as a separate `syncthing` system user whose home directory is `/srv/syncthing`.
> - Server commands are run on the server with root rights (`sudo`). The device pairing steps are done in the Syncthing UI on the clients.

## What It Is

Syncthing is an open-source tool that syncs files directly between devices. There is no central cloud service; each device has its own identity (Device ID) and shares files only with the devices we pair it with, over an encrypted connection.

The Syncthing we install on the server will be a shared peer of our devices that is always on. Even if the computer and the phone are not on at the same time, changes will reach the other devices through the server.

## Decisions Before Installing

**Native installation:** Unlike the other applications, we'll install Syncthing directly on the server with the package from the [EPEL](term:epel) repository, not with Docker. The package follows the current version and is updated together with the system with `dnf upgrade`. The [systemd](term:systemd) service that comes with the package also comes with sandbox settings (read-only system directories, limited privileges and so on).

**A separate user:** The sync port will be open to the internet, so we'll run Syncthing as a separate `syncthing` system user, not as our own user. So if there is ever a hole in Syncthing, an attacker can reach only this user's files; they can't reach our own home directory (for example the keys in `~/.ssh`).

**Ports:**

| Port | Used for | Access |
| --- | --- | --- |
| `22000/tcp` | Sync (TCP) | Public |
| `22000/udp` | Sync ([QUIC](term:quic)) | Public |
| `127.0.0.1:8384` | Web UI | Only through NGINX, with the VPN |

**The sync port will be public:** So the [full tunnel](term:full-tunnel) doesn't have to stay on all the time on the phone (the same reason as in [9 Vaultwarden Setup](/self-hosting/vaultwarden/)). Syncthing connections use [TLS](term:tls) where both sides check each other's certificate; the server talks only to devices whose Device ID we added.

**The web UI only over the VPN:** By default the Syncthing UI listens only on `127.0.0.1:8384`. We'll serve the UI through NGINX with the `vpn-only` template.

> [!note]
> The local discovery port (`21027/udp`) is used to find devices on the same local network. The server is a [VPS](term:vps) and we have no other devices on its local network, so we don't open this port.

## Installation

Let's install the package:

```bash
sudo dnf install syncthing
```

Let's create a system user for Syncthing with `/srv/syncthing` as its home directory:

```bash
sudo useradd --system --create-home --home-dir /srv/syncthing --shell /usr/sbin/nologin syncthing
```

- **`--system`:** A user for running a service, not for logging in.
- **`--home-dir /srv/syncthing`:** Syncthing's configuration (`/srv/syncthing/.local/state/syncthing`) and the synced folders will be in this directory.
- **`--shell /usr/sbin/nologin`:** You can't log in with this user.

> [!note]
> On Rocky Linux, home directories are created with `700` permissions by default (you can check with `ls -ld /home/*`). So the `syncthing` user can't read the home directories of the other users.

The `syncthing@.service` that comes with the package is a service template that runs as the user given as a parameter. Let's enable and start the service for the `syncthing` user:

```bash
sudo systemctl enable --now syncthing@syncthing
sudo systemctl status syncthing@syncthing
```

On the first run Syncthing creates its own keys and configuration. Let's check:

```bash
sudo ls /srv/syncthing/.local/state/syncthing   # cert.pem, config.xml, key.pem ...
sudo ss -tulpn | grep syncthing
```

Port `22000` should show up for TCP and UDP on all addresses (`*:22000`), and port `8384` only on `127.0.0.1`.

> [!note]
> The service logs are in [journald](term:journald): `sudo journalctl -u syncthing@syncthing`

## Firewalld

Let's open the sync port in the public [zone](term:firewalld-zone) and in the VPN zone:

```bash
sudo firewall-cmd --permanent --zone=public --add-port=22000/tcp --add-port=22000/udp
sudo firewall-cmd --permanent --zone=vpn --add-port=22000/tcp --add-port=22000/udp
sudo firewall-cmd --reload
```

> [!note]
> Why we open it in the VPN zone too: when the full tunnel is connected, the devices' traffic to the server's public IP also comes in through `wg0` and is checked against the rules of the VPN zone (see [7 WireGuard Setup](/self-hosting/wireguard/)).

## Certificate and NGINX Reverse Proxy

Let's get the certificate:

```bash
sudo certbot certonly --webroot -w /opt/www/well_known -d sync.xenonly.com
```

Let's create `/etc/nginx/vhost.d/vhost_sync.xenonly.com.conf` like this:

```nginx {title="/etc/nginx/vhost.d/vhost_sync.xenonly.com.conf"}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name sync.xenonly.com;

    ssl_certificate     /etc/letsencrypt/live/sync.xenonly.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sync.xenonly.com/privkey.pem;
    include /etc/nginx/templates/vpn-only.tmpl;

    location / {
        proxy_pass http://127.0.0.1:8384;

        proxy_set_header Host              localhost;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
```

- **We don't use `proxy.tmpl`:** While the UI is bound to `127.0.0.1`, Syncthing requires the `Host` header of incoming requests to be `localhost` (against [DNS rebinding](term:dns-rebinding) attacks). `proxy.tmpl` sends the `Host` header as `sync.xenonly.com`, so the UI would give a "Host check error". That's why we set the headers one by one here and send the `Host` header as `localhost`.
- **`proxy_read_timeout 600s`:** The UI follows changes with requests that stay open for a long time ([long polling](term:long-polling)); the default 60 second timeout cuts these requests.

Let's test the NGINX configuration and reload it:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

> [!note]
> To reach it with a [split tunnel](term:split-tunnel), add the entry `10.8.0.1 sync.xenonly.com` to the `hosts` file on your personal computer (see [7.3 Possible Problems](/self-hosting/wireguard-troubleshooting/)).

## First Configuration

While connected to the VPN, let's go to `https://sync.xenonly.com`.

1. In **Actions → Settings → GUI**, let's fill in **GUI Authentication User** and **GUI Authentication Password** and save. Even though the UI is behind the VPN, we don't leave it without a password. We don't turn on the **Use HTTPS for GUI** option on the same page.
2. In the same window, on the **Connections** tab, let's turn off **Enable Local Discovery**; there are no other devices of ours on the server's local network.
3. If we won't use the **Default Folder** that comes by default, we can remove it with the folder's **Edit → Remove** option.

> [!warning] Don't turn on Use HTTPS for GUI
> HTTPS is provided by NGINX. If this option is on, Syncthing redirects the HTTP requests from NGINX to the address in the `Host` header. NGINX sends this header as `localhost`, so the browser goes to `https://localhost/` and the UI can't be reached. If the option was turned on by mistake, we can't reach the UI, so let's turn it off in the configuration file on the server:
>
> ```bash
> sudo systemctl stop syncthing@syncthing
> sudo sed -i '/<gui /s/tls="true"/tls="false"/' /srv/syncthing/.local/state/syncthing/config.xml
> sudo systemctl start syncthing@syncthing
> ```
>
> Syncthing keeps the configuration in memory and overwrites the file when a change is saved, so we edit the file while the service is stopped.

> [!note]
> The server's device name is its hostname (`mail.xenonly.com`) by default. You can change it in **Actions → Settings → General → Device Name**.

## Pairing Devices

Syncthing must be installed on each device. The steps below are repeated for each device.

1. In the server's UI, let's copy the server's Device ID with **Actions → Show ID**.
2. In the Syncthing UI on the device, let's enter the server's Device ID with **Add Remote Device**. On the **Advanced** tab, let's write `tcp://xenonly.com:22000, dynamic` in the **Addresses** field.
3. Within a few seconds, a notice shows up in the server's UI saying that the device wants to connect; let's accept it with **Add Device**.

> [!note]
> `dynamic` lets Syncthing find the server again through global discovery if the server's address changes. `tcp://xenonly.com:22000` connects directly, without needing discovery.

### Sharing a Folder

1. In the UI on the device, let's tick the server on the **Edit → Sharing** tab of the folder we want to share.
2. In the server's UI, let's click **Add** on the notice saying the folder is being shared. By default the **Folder Path** is under the `syncthing` user's home directory (`/srv/syncthing/<FOLDER>`); let's leave it like that.
3. When the same folder is shared with the server on the other devices too, changes reach all devices through the server.

> [!warning]
> Syncthing is not a backup tool; a file deleted on one device is deleted from the other devices too. If **Edit → File Versioning → Staggered File Versioning** is turned on for the folders on the server, old versions of deleted and changed files are kept on the server in the `.stversions` directory for a while.

## Reaching the Synced Files with Our Own User (Optional)

Only the `syncthing` user can read the `/srv/syncthing` directory. If we want to read the synced files on the server with our own user, without `sudo`, let's add our user to the `syncthing` group and give the group read access:

```bash
sudo usermod -aG syncthing "$USER"
sudo chmod 750 /srv/syncthing
sudo chmod 700 /srv/syncthing/.local
```

- **`chmod 750 /srv/syncthing`:** Members of the `syncthing` group can enter the directory and read the files; other users can't enter it.
- **`chmod 700 /srv/syncthing/.local`:** Syncthing's keys and configuration are in this directory. Nobody, group members included, should be able to read it.

> [!note]
> For the group membership to take effect, you need to log out and log in again. With this setting we can read the files but not change them; changes to the files should be made from the devices, through Syncthing.

## Check

From our personal computer, while not connected to the VPN:

```bash
nc -zv -w 5 xenonly.com 22000                     # should connect
curl -sI https://sync.xenonly.com | head -1       # HTTP/2 403
```

On the server:

```bash
curl -s http://127.0.0.1:8384/rest/noauth/health   # {"status": "OK"}
```

In the server's UI, the paired devices should show as **Connected** and the folders as **Up to Date**.

## Backup and Updates

- **`/srv/syncthing/.local/state/syncthing`:** The server's identity (`cert.pem`, `key.pem`) and configuration are here. If these files are lost, the server starts with a new Device ID and all devices need to be paired again.
- **The synced folders:** A copy of the files is already on the other devices too, but Syncthing is not a backup tool, so important folders should be backed up separately.

The Syncthing package is updated together with the system with `sudo dnf upgrade`. After the update, let's restart the service so the new version runs:

```bash
sudo systemctl restart syncthing@syncthing
```
