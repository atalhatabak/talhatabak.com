---
title: "Mail Server: Extra Settings"
linkTitle: "Extra Settings"
description: "Adding an alias, auto-completing the username in Roundcube, cleaning up the passwords the installer left in plain text and limiting how much mail an account can send."
date: 2026-11-21T00:07:00+03:00
chapter: "2.5"
tags: ["mail", "iredmail", "roundcube"]
---
> [!abstract] Requirements
> - [2 Mail Server Setup](/self-hosting/mail-server/) must be done.
>
> **Assumptions**
> - The example alias forwards `abuse@xenonly.com` to the `info@xenonly.com` account.
> - Commands are run on the server with root rights (`sudo`).

In this part we'll make a few settings that the mail server doesn't need, but that are useful.

## Setting Up an Alias

An alias is an address that has no mailbox of its own and forwards incoming mail to one or more accounts. For example, we want mail sent to `abuse@xenonly.com` to land in the `info@xenonly.com` account.

> [!note]
> The open-source version of [iRedAdmin](term:iredadmin) has no alias management (the **Add → Alias** menu is only in iRedAdmin-Pro). So we'll add the alias directly to the `vmail` database.

Let's connect to the `vmail` database in the MariaDB on the host:

```bash
sudo mariadb vmail
```

Let's add the alias and the account it forwards to:

```sql
INSERT INTO alias (address, domain, active)
VALUES ('abuse@xenonly.com', 'xenonly.com', 1);

INSERT INTO forwardings (address, forwarding, domain, dest_domain, is_list, active)
VALUES ('abuse@xenonly.com', 'info@xenonly.com', 'xenonly.com', 'xenonly.com', 1, 1);

exit
```

- **`alias` table:** The alias address itself.
- **`forwardings` table:** The address the alias's mail goes to. To forward to more than one account, add a separate row for each account.
- **`is_list = 1`:** Marks this row as an alias membership.

> [!note]
> [Postfix](term:postfix) looks up the addresses in the database, so there is no need to restart any service.

Let's send a test mail to `abuse@xenonly.com`; it should land in the `info@xenonly.com` account.

## Auto-Completing the Roundcube Username

To log in to [Roundcube](term:roundcube), you have to type the full email address as the username. So that typing only `info` is completed to `info@xenonly.com`, let's add the line below to the end of `/opt/www/roundcubemail/config/config.inc.php`:

```php {title="/opt/www/roundcubemail/config/config.inc.php"}
$config['username_domain'] = 'xenonly.com';
```

> [!note]
> This setting is only for the Roundcube login screen. Users of another domain (for example `info@example.com`) still type the full address. In [IMAP](term:imap) clients, the username is always the full address too (see [2.3 Using a Mail Client](/self-hosting/mail-clients/)).

PHP reads the configuration on every request, so there is no need to restart any service.

## Checking for Plain Text Passwords

In the setup wizard we enter two passwords: the **MariaDB root password** and the **postmaster password**. On top of these, [iRedMail](term:iredmail) creates its own random passwords for the database users of the services. The install script writes all of these passwords in plain text to a few places.

In this section we'll look at which password is kept where, which service really uses it, and how to get rid of the plain text copies.

### Where the Passwords Are Kept

| Place | Content | Does a service use it? |
| --- | --- | --- |
| `/opt/iRedMail-1.8.8/iRedMail.tips` | All passwords | No, it is only for information |
| `/opt/iRedMail-1.8.8/config` | The wizard's answers and all passwords | No. The install script reads it so it doesn't ask the questions again if it runs again in the same directory; after the installation it is not needed |
| The **Details of this iRedMail installation** mail in the postmaster mailbox | The content of `iRedMail.tips` | No |
| `/root/.iredmail/kv/` | A separate file for each password | No, no part of iRedMail reads this directory |
| `/root/.my.cnf` | Only the MariaDB root password | **Yes**, see below |
| `/root/.my.cnf-<user>` | The passwords of the service database users | No, it is there so root can connect as these users easily |
| The configuration files of the services (`/etc/postfix/mysql/`, Roundcube, iRedAdmin, [Amavis](term:amavis), [iRedAPD](term:iredapd) and so on) | Only that service's own database password | **Yes**, the services read the password from these files |

### Which Password Is Used Where

**Postmaster password:** Used only for logging in (Roundcube, iRedAdmin, IMAP/[SMTP](term:smtp)). It is stored as a [hash](term:hash) in the database; no service needs it in plain text. The plain text copies:

- `iRedMail.tips`
- `config`
- `/root/.iredmail/kv/first_domain_admin_password`
- The installation mail

**MariaDB root password:** No mail service uses this password; every service has its own database user. Only these use it, through `/root/.my.cnf`:

- The `mariadb` and `mariadb-dump` commands run with root rights (for example the `sudo mariadb` commands in this part and in [2.4 Moving the Mail Server](/self-hosting/mail-server-migration/))
- The database backup script that runs every night at 03:30 (`/var/vmail/backup/backup_mysql.sh`)

