---
title: "Adding WireGuard Clients"
description: "Adding WireGuard clients by hand and with a script; desktop and mobile clients."
date: 2026-11-21T00:14:00+03:00
chapter: "7.1"
tags: ["wireguard", "vpn"]
---
> [!abstract] Requirements
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

On the server, as the normal user, we create a private key, a public key and a [preshared key](term:preshared-key) for the client in our home directory:

```bash
(
umask 077
wg genkey | tee desktop.key | wg pubkey > desktop.pub
wg genpsk > desktop.psk
)
```

> [!note]
> The commands run in a subshell inside the parentheses. So `umask 077` applies only to these files and doesn't affect the rest of the session.

The client configuration will also need the server's public key:

```bash
sudo wg show wg0 public-key
```

### 2. Preparing the Client Configuration

**Example client configuration:**

```ini {title="desktop.conf"}
[Interface]
PrivateKey = <desktop.key>
Address    = 10.8.0.2/32, fd42:8::2/128
DNS        = 1.1.1.1, 2606:4700:4700::1111

[Peer]
PublicKey           = <server.pub>
PresharedKey        = <desktop.psk>
Endpoint            = <SERVER_DOMAIN>:51820
AllowedIPs          = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
```

- **Address:** The IP address the client gets.
- **DNS:** The DNS server the client will use. If it is left empty, the client's default DNS is used.
- **PersistentKeepalive:** Sends a packet every 25 seconds so the connection doesn't drop.
- **AllowedIPs:** `0.0.0.0/0, ::/0` sends all internet traffic through the VPN ([full tunnel](term:full-tunnel)). With `10.8.0.0/24, fd42:8::/64`, only the traffic to the server and to the other devices on the VPN uses the VPN ([split tunnel](term:split-tunnel)).

We write the contents of the matching files into the places marked with `<...>` and save the configuration as `desktop.conf`.

### 3. Adding It to `wg0.conf`

We add the client to the end of `/etc/wireguard/wg0.conf`:

```ini {title="/etc/wireguard/wg0.conf"}
# peer: desktop
[Peer]
PublicKey    = <desktop.pub>
PresharedKey = <desktop.psk>
AllowedIPs   = 10.8.0.2/32, fd42:8::2/128
```

> [!important]
> The `# peer: desktop` line is the marker the script below uses to find the [peers](term:peer). We add this line so that peers added by hand can be managed with the script too.

> [!warning]
> Leave an empty line before and after every peer block. When the script removes a peer, it deletes everything from the marker line to the next empty line; if there is no empty line, the peer below gets deleted too.

### 4. Applying the Change

```bash
sudo bash -c 'wg syncconf wg0 <(wg-quick strip wg0)'
```

`syncconf` applies the change to the live interface without dropping the current connections.

If a mobile client will be used, we can print the configuration as a QR code:

```bash
qrencode -t ansiutf8 < desktop.conf
```

After the configuration has been moved to the client, we delete the key files and the configuration from the server:

```bash
rm desktop.key desktop.pub desktop.psk desktop.conf
```

## Automating It

Instead of doing this by hand every time, we'll automate it. Let's create the script below on the server at `/usr/local/sbin/wg-peer`, and then set its permissions.

> [!important]
> Before saving the script, change the `ENDPOINT` value in it to your own server's address.

