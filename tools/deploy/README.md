# Deployment of talhatabak.com

How the live site is deployed. This is specific to my server; to run the site somewhere else, serve the `public/` folder that `hugo --gc --minify` builds with any web server.

On every push to `main`, the [Deploy](../../.github/workflows/deploy.yml) workflow builds the site with Hugo, joins the server's WireGuard VPN (the server's SSH is only open there) and copies `public/` with rsync to `/opt/www/talhatabak.com`, which Nginx serves. To deploy again without a push: *Actions → Deploy → Run workflow*. The workflow is skipped until the `DEPLOY_TARGET` variable (step 5) is set.

## One-time setup

The steps assume the server from the [Self Hosting](https://talhatabak.com/self-hosting/) series: WireGuard (`wg0`, `wg-peer`), the Firewalld `vpn` zone and Nginx with `vhost.d/`. `10.8.0.X` is the IP that `wg-peer` gives the new peer in step 2.

**1. Site folder and deploy user** (server). The `deploy` user owns only the site folder and has no sudo rights.

```bash
sudo dnf install rsync
sudo useradd --create-home deploy
sudo mkdir -p /opt/www/talhatabak.com
sudo chown deploy: /opt/www/talhatabak.com
```

**2. WireGuard peer for GitHub** (server)

```bash
sudo wg-peer add github-deploy --local
```

The first line of the output shows the peer's IPs (`10.8.0.X`, `fd42:8::X`). Keep the printed config for step 5, with these two lines changed so the runner reaches only the server, over IPv4:

```ini
Address    = 10.8.0.X/32
AllowedIPs = 10.8.0.1/32
```

**3. Firewall: SSH only** (server). A VPN peer can reach everything the `vpn` zone allows: other services, the other VPN clients and the internet. A zone bound to a source address takes precedence over the `wg0` zone, so this peer can only reach SSH:

```bash
sudo firewall-cmd --permanent --new-zone=deploy
sudo firewall-cmd --permanent --zone=deploy --add-source=10.8.0.X/32
sudo firewall-cmd --permanent --zone=deploy --add-source=fd42:8::X/128
sudo firewall-cmd --permanent --zone=deploy --add-service=ssh
sudo firewall-cmd --reload
```

**4. SSH key** (your computer)

```bash
ssh-keygen -t ed25519 -N "" -C github-deploy -f deploy_key
```

On the server, allow the public key (the content of `deploy_key.pub`) only from the peer's IP, without a terminal or forwarding:

```bash
sudo install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
echo 'from="10.8.0.X",restrict <CONTENT OF deploy_key.pub>' | sudo tee /home/deploy/.ssh/authorized_keys
sudo chown deploy: /home/deploy/.ssh/authorized_keys
sudo chmod 600 /home/deploy/.ssh/authorized_keys
```

and print the server's host key for the runner's `known_hosts`:

```bash
echo "10.8.0.1 $(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub)"
```

**5. GitHub secrets and variable** (repository → *Settings → Secrets and variables → Actions*)

| Secret | Value |
| --- | --- |
| `WG_CONFIG` | The WireGuard config from step 2, with the two lines changed |
| `DEPLOY_SSH_KEY` | The content of `deploy_key` (the private key) |
| `DEPLOY_KNOWN_HOSTS` | The line printed at the end of step 4 |

| Variable | Value |
| --- | --- |
| `DEPLOY_TARGET` | `deploy@10.8.0.1:/opt/www/talhatabak.com` |

Then delete `deploy_key` and `deploy_key.pub` from your computer.

**6. Certificate and Nginx** (server, with the domain's `A` / `AAAA` records pointing to it)

```bash
sudo certbot certonly --webroot -w /opt/www/well_known -d talhatabak.com -d www.talhatabak.com
```

Run the workflow once (*Actions → Deploy → Run workflow*), copy [`vhost_talhatabak.com.conf`](vhost_talhatabak.com.conf) to `/etc/nginx/vhost.d/`, then:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Nginx needs a reload only when this file changes, not when the site does.

To take GitHub's access away: `sudo wg-peer remove github-deploy`.

## Deploying by hand

The workflow runs [`deploy.sh`](deploy.sh), which builds the site and copies it with rsync; files that are no longer in the build are deleted on the server. To run it from your computer, add your own public key to `/home/deploy/.ssh/authorized_keys`, connect to the VPN and run:

```bash
tools/deploy/deploy.sh deploy@10.8.0.1:/opt/www/talhatabak.com
```
