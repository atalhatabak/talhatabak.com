> **Requirements**
> - The MariaDB container from [10 WordPress Setup](/self-hosting/wordpress/) must be set up and the `db` network created.
> - [4.1 A Ready Template for Docker Containers](/self-hosting/docker-template/) must be done (`proxy.tmpl` and `websocket.conf`).
>
> **Assumptions**
> - The old server runs WordPress with MariaDB as the database. The example site is `example.com`, and the site directory on the old server is `/var/www/example`.
> - Our user on the new server can connect to the old server over SSH (its SSH key is allowed on the old server).
> - The moved site uses port `8031` (pick a free port from the `8030`–`8049` range set aside for WordPress).
> - The server each command runs on is written before it. On the new server, commands that need root rights are written with `sudo`.

We'll move WordPress sites running on an old server to the new server, fitting them into the setup from [10 WordPress Setup](/self-hosting/wordpress/).

## What We Need

We'll take two things from the old server:

1. **Database dump:** The `.sql` file of the site's database. Posts, pages, users, comments and all the settings are in it.
2. **Site files:** The whole WordPress directory. `wp-config.php`, `wp-content` (themes, plugins, uploaded images) and `.htaccess`, if there is one, are in this directory.

On the new server the files will be laid out like this:

@@code@@

> We keep the dump file outside the `html` directory. `html` is the site's root directory; any file put in it can be downloaded from the internet. The dump has user details and password hashes in it.

## Steps

1. Taking the database dump and the site files from the old server
2. Creating a database and a user for the site in MariaDB and importing the dump
3. Editing `wp-config.php` for the new setup and starting the container
4. Testing the site before changing DNS
5. Pointing DNS to the new server and setting up the certificate and NGINX

## Preparation

*On the old server*, let's get the site's database details, the table prefix and the site address, if it is fixed, from `wp-config.php`:

@@code@@

Let's look at the PHP and MariaDB versions:

@@code@@

> We'll use PHP 8.4 in the container. If the old server uses PHP 7.x, old themes and plugins may give errors. In that case you can use the `php8.3-apache` image for a while (it is supported until December 2027), but the real fix is to update the plugins.

> No new content (posts, comments, orders) should be created on the old site during the move. Anything added after the dump won't reach the new server.

## Taking the Data from the Old Server

*On the old server*, let's take the database dump:

@@code@@

- **`umask 077`:** So the dump file is created readable only by us. It runs in the subshell inside the parentheses, so it doesn't affect the rest of the session.
- **`--single-transaction`:** Takes a consistent dump while the site is running, without locking the tables.
- **We don't use `--databases`:** This option adds `CREATE DATABASE` and `USE` lines with the old database's name to the dump. On import, the tables would go to a new database with the old name instead of `wp_example`.

> On MariaDB versions older than 10.4, the command is called `mysqldump`.

*On the new server*, let's create the site directory and pull the files.

The new server's SSH is reachable only over the VPN, so the old server can't connect to the new server. That's why we connect from the new server to the old one and pull the data:

@@code@@

> To pull the files with our normal user's SSH key, we give the directory to our own user for a while. We'll fix the ownership below.

- `rsync` must be installed on the old server too.
- The `/` at the end of the source directory matters; it copies the contents of the directory into `html`, not the directory itself.
- `<USER>` must be able to read all the site files. If it can't, and you have sudo rights on the old server, you can add `--rsync-path="sudo rsync"` to the `rsync` command.
- If the old server's SSH port is different, use `rsync -e 'ssh -p <PORT>'` and `scp -P <PORT>`.
- If a cache plugin is used, there is no need to move the cache directory: `--exclude 'wp-content/cache/'`

## Database and User

*On the new server*, let's create a database password for the site:

@@code@@

> We'll use the password from the output wherever `<DB_PASSWORD>` is written below.

Let's connect to MariaDB:

@@code@@

and create the site's database and user:

@@code@@

> The tables in the dump are created with their own character set and collation; the database default only applies to tables created later.

## Importing the Database

@@code@@

> We use `-i` instead of `-it`. We redirect the dump file to the container's input, so no terminal (`-t`) should be opened.

Let's check that the tables are there:

@@code@@

The tables should be listed with the old site's table prefix (`wp_` or a different prefix).

## Files and wp-config.php

Let's fix the ownership of the files:

@@code@@

> In the container, Apache runs as the `www-data` user (UID 33). For things like updating plugins and uploading images, it must own the files. We also give the site directory back to root.

Let's open `/opt/docker/wp-example/html/wp-config.php` and change the database details for the new setup:

@@code@@

> We don't touch the `$table_prefix` value; the tables in the dump were created with this prefix.

