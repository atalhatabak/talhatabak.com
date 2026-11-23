---
title: "WireGuard İstemci Eklemek"
description: "WireGuard'a elle ve bir script ile istemci ekleme; masaüstü ve mobil istemciler."
date: 2026-11-21T00:14:00+03:00
chapter: "7.1"
tags: ["wireguard", "vpn"]
---
> [!abstract] Gerekenler
> - [7 WireGuard Kurulumu](/self-hosting/wireguard/) tamamlanmış olmalı.
>
> **Varsayımlar**
> - Sunucunun VPN adresi `10.8.0.1`; istemciler VPN'e `xenonly.com:51820` üzerinden bağlanmaktadır.
> - Sunucu tarafındaki komutlar sunucuda, istemci tarafındaki komutlar NetworkManager kullanan bir Linux masaüstünde çalıştırılmıştır. Root yetkisi gerekenler `sudo` ile yazılmıştır.
> - Masaüstünde iki VPN profili kullanılmıştır: tüm trafiği tünelden geçiren `xenternet` (full tunnel) ve sadece VPN ağına giden trafiği tünelden geçiren `xentranet` (split tunnel).

## İstemci Ekleme

WireGuard'a istemci ekleme adımları şu şekilde:

1. İstemci için anahtar çifti oluşturma
2. İstemci yapılandırmasını hazırlama
3. `wg0.conf` dosyasına `[Peer]` bloğu ile istemciyi ekleme
4. Değişikliği arayüze uygulama

Bu adımları önce manuel olarak uygulayacağız, ardından bir script ile otomatikleştireceğiz.

## Manuel Ekleme

Aşağıdaki adımlarda `desktop` adında bir istemci ekleyeceğiz.

### 1. Anahtar Çifti Oluşturma

Sunucuda, normal kullanıcıyla ev dizinimizde istemci için private key, public key ve [preshared key](term:preshared-key) oluşturuyoruz:

```bash
(
umask 077
wg genkey | tee desktop.key | wg pubkey > desktop.pub
wg genpsk > desktop.psk
)
```

> [!note]
> Komutlar parantez içinde bir alt kabukta çalışıyor. Böylece `umask 077` sadece bu dosyalar için geçerli oluyor ve oturumun geri kalanını etkilemiyor.

İstemci yapılandırmasında sunucunun public key'i de gerekecek:

```bash
sudo wg show wg0 public-key
```

### 2. İstemci Yapılandırmasını Hazırlama

**Örnek istemci yapılandırması:**

```ini {title="desktop.conf"}
[Interface]
PrivateKey = <desktop.key>
Address    = 10.8.0.2/32, fd42:8::2/128
DNS        = 1.1.1.1, 2606:4700:4700::1111

[Peer]
PublicKey           = <server.pub>
PresharedKey        = <desktop.psk>
Endpoint            = <SUNUCU_ALAN_ADI>:51820
AllowedIPs          = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
```

- **Address:** İstemcinin alacağı IP adresi.
- **DNS:** İstemcinin kullanacağı DNS sunucusu. Boş bırakılırsa istemci tarafındaki varsayılan DNS kullanılır.
- **PersistentKeepalive:** Bağlantının kopmaması için 25 saniyede bir paket gönderir.
- **AllowedIPs:** `0.0.0.0/0, ::/0` değeri tüm internet trafiğini VPN üzerinden geçirir ([full tunnel](term:full-tunnel)). `10.8.0.0/24, fd42:8::/64` girilirse sadece sunucuya ve VPN'e bağlı diğer cihazlara giden trafik VPN'i kullanır ([split tunnel](term:split-tunnel)).

`<...>` ile gösterilen yerlere ilgili dosyaların içeriğini yazıp yapılandırmayı `desktop.conf` olarak kaydediyoruz.

### 3. `wg0.conf` Dosyasına Ekleme

`/etc/wireguard/wg0.conf` dosyasının sonuna istemciyi ekliyoruz:

```ini {title="/etc/wireguard/wg0.conf"}
# peer: desktop
[Peer]
PublicKey    = <desktop.pub>
PresharedKey = <desktop.psk>
AllowedIPs   = 10.8.0.2/32, fd42:8::2/128
```

