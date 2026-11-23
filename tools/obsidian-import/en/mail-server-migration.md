> **Requirements**
> - [2 Mail Server Setup](/self-hosting/mail-server/) must be done on the new server.
> - You must have root access to the old server.
>
> **Assumptions**
> - The old server was also set up with iRedMail (MariaDB + `/var/vmail`).
> - There is no valuable data on the new server yet; the `vmail` database of the new installation can be overwritten.
> - Commands are run with root rights (`sudo`). The server each command runs on is written before it.

In this part we'll look at what has to go where when moving an existing mail service to another server, or when restoring it from a backup.

> The move must be done carefully and step by step. This document has the steps I used for my own move. Systems set up in a different way, or with different versions, may need different steps.

## Understanding Our Setup

In our system the mail data is kept in two places: in the MariaDB database and on the file system (Maildir).

- **In the database:** Domains, users, mailbox paths, aliases, forwardings and so on.
- **On the file system (`/var/vmail`):** The mail itself. The inbox, sent items and all the other folders, and the users' Sieve filters.

I set up the mail service on a new server from scratch, so there is no valuable data in the new mail service. So my plan is to move the whole `vmail` database and the `/var/vmail/vmail1` directory from the old server to the new one.

> Roundcube's own database (`roundcubemail`: address books, identities, signatures, user settings) is not part of this plan. If you want to keep this data of the users too, move the `roundcubemail` database the same way. If the Roundcube versions are different, a schema update may also be needed.

> Mail that reaches the old server during the move is not copied to the new server. To avoid this, you can stop the mail services on the old server with `sudo systemctl stop postfix dovecot` before starting, or run rsync once more after all the steps to copy the last changes.

## Moving the Old Data

### Comparing the Database Schema

Let's check whether the schemas of the old and new `vmail` databases differ because of a version difference.

*On the old server:*

@@code@@

*On the new server:*

@@code@@

> We use `--result-file` instead of redirecting the output with `> /root/...`. The redirect is done by the normal user's shell, not by `sudo`, so it can't write to the `/root` directory.

With these commands we took the database schemas. Next, let's get both files to the same place with `scp` or another way that suits you, and look at the differences:

@@code@@

In my case there was no difference, so I decided to move the whole database.

### Moving the Database

*On the old server* we take a dump of the database:

@@code@@

We copy the file `/root/vmail-old.sql` to the new server.

*On the new server* we first back up the current database:

@@code@@

Then we import the old database:

@@code@@

> An input redirect is also done in the normal user's shell, so it can't read the file under `/root`. That's why we run the command in a single root shell with `sudo sh -c`.

We can check the result with the commands below:

@@code@@

### Moving the Maildir

*On the old server* we send the Maildir to the new server with rsync:

@@code@@

> `--numeric-ids` copies file ownership by uid/gid number instead of by username. So the uid/gid of the `vmail` user must be the same on both servers; you can check it with `id vmail` on both.

> The users' Sieve filters are kept in their own mailbox directories (`~/sieve`), so they move together with `vmail1`. To see whether there is any other directory under `/var/vmail` that needs to move, run `ls /var/vmail` on the old server.

> Rsync sends the files over SSH as the root user. Because of the `PermitRootLogin no` setting from [1 Post-Install Configuration](/self-hosting/post-install-configuration/), root can't log in over SSH. Just for this job, set `PermitRootLogin prohibit-password` for a while in `/etc/ssh/sshd_config.d/00-hardening.conf` on the new server, and add the old server's root public key to `/root/.ssh/authorized_keys`. Undo both after the transfer.

> This method works while SSH is reachable from the internet. After [7.2 Putting Services Behind the VPN](/self-hosting/services-behind-vpn/), SSH is reachable only over the VPN, so the old server can't connect to the new one; in that case pull the data from the new server, as in [10.1 Moving an Old WordPress Site into This Setup](/self-hosting/wordpress-migration/).

### Moving the DKIM Keys

We also need to move the DKIM keys of the domains on the old server:

1. We copy the `/var/lib/dkim/*.pem` files on the old server to the same directory on the new server and fix their permissions (`chown amavis:amavis`, `chmod 0400`).
2. We add each domain to `/etc/amavisd/amavisd.conf` as explained in [2.2 Adding a New Domain to the Mail Server](/self-hosting/mail-server-new-domain/).

### Restarting the Services

*On the new server* let's restart the services:

@@code@@

### Recalculating the Mailbox Quotas

@@code@@

With this command we recalculate the current usage of the mailboxes.

## Final Checks

- For every domain, check that the DKIM public key on the server matches the record in DNS:

  @@code@@

- Update the DNS records of the moved domains for the new server:
  - The IP addresses in the SPF records must be the new server's IP addresses.
  - The MX records must point to the new mail server (`mail.xenonly.com`).
  - The PTR record of the new server must be set (see [2 Mail Server Setup](/self-hosting/mail-server/)).
