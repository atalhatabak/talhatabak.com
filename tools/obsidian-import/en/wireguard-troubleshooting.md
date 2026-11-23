> **Requirements**
> - [7.1 Adding WireGuard Clients](/self-hosting/wireguard-clients/) and [7.2 Putting Services Behind the VPN](/self-hosting/services-behind-vpn/) must be done.
>
> **Assumptions**
> - The desktop has the two profiles created in [7.1 Adding WireGuard Clients](/self-hosting/wireguard-clients/): `xenternet` (full tunnel) and `xentranet` (split tunnel).
> - The commands in this part are run on the Linux desktop (the client) that uses NetworkManager.

## Access Problem with a Split Tunnel

We can set up the VPN connection in two ways. If we set `AllowedIPs` in the client configuration to:

- `AllowedIPs = 0.0.0.0/0, ::/0` (full tunnel), all traffic goes through the VPN.
- `AllowedIPs = 10.8.0.0/24, fd42:8::/64` (split tunnel), only the traffic for the VPN network goes through the VPN.

We can use either one, depending on what we need. But here a problem shows up:

If our connection is a **full tunnel** and we try to reach a service that is reachable only from the VPN network (for example the iRedAdmin panel), all traffic, the DNS query included, goes through the VPN when we enter iRedAdmin's domain, and we can reach the service.

If our connection is a **split tunnel** and we try to reach iRedAdmin:

- Our DNS query goes over the public internet, and we try to connect to the server's public IP address.
- Our connection goes over the public internet, so the server sees the request as coming from outside the VPN network and rejects it.

To fix this, the DNS query must return the server's IP address on the VPN network (`10.8.0.1`) instead of its public IP. We can solve this problem in these ways:

1. **VPN IP at the DNS provider:** We set the `A` record of the domains we'll reach only over the VPN to `10.8.0.1` instead of the server's public IP. Wherever the DNS query comes from, it returns `10.8.0.1`, and if there is a VPN connection, the service can be reached.
   But Let's Encrypt can't reach this address during its check, so a certificate can't be issued with the HTTP-01 (webroot) method; a DNS-01 check is needed. Not a great method just to reach a simple service.
2. **The `hosts` file:** We add the record to the `hosts` file on the client computer ourselves. The public DNS record stays only so we can get certificates, and NGINX handles the access restriction. For personal use, the services behind the VPN will be few and for specific needs (for example connecting to SSH and the iRedAdmin panel now and then, only over the VPN), so this one-time effort is not much of a problem.
   The downside: on mobile devices it can't be done without root access.
3. **A DNS service on the server:** We install a light DNS service on the server and put its address in the `DNS` value of the VPN client configuration. For queries about the services behind the VPN, the DNS service on the server returns the server's VPN address, and it asks a public DNS server for everything else.
   This method can add a small delay to DNS queries.

I plan to reach the services I put behind the VPN only from my own computer, and it is simpler than the others, so I'll use method 2, adding a record to the `hosts` file:

@@code@@

## Access Problem with Both Profiles On

### When It Happens

If we want the split tunnel profile (`xentranet`) to stay on all the time so we can always reach the `10.8.0.0/24` network, and turn the full tunnel profile (`xenternet`) on and off only when needed, both profiles stay connected at the same time. In this case our access to `10.8.0.0/24` stops and we can't reach the services behind the VPN.

With both profiles connected at the same time, the internet works, but ping to `10.8.0.1`, SSH and the services reachable only from the VPN don't work. With only one profile connected, there is no problem.

### Why It Happens

Every packet that goes through WireGuard has two layers:

@@code@@

The kernel makes a separate routing decision for each of these two packets:

1. With a full tunnel, NetworkManager puts the default route in a separate routing table and adds a rule: "every packet without a mark (fwmark) goes to this table". The full tunnel marks its own packets, so they don't go back into the tunnel.
2. The inner packet takes the right path. The kernel looks at the main table first (except for the default route). The `10.8.0.0/24` route of `xentranet` is in the main table, so the ping goes into `xentranet`.
3. The outer packet of `xentranet` has no mark, so it matches the rule of `xenternet` and goes into the `xenternet` tunnel.
4. The server receives this packet through `wg0` and checks it against the rules of the VPN zone. In our current firewall configuration the `wireguard` service is not allowed in the VPN zone, so the packet is rejected and the handshake of `xentranet` never completes.
5. WireGuard has no idea of a connection state, so the kernel doesn't know that the tunnel isn't working. The most specific route for `10.8.0.0/24` is still `xentranet`, so access to the server stops.

With only one profile connected, the outer packet of `xentranet` goes over the normal internet and reaches the server through the public zone. `wireguard` is allowed in the public zone, so there is no problem.

A check with both profiles connected:

@@code@@

### Ways to Fix It

| Method | What It Does | Effect |
| --- | --- | --- |
| Switching between profiles | Only one profile is on at a time. The full tunnel covers `10.8.0.0/24` too | The simplest method. Open connections drop while switching |
| Allowing `wireguard` in the VPN zone | The packet of `xentranet` reaches the server inside the `xenternet` tunnel | The packet is encrypted and decrypted twice. The MTU of `xentranet` must be lowered. Not recommended |
| Priority with metric | While `xenternet` is on, `10.8.0.0/24` traffic always goes through `xenternet` | The firewall is not touched. When `xenternet` comes up, connections opened through `xentranet` drop, because the server doesn't accept `xentranet`'s IP from the `xenternet` peer |
| **fwmark (chosen)** | The outer packets of `xentranet` are marked too, so they go over the normal internet | The packet is encrypted only once, connections don't drop, and `xenternet` can be turned on and off on its own |

### Steps: fwmark

> **fwmark:** A number the kernel puts on a packet. It lives only in the computer's memory, it never goes out on the network and it has nothing to do with ports. `51820` is a habit that comes from wg-quick; it can be any number. NetworkManager also uses this number as the routing table number of the full tunnel.

Let's give both profiles the same fwmark value. Then the rule of `xenternet` becomes "packets whose mark is not 51820", and the packets of `xentranet` don't match it.

@@code@@

A check with both profiles connected:

@@code@@

Test: let's open an SSH session to the server through `xentranet` and turn `xenternet` on and off a few times. The session should not drop.
