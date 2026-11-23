---
title: "Docker Setup"
description: "Installing Docker and setting it up so that containers are reachable only over localhost."
date: 2026-11-21T00:09:00+03:00
chapter: "4"
tags: ["docker"]
---
> [!abstract] Requirements
> - [1 Post-Install Configuration](/self-hosting/post-install-configuration/) must be done.
>
> **Assumptions**
> - Containers are reached through the NGINX configured in [3 NGINX Configuration](/self-hosting/nginx/).
> - Firewalld is still off. Docker's Firewalld integration is finished in [5 Firewalld Configuration](/self-hosting/firewalld/).
> - Commands are run on the server with root rights (`sudo`).

## Check and Install

On [RHEL](term:rhel)-based systems, Podman, Buildah and runc may come preinstalled. Since they may clash with Docker's own packages, let's remove them and install Docker from its own repository:

```bash
sudo dnf remove podman buildah runc
```

Let's add the Docker repository and install it:

```bash
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo

sudo dnf install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Before starting Docker, let's write our configuration to `/etc/docker/daemon.json`. If the directory doesn't exist yet, let's create it first:

```bash
sudo mkdir -p /etc/docker
```

```json {title="/etc/docker/daemon.json"}
{
  "ip": "127.0.0.1",
  "default-network-opts": {
    "bridge": { "com.docker.network.bridge.host_binding_ipv4": "127.0.0.1" }
  },
  "log-driver": "journald",
  "live-restore": true,
  "default-address-pools": [
    { "base": "172.20.0.0/16", "size": 24 }
  ]
}
```

Why each line is there:

1. **`"ip"` and `"default-network-opts"`:** By default, Docker binds ports published without an IP address, like `-p 8080:80`, to `0.0.0.0` and writes its own rules for them. Traffic to these ports is passed to the [container](term:container) without going through Firewalld's [zone](term:firewalld-zone) rules; even with Firewalld on, the port stays open to the internet. The services that need to be reached will be reached through NGINX, so no container needs to be open to the internet; being reachable over localhost is enough. The `"ip"` setting only applies to the default `bridge` network (`docker run`). For the networks Compose creates, we set the same default with `default-network-opts`. This setting is applied when a network is created; if it is added later, it doesn't affect the existing networks. Still, in the compose files we'll write the ports explicitly, like `127.0.0.1:8080:80`.
2. **`"log-driver": "journald"`:** By default, logs are written to files with the `json-file` driver. To reach and manage all logs from one place, we send them to [journald](term:journald). The `docker logs` command keeps working.
3. **`"live-restore": true`:** Keeps the containers running when the Docker service is restarted or updated.
4. **`"default-address-pools"`:** Sets the range the container networks get their IP addresses from.

We can start the service:

```bash
sudo systemctl enable --now docker
```

We can check that Docker works with the command below:

```bash
sudo docker run --rm hello-world
```

The output should have these lines:

```text
Hello from Docker!
This message shows that your installation appears to be working correctly.
```

Let's check that a port published without an IP address is bound only to localhost on the kind of network Compose uses too:

```bash
sudo docker network create porttest
sudo docker network inspect porttest --format '{{json .Options}}'
sudo docker run -d --rm --name porttest --network porttest -p 18080:80 alpine sleep 60
sudo ss -tln | grep 18080
sudo docker rm -f porttest && sudo docker network rm porttest
```

The `inspect` output should show `"com.docker.network.bridge.host_binding_ipv4":"127.0.0.1"`, and the `ss` output only `127.0.0.1:18080`; `0.0.0.0` or `[::]` should not show up.

## Things to Keep in Mind

1. We don't add the normal user to the `docker` group, because that would let the user become root without a password.
2. When NGINX proxies to a container, it must send the `X-Forwarded-For` and `X-Real-IP` headers. Otherwise the applications see every visitor as 172.20.x.x. For this we'll create a shared template in [4.1 A Ready Template for Docker Containers](/self-hosting/docker-template/).
