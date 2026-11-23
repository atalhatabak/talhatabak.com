---
title: "Syncthing Kurulumu"
description: "Cihazlar arasında dosya senkronizasyonu için Syncthing; sunucu her zaman açık olan ortak eş olarak kullanılıyor."
date: 2026-11-21T00:22:00+03:00
chapter: "12"
tags: ["syncthing"]
---
> [!abstract] Gerekenler
> - [1 Kurulum Sonrası Yapılandırma](/self-hosting/post-install-configuration/) (EPEL deposu), [5 Firewalld Yapılandırma](/self-hosting/firewalld/) ve [7.2 Servisleri VPN Arkasına Almak](/self-hosting/services-behind-vpn/) tamamlanmış olmalı.
>
> **Varsayımlar**
> - Syncthing arayüzüne `sync.xenonly.com` adresinden, sadece VPN üzerinden erişilmektedir. Bu alan adı için `A` ve `AAAA` kayıtlarının girildiği varsayılmıştır.
> - Cihazlar sunucuya `xenonly.com:22000` adresinden bağlanmaktadır.
> - Syncthing, ev dizini `/srv/syncthing` olan ayrı bir `syncthing` sistem kullanıcısıyla çalışmaktadır.
> - Sunucu komutları sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır. Cihaz eşleştirme adımları istemcilerdeki Syncthing arayüzünden yapılmıştır.

## Nedir

Syncthing, dosyaları cihazlar arasında doğrudan senkronize eden açık kaynak bir araç. Merkezi bir bulut hizmeti yok; her cihaz kendi kimliğine (Device ID) sahip ve sadece eşleştirdiğimiz cihazlarla, şifreli bağlantı üzerinden dosya paylaşıyor.

Sunucuya kurduğumuz Syncthing, cihazlarımızın her zaman açık olan ortak bir eşi olacak. Bilgisayar ve telefon aynı anda açık olmasa bile değişiklikler sunucu üzerinden diğer cihazlara ulaşacak.

## Kurulum Öncesi Kararlar

**Native kurulum:** Syncthing'i diğer uygulamalar gibi Docker ile değil, [EPEL](term:epel) deposundaki paketle doğrudan sunucuya kuracağız. Paket güncel sürümü takip ediyor ve sistemle birlikte `dnf upgrade` ile güncelleniyor. Paketle gelen [systemd](term:systemd) servisi de sandbox ayarlarıyla (sistem dizinlerini salt okunur yapma, yetki kısıtlamaları vb.) geliyor.

**Ayrı kullanıcı:** Senkronizasyon portu internete açık olacağı için Syncthing'i kendi kullanıcımızla değil, ayrı bir `syncthing` sistem kullanıcısıyla çalıştıracağız. Böylece olası bir Syncthing açığında saldırgan sadece bu kullanıcının dosyalarına erişebilir; kendi ev dizinimize (ör. `~/.ssh` içindeki anahtarlara) erişemez.

**Portlar:**

| Port             | Kullanım              | Erişim                          |
| ---------------- | --------------------- | ------------------------------- |
| `22000/tcp`      | Senkronizasyon (TCP)  | Herkese açık                    |
| `22000/udp`      | Senkronizasyon ([QUIC](term:quic)) | Herkese açık                    |
| `127.0.0.1:8384` | Web arayüzü           | Sadece NGINX üzerinden, VPN ile |

