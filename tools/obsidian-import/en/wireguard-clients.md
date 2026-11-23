> **Requirements**
> - [7 WireGuard Setup](/self-hosting/wireguard/) must be done.
>
> **Assumptions**
> - The server's VPN address is `10.8.0.1`; clients connect to the VPN through `xenonly.com:51820`.
> - Server-side commands are run on the server, client-side commands on a Linux desktop that uses NetworkManager. Commands that need root rights are written with `sudo`.
> - The desktop uses two VPN profiles: `xenternet` (full tunnel), which sends all traffic through the tunnel, and `xentranet` (split tunnel), which sends only the traffic for the VPN network through the tunnel.

## Adding a Client

These are the steps for adding a client to WireGuard:

1. Creating a key pair for the client
2. Preparing the client configuration
3. Adding the client to `wg0.conf` with a `[Peer]` block
4. Applying the change to the interface

We'll do these steps by hand first, then automate them with a script.

## Adding by Hand

In the steps below we'll add a client named `desktop`.

### 1. Creating the Key Pair

On the server, as the normal user, we create a private key, a public key and a preshared key for the client in our home directory:

@@code@@

> The commands run in a subshell inside the parentheses. So `umask 077` applies only to these files and doesn't affect the rest of the session.

The client configuration will also need the server's public key:

@@code@@

### 2. Preparing the Client Configuration

**Example client configuration:**

@@code@@

- **Address:** The IP address the client gets.
- **DNS:** The DNS server the client will use. If it is left empty, the client's default DNS is used.
- **PersistentKeepalive:** Sends a packet every 25 seconds so the connection doesn't drop.
- **AllowedIPs:** `0.0.0.0/0, ::/0` sends all internet traffic through the VPN (full tunnel). With `10.8.0.0/24, fd42:8::/64`, only the traffic to the server and to the other devices on the VPN uses the VPN (split tunnel).

We write the contents of the matching files into the places marked with `<...>` and save the configuration as `desktop.conf`.

### 3. Adding It to `wg0.conf`

We add the client to the end of `/etc/wireguard/wg0.conf`:

@@code@@

> The `# peer: desktop` line is the marker the script below uses to find the peers. We add this line so that peers added by hand can be managed with the script too.

> Leave an empty line before and after every peer block. When the script removes a peer, it deletes everything from the marker line to the next empty line; if there is no empty line, the peer below gets deleted too.

### 4. Applying the Change

@@code@@

`syncconf` applies the change to the live interface without dropping the current connections.

If a mobile client will be used, we can print the configuration as a QR code:

@@code@@

After the configuration has been moved to the client, we delete the key files and the configuration from the server:

@@code@@

## Automating It

Instead of doing this by hand every time, we'll automate it. Let's create the script below on the server at `/usr/local/sbin/wg-peer`, and then set its permissions.

> Before saving the script, change the `ENDPOINT` value in it to your own server's address.

@@code@@

@@code@@

### How It Works

- It finds the peers by a marker. A `# peer: <name>` line is written before each peer's `[Peer]` block. The `remove` and `list` commands find the peers by this line.
- The name rule comes from Linux's limit for network interface names. Names may contain lowercase letters, digits and `-`, and can be at most 15 characters long; this is the same as the interface name limit in the Linux kernel. So the client name can also be used directly as the interface name in NetworkManager.
- Changes don't drop connections. Before every change the script makes a `wg0.conf.bak` backup and applies the change to the live interface with `syncconf`. If applying fails, it restores the backup.
- The configuration is shown only once. If it is lost, you need to create it again with `remove` and `add`.
- The `--local` option only changes the client configuration: the `AllowedIPs` line is limited to the VPN network and no `DNS` line is added. The peer entry on the server is the same in both cases; the client decides which traffic goes through the tunnel.
- The split tunnel has no `DNS` line because internet traffic doesn't go through the tunnel. With the line, the client's DNS setting would change for no reason and the queries would still go outside the tunnel. The client keeps using its own DNS server.

### Usage

#### The Secure Path Setting

We put `wg-peer` in the `/usr/local/sbin` directory. sudo looks for the command to run in the `secure_path` list in `/etc/sudoers`, and on Rocky Linux `/usr/local/sbin` is not in this list. So without this setting, `sudo wg-peer` is not found. The same problem happens in a root shell opened with `sudo -s`; it doesn't happen in a shell opened with `sudo -i`.

To add `/usr/local/sbin` to the `secure_path` list, let's open a new file with `visudo`:

@@code@@

and add the line below to it:

@@code@@

#### Adding a New Device

Full tunnel (all traffic through the VPN):

> If you did the manual steps, we already added a `peer` named `desktop`. Use a different name so the script doesn't give an error.

@@code@@

Split tunnel (only the VPN network, `--local`):

@@code@@

After it runs, it prints the client configuration on the screen as text and as a QR code. The difference between the configurations of the two commands is in the `AllowedIPs` and `DNS` lines:

| Command | `AllowedIPs` on the client | `DNS` on the client |
| --- | --- | --- |
| `wg-peer add <name>` | `0.0.0.0/0, ::/0` | `1.1.1.1, 2606:4700:4700::1111` |
| `wg-peer add <name> --local` | `10.8.0.0/24, fd42:8::/64` | None (the client's own DNS) |

#### Listing

@@code@@

#### Removing a Device

@@code@@

## Desktop Client

I do the steps below on a Linux desktop that uses NetworkManager. I'll use two profiles on the desktop:

- `xenternet`: All traffic goes through the tunnel (full tunnel). For going out to the internet through the VPN.
- `xentranet`: Only the traffic for the VPN network (`10.8.0.0/24`, `fd42:8::/64`) goes through the tunnel (split tunnel). For reaching the services behind the VPN at any time.

> The server accepts packets from a peer only from that peer's `AllowedIPs` addresses, so each profile must be added on the server as a separate peer (with its own key and IP).

### Full Tunnel Profile (xenternet)

We copy the configuration text (the output of `wg-peer add`, or the `desktop.conf` we prepared by hand), create the file `/tmp/xenternet.conf` on our personal computer and paste it in.

> The file name will be used as the connection and interface name in NetworkManager.

@@code@@

### Split Tunnel Profile (xentranet)

On the server we create a separate peer for this profile with the `--local` option:

@@code@@

In the configuration in the output, the `AllowedIPs` line is already `10.8.0.0/24, fd42:8::/64` and there is no `DNS` line; the system's DNS setting doesn't change. We paste the configuration into the file `/tmp/xentranet.conf` on our personal computer.

@@code@@

The connections should work. From now on the profiles can be turned on and off from the desktop's network menu.

> When both profiles are connected at the same time, access to the VPN network stops. The reason and the fix are in [7.3 Possible Problems](/self-hosting/wireguard-troubleshooting/).

## Mobile Client

In the WireGuard mobile app we use the "Create from QR code" option to scan the QR code in the terminal, and the connection is set up.

## Check

@@code@@
