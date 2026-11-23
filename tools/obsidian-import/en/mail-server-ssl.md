> **Requirements**
> - [2 Mail Server Setup](/self-hosting/mail-server/) must be done.
>
> **Assumptions**
> - The `A` and `AAAA` records of `mail.xenonly.com` point to the server.
> - Port 80 (HTTP) of the server is reachable from the internet (Firewalld is still off).
> - Commands are run on the server with root rights (`sudo`).

We finished setting up the mail server. Right now the system uses the self-signed certificate created during the iRedMail installation. Instead, we'll get a Let's Encrypt certificate for `mail.xenonly.com` and make the system use it.

## Getting a Certificate from Let's Encrypt

`certbot` was installed in [1 Post-Install Configuration](/self-hosting/post-install-configuration/). We'll get the certificate with the `webroot` method. For this method, the domain's `A` record must point to the server and the server must listen on port 80 (HTTP).

NGINX was installed during the iRedMail installation and is already configured for the Let's Encrypt (ACME) check:

@@code@@

To get the certificate, running the command below is enough.

> On the first run it asks for an email address and for accepting the terms of service.

@@code@@

@@code@@

The self-signed certificates iRedMail uses are at these paths:

@@code@@

Let's back up the old certificates:

@@code@@

Then let's create symbolic links for the new certificate with the commands below:

@@code@@

and restart the related services:

@@code@@

## Certificate Renewal

Let's Encrypt certificates are valid for 90 days. The certbot package comes with a systemd timer for renewal (`certbot-renew.timer`). Let's make sure the timer is enabled:

@@code@@

We'll also create a hook that reloads the services when the certificate is renewed. Let's create the file `/etc/letsencrypt/renewal-hooks/deploy/reload-mail.sh` with the content below:

@@code@@

> The hooks under `renewal-hooks/deploy/` run for **every renewed certificate**, not only for the mail certificate. This is useful for us: when the other certificates we'll get in the next parts (for example `iredadmin.xenonly.com`) are renewed, this hook also reloads NGINX. If you want Postfix and Dovecot to reload only when the mail certificate is renewed, you can check the `$RENEWED_DOMAINS` variable that certbot passes to the hook.

Let's make the hook executable:

@@code@@

Let's test that the renewal and the hook work:

@@code@@

> `--dry-run` doesn't run the deploy hooks, so we test the hook by running it by hand.