**Senkronizasyon portu herkese açık olacak:** Telefonda [full tunnel'ın](term:full-tunnel) sürekli açık olması gerekmesin ([9 Vaultwarden Kurulumu](/self-hosting/vaultwarden/) bölümündeki gerekçeyle aynı). Syncthing bağlantıları karşılıklı sertifika doğrulamalı [TLS](term:tls) ile yapılıyor; sunucu sadece Device ID'sini eklediğimiz cihazlarla konuşuyor.

**Web arayüzü sadece VPN'den:** Syncthing arayüzü varsayılan olarak sadece `127.0.0.1:8384` adresini dinliyor. Arayüzü NGINX üzerinden `vpn-only` şablonuyla sunacağız.

> [!note]
> Local discovery portu (`21027/udp`) aynı yerel ağdaki cihazları bulmak için kullanılıyor. Sunucu bir [VPS](term:vps) olduğu ve yerel ağda başka cihazımız olmadığı için bu portu açmıyoruz.

## Kurulum

Paketi kuralım:

```bash
sudo dnf install syncthing
```

Syncthing için ev dizini `/srv/syncthing` olan bir sistem kullanıcısı oluşturalım:

```bash
sudo useradd --system --create-home --home-dir /srv/syncthing --shell /usr/sbin/nologin syncthing
```

- **`--system`:** Giriş yapmak için değil, bir servisi çalıştırmak için kullanılan bir kullanıcı.
- **`--home-dir /srv/syncthing`:** Syncthing'in yapılandırması (`/srv/syncthing/.local/state/syncthing`) ve senkronize edilen klasörler bu dizinde duracak.
- **`--shell /usr/sbin/nologin`:** Bu kullanıcıyla oturum açılamıyor.

> [!note]
> Rocky Linux'ta ev dizinleri varsayılan olarak `700` izniyle oluşturuluyor (`ls -ld /home/*` ile kontrol edilebilir). Bu yüzden `syncthing` kullanıcısı diğer kullanıcıların ev dizinlerini okuyamıyor.

Paketle gelen `syncthing@.service`, parametre olarak verilen kullanıcıyla çalışan bir servis şablonu. Servisi `syncthing` kullanıcısı için etkinleştirip başlatalım:

```bash
sudo systemctl enable --now syncthing@syncthing
sudo systemctl status syncthing@syncthing
```

İlk çalıştırmada Syncthing kendi anahtarlarını ve yapılandırmasını oluşturuyor. Kontrol edelim:

```bash
sudo ls /srv/syncthing/.local/state/syncthing   # cert.pem, config.xml, key.pem ...
sudo ss -tulpn | grep syncthing
```

`22000` portu TCP ve UDP için tüm adreslerde (`*:22000`), `8384` portu ise sadece `127.0.0.1` üzerinde görünmeli.

> [!note]
> Servisin logları [journald'de](term:journald): `sudo journalctl -u syncthing@syncthing`

## Firewalld

Senkronizasyon portunu public [zone'da](term:firewalld-zone) ve VPN zone'unda açalım:

```bash
sudo firewall-cmd --permanent --zone=public --add-port=22000/tcp --add-port=22000/udp
sudo firewall-cmd --permanent --zone=vpn --add-port=22000/tcp --add-port=22000/udp
sudo firewall-cmd --reload
```

> [!note]
> VPN zone'unda da açmamızın sebebi: Full tunnel bağlıyken cihazların sunucunun public IP'sine giden trafiği de `wg0` üzerinden geliyor ve VPN zone'unun kurallarıyla değerlendiriliyor (bkz. [7 WireGuard Kurulumu](/self-hosting/wireguard/)).

## Sertifika ve NGINX Reverse Proxy

Sertifikayı alalım:

```bash
sudo certbot certonly --webroot -w /opt/www/well_known -d sync.xenonly.com
```

`/etc/nginx/vhost.d/vhost_sync.xenonly.com.conf` dosyasını aşağıdaki gibi oluşturalım:

```nginx {title="/etc/nginx/vhost.d/vhost_sync.xenonly.com.conf"}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name sync.xenonly.com;

    ssl_certificate     /etc/letsencrypt/live/sync.xenonly.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sync.xenonly.com/privkey.pem;
    include /etc/nginx/templates/vpn-only.tmpl;

    location / {
        proxy_pass http://127.0.0.1:8384;

        proxy_set_header Host              localhost;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
```

- **`proxy.tmpl` kullanmıyoruz:** Syncthing, arayüz `127.0.0.1`'e bağlıyken gelen isteklerdeki `Host` başlığının `localhost` olmasını şart koşuyor ([DNS rebinding](term:dns-rebinding) saldırılarına karşı). `proxy.tmpl` `Host` başlığını `sync.xenonly.com` olarak gönderdiği için arayüz "Host check error" hatası verir. Bu yüzden başlıkları burada tek tek tanımlıyor ve `Host` başlığını `localhost` olarak gönderiyoruz.
- **`proxy_read_timeout 600s`:** Arayüz değişiklikleri uzun süre açık kalan isteklerle ([long polling](term:long-polling)) takip ediyor; varsayılan 60 saniyelik süre bu istekleri kesiyor.

NGINX yapılandırmasını test edip yeniden yükleyelim:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

> [!note]
> [Split tunnel](term:split-tunnel) ile erişmek için kişisel bilgisayardaki `hosts` dosyasına `10.8.0.1 sync.xenonly.com` kaydı eklenmeli (bkz. [7.3 Olası Problemler](/self-hosting/wireguard-troubleshooting/)).

## İlk Yapılandırma

VPN'e bağlıyken `https://sync.xenonly.com` adresine gidelim.

1. **Actions → Settings → GUI** yolundan **GUI Authentication User** ve **GUI Authentication Password** alanlarını doldurup kaydedelim. Arayüz VPN arkasında olsa da parolasız bırakmıyoruz. Aynı sayfadaki **Use HTTPS for GUI** seçeneğini ise açmıyoruz.
2. Aynı pencerede **Connections** sekmesinden **Enable Local Discovery** seçeneğini kapatalım; sunucunun yerel ağında başka cihazımız yok.
3. Varsayılan olarak gelen **Default Folder** klasörünü kullanmayacaksak klasörün **Edit → Remove** seçeneğiyle kaldırabiliriz.

> [!warning] Use HTTPS for GUI açılmamalı
> HTTPS'i NGINX sağlıyor. Bu seçenek açılırsa Syncthing, NGINX'ten gelen HTTP isteklerini `Host` başlığındaki adrese yönlendiriyor. NGINX bu başlığı `localhost` olarak gönderdiği için tarayıcı `https://localhost/` adresine gider ve arayüze erişilemez. Seçenek yanlışlıkla açıldıysa arayüze erişemeyeceğimiz için sunucuda yapılandırma dosyasından kapatalım:
>
> ```bash
> sudo systemctl stop syncthing@syncthing
> sudo sed -i '/<gui /s/tls="true"/tls="false"/' /srv/syncthing/.local/state/syncthing/config.xml
> sudo systemctl start syncthing@syncthing
> ```
>
> Syncthing yapılandırmayı bellekte tuttuğu ve değişiklik kaydedildiğinde dosyanın üzerine yazdığı için dosyayı servis durmuşken düzenliyoruz.

> [!note]
> Sunucunun cihaz adı varsayılan olarak hostname (`mail.xenonly.com`) oluyor. **Actions → Settings → General → Device Name** alanından değiştirilebilir.

## Cihaz Eşleştirme

Her cihaza Syncthing kurulu olmalı. Aşağıdaki adımlar her cihaz için tekrarlanıyor.

1. Sunucunun arayüzünde **Actions → Show ID** ile sunucunun Device ID'sini kopyalayalım.
2. Cihazdaki Syncthing arayüzünde **Add Remote Device** ile sunucunun Device ID'sini girelim. **Advanced** sekmesinde **Addresses** alanına `tcp://xenonly.com:22000, dynamic` yazalım.
3. Birkaç saniye içinde sunucunun arayüzünde cihazın bağlanmak istediğini bildiren bir uyarı çıkıyor; **Add Device** ile onaylayalım.

> [!note]
> `dynamic`, sunucunun adresi değişirse Syncthing'in global discovery ile sunucuyu yine bulmasını sağlıyor. `tcp://xenonly.com:22000` ise discovery'ye gerek kalmadan doğrudan bağlanıyor.

### Klasör Paylaşma

1. Cihazdaki arayüzde paylaşmak istediğimiz klasörün **Edit → Sharing** sekmesinden sunucuyu işaretleyelim.
2. Sunucunun arayüzünde klasörün paylaşılmak istendiğini bildiren uyarıda **Add** diyelim. **Folder Path** alanı varsayılan olarak `syncthing` kullanıcısının ev dizini altında (`/srv/syncthing/<KLASOR>`); bu şekilde bırakalım.
3. Diğer cihazlarda da aynı klasörü sunucuyla paylaşınca değişiklikler sunucu üzerinden tüm cihazlara ulaşıyor.

> [!warning]
> Syncthing bir yedekleme aracı değil; bir cihazda silinen dosya diğer cihazlardan da siliniyor. Sunucudaki klasörlerde **Edit → File Versioning → Staggered File Versioning** açılırsa silinen ve değiştirilen dosyaların eski sürümleri sunucuda `.stversions` dizininde bir süre tutuluyor.

## Senkronize Dosyalara Kendi Kullanıcımızla Erişmek (İsteğe Bağlı)

`/srv/syncthing` dizinini sadece `syncthing` kullanıcısı okuyabiliyor. Senkronize edilen dosyaları sunucuda kendi kullanıcımızla `sudo` olmadan okumak istersek kullanıcımızı `syncthing` grubuna ekleyip gruba okuma izni verelim:

```bash
sudo usermod -aG syncthing "$USER"
sudo chmod 750 /srv/syncthing
sudo chmod 700 /srv/syncthing/.local
```

- **`chmod 750 /srv/syncthing`:** `syncthing` grubundakiler dizine girip dosyaları okuyabiliyor, diğer kullanıcılar giremiyor.
- **`chmod 700 /srv/syncthing/.local`:** Syncthing'in anahtarları ve yapılandırması bu dizinde. Grup üyeleri dahil kimse okuyamasın.

> [!note]
> Grup üyeliğinin geçerli olması için oturumu kapatıp tekrar açmak gerekiyor. Bu ayarla dosyaları okuyabiliyoruz ama değiştiremiyoruz; dosyaları değiştirmek cihazlardan, Syncthing üzerinden yapılmalı.

## Kontrol

Kişisel bilgisayarımızdan, VPN'e bağlı değilken:

```bash
nc -zv -w 5 xenonly.com 22000                     # bağlanmalı
curl -sI https://sync.xenonly.com | head -1       # HTTP/2 403
```

Sunucuda:

```bash
curl -s http://127.0.0.1:8384/rest/noauth/health   # {"status": "OK"}
```

Sunucunun arayüzünde eşleştirilen cihazlar **Connected**, klasörler **Up to Date** olarak görünmeli.

## Yedekleme ve Güncellemeler

- **`/srv/syncthing/.local/state/syncthing`:** Sunucunun kimliği (`cert.pem`, `key.pem`) ve yapılandırması burada. Bu dosyalar kaybolursa sunucu yeni bir Device ID ile başlar ve tüm cihazların yeniden eşleştirilmesi gerekir.
- **Senkronize edilen klasörler:** Dosyaların kopyası zaten diğer cihazlarda da var, ama Syncthing bir yedekleme aracı olmadığı için önemli klasörler ayrıca yedeklenmeli.

Syncthing paketi sistemle birlikte `sudo dnf upgrade` ile güncelleniyor. Güncellemeden sonra yeni sürümün çalışması için servisi yeniden başlatalım:

```bash
sudo systemctl restart syncthing@syncthing
```