> [!important]
> `# peer: desktop` satırı, aşağıdaki script'in [peer'ları](term:peer) bulmak için kullandığı işaret. Manuel eklenen peer'ların da script ile yönetilebilmesi için bu satırı ekliyoruz.

> [!warning]
> Her peer bloğundan önce ve sonra boş bir satır bırakılmalı. Script bir peer'ı silerken işaret satırından sonraki ilk boş satıra kadar olan her şeyi siliyor; boş satır yoksa alttaki peer da silinir.

### 4. Değişikliği Uygulama

```bash
sudo bash -c 'wg syncconf wg0 <(wg-quick strip wg0)'
```

`syncconf`, değişikliği mevcut bağlantıları koparmadan canlı arayüze uyguluyor.

Mobil istemci kullanılacaksa yapılandırmayı QR kod olarak yazdırabiliriz:

```bash
qrencode -t ansiutf8 < desktop.conf
```

Yapılandırma istemciye aktarıldıktan sonra anahtar dosyalarını ve yapılandırmayı sunucudan siliyoruz:

```bash
rm desktop.key desktop.pub desktop.psk desktop.conf
```

## Otomatikleştirme

Bu süreci her seferinde manuel yapmak yerine otomatikleştireceğiz. Aşağıdaki script'i sunucuda `/usr/local/sbin/wg-peer` yolunda oluşturalım ve ardından izinlerini düzenleyelim.

> [!important]
> Script'i kaydetmeden önce içindeki `ENDPOINT` değeri kendi sunucumuzun adresiyle değiştirilmeli.

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

### Nasıl Çalışıyor

- Peer'ları bir işaretle buluyor. Her peer'ın `[Peer]` bloğunun önüne `# peer: <isim>` satırı yazılıyor. `remove` ve `list` komutları peer'ları bu satırla buluyor.
- İsim kuralı Linux'un ağ arayüzü adı sınırından geliyor. İsimler küçük harf, rakam ve `-` içerebiliyor ve en fazla 15 karakter olabiliyor; bu, Linux çekirdeğindeki arayüz adı sınırıyla aynı. Böylece istemci adı [NetworkManager'da](term:networkmanager) doğrudan arayüz adı olarak da kullanılabiliyor.
- Değişiklikler bağlantıları koparmıyor. Script her değişiklikten önce `wg0.conf.bak` yedeğini alıyor ve değişikliği `syncconf` ile canlı arayüze uyguluyor. Uygulama başarısız olursa yedeği geri yüklüyor.
- Yapılandırma sadece bir kez gösteriliyor. Kaybedilirse `remove` ve `add` ile yeniden oluşturmak gerekiyor.
- `--local` parametresi sadece istemci yapılandırmasını değiştiriyor: `AllowedIPs` satırı VPN ağıyla sınırlanıyor ve `DNS` satırı eklenmiyor. Sunucudaki peer kaydı iki durumda da aynı; tünelden hangi trafiğin geçeceğine istemci karar veriyor.
- Split tunnel'da `DNS` satırı yok, çünkü internet trafiği tünelden geçmiyor. Satır olsaydı istemcinin DNS ayarı gereksiz yere değişirdi ve sorgular yine tünelin dışından giderdi. İstemci kendi DNS sunucusunu kullanmaya devam ediyor.

### Kullanım

#### Secure Path Ayarı

`wg-peer`'i `/usr/local/sbin` dizinine koyduk. sudo, çalıştırılacak komutu `/etc/sudoers` içindeki `secure_path` listesinde arıyor ve Rocky Linux'ta `/usr/local/sbin` bu listede yok. Bu yüzden bu ayar yapılmadan `sudo wg-peer` komutu bulunamaz. Aynı sorun `sudo -s` ile açılan root kabuğunda da yaşanır; `sudo -i` ile açılan kabukta yaşanmaz.

`secure_path` listesine `/usr/local/sbin` eklemek için `visudo` ile yeni bir dosya açalım:

```bash
sudo visudo -f /etc/sudoers.d/secure_path
```

ve içine aşağıdaki satırı ekleyelim:

```text {title="/etc/sudoers.d/secure_path"}
Defaults secure_path = /sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin
```

#### Yeni Cihaz Ekleme

Full tunnel (tüm trafik VPN üzerinden):

