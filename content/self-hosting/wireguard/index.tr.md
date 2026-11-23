---
title: "WireGuard Kurulumu"
description: "VPN sunucusu: istemcileri VPN üzerinden internete çıkarma, istemciler arası iletişim ve bazı servisleri sadece VPN üzerinden erişilebilir yapma."
date: 2026-11-21T00:13:00+03:00
chapter: "7"
tags: ["wireguard", "vpn", "firewalld"]
---
> [!abstract] Gerekenler
> - [4 Docker Kurulumu](/self-hosting/docker/) ve [5 Firewalld Yapılandırma](/self-hosting/firewalld/) tamamlanmış olmalı (bu bölüm her ikisinin yapılandırmasını da değiştiriyor).
>
> **Varsayımlar**
> - Dış ağ arayüzünün `eth0` olduğu, NetworkManager tarafından yönetildiği ve IPv6 adresinin statik olarak tanımlandığı varsayılmıştır.
> - VPN ağı olarak `10.8.0.0/24` (IPv4) ve `fd42:8::/64` (IPv6) kullanılmıştır; sunucunun VPN adresi `10.8.0.1` / `fd42:8::1`.
> - WireGuard `51820/udp` portunu dinlemektedir.
> - Komutlar sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır.

WireGuard'ı şu amaçlarla kullanacağız:

1. İstemcileri VPN üzerinden internete çıkarmak
2. İstemcilerin birbiriyle konuşabilmesini sağlamak (ör. laptop ve telefon)
3. Sunucudaki bazı servisleri (ör. [iRedAdmin](term:iredadmin) paneli) herkese açık değil de sadece VPN üzerinden erişilebilir yapmak

## Kurulum

```bash
sudo dnf install wireguard-tools qrencode
```

> [!note]
> WireGuard'ın çekirdek modülü Rocky Linux 10 çekirdeğinde bulunduğu için sadece araçları kuruyoruz. `qrencode`, telefon yapılandırmasını QR kod olarak göstermek için.

## Anahtar Çifti Oluşturma

WireGuard servisinin kullanacağı anahtar çiftini (key pair) oluşturalım:

```bash
sudo sh -c 'cd /etc/wireguard && umask 077 && wg genkey | tee server.key | wg pubkey > server.pub'
```

> [!note]
> `cd` ve `umask` kabuğun kendi komutları olduğu için `sudo cd` veya `sudo umask` şeklinde çalıştırıldıklarında mevcut kabuğu etkilemiyorlar. Bu yüzden komutları `sudo sh -c` ile tek bir root kabuğunda çalıştırıyoruz. `umask 077`, oluşturulan anahtar dosyalarını sadece root'un okuyabilmesini sağlıyor.

## Kalıcı IP Yönlendirme