The plain text copies: `iRedMail.tips`, `config`, `/root/.iredmail/kv/sql_user_root`, the installation mail and `/root/.my.cnf`.

**Service passwords:** The passwords of the `vmail`, `vmailadmin`, `roundcube`, `amavisd`, `iredadmin`, `iredapd` and `fail2ban` database users, Roundcube's encryption key (`roundcube_des_key`) and iRedAPD's SRS key (`iredapd_srs_secret`). They are all random and used in the services' own configuration files; we don't touch them.

> [!note]
> The wizard asks for the MariaDB root password and the postmaster password separately and suggests a random sample password for both. If the same password was entered for both, you'll see the postmaster password in `/root/.my.cnf`, but the password in that file is the MariaDB root password.

### Cleaning Up

#### 1. Deleting the Copies Kept for Information

If needed, after saving the passwords in a password manager (for example [9 Vaultwarden Setup](/self-hosting/vaultwarden/)), let's delete the files in the installation directory:

```bash
sudo rm /opt/iRedMail-1.8.8/iRedMail.tips /opt/iRedMail-1.8.8/config
sudo chmod 700 /opt/iRedMail-1.8.8
sudo rm /opt/1.8.8.tar.gz
```

Let's delete the copies of the two passwords we typed in from the `/root/.iredmail/kv/` directory:

```bash
sudo rm /root/.iredmail/kv/first_domain_admin_password /root/.iredmail/kv/sql_user_root
```

> [!note]
> The files left in the directory are the random service passwords. They are not used anywhere else and only root can read them, so we keep them; if you ever need a service's database password, you can look it up here.

Let's log in to Roundcube as `postmaster@xenonly.com`, delete the mail with the subject **Details of this iRedMail installation** and empty the trash. Let's check that the mail is completely gone from the server:

```bash
sudo find /var/vmail -name 'details.eml*'   # output should be empty
```

#### 2. Changing the MariaDB Root Password

If the MariaDB root password was not random (for example if it is the same as the postmaster password, or a password we also use somewhere else), it should be changed. Only `/root/.my.cnf` uses this password, so it is enough to create a new random password and update it in the database and in this file.

First let's see which hosts the root user is defined for:

```bash
sudo mariadb -e "SELECT user, host FROM mysql.user WHERE user='root';"
```

The output should have only the `root | localhost` row. If there are other rows, repeat the `SET PASSWORD` command below for each of them.

```bash
PW=$(openssl rand -hex 24)
sudo mariadb -e "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('$PW');"
sudo sed -i "s/^password=.*/password=\"$PW\"/" /root/.my.cnf
unset PW
```

- The command history gets `$PW`, not the password itself, so the new password doesn't show up in the history.
- The order matters: the second command connects with the old password (through `/root/.my.cnf`) and changes the password, the third command updates the file with the new password.

> [!note]
> We don't need to write the new password down anywhere. The root user connects to MariaDB through `/root/.my.cnf`; if you ever need the password, you can look at it with `sudo cat /root/.my.cnf`.

Let's check that root can still connect and that the backup script works:

```bash
sudo mariadb -e "SELECT CURRENT_USER();"     # root@localhost
sudo bash /var/vmail/backup/backup_mysql.sh  # should take a backup without errors
```

The backups are written to the `/var/vmail/backup/mysql/<year>/<month>/<day>/` directory.

## Sending Limit (Throttle)

Every account that can log in to SMTP can send as much mail as it wants from its own address. An account with a stolen password, or a service account in a compromised [container](term:container), can send thousands of spam mails in a short time. All domains send from the same IP, so the damage doesn't stay with that account: the IP gets on [blocklists](term:dnsbl) and the mail of every domain starts to be rejected.

The `throttle` plugin of iRedAPD, which comes with iRedMail, limits how many mails an account can send in a given time. In this section we'll set a default limit for all accounts.

> [!note]
> The open-source version of iRedAdmin has no throttle settings; they are only in iRedAdmin-Pro. So we'll add the settings directly to the `iredapd` database.

### 1. First Checks

Let's check that the throttle plugin is on:

```bash
sudo grep '^plugins' /opt/iredapd/settings.py
```

`throttle` should be in the list. If it is not, add it to the list and restart iRedAPD (`sudo systemctl restart iredapd`).

The plugin counts sent mail after the whole mail has been received (at the END-OF-MESSAGE stage). For this, Postfix must also ask iRedAPD at this stage:

```bash
sudo postconf smtpd_end_of_data_restrictions   # check_policy_service ... 127.0.0.1 ... 7777
sudo postconf -P | grep -E '^(submission|smtps)/.*end_of_data'   # output should be empty
```

