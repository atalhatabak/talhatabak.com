---
title: "Mail Server Setup"
description: "The first main service on the server: a mail server with iRedMail. This setup also installs NGINX and MariaDB."
date: 2026-11-21T00:02:00+03:00
chapter: "2"
tags: ["mail", "iredmail", "dns"]
---
> [!abstract] Requirements
> - [1 Post-Install Configuration](/self-hosting/post-install-configuration/) must be done.
> - iRedMail must be installed on a freshly installed server; this part installs the first service on the server.
>
> **Assumptions**
> - The name of the mail server (hostname) is set to `mail.xenonly.com` and the first mail domain is `xenonly.com`.
> - `A` and `AAAA` records exist for `xenonly.com` and `mail.xenonly.com`. The other records mail needs (MX, SPF, DKIM, DMARC, PTR) are added in this part.
> - Commands are run on the server with root rights (`sudo`). The DNS checks with `dig` are done from a personal computer.

For mail we'll mainly use [Postfix](term:postfix) and [Dovecot](term:dovecot). For the installation and the first configuration we'll use the [iRedMail](term:iredmail) install script.

> [!important]
> iRedMail must be installed on a freshly installed server. That's why iRedMail is the first thing we install after setting up the server. We'll add the other services later and adjust the configuration of the services that clash with iRedMail to fit our needs.

## Preparation

### Changing the Hostname

I'll use `mail.xenonly.com` as the name of the mail server. The other domains added later will also send mail using this server name. Let's change the hostname with the command below:

```bash
sudo hostnamectl set-hostname mail.xenonly.com
```

During the installation, iRedMail expects the hostname to resolve as a fully qualified domain name ([FQDN](term:fqdn)). Let's check it:

```bash
hostname -f   # mail.xenonly.com
```

If the output is not `mail.xenonly.com`, let's add the server name to the start of the `127.0.0.1` line in `/etc/hosts`:

```text {title="/etc/hosts"}
127.0.0.1   mail.xenonly.com mail localhost localhost.localdomain
```

### Turning Off SELinux

iRedMail says it doesn't work with [SELinux](term:selinux) and recommends turning it off. This is the recommended way to turn it off on Rocky Linux 10:

```bash
sudo grubby --update-kernel ALL --args selinux=0
```

After turning SELinux off with this command, let's reboot the system:

```bash
sudo reboot
```

## Downloading and Installing iRedMail

We get the download link of the latest release from https://www.iredmail.org/download.html. At the time of writing (November 2026), the latest release is 1.8.8.

```bash
cd /opt
sudo wget https://github.com/iredmail/iRedMail/archive/refs/tags/1.8.8.tar.gz
sudo tar zxf 1.8.8.tar.gz
cd iRedMail-1.8.8
sudo bash iRedMail.sh
```

> [!note]
> `cd` is a command of the shell itself, so it is run directly, not with `sudo`. The commands that write files run with `sudo`, so they can write under `/opt`.

With these commands we download and run the iRedMail installer. After the needed packages are installed, the setup wizard opens:

- We continue with **Yes** and leave the mail storage directory at the default, **/var/vmail**.
- Web server → **Nginx**
- Database for the mail accounts → **MariaDB**
- We set a password for the MariaDB root user. This password is written to `/root/.my.cnf` and used by root's database commands and by the backup script; it should be random and different from the postmaster password.
- First mail domain → **xenonly.com**. The important point here: this value must not be the server's hostname (`mail.xenonly.com`).
- We set a password for the address `postmaster@xenonly.com`. This address and password will be used as the admin account.

> [!warning]
> Strong random passwords are recommended for both; the wizard shows a random sample password on both screens. After the installation, the passwords entered during the setup are written in plain text to a few files on the server. Where they are kept and how to clean them up is in [2.5 Extra Settings](/self-hosting/mail-server-extras/).

Next we choose the optional components:

- Webmail → **[Roundcube](term:roundcube)**
- Admin panel → **[iRedAdmin](term:iredadmin)**
- Security → **Fail2ban**

These are already selected by default. I also remove the system monitoring service **Netdata**.

When the wizard is done, it shows a summary like this:

