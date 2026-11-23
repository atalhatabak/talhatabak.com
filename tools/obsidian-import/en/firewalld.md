> **Requirements**
> - [2 Mail Server Setup](/self-hosting/mail-server/), [3 NGINX Configuration](/self-hosting/nginx/) and [4 Docker Setup](/self-hosting/docker/) must be done.
>
> **Assumptions**
> - Firewalld was turned off in [1 Post-Install Configuration](/self-hosting/post-install-configuration/), and iRedMail's Firewalld configuration was not applied during the installation.
> - The outside network interface is `eth0`, and SSH runs on the default port, 22.
> - Commands are run on the server with root rights (`sudo`).

## Which Ports We'll Open

| Service | Port | Why |
| --- | --- | --- |
| ssh | 22/tcp | The default port for SSH. If SSH runs on another port, add it with `--add-port=<PORT>/tcp` |
| http / https | 80/tcp, 443/tcp | NGINX |
| smtp | 25/tcp | Mail coming from other servers |
| smtp-submission | 587/tcp | Clients sending mail (STARTTLS) |
| smtps | 465/tcp | Clients sending mail (TLS) |
| imap / imaps | 143/tcp, 993/tcp | Reading mail |

## Starting Point

Let's check the starting point:

@@code@@

The output should look like this:

@@code@@

This is the default Firewalld configuration. Firewalld is off right now; we'll keep it that way for now.

## Public Zone Configuration

Cockpit is allowed by default; we won't use it, so let's remove it. Firewalld is off, so we'll use `firewall-offline-cmd` instead of `firewall-cmd`.

@@code@@

We add the services we use:

@@code@@

`ssh` is on by default, so the warning `Warning: ALREADY_ENABLED: ssh` is normal. After it, a `success` output follows.

The services we added are `http` and `https` for NGINX, and the ones the mail service needs. I won't use POP3, so I didn't add it.

Let's check the changes:

@@code@@

The output should look like this:

@@code@@

## Rescue Timer and Start

In case something goes wrong after Firewalld is on and we can't connect over SSH, let's set up a timer that stops Firewalld after 10 minutes:

@@code@@

Then we can enable and start Firewalld:

@@code@@

When Firewalld starts, the current SSH session doesn't drop, because connections that are already open are still allowed. So let's do the test by opening **a new SSH connection from a new terminal**. If the connection works, we can cancel the timer:

@@code@@

## Docker Integration

We installed Docker before configuring Firewalld, so Docker couldn't create its own Firewalld settings (the `docker` zone and the `docker-forwarding` policy). Restarting Docker is enough for this:

@@code@@

### Check

@@code@@

@@code@@

@@code@@

@@code@@

@@code@@

@@code@@

If the outputs show the `docker` zone and the `docker-forwarding` policy, Docker's Firewalld configuration was done.

## Blocking Outgoing Port 25

Everything that goes out to the internet through the server, so the containers and the VPN clients we'll set up in [7 WireGuard Setup](/self-hosting/wireguard/), uses the same IP addresses as the mail server. The PTR record of these addresses points to `mail.xenonly.com`. If a compromised container or a device on the VPN sends spam directly out on port 25, our mail server's IP gets on a blocklist.

Mail servers talk to each other on port 25, and only Postfix on the host needs to go out on this port. The containers send their mail to our own mail server on port 587, with a login. That connection is not forwarded, it comes straight to the host, so the block doesn't affect it.

First let's see the problem. Let's try to connect from a container to Gmail's mail server on port 25:

@@code@@

@@code@@

The `open` line shows that the container can connect directly to a mail server outside on port 25.

Let's create a policy that rejects traffic that goes through the server (is forwarded) to port 25 outside:

@@code@@

> Policies are checked in order of their `priority` value; the smaller value comes first. Policies with a negative priority run before the zone rules. `-10` makes this policy run before the ACCEPT target of the `docker` zone and before the `vpn-internet` policy (`-1`) we'll create in part 7.

> We didn't change the policy's target; the default is `CONTINUE`. Traffic to ports other than 25 moves on to the next rule and works as before. We didn't set `family` in the rich rule, so the rule applies to both IPv4 and IPv6.

> We used `ANY` as the ingress zone, so the rule also applies by itself to zones added later (for example the `vpn` zone in part 7).

Let's check the policy:

@@code@@

The output should show `priority: -10`, `ingress-zones: ANY`, `egress-zones: public` and the rich rule we added.

Let's run the test again:

@@code@@

This time the `open` line should not show up; `nc` should print a connection error. The blocked attempts go to the kernel log:

@@code@@

> The `SRC=` field in the log shows the IP address of the container or VPN client that tried to go out on port 25. If there is an unexpected entry here, that container or device may be compromised.

To see that Postfix is not affected, let's send a mail to a Gmail address and look for the `status=sent` line in Postfix's log:

@@code@@
