In this series I'll look at what you can self-host on a VPS and how to do it, in a technical and hands-on way.

## Server and Environment

This is the server I used while preparing these documents:

@@code@@

You also need a domain name. In this series I use the domain `xenonly.com`.

## Assumptions and Conventions

### Domain Names

The domain I'll use is `xenonly.com`. The mail server will use the name `mail.xenonly.com`, and I'll serve the other services on subdomains of `xenonly.com` (for example `iredadmin.xenonly.com`).

The series assumes that the DNS records for the domain and the subdomains it uses are already in place. This step is not explained again, except for the records that need special care (MX, SPF, DKIM, DMARC, PTR).

> Basically, what you need to do is add `A` and `AAAA` records for the domain and its subdomains (or `*.xenonly.com` if you like).

### Notes at the Start of Each Part

At the start of each part there is a short note with the **requirements** (the parts that must be done first) and the **assumptions** (the domain names used, where and with which rights the commands are run, and so on).

### Code Blocks

Most commands need root rights. To show this and to keep the commands easy to copy, I write them as `sudo ...` instead of using a `#` prompt for root and a `$` prompt for a normal user. Commands written without `sudo` are run as a normal user.

The expected output of a command is given in a separate `text` block, or as a comment starting with `#` next to the command.

### Placeholders

Values written in capitals inside angle brackets, like `<SERVER_IPV4>`, must be replaced with your own values. Names that contain a file name, like `<server.key>`, stand for the contents of that file.

## Roadmap

### [1 Post-Install Configuration](/self-hosting/post-install-configuration/)

First checks and basic settings on a freshly installed Rocky Linux 10 server.

### [2 Mail Server Setup](/self-hosting/mail-server/)

The first main service on the server will be mail. Right after setting up the server, we'll install the mail service with [iRedMail](https://www.iredmail.org/). This also installs NGINX and MariaDB.

- [2.1 Setting Up SSL for the Mail Server](/self-hosting/mail-server-ssl/)
- [2.2 Adding a New Domain to the Mail Server](/self-hosting/mail-server-new-domain/)
- [2.3 Using a Mail Client](/self-hosting/mail-clients/)
- [2.4 Moving the Mail Server](/self-hosting/mail-server-migration/)
- [2.5 Extra Settings](/self-hosting/mail-server-extras/)

### [3 NGINX Configuration](/self-hosting/nginx/)

Turning the NGINX setup that iRedMail installed into one that can serve many services and virtual hosts.

### [4 Docker Setup](/self-hosting/docker/)

Installing Docker and setting it up so that containers are reachable only over localhost.

- [4.1 A Ready Template for Docker Containers](/self-hosting/docker-template/)

### [5 Firewalld Configuration](/self-hosting/firewalld/)

Configuring and turning on Firewalld, which we keep off during the setup, and blocking containers and VPN clients from going out on port 25.

### [6 Fail2Ban Configuration](/self-hosting/fail2ban/)

Adding longer and longer ban times for repeat attackers to the Fail2Ban that comes with iRedMail.

### [7 WireGuard Setup](/self-hosting/wireguard/)

A VPN server: sending clients to the internet through the VPN, letting clients talk to each other and making some services reachable only over the VPN.

- [7.1 Adding WireGuard Clients](/self-hosting/wireguard-clients/)
- [7.2 Putting Services Behind the VPN](/self-hosting/services-behind-vpn/)
- [7.3 Possible Problems](/self-hosting/wireguard-troubleshooting/)

### [8 Vault Setup](/self-hosting/vault/)

Keeping secrets (API keys, tokens, passwords) in one central, encrypted place with HashiCorp Vault.

### [9 Vaultwarden Setup](/self-hosting/vaultwarden/)

Installing Vaultwarden, a Bitwarden-compatible password manager.

### [10 WordPress Setup](/self-hosting/wordpress/)

A WordPress setup where every site runs in its own container and all sites use one shared MariaDB container.

- [10.1 Moving an Old WordPress Site into This Setup](/self-hosting/wordpress-migration/)

### [11 Usememos Setup](/self-hosting/memos/)

Installing Memos, a note app you can host yourself.

### [12 Syncthing Setup](/self-hosting/syncthing/)

Syncthing for syncing files between devices; the server is used as the shared peer that is always on.

### 13 Hugo Blog Setup

Coming soon

### 14 Log Management and Monitoring

Coming soon

### 15 Backup Strategy

Coming soon
