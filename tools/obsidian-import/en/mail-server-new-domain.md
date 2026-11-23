> **Requirements**
> - [2 Mail Server Setup](/self-hosting/mail-server/) must be done.
>
> **Assumptions**
> - The main mail server is `mail.xenonly.com`; the example domain we add is `example.com`.
> - You can edit the DNS records of `example.com`. The mail records it needs are explained in this part.
> - iRedAdmin is reached at `https://xenonly.com/iredadmin` before [3 NGINX Configuration](/self-hosting/nginx/), and at `https://iredadmin.xenonly.com` after it (only over the VPN after [7.2 Putting Services Behind the VPN](/self-hosting/services-behind-vpn/)).
> - Commands are run on the server with root rights (`sudo`).

In the current setup, `mail.xenonly.com` is the name of this server's mail server, and `xenonly.com` is the first domain the server sends and receives mail for. The settings behind this fall into two groups.

**Server identity** (`mail.xenonly.com`, shared by all domains):

- `A` and `AAAA` records
- `Reverse DNS (PTR)` record for IPv4 and IPv6

**Domain identity** (`xenonly.com`, separate for each domain):

- `MX` record
- `SPF` record
- `DKIM` record
- `DMARC` record

> Giving each domain its own mail server identity (its own server name, PTR record and IPv4 address) needs extra IP addresses and extra configuration on a single VPS. Unless there is a special reason for it, it is not worth it.

In our design the main mail server is `mail.xenonly.com`. The domains added later also use this server to send and receive mail. For each of them, only their own MX, SPF, DKIM and DMARC records are set.

## What to Do for Each Domain

1. Adding the domain to the server in iRedAdmin
2. Creating the DKIM key on the server and adding it to the Amavis configuration and to DNS
3. Adding the MX record
4. Adding the SPF record
5. Adding the DMARC record and creating the report account

## Steps

### 1. Adding the Domain to the Server in iRedAdmin

We log in to the iRedAdmin panel and add the domain `example.com` by following **Add → Domain**.

Then, following **Add → User**, we create at least one user for `example.com` (for example `info@example.com`). We'll use this account at the end to send a test mail.

### 2. Creating the DKIM Key on the Server and Adding It to the Amavis Configuration and to DNS

#### Creating the DKIM Key

Let's create the DKIM key with the commands below:

@@code@@

#### Editing the Amavis Configuration

We open `/etc/amavisd/amavisd.conf`:

- Under `# Add dkim_key here`, we add our new key in the format shown there. The key of the primary domain was added automatically during the installation.
- We comment out the `catch-all` part under `@dkim_signature_options_bysender_maps`.
- Under `Per-domain dkim key`, we add our domains in the format shown there.

> The `catch-all` entry signs the mail of all domains with the key of the first domain. Then mail from `example.com` is signed with `d=xenonly.com` and fails the `adkim=s` (strict matching) check in DMARC. That's why we define each domain with its own key.

The file should look roughly like this:

@@code@@

After editing, let's restart the service:

@@code@@

#### Adding the DKIM Key to DNS

To see the existing keys:

@@code@@

To get a single-line output that can go straight into the DNS record:

@@code@@

> The value added to DNS must be a single line. `amavisd showkeys` splits the key over several lines; the command above joins them.

We add this output to the DNS of `example.com` like this:

| Name | Type | Content | What It Means |
| --- | --- | --- | --- |
| dkim._domainkey | TXT | `<DKIM_KEY>` | Lets receivers verify the mail signed by Amavis |

After the DNS record has spread, let's check that the key on the server matches the record in DNS. The output should show `=> pass`:

@@code@@

### 3. Adding the MX Record

In the panel of the provider that manages the DNS of `example.com`, let's add the `MX` record below:

| Name | Type | Content |
| --- | --- | --- |
| example.com | MX | `mail.xenonly.com` |

### 4. Adding the SPF Record

In the same panel, let's add the `SPF` record below:

| Name | Type | Content |
| --- | --- | --- |
| example.com | TXT | `"v=spf1 mx a ip4:<SERVER_IPV4> ip6:<SERVER_IPV6> ~all"` |

> The `a` mechanism also allows the server in the `A` record of `example.com` to send mail. If the website of `example.com` is on another server, that server gets the permission too; in that case you can remove `a` from the record.

### 5. Adding the DMARC Record and Creating the Report Account

In the same panel, let's add the `DMARC` record below:

| Name | Type | Content |
| --- | --- | --- |
| _dmarc | TXT | `"v=DMARC1; p=quarantine; sp=quarantine; np=reject; adkim=s; aspf=s; rua=mailto:dmarc@example.com"` |

So that the reports can reach `dmarc@example.com` from the DMARC record, we create the user `dmarc` for `example.com` in iRedAdmin by following **Add → User**.

## Check

### Example DNS Records for `example.com`

The DNS records should look roughly like this:

| Name | Type | Content | What It Means |
| --- | --- | --- | --- |
| example.com | MX | `mail.xenonly.com` | Says which mail server incoming mail should go to |
| dkim._domainkey | TXT | `<DKIM_KEY>` | Lets receivers verify the mail signed by Amavis |
| _dmarc | TXT | `"v=DMARC1; p=quarantine; sp=quarantine; np=reject; adkim=s; aspf=s; rua=mailto:dmarc@example.com"` | Says what to do with mail that fails the SPF or DKIM check |
| example.com | TXT | `"v=spf1 mx a ip4:<SERVER_IPV4> ip6:<SERVER_IPV6> ~all"` | Says which servers may send mail for this domain |

### Checking SPF, DKIM and DMARC with a Test Mail

Let's log in to Roundcube as `info@example.com` and send a test mail to the address shown on <https://www.mail-tester.com/>. The expected result:

@@code@@
