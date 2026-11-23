---
title: "Mail Server: Using a Mail Client"
linkTitle: "Using a Mail Client"
description: "Connecting to the mail accounts with any mail client that supports IMAP, like Thunderbird."
date: 2026-11-21T00:05:00+03:00
chapter: "2.3"
tags: ["mail", "imap"]
---
> [!abstract] Requirements
> - [2 Mail Server Setup](/self-hosting/mail-server/) and [2.1 Setting Up SSL for the Mail Server](/self-hosting/mail-server-ssl/) must be done.
>
> **Assumptions**
> - The mail server's name is `mail.xenonly.com` and the example user is `info@xenonly.com`.
> - The settings in this part are made in the mail client on a personal computer or phone, not on the server.

Our mail server is installed and working. We can log in with the users we created through [Roundcube](term:roundcube) Webmail: at `https://xenonly.com/mail` before [3 NGINX Configuration](/self-hosting/nginx/), and at `https://mail.xenonly.com` after it.

We can also connect to the mail accounts with any mail client that supports [IMAP](term:imap), like Thunderbird, Outlook, iOS Mail or Thunderbird for Android.

## Connection Details

> [!note]
> Whatever domain is used, the server address is always `mail.xenonly.com`.

| | Server | Port | Security | Authentication |
| --- | --- | --- | --- | --- |
| **Incoming (IMAP)** | `mail.xenonly.com` | 993 | SSL/[TLS](term:tls) | Normal password |
| **Outgoing ([SMTP](term:smtp))** | `mail.xenonly.com` | 587 | [STARTTLS](term:starttls) | Normal password |

- **Username:** The full email address (for example `info@xenonly.com`). If you write only `info`, the login fails.
- **Password:** The account's password.

> [!note]
> We use IMAP because the POP3 ports are not opened in the firewall ([5 Firewalld Configuration](/self-hosting/firewalld/)). With IMAP the mail stays on the server and looks the same on every device.

### Adding an Account in Thunderbird

1. We go to **Account Settings → Account Actions → Add Mail Account**.
2. We enter the name, email address and password, and click **Continue**.
3. Thunderbird tries to find the settings by itself. If it can't, or if the settings it finds don't match the table above, we click **Configure manually** and enter the details as in the table.
4. We click **Re-test**, then **Done**.

### Common Problems

- **Certificate warning:** A name other than `mail.xenonly.com` (for example `mail.example.com`) may have been entered as the server address. The certificate is valid only for `mail.xenonly.com`.
- **Authentication error:** Make sure the full email address is entered as the username.
- **Mail can't be sent:** Port 25 may have been chosen for the outgoing server. That port is for server-to-server traffic; clients should use 587.
