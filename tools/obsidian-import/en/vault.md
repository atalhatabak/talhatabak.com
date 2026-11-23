> **Requirements**
> - [3 NGINX Configuration](/self-hosting/nginx/) and [7.2 Putting Services Behind the VPN](/self-hosting/services-behind-vpn/) must be done (the `vpn-only` template is used).
>
> **Assumptions**
> - Vault is reached at `vault.xenonly.com`, only over the VPN. `A` and `AAAA` records exist for this domain.
> - The install commands are run on the server with root rights (`sudo`). The `vault` CLI commands are run on the server as the normal user.

## What It Is

Vault is a service that keeps secrets (passwords, API keys, certificates, tokens) in one central, encrypted place, controls who can reach what, and records every access. It is not just an "encrypted safe"; it can create many secrets itself and revoke them itself when they expire.

## Installation

Let's add the HashiCorp repository and install Vault with the commands below:

@@code@@

### Storage Method

We'll edit the configuration before starting the service. Vault has two options for storing data:

- **File:** The default after installation. Vault writes its data as encrypted files straight to a directory on disk (`/opt/vault/data`). The simplest method to set up and configure. It works only on a single server and doesn't support high availability (HA).
- **Raft (Integrated Storage):** The distributed storage that comes built into Vault. The data is again kept encrypted on disk. You can build a cluster with several servers, and it gives HA. You can take a backup with `vault operator raft snapshot save` while Vault is running. It needs a bit more configuration (`api_addr`, `cluster_addr`, port 8201). If the server address changes, you may need to recover it by hand.

This setup is for a single server and personal use, so I'll install it with the `File` method.

### Configuration

In `/etc/vault.d/vault.hcl`, let's comment out the `HTTPS listener` section and uncomment the `HTTP listener` section. That part should look like this:

@@code@@

> Vault listens only on `127.0.0.1` and will be opened to the outside through NGINX. NGINX provides HTTPS, so inside the server Vault doesn't need to use HTTPS too.

> The `x_forwarded_for_*` settings let Vault take the client's real IP address from the `X-Forwarded-For` header NGINX sends; the audit logs show the client's address instead of NGINX's.

Let's fix the directory ownership and the permissions of the configuration file:

@@code@@

Let's enable and start the service:

@@code@@

To use Vault from the CLI, let's set Vault's address in our normal user's shell:

@@code@@

## Initialize and Unseal

@@code@@

- **`-key-shares`:** The number of unseal keys to create.
- **`-key-threshold`:** The number of unseal keys needed to open Vault.

> This is for personal use, so I chose 1 and 1, but in production values like 5 and 3 make more sense.

**The output of this command has the unseal key and the root token, and it is shown only once. Keep the unseal key and the root token somewhere safe, outside the server.**

> When the system or the service restarts, Vault starts sealed (locked), and we need to unseal it by hand by entering the keys with `vault operator unseal`. There are ways to automate this, but that makes sealing pointless. So I'll do this by hand when needed and try not to make the services that run all the time depend on Vault.

We can open Vault by entering the unseal key with the command below:

@@code@@

## NGINX Reverse Proxy

Vault is not open to the outside right now; to reach it we'll use NGINX.

Let's get the certificate:

@@code@@

Let's create `/etc/nginx/vhost.d/vhost_vault.xenonly.com.conf` like this:

@@code@@

Let's test the NGINX configuration and reload it:

@@code@@

The Vault UI can now be used at `https://vault.xenonly.com`.

> Because the `vpn-only` template is used, Vault can be reached only with a VPN connection. To reach it with a split tunnel, add the entry `10.8.0.1 vault.xenonly.com` to the `hosts` file on your personal computer (see [7.3 Possible Problems](/self-hosting/wireguard-troubleshooting/)).

## Using the CLI from the Desktop

We need to install Vault on our personal computer, in a version close to the one on the server. Then adding the line below to the configuration of the shell we use (bash, zsh, fish) is enough:

@@code@@

## First Configuration After the Installation

We unseal Vault and log in with the `vault login` command, entering the root token.

### Secrets Engine

Let's list the current secrets engines:

@@code@@

@@code@@

If the list has no engine of type `kv`, let's mount a secrets engine of type `kv-v2` with the command below:

@@code@@

- **`kv-v2`:** A secrets engine that keeps key-value data. The data is permanent; it stays there until it is deleted.
- **`cubbyhole`:** The private area of each token. When the token expires, this area is deleted too.
- **`-path=secret`:** The name of the mount point; you can give it any value.

### Logging

With the command below we send the audit logs to the service's standard output, so to journald:

@@code@@

### Admin Policy and User

To use instead of the root token, let's create a policy and a user with admin rights:

@@code@@

> `read -rs`: Reads the password without showing it on the screen, and the password is not written to the command history.

> In practice this policy gives the same rights as root. The difference: the token is valid for at most 24 hours, it can be revoked, and the actions show up in the audit log with our own username.

Let's check that we can log in with the new user:

@@code@@

> You can also log in from the UI by choosing `userpass` as the login method.

If the new user works, let's revoke the root token:

@@code@@

> The CLI and policies are worth reading about on your own; I won't go into them here.