```text
********************** Review your settings *****************************
*************************************************************************

* Storage base directory:               /var/vmail
* Mailboxes:
* Daily backup of SQL/LDAP databases:
* Store mail accounts in:               MariaDB
* Web server:                           Nginx
* First mail domain name:               xenonly.com
* Mail domain admin:                    postmaster@xenonly.com
* Additional components:                Roundcubemail iRedAdmin Fail2ban
```

We continue with **y** and the installation starts. During the installation there will be some questions about the configuration.

```text
< Question > Would you like to use firewall rules provided by iRedMail?
< Question > File: /etc/firewalld/zones/iredmail.xml, with SSHD ports: 22. [Y|n]
```

I answer this question with `n`. I'll do the firewall settings myself in [5 Firewalld Configuration](/self-hosting/firewalld/).

```text
< Question > Would you like to use MySQL configuration file shipped within iRedMail now?
< Question > File: /etc/my.cnf. [Y|n]
```

We confirm this question with `Y`.

The installation finishes with an output like this:

```text
********************************************************************
* URLs of installed web applications:
*
* - Roundcube webmail: https://mail.xenonly.com/mail/
*
* - Web admin panel (iRedAdmin): https://mail.xenonly.com/iredadmin/
*
* You can login to above links with below credential:
*
* - Username: postmaster@xenonly.com
* - Password: ***
*
********************************************************************
* Congratulations, mail server setup completed successfully. Please
* read below file for more information:
*
*   - /opt/iRedMail-1.8.8/iRedMail.tips
*
* And it's sent to your mail account postmaster@xenonly.com.
*
********************* WARNING **************************************
*
* Please reboot your system to enable all mail services.
*
********************************************************************
```

Then we reboot the system:

```bash
sudo reboot
```

## After the Installation

### DNS Settings

To add the DNS records, we go to the panel of the provider that manages the domain's DNS.

At this point we'll add the DNS records `xenonly.com` needs for the mail server. The records will look roughly like the ones below.
We'll get the `<DKIM_KEY>` value in the [DKIM](term:dkim) Record section below.

| Name | Type | Content | What It Means |
| --- | --- | --- | --- |
| xenonly.com | A | `<SERVER_IPV4>` | IPv4 record for the domain |
| xenonly.com | AAAA | `<SERVER_IPV6>` | IPv6 record for the domain |
| mail.xenonly.com | A | `<SERVER_IPV4>` | IPv4 record for the mail server |
| mail.xenonly.com | AAAA | `<SERVER_IPV6>` | IPv6 record for the mail server |
| xenonly.com | [MX](term:mx-record) | `mail.xenonly.com` | Says which mail server incoming mail should go to |
| dkim._domainkey | TXT | `<DKIM_KEY>` | Lets receivers verify the mail signed by [Amavis](term:amavis) |
| _dmarc | TXT | `"v=DMARC1; p=quarantine; sp=quarantine; np=reject; adkim=s; aspf=s; rua=mailto:dmarc@xenonly.com"` | Says what to do with mail that fails the [SPF](term:spf) or DKIM check |
| xenonly.com | TXT | `"v=spf1 mx a ip4:<SERVER_IPV4> ip6:<SERVER_IPV6> ~all"` | Says which servers may send mail for this domain |
| mail.xenonly.com | TXT | `"v=spf1 a -all"` | SPF for the server's [HELO](term:helo) name; [bounces](term:bounce) with an empty sender address are checked against this name |

> [!note]
> The `dkim._domainkey` and `_dmarc` values in the `Name` column are relative to the domain; the full names are `dkim._domainkey.xenonly.com` and `_dmarc.xenonly.com`.

### DMARC Record

Example record:

```text
v=DMARC1; p=quarantine; sp=quarantine; np=reject; adkim=s; aspf=s; rua=mailto:dmarc@xenonly.com
```

| Parameter | Meaning |
| --- | --- |
| `v=DMARC1` | Version. It must always come first. |
| `p=quarantine` | Mail that fails the check goes to the spam folder. The other options: `none` (only a report is sent, the mail is not affected) and `reject` (the mail is rejected completely). |
| `sp=quarantine` | The same rule for subdomains (for example `x.xenonly.com`). If it is not written, the `p` value applies. If no mail is sent from any subdomain, `reject` can be used too. |
| `np=reject` | Mail sent in the name of subdomains that don't exist in DNS at all (for example `random.xenonly.com`) is rejected. No real mail can come from these names, so the strictest setting is safe here. It is a fairly new parameter, so some servers may not know it yet, but adding it does no harm. |
| `adkim=s` | Strict matching for DKIM: the domain in the signature must be exactly the same as the domain in the sender address. With `r` (relaxed), subdomains are accepted too. |
| `aspf=s` | Strict matching for SPF. Same idea as above. |
| `rua=mailto:…` | The address the daily summary reports are sent to. |