```bash {title="/usr/local/sbin/wg-peer"}
#!/usr/bin/env bash
# wg-peer: WireGuard client management
#   wg-peer add <name>           create a new client (full tunnel), print its config as text and QR code
#   wg-peer add <name> --local   same, but the client routes only the VPN network and keeps its own DNS (split tunnel)
#   wg-peer remove <name>        remove a client
#   wg-peer list                 list clients and their latest handshake
set -euo pipefail

IFACE="wg0"
CONF="/etc/wireguard/${IFACE}.conf"
ENDPOINT="xenonly.com:51820"
NET4="10.8.0."      # clients: 10.8.0.2 - 10.8.0.254
NET6="fd42:8::"     # clients: fd42:8::2 - fd42:8::254
DNS="1.1.1.1, 2606:4700:4700::1111"
FULL_ALLOWED="0.0.0.0/0, ::/0"            # full tunnel: all traffic goes through the VPN
LOCAL_ALLOWED="${NET4}0/24, ${NET6}/64"   # split tunnel (--local): only the VPN network

# Print an error message and exit
die() { echo "Error: $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "must be run as root"
umask 077

# Apply wg0.conf to the live interface without dropping connections,
# restore the backup if it fails
apply() {
   if ! wg syncconf "$IFACE" <(wg-quick strip "$IFACE"); then
       cp -p "$CONF.bak" "$CONF"
       wg syncconf "$IFACE" <(wg-quick strip "$IFACE")
       die "failed to apply config, backup restored"
   fi
}

# Check whether a peer with the given name exists
peer_exists() { grep -qxF "# peer: $1" "$CONF"; }

# Create a peer: pick the first free IP, generate keys, append it to wg0.conf,
# then print the client config (the private key is never written to disk).
# $2 is the client's AllowedIPs: FULL_ALLOWED or LOCAL_ALLOWED.
# The DNS line is added only for the full tunnel.
cmd_add() {
   local name=$1 allowed=$2 n ip="" priv pub psk server_pub client dns=""

   [[ $allowed == "$FULL_ALLOWED" ]] && dns="DNS        = $DNS"$'\n'

   [[ $name =~ ^[a-z0-9-]{1,15}$ ]] || die "name may contain only lowercase letters, digits and '-' (max 15 chars)"
   peer_exists "$name" && die "'$name' already exists"

   for n in $(seq 2 254); do
       grep -qF "${NET4}${n}/32" "$CONF" || { ip=$n; break; }
   done
   [[ -n $ip ]] || die "no free IP left"

   server_pub=$(wg show "$IFACE" public-key)
   priv=$(wg genkey)
   pub=$(wg pubkey <<< "$priv")
   psk=$(wg genpsk)

   cp -p "$CONF" "$CONF.bak"
   cat >> "$CONF" <<EOF

# peer: $name
[Peer]
PublicKey    = $pub
PresharedKey = $psk
AllowedIPs   = ${NET4}${ip}/32, ${NET6}${ip}/128
EOF
   apply

   client=$(cat <<EOF
[Interface]
PrivateKey = $priv
Address    = ${NET4}${ip}/32, ${NET6}${ip}/128
${dns}
[Peer]
PublicKey           = $server_pub
PresharedKey        = $psk
Endpoint            = $ENDPOINT
AllowedIPs          = $allowed
PersistentKeepalive = 25
EOF
)

   echo "=== $name  ${NET4}${ip}  ${NET6}${ip}  AllowedIPs: $allowed ==="
   echo
   echo "$client"
   echo
   qrencode -t ansiutf8 <<< "$client"
   echo
   echo "This config is shown only once, the client's private key is not stored on the server."
}

# Remove a peer: drop its block (from the marker line to the next blank line)
# from wg0.conf and apply
cmd_remove() {
   local name=$1

   peer_exists "$name" || die "'$name' not found"

   cp -p "$CONF" "$CONF.bak"
   awk -v m="# peer: $name" '
       $0 == m    { skip = 1; next }
       skip && NF { next }
       skip       { skip = 0; next }
       { print }
   ' "$CONF.bak" > "$CONF"
   apply

   echo "'$name' removed."
}

# List peers with their IP and latest handshake time
cmd_list() {
   local handshakes name pub ip ts last

   handshakes=$(wg show "$IFACE" latest-handshakes)
   printf '%-15s %-12s %s\n' "NAME" "IP" "LATEST HANDSHAKE"

   awk '
       /^# peer: /             { name = substr($0, 9) }
       /^PublicKey/  && name   { pub = $3 }
       /^AllowedIPs/ && name   { split($3, a, ","); sub("/32", "", a[1]); print name, pub, a[1]; name = "" }
   ' "$CONF" | while read -r name pub ip; do
       ts=$(awk -v k="$pub" '$1 == k { print $2 }' <<< "$handshakes")
       if [[ -z $ts || $ts == 0 ]]; then
           last="-"
       else
           last=$(date -d "@$ts" '+%F %T')
       fi
       printf '%-15s %-12s %s\n' "$name" "$ip" "$last"
   done
}

case "${1:-}" in
   add)
       [[ $# -eq 2 || ( $# -eq 3 && ${3:-} == "--local" ) ]] || die "usage: wg-peer add <name> [--local]"
       if [[ ${3:-} == "--local" ]]; then
           cmd_add "$2" "$LOCAL_ALLOWED"
       else
           cmd_add "$2" "$FULL_ALLOWED"
       fi
       ;;
   remove) [[ $# -eq 2 ]] || die "usage: wg-peer remove <name>"; cmd_remove "$2" ;;
   list)   cmd_list ;;
   *)      echo "usage: wg-peer {add <name> [--local] | remove <name> | list}" >&2; exit 1 ;;
esac
```

```bash
sudo chown root:root /usr/local/sbin/wg-peer
sudo chmod 700 /usr/local/sbin/wg-peer
```

### How It Works

