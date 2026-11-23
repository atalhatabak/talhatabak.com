> **Requirements**
> - [1 Post-Install Configuration](/self-hosting/post-install-configuration/) must be done.
>
> **Assumptions**
> - Containers are reached through the NGINX configured in [3 NGINX Configuration](/self-hosting/nginx/).
> - Firewalld is still off. Docker's Firewalld integration is finished in [5 Firewalld Configuration](/self-hosting/firewalld/).
> - Commands are run on the server with root rights (`sudo`).

## Check and Install

On RHEL-based systems, Podman, Buildah and runc may come preinstalled. Since they may clash with Docker's own packages, let's remove them and install Docker from its own repository:

@@code@@

Let's add the Docker repository and install it:

@@code@@

Before starting Docker, let's write our configuration to `/etc/docker/daemon.json`. If the directory doesn't exist yet, let's create it first:

@@code@@

@@code@@

Why each line is there:

1. **`"ip"` and `"default-network-opts"`:** By default, Docker binds ports published without an IP address, like `-p 8080:80`, to `0.0.0.0` and writes its own rules for them. Traffic to these ports is passed to the container without going through Firewalld's zone rules; even with Firewalld on, the port stays open to the internet. The services that need to be reached will be reached through NGINX, so no container needs to be open to the internet; being reachable over localhost is enough. The `"ip"` setting only applies to the default `bridge` network (`docker run`). For the networks Compose creates, we set the same default with `default-network-opts`. This setting is applied when a network is created; if it is added later, it doesn't affect the existing networks. Still, in the compose files we'll write the ports explicitly, like `127.0.0.1:8080:80`.
2. **`"log-driver": "journald"`:** By default, logs are written to files with the `json-file` driver. To reach and manage all logs from one place, we send them to journald. The `docker logs` command keeps working.
3. **`"live-restore": true`:** Keeps the containers running when the Docker service is restarted or updated.
4. **`"default-address-pools"`:** Sets the range the container networks get their IP addresses from.

We can start the service:

@@code@@

We can check that Docker works with the command below:

@@code@@

The output should have these lines:

@@code@@

Let's check that a port published without an IP address is bound only to localhost on the kind of network Compose uses too:

@@code@@

The `inspect` output should show `"com.docker.network.bridge.host_binding_ipv4":"127.0.0.1"`, and the `ss` output only `127.0.0.1:18080`; `0.0.0.0` or `[::]` should not show up.

## Things to Keep in Mind

1. We don't add the normal user to the `docker` group, because that would let the user become root without a password.
2. When NGINX proxies to a container, it must send the `X-Forwarded-For` and `X-Real-IP` headers. Otherwise the applications see every visitor as 172.20.x.x. For this we'll create a shared template in [4.1 A Ready Template for Docker Containers](/self-hosting/docker-template/).