> [!note]
> We need a mailbox for `dmarc@xenonly.com`, the address the [DMARC](term:dmarc) reports are sent to. We'll create it below, in the Account for DMARC Reports section.

### PTR Record

The [PTR](term:ptr-record) (reverse DNS) record shows which name an IP address belongs to, and it is set in the [VPS](term:vps) provider's control panel. In the rDNS/PTR section of the panel, we enter `mail.xenonly.com` for the server's IPv4 address and, if there is one, `mail.xenonly.com` again for the IPv6 address.

> [!warning]
> The PTR value must be the server's hostname, `mail.xenonly.com`, not `xenonly.com`.

> [!warning]
> If the server has IPv6, mail will most likely be sent over IPv6. If the PTR for IPv6 doesn't match, providers like Gmail reject the mail right away.

We can check the records from our personal computer with the commands below:

```bash
dig +short A mail.xenonly.com      # <SERVER_IPV4>
dig +short AAAA mail.xenonly.com   # <SERVER_IPV6>
dig +short -x <SERVER_IPV4>        # mail.xenonly.com.
dig +short -x <SERVER_IPV6>        # mail.xenonly.com.
```

### DKIM Record

**What it is:** A digital signature standard that proves the mail really comes from the authorized domain and was not changed on the way.

#### How It Works

- There is a private key for each domain in the `/var/lib/dkim/` directory.
- The domain and its key are defined for the Amavis service in `/etc/amavisd/amavisd.conf`.
- The public key is in the `dkim._domainkey` DNS record.

> [!note]
> We gave `xenonly.com` as the first domain during the installation, so its keys were created automatically.

To see the existing keys:

```bash
sudo amavisd showkeys
```

To get a single-line output that can go straight into the DNS record:

```bash
sudo amavisd showkeys xenonly.com | awk -F'"' '/^[[:space:]]*"/ {printf "%s", $2} END {print ""}'
```

> [!note]
> The value added to DNS must be a single line. `amavisd showkeys` splits the key over several lines; the command above joins them.

We add this output to DNS like this:

| Name | Type | Content | What It Means |
| --- | --- | --- | --- |
| dkim._domainkey | TXT | `<DKIM_KEY>` | Lets receivers verify the mail signed by Amavis |

At this point our server can send and receive mail for `xenonly.com`.

## Creating Users in iRedAdmin

> [!note]
> In the NGINX configuration that comes with iRedMail, iRedAdmin is at the `/iredadmin` path and Roundcube is at `/mail`. In [3 NGINX Configuration](/self-hosting/nginx/) these addresses are moved to subdomains (`iredadmin.xenonly.com` and `mail.xenonly.com`).

> [!note]
> The server is still using the [self-signed certificate](term:self-signed) iRedMail created, so the browser will show a certificate warning. We'll get a [Let's Encrypt](term:lets-encrypt) certificate in [2.1 Setting Up SSL for the Mail Server](/self-hosting/mail-server-ssl/).

We go to <https://xenonly.com/iredadmin> and log in with the admin account (`postmaster@xenonly.com`).

> [!note]
> The `xenonly.com` domain was created as the first domain during the installation, so we don't need to add it.

Following **Add → User**, we create a user named `info` for `xenonly.com`.

> [!tip]
> You can create as many users as you want for the existing domains. To add a new domain, see [2.2 Adding a New Domain to the Mail Server](/self-hosting/mail-server-new-domain/).

### Account for DMARC Reports

So that the reports can reach `rua=mailto:dmarc@xenonly.com` from the DMARC record, we again follow **Add → User** and create a user named `dmarc` for `xenonly.com`.

> [!note]
> For every domain, there must be a mailbox for the report address given in that domain's DMARC record.

## Test and Check

Let's go to Roundcube at <https://xenonly.com/mail> and log in as `info@xenonly.com`.

Let's send a test mail to the address shown on <https://www.mail-tester.com/>. The expected result:

```text
Your lovely total: 10/10
```