> [!note]
> Paketlerin bir arayüzden diğerine yönlendirilebilmesi (pratikte VPN arayüzündeki trafiğin internete çıkabilmesi) için [IP forwarding'i](term:ip-forwarding) açıyoruz.

> [!note]
> Docker forwarding'i zaten açıyor, ama sadece kendi servisi başladığında. Bu dosya forwarding'in açılışta, Docker'dan bağımsız olarak açılmasını sağlıyor.

### Önce IPv6 Kontrolü

Linux'ta IPv6 forwarding açıldığında çekirdek artık [Router Advertisement](term:slaac) (RA) kabul etmiyor. [VPS](term:vps) IPv6 adresini RA (SLAAC) ile alıyorsa forwarding'i açtığımız anda IPv6 bağlantısı kopabilir. Bu yüzden forwarding'i açmadan önce IPv6 varsayılan rotasını kontrol edelim:

```bash
ip -6 route show default
```

Çıktı aşağıdakine benzer olmalı:

```text
default via fe80::1 dev eth0 proto static metric 100 pref medium
```

Bu sunucuda IPv6 statik (`proto static`), RA kullanılmıyor; bu yüzden forwarding'i açmak IPv6 bağlantısını etkilemiyor. Çıktıda `proto ra` görünüyorsa aşağıdaki dosyaya `net.ipv6.conf.eth0.accept_ra = 2` satırının da eklenmesi gerekiyor.

### Forwarding'i Açma

`/etc/sysctl.d/90-wireguard.conf` dosyasını aşağıdaki içerikle oluşturalım:

```ini {title="/etc/sysctl.d/90-wireguard.conf"}
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
```

Ayarları uygulayalım:

```bash
sudo sysctl --system
```

## WireGuard Yapılandırması

`/etc/wireguard/wg0.conf` dosyasını aşağıdaki gibi oluşturalım:

```ini {title="/etc/wireguard/wg0.conf"}
[Interface]
Address    = 10.8.0.1/24, fd42:8::1/64
ListenPort = 51820
PrivateKey = <server.key>
```

> [!note]
> `<server.key>`: `/etc/wireguard/server.key` dosyasının içeriği (`sudo cat /etc/wireguard/server.key`).

Dosyanın izinlerini sadece root okuyabilecek şekilde düzenleyelim:

```bash
sudo chmod 600 /etc/wireguard/wg0.conf
```

## Firewalld Yapılandırması

### Dış Arayüzü Public Zone'a Açıkça Bağlama

> [!note]
> `eth0` şu an varsayılan [zone'da](term:firewalld-zone) olduğu için zaten public zone'da. Bu adım, varsayılan zone ileride değişse bile `eth0`'ın public zone'da kalmasını ve aşağıda tanımlayacağımız VPN [policy'sinin](term:firewalld-policy) (çıkış zone'u public) çalışmaya devam etmesini garantiliyor.

```bash
sudo nmcli -t -f NAME,DEVICE con show --active
sudo nmcli con modify "<BAGLANTI_ADI>" connection.zone public
```

> [!note]
> `<BAGLANTI_ADI>`: İlk komutun çıktısında `eth0`'a ait bağlantının adı.

### WireGuard Portunu Açma

```bash
sudo firewall-cmd --permanent --zone=public --add-service=wireguard
```

### VPN için Firewalld'de Zone Oluşturma

```bash
# vpn adında yeni ve boş bir zone oluşturur
sudo firewall-cmd --permanent --new-zone=vpn

# wg0 arayüzünü bu zone'a bağlar. Bundan sonra WireGuard tünelinden gelen tüm trafik public zone'un değil, vpn zone'unun kurallarıyla değerlendirilir.
sudo firewall-cmd --permanent --zone=vpn --add-interface=wg0

# VPN'den gelen trafik için sunucudaki hangi servislere izin verileceğini belirler:
sudo firewall-cmd --permanent --zone=vpn \
  --add-service=ssh --add-service=http --add-service=https \
  --add-service=smtp-submission --add-service=smtps \
  --add-service=imap --add-service=imaps

# Aynı zone içindeki trafiğin yönlendirilmesine izin verir. İstemcilerin birbiriyle konuşabilmesini sağlar.
sudo firewall-cmd --permanent --zone=vpn --add-forward
```

> [!note]
> Public zone'da izin verdiğimiz servislere VPN zone'unda tekrar izin vermemizin sebebi şu: VPN'e bağlı bir istemcinin sunucuya giden trafiği ([full tunnel'da](term:full-tunnel) sunucunun public IP'sine giden trafik de dahil) `wg0` üzerinden gelir. VPN zone'unda bu servislere izin vermezsek istemci VPN'e bağlıyken bu servislere erişemez.

### VPN'den İnternete Çıkış

> [!note]
> **Zone**, sunucunun kendisine gelen trafiği yönetiyor. Örneğin: "VPN'den gelen biri sunucudaki SSH'a bağlanabilir mi?"

> [!note]
> **Policy**, sunucunun üzerinden geçen trafiği, yani bir zone'dan diğerine yönlendirilen paketleri yönetiyor.

Firewalld'de zone'lar arasındaki yönlendirme varsayılan olarak kapalı. Bu yüzden VPN istemcilerinin internete çıkabilmesi için açıkça bir policy tanımlamamız gerekiyor.

```bash
# vpn-internet adında yeni ve boş bir policy oluşturur.
sudo firewall-cmd --permanent --new-policy=vpn-internet

# Policy'nin yönünü belirler. Trafik vpn zone'undan (wg0) gelip public zone'una (dış arayüz, yani internet) gidiyorsa bu policy uygulanır.
sudo firewall-cmd --permanent --policy=vpn-internet --add-ingress-zone=vpn
sudo firewall-cmd --permanent --policy=vpn-internet --add-egress-zone=public

# Bu yöndeki trafiği kabul eder. VPN istemcisi internette istediği adrese gidebilir; 25. port, 5. bölümdeki no-smtp-out policy'siyle engelli.
sudo firewall-cmd --permanent --policy=vpn-internet --set-target=ACCEPT

# NAT'ı etkinleştirir.
sudo firewall-cmd --permanent --policy=vpn-internet --add-masquerade

# --add-masquerade sadece IPv4 için uygulanıyor, IPv6 için ayrı bir rich rule gerekiyor
sudo firewall-cmd --permanent --policy=vpn-internet \
    --add-rich-rule='rule family="ipv6" source address="fd42:8::/64" masquerade'
```

Firewalld'ye eklediğimiz kuralları uygulayalım:

```bash
sudo firewall-cmd --reload
```

Zone ve policy'yi kontrol edelim:

```bash
# Hangi arayüzün hangi zone'da olduğunu gösterir
sudo firewall-cmd --get-active-zones
```

```text
docker
 interfaces: docker0
public (default)
 interfaces: eth0
vpn
 interfaces: wg0
```

```bash
# Policy'nin ayarlarını gösterir
sudo firewall-cmd --info-policy=vpn-internet
```

```text
vpn-internet (active)  
 disable: no  
 priority: -1  
 target: ACCEPT  
 ingress-zones: vpn  
 egress-zones: public  
 services:    
 ports:    
 protocols:    
 masquerade: yes  
 forward-ports:    
 source-ports:    
 icmp-blocks:    
 rich rules:    
       rule family="ipv6" source address="fd42:8::/64" masquerade
```

> [!note]
> [5 Firewalld Yapılandırma](/self-hosting/firewalld/) bölümünde oluşturduğumuz `no-smtp-out` policy'si ingress zone olarak `ANY` kullandığı için VPN istemcilerine de uygulanıyor. Priority değeri (`-10`) `vpn-internet`'inkinden (`-1`) küçük olduğu için önce o değerlendiriliyor. İstemci ekledikten sonra ([7.1](/self-hosting/wireguard-clients/)) full tunnel profiliyle bağlıyken istemcide `nc -v -w 5 gmail-smtp-in.l.google.com 25 </dev/null` komutu bağlantı hatası vermeli. Windows'ta `Test-NetConnection gmail-smtp-in.l.google.com -Port 25` komutu `TcpTestSucceeded : False` döndürmeli.

## Docker'ın FORWARD DROP Politikası

Docker, [iptables'ta](term:iptables) FORWARD zincirinin varsayılan politikasını DROP yapıyor. Firewalld VPN trafiğine izin verse bile paket Docker'ın tablosuna da uğruyor ve DROP politikası paketi düşürüyor.

Bu politikanın uygulanıp uygulanmadığını kontrol edelim:

```bash
sudo iptables -S FORWARD | head -1
sudo ip6tables -S FORWARD | head -1
```

Çıktıda `-P FORWARD DROP` görünüyorsa politika uygulanıyor.

`/etc/docker/daemon.json` dosyasına aşağıdaki satırı ekleyerek Docker'ın DROP politikası uygulamasını engelleyelim:

```json {title="/etc/docker/daemon.json"}
"ip-forward-no-drop": true
```

Dosya şu şekilde görünmeli:

```json {title="/etc/docker/daemon.json"}
{
  "ip": "127.0.0.1",
  "default-network-opts": {
    "bridge": { "com.docker.network.bridge.host_binding_ipv4": "127.0.0.1" }
  },
  "log-driver": "journald",
  "live-restore": true,
  "ip-forward-no-drop": true,
  "default-address-pools": [
    { "base": "172.20.0.0/16", "size": 24 }
  ]
}
```

Docker yapılandırmasını doğrulayalım:

```bash
sudo dockerd --validate --config-file /etc/docker/daemon.json
```

`configuration OK` çıktısını aldıysak Docker'ı yeniden başlatalım ve FORWARD politikasını düzeltelim:

```bash
sudo systemctl restart docker
sudo iptables -P FORWARD ACCEPT && sudo ip6tables -P FORWARD ACCEPT
```

> [!note]
> Docker'ı yeniden başlatmak mevcut DROP politikasını değiştirmiyor. `ip-forward-no-drop` ayarı, Docker'ın bundan sonra politikayı DROP yapmasını engelliyor. Şu an DROP olan politika kendiliğinden düzelmediği için onu bir kez elle ACCEPT yapıyoruz.

> [!note]
> Bu, yönlendirilen trafiğin artık filtrelenmeyeceği anlamına gelmiyor. Firewalld yönlendirilen trafiği kendi nftables tablosunda zone ve policy kurallarıyla filtrelemeye devam ediyor. iptables'taki ACCEPT politikası sadece Docker'ın koyduğu ikinci engeli kaldırıyor.

## WireGuard'ı Başlatma

Aşağıdaki komutlarla servisi etkinleştirip başlatalım:

```bash
sudo systemctl enable --now wg-quick@wg0
sudo wg show
```

Çıktıda `interface: wg0` ve `listening port: 51820` görünmeli.
