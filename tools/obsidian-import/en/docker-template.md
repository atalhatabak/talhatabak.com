> **Requirements**
> - [3 NGINX Configuration](/self-hosting/nginx/) and [4 Docker Setup](/self-hosting/docker/) must be done.
>
> **Assumptions**
> - Container ports are published in the compose files as `127.0.0.1:<HOST_PORT>:<CONTAINER_PORT>` and opened to the outside only through NGINX. The settings in [4 Docker Setup](/self-hosting/docker/) also bind ports published without an IP address to `127.0.0.1`.
> - Commands are run on the server with root rights (`sudo`).

Let's put the containers we'll install into a standard layout.

Let's keep the Docker Compose files in one place:

@@code@@

## Port Plan

The containers open their ports only on `127.0.0.1`, and NGINX forwards to these ports. To avoid clashes, the ports of the services installed in this series are:

| Service | Port | Note |
| --- | --- | --- |
| [8 Vault Setup](/self-hosting/vault/) | `127.0.0.1:8200` | Not Docker, runs as a service on the host |
| [9 Vaultwarden Setup](/self-hosting/vaultwarden/) | `127.0.0.1:8004` | |
| [10 WordPress Setup](/self-hosting/wordpress/) | `127.0.0.1:8030`–`8049` | One port for each site |
| [11 Usememos Setup](/self-hosting/memos/) | `127.0.0.1:8001` | |
| [12 Syncthing Setup](/self-hosting/syncthing/) | `127.0.0.1:8384`, `22000` | Not Docker, runs as a service on the host |

You can check the ports in use with `sudo ss -tlnp | grep docker-proxy`.

## NGINX Settings

### WebSocket Support

First let's check whether the `$connection_upgrade` variable is already defined. If the same map is defined twice, NGINX gives an error.

@@code@@

If the output is empty, let's create `/etc/nginx/conf.d/websocket.conf` like this:

@@code@@

### Proxy Template

Let's create `/etc/nginx/templates/proxy.tmpl` like this:

@@code@@

> The basic configuration for a reverse proxy; we'll use it in most of the virtual hosts that forward to containers.

> `proxy_set_header` is inherited the same way as `add_header`: if even one `proxy_set_header` is defined in a location block, all the ones from the parent block stop working in that block. That's why the safest way is to include the template in the same location block as `proxy_pass`.
