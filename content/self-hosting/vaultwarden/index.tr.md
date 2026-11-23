---
title: "Vaultwarden Kurulumu"
description: "Bitwarden uyumlu parola yöneticisi Vaultwarden'ın kurulumu."
date: 2026-11-21T00:18:00+03:00
chapter: "9"
tags: ["vaultwarden", "docker"]
---
> [!abstract] Gerekenler
> - [2 Mail Sunucu Kurulumu](/self-hosting/mail-server/), [4.1 Docker Konteynerleri için Hazır Şablon](/self-hosting/docker-template/), [6 Fail2Ban Yapılandırma](/self-hosting/fail2ban/) ve [7.2 Servisleri VPN Arkasına Almak](/self-hosting/services-behind-vpn/) tamamlanmış olmalı.
>
> **Varsayımlar**
> - Vaultwarden'a `password.xenonly.com` adresinden erişilmektedir. Bu alan adı için `A` ve `AAAA` kayıtlarının girildiği varsayılmıştır.
> - Vaultwarden konteyneri `127.0.0.1:8004` portunu kullanmaktadır.
> - Komutlar sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır.

## Nedir

Vaultwarden, Bitwarden sunucusunun Rust ile yazılmış hafif bir sürümü. Resmi Bitwarden istemcileriyle (tarayıcı eklentisi, masaüstü, mobil) çalışıyor. Resmi Bitwarden'ı self-host etmek birden fazla [konteyner](term:container), MSSQL ve GB'larca RAM istiyor; Vaultwarden tek konteynerde birkaç on MB RAM ile çalışıyor.

Kasa istemcide şifreleniyor. Sunucu master parolayı hiç görmüyor, sadece şifreli veriyi saklıyor. Aşağıdaki erişim kararını da bu belirliyor.

## Kurulum Öncesi Kararlar

**Alt alan adı:** Vaultwarden için `password.xenonly.com` kullanacağım.

**Port:** Vaultwarden `8004` portundan sunulacak.

**Veritabanı:** Vaultwarden [SQLite](term:sqlite), MariaDB ve PostgreSQL destekliyor. WordPress için [10 WordPress Kurulumu](/self-hosting/wordpress/) bölümünde kuracağımız MariaDB konteynerini kullanabilirdik, ama tek kullanıcı için SQLite yeterli. Bütün veri tek bir `data` dizininde duruyor, yedeklemesi kolay ve servis MariaDB'ye bağımlı olmuyor.

**Erişim:** Herkese açık (public) olacak.

- Telefonda otomatik doldurma ve senkronizasyon için sunucuya her zaman erişilebilmesi gerekiyor. VPN arkasındaki servisler için seçtiğimiz `hosts` dosyası yöntemi mobil cihazlarda root yetkisi olmadan yapılamıyor; Vaultwarden sadece VPN'den erişilebilir olursa telefonda [full tunnel'ın](term:full-tunnel) sürekli açık olması gerekir.
- İstemciler kasanın bir kopyasını cihazda tutuyor. Sunucuya erişim yokken kasa okunabiliyor ama yeni kayıtlar senkronize olmuyor.
- Veri istemcide şifrelendiği için sunucu ele geçirilse bile master parola olmadan kasa açılamıyor.