- **The first command:** The output should show iRedAPD's address (`127.0.0.1`, port `7777`). If it is empty, the limit doesn't apply to any mail.
- **The second command:** Checks whether the 587 (`submission`) or 465 (`smtps`) service in `master.cf` overrides this setting. If it does, the limit doesn't apply to mail sent by clients.

Let's look at the current throttle settings:

```bash
sudo mariadb iredapd -e "SELECT * FROM throttle;"
```

On a clean installation the table is empty. That means no account has a limit.

### 2. Adding the Default Limit

Let's connect to the `iredapd` database in the MariaDB on the host:

```bash
sudo mariadb iredapd
```

Let's add a limit of 300 mails a day for all accounts:

```sql
INSERT INTO throttle (account, kind, priority, period, max_msgs)
VALUES ('@.', 'outbound', 0, 86400, 300);

exit
```

- **`account = '@.'`:** All accounts. The dot at the end is needed. The limit applies to each account separately; mail sent by one account doesn't count against the limit of the others.
- **`kind = 'outbound'`:** Mail sent after logging in ([SASL](term:sasl)). Clients like Thunderbird, Roundcube and the containers all log in on port 587 or 465 to send, so this covers all of them.
- **`period = 86400`:** The time window in seconds (1 day). It starts with the account's first mail; when it ends, the counter resets.
- **`max_msgs = 300`:** How many mails can be sent in this time. It counts per recipient: a mail with 10 recipients counts as 10 mails.
- **`priority = 0`:** If more than one setting matches an account, the one with the higher priority wins. We'll add account-specific settings with `100`.
- **The columns we didn't add (`msg_size`, `max_quota`, `max_rcpts`):** They stay at `-1`. `-1` means the value is taken from a setting with a lower priority. There is no setting with a lower priority, so these limits don't apply. The mail size is already limited by Postfix's `message_size_limit` setting.

> [!note]
> Mail to addresses in the same domain is not counted (`THROTTLE_BYPASS_SAME_DOMAIN`, `True` by default). For example, a mail from `info@xenonly.com` to `abuse@xenonly.com` doesn't count against the limit. Spam is sent to the outside, so this doesn't open a hole.

iRedAPD reads the settings from the database for every mail, so there is no need to restart the service.

> [!note]
> 300 is a value picked for personal use. With this limit, an account with a stolen password can send mail to at most 300 recipients a day. Even if nobody notices the account, the chance of the IP getting on a blocklist becomes very low. Accounts that need to send more can get a separate limit as below.

### 3. A Limit for One Account

Service accounts (for example `vaultwarden@xenonly.com` from [9 Vaultwarden Setup](/self-hosting/vaultwarden/)) send a few mails a day. Let's give them a lower limit:

```sql
INSERT INTO throttle (account, kind, priority, period, max_msgs)
VALUES ('vaultwarden@xenonly.com', 'outbound', 100, 86400, 50);
```

Because of `priority = 100`, this setting is used for this account instead of the default one. In the same way, an account that needs to send more can get a higher limit. To remove an account's limit completely, set `max_msgs = 0`.

To change an existing limit:

```sql
UPDATE throttle SET max_msgs = 100
WHERE account = 'vaultwarden@xenonly.com' AND kind = 'outbound';
```

To reset the counter of an account that hit its limit before the time is up:

```bash
sudo mariadb iredapd -e "DELETE FROM throttle_tracking WHERE account = 'info@xenonly.com';"
```

### 4. Test

Let's test that the limit works with a low limit. Let's add a temporary limit of 2 mails an hour for `info@xenonly.com`:

```bash
sudo mariadb iredapd -e "INSERT INTO throttle (account, kind, priority, period, max_msgs) VALUES ('info@xenonly.com', 'outbound', 100, 3600, 2);"
```

From Roundcube, as `info@xenonly.com`, let's send three mails one by one to an address **in another domain** (for example our personal Gmail address). The first two mails should go out, and Roundcube should show an error on the third.

> [!important]
> The test must go to another domain. Mail to addresses in the same domain is not counted, so mail sent to `xenonly.com` addresses doesn't fill the limit.

We can see the rejected mail in the iRedAPD log and in the account's counter:

```bash
sudo grep -i exceeded /var/log/iredapd/iredapd.log | tail -n 3
sudo mariadb iredapd -e "SELECT account, cur_msgs, FROM_UNIXTIME(init_time) FROM throttle_tracking;"
```

After the test, let's delete the temporary limit and its counter:

```bash
sudo mariadb iredapd -e "
DELETE FROM throttle_tracking WHERE tid = (SELECT id FROM throttle WHERE account = 'info@xenonly.com' AND kind = 'outbound');
DELETE FROM throttle WHERE account = 'info@xenonly.com' AND kind = 'outbound';"
```

> [!note]
> The counter table (`throttle_tracking`) is tied to the settings table with a [foreign key](term:foreign-key). If the counter is not deleted first, the setting can't be deleted.