- It finds the peers by a marker. A `# peer: <name>` line is written before each peer's `[Peer]` block. The `remove` and `list` commands find the peers by this line.
- The name rule comes from Linux's limit for network interface names. Names may contain lowercase letters, digits and `-`, and can be at most 15 characters long; this is the same as the interface name limit in the Linux kernel. So the client name can also be used directly as the interface name in [NetworkManager](term:networkmanager).
- Changes don't drop connections. Before every change the script makes a `wg0.conf.bak` backup and applies the change to the live interface with `syncconf`. If applying fails, it restores the backup.
- The configuration is shown only once. If it is lost, you need to create it again with `remove` and `add`.
- The `--local` option only changes the client configuration: the `AllowedIPs` line is limited to the VPN network and no `DNS` line is added. The peer entry on the server is the same in both cases; the client decides which traffic goes through the tunnel.
- The split tunnel has no `DNS` line because internet traffic doesn't go through the tunnel. With the line, the client's DNS setting would change for no reason and the queries would still go outside the tunnel. The client keeps using its own DNS server.

### Usage

#### The Secure Path Setting

We put `wg-peer` in the `/usr/local/sbin` directory. sudo looks for the command to run in the `secure_path` list in `/etc/sudoers`, and on Rocky Linux `/usr/local/sbin` is not in this list. So without this setting, `sudo wg-peer` is not found. The same problem happens in a root shell opened with `sudo -s`; it doesn't happen in a shell opened with `sudo -i`.

To add `/usr/local/sbin` to the `secure_path` list, let's open a new file with `visudo`:

```bash
sudo visudo -f /etc/sudoers.d/secure_path
```

and add the line below to it:

```text {title="/etc/sudoers.d/secure_path"}
Defaults secure_path = /sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin
```

#### Adding a New Device

Full tunnel (all traffic through the VPN):

> [!warning]
> If you did the manual steps, we already added a `peer` named `desktop`. Use a different name so the script doesn't give an error.

```bash
sudo wg-peer add desktop
```

Split tunnel (only the VPN network, `--local`):

```bash
sudo wg-peer add xentranet --local
```

After it runs, it prints the client configuration on the screen as text and as a QR code. The difference between the configurations of the two commands is in the `AllowedIPs` and `DNS` lines:

| Command | `AllowedIPs` on the client | `DNS` on the client |
| --- | --- | --- |
| `wg-peer add <name>` | `0.0.0.0/0, ::/0` | `1.1.1.1, 2606:4700:4700::1111` |
| `wg-peer add <name> --local` | `10.8.0.0/24, fd42:8::/64` | None (the client's own DNS) |

#### Listing

```bash
sudo wg-peer list
```

#### Removing a Device

```bash
sudo wg-peer remove desktop
```

## Desktop Client

I do the steps below on a Linux desktop that uses NetworkManager. I'll use two profiles on the desktop:

- `xenternet`: All traffic goes through the tunnel (full tunnel). For going out to the internet through the VPN.
- `xentranet`: Only the traffic for the VPN network (`10.8.0.0/24`, `fd42:8::/64`) goes through the tunnel (split tunnel). For reaching the services behind the VPN at any time.

> [!note]
> The server accepts packets from a peer only from that peer's `AllowedIPs` addresses, so each profile must be added on the server as a separate peer (with its own key and IP).

### Full Tunnel Profile (xenternet)

We copy the configuration text (the output of `wg-peer add`, or the `desktop.conf` we prepared by hand), create the file `/tmp/xenternet.conf` on our personal computer and paste it in.

> [!note]
> The file name will be used as the connection and interface name in NetworkManager.

```bash
nmcli connection import type wireguard file /tmp/xenternet.conf
rm /tmp/xenternet.conf

nmcli con modify xenternet connection.autoconnect no \
  ipv4.dns-priority -50 ipv6.dns-priority -50 ipv4.dns-search "~."
nmcli con up xenternet
```

### Split Tunnel Profile (xentranet)

On the server we create a separate peer for this profile with the `--local` option:

```bash
sudo wg-peer add xentranet --local
```

In the configuration in the output, the `AllowedIPs` line is already `10.8.0.0/24, fd42:8::/64` and there is no `DNS` line; the system's DNS setting doesn't change. We paste the configuration into the file `/tmp/xentranet.conf` on our personal computer.

```bash
nmcli connection import type wireguard file /tmp/xentranet.conf
rm /tmp/xentranet.conf
nmcli con up xentranet
```

The connections should work. From now on the profiles can be turned on and off from the desktop's network menu.

> [!note]
> When both profiles are connected at the same time, access to the VPN network stops. The reason and the fix are in [7.3 Possible Problems](/self-hosting/wireguard-troubleshooting/).

## Mobile Client

In the WireGuard mobile app we use the "Create from QR code" option to scan the QR code in the terminal, and the connection is set up.

## Check

```bash
ping 10.8.0.1          # should answer
curl -4 ifconfig.me    # with the full tunnel, the server's IPv4 address
curl -6 ifconfig.me    # with the full tunnel, the server's IPv6 address
```