In the same file, let's add the lines below above the line `/* That's all, stop editing! */`:

@@code@@

> In a new installation, the `wp-config.php` the image creates already has this. The moved site has its own `wp-config.php`, so the image doesn't touch it, and we need to add it by hand. Without it, WordPress thinks the request from NGINX is HTTP and keeps redirecting to HTTPS; the browser shows a "too many redirects" error.

Some plugins (cache, security and WAF plugins) write the old server's directory path into files. Let's find the files that contain the old path:

@@code@@

> Inside the container the new path is `/var/www/html`. Fix the path in the files you find, or reset the settings of that plugin.

Let's check whether `.htaccess` has lines that run PHP in a different way:

@@code@@

> `AddHandler` / `SetHandler` lines specific to the old server or hosting panel stop PHP from running in the Apache in the container. Then the `.php` files may be served as plain text instead of being run, and the passwords in `wp-config.php` get exposed. If there are such lines, delete them.

> If the old server used PHP-FPM, the PHP settings in the `.user.ini` file are not read in the container. Move the needed settings to the `php.ini` file.

## PHP Settings and Compose

Let's create the file `/opt/docker/wp-example/php.ini` with the content below:

@@code@@

Let's create `/opt/docker/wp-example/compose.yaml` like this:

@@code@@

> The difference from a new installation is that there is no `environment` section. The database details are in `wp-config.php`, and there is no need for a `.env` file either.

> The `html` directory is not empty, so the image doesn't copy WordPress and doesn't touch the existing `wp-config.php`.

Let's start the container:

@@code@@

## Testing Before Changing DNS

While DNS still points to the old server, we can test the site from inside the server. Let's send a request straight to the container, sending the headers NGINX would send ourselves:

@@code@@

- If you get `HTTP/1.1 200 OK` and the site's title, the database connection and `wp-config.php` are correct.
- If you get `Error establishing a database connection` or a `500` error, check the database details in `wp-config.php` and the output of `sudo docker logs wp-example`.
- If you keep getting a `301` to `https://example.com/`, the HTTPS lines were not added to `wp-config.php`.
- If the site address is set with `www` (`https://www.example.com`), use `www.example.com` in the `Host` header; otherwise a redirect to the `www` address is normal.

## DNS, Certificate and NGINX

We get the certificate with the webroot method, so Let's Encrypt must reach the new server when it checks the domain. That's why we change DNS first.

In DNS, let's change the `A` and `AAAA` records of `example.com` and `www.example.com` to the new server's addresses. When `dig +short example.com` returns the new IP address, let's get the certificate:

@@code@@

> If the TTL of the DNS record is high, the change can take a long time to spread. Lowering the TTL to a small value (for example 300) a day before the move makes this shorter.

Let's create `/etc/nginx/vhost.d/vhost_example.com.conf` like this:

@@code@@

> The site is already installed, so there is no setup wizard step and no `vpn-only` line. The lines are explained in the **Certificate and NGINX Reverse Proxy** section of [10 WordPress Setup](/self-hosting/wordpress/).

Let's test the NGINX configuration and reload it:

@@code@@

> Until the DNS change has spread, some visitors keep going to the old server; let's not shut down the old site for a few days.

## If the Domain or Address Changed

If the site ran with `http://` on the old server, or if the domain changed, we need to change the addresses in the database.

We don't use `sed` on the dump file for this. WordPress stores some settings serialized, so together with the character count of the text. When `sed` changes the length of the address, this data breaks. WP-CLI fixes the character counts while it replaces.

@@code@@

- **`--dry-run`:** Shows how many records would change, without changing anything. If the result makes sense, run it again without `--dry-run`.
- **`--volumes-from` and `--network container:`:** The WP-CLI container uses the site's files and network; it connects to MariaDB with the details in `wp-config.php`.
- **`--user 33:33`:** The WP-CLI image is based on Alpine, and its default user has a different UID (82). It should reach the files with the same user as the site container.
- **`--skip-columns=guid`:** The `guid` of the posts is used as a permanent ID; we don't change it, so RSS readers don't think the old posts are new.

> If `WP_HOME` or `WP_SITEURL` is defined in `wp-config.php` (the `grep` output in the Preparation section), the site address comes from these lines, not from the database; update them too.

Let's check the site address:

@@code@@

> On sites installed from scratch, like in [10 WordPress Setup](/self-hosting/wordpress/), `wp-config.php` reads the database details from the environment variables. On those sites, give WP-CLI the same variables (`-e WORDPRESS_DB_HOST=mariadb -e WORDPRESS_DB_NAME=... -e WORDPRESS_DB_USER=... -e WORDPRESS_DB_PASSWORD=...`).

## Final Checks

- Do the home page, the post pages and the images open?
- If the post pages give 404: **Settings → Permalinks → Save Changes**. WordPress writes the `.htaccess` file again. If the old server used NGINX, there is no `.htaccess` file and this step is needed.
- On the **Settings → General** page, the WordPress Address and Site Address must be `https://example.com`.
- The **Tools → Site Health** page should show no critical problems.
- If there is a cache plugin, let's clear the cache.
- Do the contact form and password reset mails go out? If not, look at the **Sending Mail** section of [10 WordPress Setup](/self-hosting/wordpress/). If an SMTP plugin on the old site is set up for the old mail server, update its settings.

Let's delete the dump files; they have user details and password hashes in them.

*On the new server:*

@@code@@

*On the old server:*

@@code@@