Herkese açık olacağı için kayıtları kapatacağız, yönetim panelini VPN arkasına alacağız, [2FA](term:2fa) açacağız ve bir Fail2Ban [jail'i](term:jail) ekleyeceğiz.

## Kurulum

### Mail Hesabı

Vaultwarden 2FA, yeni cihaz bildirimleri ve davetler için mail gönderiyor. [iRedAdmin'den](term:iredadmin) `vaultwarden@xenonly.com` hesabını oluşturalım.

### Admin Token

```bash
sudo mkdir -p /opt/docker/vaultwarden
cd /opt/docker/vaultwarden
sudo docker run --rm -it vaultwarden/server /vaultwarden hash
```

Komut iki kez parola soruyor ve `ADMIN_TOKEN='$argon2id$v=19$...'` şeklinde bir satır yazdırıyor. Bu satırı olduğu gibi `/opt/docker/vaultwarden/.env` dosyasına ekleyelim:

```ini {title="/opt/docker/vaultwarden/.env"}
ADMIN_TOKEN='$argon2id$v=19$...'
SMTP_PASSWORD='<SMTP_PAROLASI>'
```

> [!note]
> `<SMTP_PAROLASI>`: `vaultwarden@xenonly.com` hesabının parolası.

```bash
sudo chmod 600 .env
```

> [!important]
> Tek tırnak önemli. [Hash'in](term:hash) içinde `$` karakterleri var; tırnak olmazsa [Docker Compose](term:docker-compose) bunları değişken olarak okuyup siliyor.

> [!note]
> Yönetim paneline hash ile değil, komutta girdiğimiz parola ile giriş yapıyoruz.

### Compose

`/opt/docker/vaultwarden/compose.yaml` dosyasını aşağıdaki gibi oluşturalım:

```yaml {title="/opt/docker/vaultwarden/compose.yaml"}
services:
  vaultwarden:
    image: vaultwarden/server:latest
    container_name: vaultwarden
    restart: unless-stopped
    ports:
      - "127.0.0.1:8004:80"
    volumes:
      - ./data:/data
    environment:
      DOMAIN: "https://password.xenonly.com"
      SIGNUPS_ALLOWED: "true"
      INVITATIONS_ALLOWED: "false"
      PASSWORD_HINTS_ALLOWED: "false"
      ADMIN_TOKEN: ${ADMIN_TOKEN}
      SMTP_HOST: mail.xenonly.com
      SMTP_PORT: 587
      SMTP_SECURITY: starttls
      SMTP_FROM: vaultwarden@xenonly.com
      SMTP_FROM_NAME: Vaultwarden
      SMTP_USERNAME: vaultwarden@xenonly.com
      SMTP_PASSWORD: ${SMTP_PASSWORD}
      TZ: Europe/Istanbul
```

Her satırın neden eklendiği:

1. **`DOMAIN`:** Maillerdeki linkler, [WebSocket](term:websocket) ve [WebAuthn](term:webauthn) bu adresi kullanıyor. `https://` ile birlikte tam adres yazılmalı.
2. **`SIGNUPS_ALLOWED: "true"`:** Sadece ilk hesabı oluşturmak için. Hesap oluşturulduktan sonra `false` yapılacak.
3. **`INVITATIONS_ALLOWED: "false"`:** Açık olduğunda kayıtlar kapalı olsa bile organizasyon davetleriyle yeni hesap açılabiliyor. Tek kullanıcı olacağı için kapatıyoruz.
4. **`PASSWORD_HINTS_ALLOWED: "false"`:** Parola ipucu, master parola hakkında bilgi sızdırıyor.
5. **`SMTP_FROM` ile `SMTP_USERNAME` aynı:** [iRedMail](term:iredmail), giriş yapılan hesaptan farklı bir gönderici adresiyle gönderilen mailleri reddediyor.
6. **`TZ`:** Log zamanlarının yerel saatle yazılması için.

> [!note]
> Vaultwarden ziyaretçinin IP adresini varsayılan olarak `X-Real-IP` başlığından okuyor; `proxy.tmpl` bu başlığı gönderiyor. Fail2Ban'ın çalışması buna bağlı, başlık gelmezse her istek 172.20.x.x adresinden geliyormuş gibi görünür.

Konteyneri başlatalım:

```bash
sudo docker compose up -d
sudo docker logs vaultwarden 2>&1 | tail -5
```

> [!warning] Dikkat
> Yönetim panelinden bir ayar değiştirilip kaydedilirse Vaultwarden `data/config.json` dosyasını oluşturuyor ve bu dosyadaki değerler compose dosyasındaki ortam değişkenlerini eziyor. Sonrasında compose dosyasında yapılan değişiklikler sessizce uygulanmıyor. Bu yüzden ayarları sadece compose dosyasından yöneteceğiz; yönetim panelini kullanıcı yönetimi ve tanılama için kullanacağız, ayar kaydetmek için değil.

## Sertifika ve NGINX Reverse Proxy

Sertifikayı alalım:

```bash
sudo certbot certonly --webroot -w /opt/www/well_known -d password.xenonly.com
```

`/etc/nginx/vhost.d/vhost_password.xenonly.com.conf` dosyasını aşağıdaki gibi oluşturalım:

```nginx {title="/etc/nginx/vhost.d/vhost_password.xenonly.com.conf"}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name password.xenonly.com;

    ssl_certificate     /etc/letsencrypt/live/password.xenonly.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/password.xenonly.com/privkey.pem;

    add_header Strict-Transport-Security "max-age=31536000" always;
    client_max_body_size 128m;

    # İlk hesap oluşturulana kadar, sonra kaldırılacak
    include /etc/nginx/templates/vpn-only.tmpl;

    location / {
        proxy_pass http://127.0.0.1:8004;
        include /etc/nginx/templates/proxy.tmpl;
    }

    location /admin {
        include /etc/nginx/templates/vpn-only.tmpl;
        proxy_pass http://127.0.0.1:8004;
        include /etc/nginx/templates/proxy.tmpl;
    }
}
```

- **`add_header Strict-Transport-Security`:** Vaultwarden kendi [CSP'sini](term:csp) ve güvenlik başlıklarını gönderiyor; `headers.conf`'taki başlıklar da eklenirse bazıları yanıtta iki kez gider. [Virtual host'ta](term:virtual-host) tek bir `add_header` tanımlandığında `headers.conf`'taki başlıklar bu virtual host'a miras kalmıyor (bkz. [3 NGINX Yapılandırması](/self-hosting/nginx/)). [HSTS'yi](term:hsts) biz ekliyoruz, gerisini Vaultwarden gönderiyor.
- **`client_max_body_size 128m`:** Dosya ekleri ve Send için. iRedMail'in tanımladığı 12m yetmiyor.
- **WebSocket:** Diğer cihazlara anlık senkronizasyon `/notifications/hub` üzerinden WebSocket ile yapılıyor. 1.29 sürümünden beri ayrı bir port gerekmiyor; `proxy.tmpl`'deki `Upgrade` ve `Connection` başlıkları yeterli.
- **`location /admin`:** Server bloğundaki `vpn-only` satırı kaldırıldıktan sonra da yönetim paneli VPN arkasında kalıyor. [Split tunnel](term:split-tunnel) ile erişmek için kişisel bilgisayardaki `hosts` dosyasına `10.8.0.1 password.xenonly.com` kaydı eklenmeli (bkz. [7.3 Olası Problemler](/self-hosting/wireguard-troubleshooting/)).

NGINX yapılandırmasını test edip yeniden yükleyelim:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## İlk Hesap ve Kayıtları Kapatma

1. VPN'e full tunnel ile bağlanıp `https://password.xenonly.com` adresinden hesabımızı oluşturalım.
2. **Settings → Security → Two-step login → Authenticator app** yolundan 2FA'yı açalım. Recovery code'u sunucu dışında bir yere kaydedelim.
3. Compose dosyasında `SIGNUPS_ALLOWED: "false"` yapalım ve `sudo docker compose up -d` ile konteyneri yeniden oluşturalım.
4. Virtual host'ta server seviyesindeki `include /etc/nginx/templates/vpn-only.tmpl;` satırını silelim ve `sudo nginx -t && sudo systemctl reload nginx` ile NGINX'i yeniden yükleyelim.

> [!warning] Dikkat
> Master parola unutulursa kurtarmanın bir yolu yok, sunucu tarafında sıfırlanamıyor. Ezberlenmeli ve kâğıt üzerinde güvenli bir yerde saklanmalı.

### İstemciler

Bitwarden uygulamalarında giriş ekranındaki bölge seçiminden **Self-hosted** seçilip Server URL olarak `https://password.xenonly.com` girilir.

## Kontrol

Kişisel bilgisayarımızdan, VPN'e bağlı değilken:

```bash
curl -s https://password.xenonly.com/alive    # zaman damgası dönmeli
curl -I https://password.xenonly.com/admin    # 403 dönmeli
```

- VPN ile `https://password.xenonly.com/admin/diagnostics` sayfasında alan adı, saat ve WebSocket kontrollerinde hata olmamalı.
- Yönetim panelindeki **Send test email** ile [SMTP](term:smtp) test edilebilir; bu buton ayar kaydetmiyor.
- İki cihazda kasa açıkken birinde eklenen kayıt diğerinde birkaç saniye içinde görünüyorsa WebSocket çalışıyor.

## Ek Ayarlar

### Fail2Ban

Docker logları [journald'ye](term:journald) gittiği için jail'i `systemd` backend'iyle tanımlayacağız.

`/etc/fail2ban/filter.d/vaultwarden.local` dosyasını aşağıdaki içerikle oluşturalım:

```ini {title="/etc/fail2ban/filter.d/vaultwarden.local"}
[Definition]
failregex = ^.*Username or password is incorrect\. Try again\. IP: <ADDR>\. Username:.*$
ignoreregex =
```

`/etc/fail2ban/jail.d/vaultwarden.local` dosyasını aşağıdaki içerikle oluşturalım:

```ini {title="/etc/fail2ban/jail.d/vaultwarden.local"}
[vaultwarden]
enabled      = true
backend      = systemd
journalmatch = CONTAINER_NAME=vaultwarden
filter       = vaultwarden
port         = http,https
maxretry     = 5
findtime     = 10m
```

Yanlış parolayla bir giriş denemesi yaptıktan sonra filtreyi test edelim ve servisi yeniden başlatalım:

```bash
sudo fail2ban-regex "systemd-journal[journalmatch='CONTAINER_NAME=vaultwarden']" vaultwarden
sudo systemctl restart fail2ban
sudo fail2ban-client status vaultwarden
```

> [!note]
> NGINX host'ta çalıştığı için ban işe yarıyor; istek host'taki 443 portuna geliyor. Konteyner portu doğrudan internete açılmış olsaydı trafik Docker'ın FORWARD zinciri üzerinden geçerdi ve host'taki ban kurallarına takılmazdı.

> [!note]
> Yönetim paneli için jail eklemedim; panel VPN arkasında ve VPN ağı zaten `ignoreip` içinde.

> [!tip]
> Backend hatası alınırsa journald desteği için `sudo dnf install fail2ban-systemd` ile paket kurulmalı.

### Yedekleme

Yedeklenmesi gereken her şey `/opt/docker/vaultwarden/data` altında:

| Dosya                    | Not                                                                                |
| ------------------------ | ---------------------------------------------------------------------------------- |
| `db.sqlite3`             | Servis çalışırken düz kopyalama tutarsız yedek verebilir, `.backup` ile alınmalı   |
| `attachments/`, `sends/` | Dosya ekleri ve Send dosyaları                                                     |
| `config.json`            | Varsa                                                                              |
| `rsa_key.pem`            | Oturumları imzalıyor. Kaybolursa tüm cihazlardan çıkış yapılır, veri kaybı olmaz   |

```bash
sudo dnf install sqlite
sudo sqlite3 /opt/docker/vaultwarden/data/db.sqlite3 ".backup '<YEDEK_DIZINI>/db-$(date +%F).sqlite3'"
```

> [!note]
> Kasa verisi master parola ile şifreli; yedekten geri dönüldüğünde de master parola gerekiyor.

> [!tip]
> En kötü senaryo için ara ara web kasadan **Tools → Export → Encrypted JSON** ile dışa aktarma alınıp sunucu dışında saklanmalı.

### Güncellemeler

```bash
cd /opt/docker/vaultwarden && sudo docker compose pull && sudo docker compose up -d
```

Bitwarden istemcileri kendiliğinden güncelleniyor ve eski bir Vaultwarden sürümü yeni istemcilerle sorun çıkarabiliyor. Bu yüzden Vaultwarden'ı güncel tutmak diğer servislere göre daha önemli; otomatik güncelleme yapılacak servislerin başında olmalı.