> [!warning]
> Manuel ekleme adımlarını uyguladıysanız `desktop` isminde bir `peer` ekledik. Script'in hata vermemesi için farklı bir isim kullanın.

```bash
sudo wg-peer add desktop
```

Split tunnel (sadece VPN ağı, `--local`):

```bash
sudo wg-peer add xentranet --local
```

Çalıştırıldıktan sonra istemci yapılandırmasını metin ve QR kod olarak ekrana yazdırıyor. İki komutun ürettiği yapılandırma arasındaki fark `AllowedIPs` ve `DNS` satırları:

| Komut                        | İstemcideki `AllowedIPs`   | İstemcideki `DNS`                |
| ---------------------------- | -------------------------- | -------------------------------- |
| `wg-peer add <isim>`         | `0.0.0.0/0, ::/0`          | `1.1.1.1, 2606:4700:4700::1111`  |
| `wg-peer add <isim> --local` | `10.8.0.0/24, fd42:8::/64` | Yok (istemcinin kendi DNS'i)     |

#### Listeleme

```bash
sudo wg-peer list
```

#### Cihaz Silme

```bash
sudo wg-peer remove desktop
```

## Masaüstü İstemcisi

Aşağıdaki adımları NetworkManager kullanan bir Linux masaüstü için uyguluyorum. Masaüstünde iki profil kullanacağım:

- `xenternet`: Tüm trafik tünelden geçer (full tunnel). İnternete VPN üzerinden çıkmak için.
- `xentranet`: Sadece VPN ağına (`10.8.0.0/24`, `fd42:8::/64`) giden trafik tünelden geçer (split tunnel). VPN arkasındaki servislere her zaman erişebilmek için.

> [!note]
> Sunucu bir peer'dan sadece o peer'ın `AllowedIPs` adresinden gelen paketleri kabul ettiği için her profil sunucuda ayrı bir peer (ayrı anahtar ve IP) olarak eklenmeli.

### Full Tunnel Profili (xenternet)

Yapılandırma metnini (`wg-peer add` komutunun çıktısı veya manuel hazırladığımız `desktop.conf`) kopyalıyoruz ve kişisel bilgisayarımızda `/tmp/xenternet.conf` dosyasını oluşturup içine yapıştırıyoruz.

> [!note]
> Dosya adı NetworkManager'da bağlantı ve arayüz adı olarak kullanılacak.

```bash
nmcli connection import type wireguard file /tmp/xenternet.conf
rm /tmp/xenternet.conf

nmcli con modify xenternet connection.autoconnect no \
  ipv4.dns-priority -50 ipv6.dns-priority -50 ipv4.dns-search "~."
nmcli con up xenternet
```

### Split Tunnel Profili (xentranet)

Sunucuda bu profil için `--local` parametresiyle ayrı bir peer oluşturuyoruz:

```bash
sudo wg-peer add xentranet --local
```

Çıktıdaki yapılandırmada `AllowedIPs` satırı zaten `10.8.0.0/24, fd42:8::/64` olarak geliyor ve `DNS` satırı yok; sistemin DNS ayarı değişmiyor. Yapılandırmayı kişisel bilgisayarımızda `/tmp/xentranet.conf` dosyasına yapıştırıyoruz.

```bash
nmcli connection import type wireguard file /tmp/xentranet.conf
rm /tmp/xentranet.conf
nmcli con up xentranet
```

Bağlantılar başarılı olmalı. Bundan sonra profiller masaüstünün ağ menüsünden açılıp kapatılabilir.

> [!note]
> İki profil aynı anda bağlıyken VPN ağına erişim kesiliyor. Sebebi ve çözümü [7.3 Olası Problemler](/self-hosting/wireguard-troubleshooting/) bölümünde.

## Mobil İstemci

WireGuard mobil uygulamasında "QR kodundan oluştur" seçeneğiyle terminaldeki QR kodu okutuyoruz ve bağlantı kuruluyor.

## Kontrol

```bash
ping 10.8.0.1          # yanıt gelmeli
curl -4 ifconfig.me    # full tunnel'da sunucunun IPv4 adresi
curl -6 ifconfig.me    # full tunnel'da sunucunun IPv6 adresi
```
