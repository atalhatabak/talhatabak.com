---
title: "WordPress Kurulumu"
description: "Her sitenin kendi konteynerinde çalıştığı, ortak bir MariaDB konteyneri kullanan WordPress yapısı."
date: 2026-11-21T00:19:00+03:00
chapter: "10"
tags: ["wordpress", "docker", "mariadb"]
---
> [!abstract] Gerekenler
> - [3 NGINX Yapılandırması](/self-hosting/nginx/), [4 Docker Kurulumu](/self-hosting/docker/) ve [4.1 Docker Konteynerleri için Hazır Şablon](/self-hosting/docker-template/) tamamlanmış olmalı.
> - Sitelerin mail gönderebilmesi için [2 Mail Sunucu Kurulumu](/self-hosting/mail-server/) tamamlanmış olmalı.
> - Kurulum sihirbazını VPN arkasında tamamlamak için [7.2 Servisleri VPN Arkasına Almak](/self-hosting/services-behind-vpn/) tamamlanmış olmalı.
>
> **Varsayımlar**
> - Örnek site `example.com`, sitenin kısa adı `example` olarak alınmıştır. Kısa ad dizin, konteyner ve veritabanı adlarında kullanılıyor; her site için `example` geçen yerler sitenin adıyla değiştirilmeli.
> - `example.com` ve `www.example.com` için `A` ve `AAAA` kayıtlarının girildiği varsayılmıştır.
> - WordPress siteleri için `8030`–`8049` port aralığı ayrılmıştır; ilk site `8030` portunu kullanmaktadır.
> - Komutlar sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır.

WordPress sitelerini Docker ile kuracağız. Her site kendi [konteynerinde](term:container) çalışacak ve tüm siteler ortak bir MariaDB konteynerini kullanacak.

## Mimari

```text
                      ┌→ 127.0.0.1:8030 → wp-example ──┐
İnternet → NGINX:443 ─┤                                ├─ db ağı (internal) → mariadb
                      └→ 127.0.0.1:8031 → wp-diger ────┘
```

- Her site resmi `wordpress` [imajıyla](term:image) kendi konteynerinde çalışıyor (Apache + PHP).
- Tüm siteler tek bir MariaDB konteynerini kullanıyor. Her sitenin kendi veritabanı ve sadece o veritabanına yetkisi olan kendi kullanıcısı var.
- MariaDB `db` adında `internal` bir Docker ağında. Bu ağa sadece WordPress konteynerleri bağlı; MariaDB'ye host'tan veya internetten erişilemiyor, MariaDB'nin de internete çıkışı yok.
- Site dosyaları host'ta `/opt/docker/wp-<site>/html` dizininde duruyor.
- WordPress konteynerleri diğer servisler gibi sadece `127.0.0.1` üzerinde port açıyor ve NGINX ile dışarıya sunuluyor.

> [!note]
> Neden tek MariaDB: Her site için ayrı bir MariaDB konteyneri, her biri için ayrıca RAM harcanması demek. Bu ölçekte tek MariaDB yeterli; siteler arası izolasyonu her siteye ayrı veritabanı kullanıcısı vererek sağlıyoruz.

> [!note]
> Ortak `db` ağı WordPress konteynerlerini birbirine de bağlıyor; ele geçirilmiş bir site diğer sitelere NGINX'i atlayarak doğrudan 80 portundan erişebilir. Siteler zaten internete açık olduğu için bu ek bir yetki vermiyor; tek fark NGINX'teki kısıtlamaların (`vpn-only`, Fail2Ban) atlanması. Tam ayrım istenirse her site için ayrı bir internal ağ oluşturulup MariaDB bu ağların hepsine bağlanabilir.

> [!note]
> Host'taki MariaDB'yi ([iRedMail'in](term:iredmail) kurduğu) kullanmıyoruz. Mail sunucusunun veritabanı ile web sitelerinin veritabanı birbirinden ayrı kalsın.

## MariaDB Konteyneri

Bu bölüm tüm siteler için bir kez yapılıyor.

Dizini oluşturalım ve root parolasını rastgele üreterek `.env` dosyasına yazalım:

```bash
sudo mkdir -p /opt/docker/mariadb
cd /opt/docker/mariadb
sudo sh -c 'umask 077; echo "MARIADB_ROOT_PASSWORD=$(openssl rand -hex 24)" > .env'
```

> [!note]
> `cd` ve yönlendirme (`>`) kabuğun kendi işlemleri olduğu için `sudo cd` veya `sudo echo ... > .env` şeklinde yazıldıklarında root yetkisiyle çalışmıyorlar. Bu yüzden dosyayı `sudo sh -c` ile tek bir root kabuğunda oluşturuyoruz; `umask 077` dosyanın sadece root tarafından okunabilmesini sağlıyor.

`/opt/docker/mariadb/compose.yaml` dosyasını aşağıdaki gibi oluşturalım:

```yaml {title="/opt/docker/mariadb/compose.yaml"}
services:
  mariadb:
    image: mariadb:11.4
    container_name: mariadb
    restart: unless-stopped
    environment:
      MARIADB_ROOT_PASSWORD: ${MARIADB_ROOT_PASSWORD}
      MARIADB_AUTO_UPGRADE: "1"
      MARIADB_ROOT_HOST: localhost
    volumes:
      - ./data:/var/lib/mysql
    networks:
      - db

networks:
  db:
    name: db
    internal: true
```

Her satırın neden eklendiği:

1. **`ports` yok:** MariaDB'ye sadece `db` ağındaki konteynerler erişecek, host'a port açmıyoruz.
2. **`${MARIADB_ROOT_PASSWORD}`:** [Docker Compose](term:docker-compose) bu değeri aynı dizindeki `.env` dosyasından okuyor; parola compose dosyasında açıkta durmuyor.
3. **`MARIADB_AUTO_UPGRADE: "1"`:** İmaj güncellendiğinde veritabanı dosyaları yeni sürüme otomatik olarak yükseltiliyor.
4. **`MARIADB_ROOT_HOST: localhost`:** Ağ üzerinden root erişimine ihtiyacımız olmadığı için `root@'%'` kullanıcısının oluşturulmasını engelliyoruz. Root erişimi sadece konteynerin içinden yapılabilecek.
5. **`name: db`:** Ağın adını sabitliyoruz. Compose normalde ağ adının başına proje adını ekliyor (`mariadb_db`); WordPress compose dosyalarından bu ağa `db` adıyla bağlanacağız.
6. **`internal: true`:** Bu ağdaki konteynerlerin internete çıkışı yok. MariaDB'nin internete ihtiyacı yok, WordPress konteynerleri internete kendi ağları üzerinden çıkacak.

Servisi başlatalım:

```bash
sudo docker compose up -d
sudo docker logs mariadb 2>&1 | tail -3
```

Çıktıda `ready for connections` görünüyorsa MariaDB hazır.

> [!note]
> `MARIADB_ROOT_PASSWORD` sadece ilk çalıştırmada, `data` dizini boşken kullanılıyor. Sonradan `.env` dosyasındaki parolayı değiştirmek root parolasını değiştirmiyor. Değiştirmek istersek önce MariaDB'de `ALTER USER` ile, ardından `.env` dosyasında değiştirmeliyiz.

MariaDB'ye root ile bağlanmak için:

```bash
sudo docker exec -it mariadb sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD"'
```

> [!note]
> Parola konteynerin içindeki `MARIADB_ROOT_PASSWORD` değişkeninden okunuyor, elle yazmamıza gerek kalmıyor. Tek tırnak önemli; değişken host'ta değil konteynerin içinde açılmalı.

## Yeni Site Kurulumu

Bu bölüm her yeni site için tekrarlanıyor. İlk site için `8030` portunu kullanacağım.

### Veritabanı ve Kullanıcı

Site için bir veritabanı parolası oluşturalım:

```bash
openssl rand -hex 24
```

> [!note]
> Çıkan parolayı aşağıda `<DB_PAROLASI>` yazan yerlerde kullanacağız.

MariaDB'ye bağlanalım:

```bash
sudo docker exec -it mariadb sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD"'
```

ve sitenin veritabanını ve kullanıcısını oluşturalım:

```sql
CREATE DATABASE wp_example CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'wp_example'@'%' IDENTIFIED BY '<DB_PAROLASI>';
GRANT ALL PRIVILEGES ON wp_example.* TO 'wp_example'@'%';
exit
```

> [!note]
> `'%'` her adresten bağlanabilir demek. MariaDB'ye sadece `db` ağından erişilebildiği için bu bir sorun değil.

> [!note]
> Kullanıcının yetkisi sadece kendi veritabanında. Bir site ele geçirilse bile diğer sitelerin veritabanlarına erişilemez.

### Site Dizini

```bash
sudo mkdir -p /opt/docker/wp-example
cd /opt/docker/wp-example
```

`/opt/docker/wp-example/.env` dosyasını aşağıdaki içerikle oluşturalım:

```ini {title="/opt/docker/wp-example/.env"}
DB_PASSWORD=<DB_PAROLASI>
```

```bash
sudo chmod 600 .env
```

### PHP Ayarları

İmajın varsayılan PHP ayarlarında dosya yükleme sınırı 2 MB. Bu sınır tema, eklenti veya büyük görsel yüklerken sorun çıkarıyor; kendi ayarlarımızı ekleyelim.

`/opt/docker/wp-example/php.ini` dosyasını aşağıdaki içerikle oluşturalım:

```ini {title="/opt/docker/wp-example/php.ini"}
upload_max_filesize = 64M
post_max_size = 64M
memory_limit = 256M
max_execution_time = 300
```

### Compose

`/opt/docker/wp-example/compose.yaml` dosyasını aşağıdaki gibi oluşturalım:

```yaml {title="/opt/docker/wp-example/compose.yaml"}
services:
  wordpress:
    image: wordpress:php8.4-apache
    container_name: wp-example
    restart: unless-stopped
    ports:
      - "127.0.0.1:8030:80"
    environment:
      WORDPRESS_DB_HOST: mariadb
      WORDPRESS_DB_NAME: wp_example
      WORDPRESS_DB_USER: wp_example
      WORDPRESS_DB_PASSWORD: ${DB_PASSWORD}
    volumes:
      - ./html:/var/www/html
      - ./php.ini:/usr/local/etc/php/conf.d/custom.ini:ro
    networks:
      - default
      - db

networks:
  db:
    external: true
```

Her satırın neden eklendiği:

1. **`wordpress:php8.4-apache`:** İmaj sadece PHP ve Apache'yi sağlıyor. PHP sürümünü sabitliyoruz; eklentilerin uyumluluğunu kontrol etmeden PHP sürümü değişmesin.
2. **`WORDPRESS_DB_HOST: mariadb`:** MariaDB konteynerinin adı; `db` ağında bu isimle çözülüyor.
3. **`./html:/var/www/html`:** WordPress dosyaları (çekirdek, temalar, eklentiler, yüklemeler) host'ta duruyor. Dizin boşsa imaj ilk çalıştırmada WordPress'i buraya kopyalıyor.
4. **`./php.ini`:** Kendi PHP ayarlarımız. `:ro` ile konteyner bu dosyayı sadece okuyabiliyor.
5. **`networks: default, db`:** `default` ağı ile internete çıkıyor (güncellemeler, eklentiler) ve port açıyor, `db` ağı ile MariaDB'ye erişiyor.
6. **`external: true`:** `db` ağı bu compose dosyasında oluşturulmuyor; MariaDB'nin compose dosyasının oluşturduğu ağa bağlanıyoruz. Bu yüzden MariaDB konteyneri önceden kurulmuş olmalı.

Konteyneri başlatalım:

```bash
sudo docker compose up -d
sudo ls html
sudo docker logs wp-example 2>&1 | tail -5
```

`html` dizininde `wp-admin`, `wp-content`, `wp-config.php` gibi dosyalar oluşmuş olmalı.

> [!note]
> İmaj `wp-config.php` dosyasını kendi şablonuyla oluşturuyor. Veritabanı bilgilerini ortam değişkenlerinden okuyor ve güvenlik anahtarlarını ([salt](term:salt)) rastgele üretiyor. Aynı şablon NGINX'ten gelen `X-Forwarded-Proto` başlığına bakarak HTTPS arkasında çalıştığını anlıyor; ek bir ayar gerekmiyor.

> [!note]
> İmajda Apache'nin `remoteip` modülü açık; loglarda ve WordPress'te ziyaretçinin gerçek IP adresi (`X-Forwarded-For`) görünüyor.

> [!note]
> Sunucu yeniden başladığında WordPress konteyneri MariaDB'den önce açılırsa birkaç saniye "Error establishing a database connection" hatası verebilir; MariaDB açılınca kendiliğinden düzelir.

### Sertifika ve NGINX Reverse Proxy

Sertifikayı alalım:

```bash
sudo certbot certonly --webroot -w /opt/www/well_known -d example.com -d www.example.com
```

`/etc/nginx/vhost.d/vhost_example.com.conf` dosyasını aşağıdaki gibi oluşturalım:

```nginx {title="/etc/nginx/vhost.d/vhost_example.com.conf"}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name example.com www.example.com;

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    client_max_body_size 64m;

    # Kurulum sihirbazı tamamlanana kadar, sonra kaldırılacak
    include /etc/nginx/templates/vpn-only.tmpl;

    location = /xmlrpc.php {
        deny all;
    }

    location / {
        proxy_pass http://127.0.0.1:8030;
        include /etc/nginx/templates/proxy.tmpl;
    }
}
```

- **`client_max_body_size 64m`:** `php.ini`'deki yükleme sınırıyla aynı. iRedMail kurulumu 12m tanımlıyor ve daha büyük yüklemeleri PHP'ye ulaşmadan reddediyor.
- **`vpn-only.tmpl`:** [Let's Encrypt](term:lets-encrypt) aldığımız her sertifikayı herkese açık [Certificate Transparency](term:certificate-transparency) loglarına yazıyor. Bazı botlar bu loglarda yeni çıkan alan adlarını takip edip yarım kalmış WordPress kurulumlarını arıyor; sihirbazı ilk tamamlayan yönetici oluyor. Bu yüzden sihirbaz tamamlanana kadar siteye sadece VPN'den erişilebilecek.
- **`xmlrpc.php`:** Eski bir uzaktan erişim API'si; [brute force](term:brute-force) ve [DDoS](term:ddos) saldırılarının sık kullandığı bir hedef. Jetpack veya WordPress mobil uygulaması kullanılacaksa bu blok kaldırılmalı.
- `www.example.com`'a gelen istekleri WordPress kendisi site adresine (`example.com`) yönlendiriyor.

NGINX yapılandırmasını test edip yeniden yükleyelim:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### Kurulum Sihirbazı

VPN'e [full tunnel](term:full-tunnel) ile bağlanıp `https://example.com` adresine giderek kurulum sihirbazını tamamlayalım:

- Yönetici kullanıcı adı olarak `admin` kullanmayalım; brute force denemelerinin ilk denediği kullanıcı adı.
- Parolayı güçlü seçip parola yöneticisine kaydedelim.

> [!note]
> [Split tunnel'da](term:split-tunnel) alan adı sunucunun public IP'sine çözüldüğü için istek VPN'den geçmiyor ve 403 alınıyor (bkz. [7.3 Olası Problemler](/self-hosting/wireguard-troubleshooting/)).

Sihirbaz tamamlandıktan sonra [virtual host'taki](term:virtual-host) `include /etc/nginx/templates/vpn-only.tmpl;` satırını silelim ve NGINX'i yeniden yükleyelim:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### Kontrol

```bash
curl -I https://example.com   # HTTP/2 200
```

Yönetim panelinde **Araçlar → Site Sağlığı** (Tools → Site Health) sayfasında kritik bir sorun olmamalı.

## Ek Ayarlar

### Mail Gönderimi

WordPress konteynerinde mail sunucusu yok, PHP'nin `mail()` fonksiyonu çalışmıyor. Şifre sıfırlama, yeni kullanıcı ve iletişim formu mailleri gitmez. Bir [SMTP](term:smtp) eklentisi (WP Mail SMTP vb.) kurup kendi mail sunucumuzu kullanalım:

| Ayar        | Değer                                     |
| ----------- | ----------------------------------------- |
| SMTP sunucu | `mail.xenonly.com`                        |
| Port        | 587 ([STARTTLS](term:starttls))                            |
| Kullanıcı   | [iRedAdmin'de](term:iredadmin) site için açılan mail hesabı |

> [!note]
> Konteyner `mail.xenonly.com`'u sunucunun public IP'sine çözüyor ve bağlantı host'a Docker ağı üzerinden geliyor. Firewalld'de `docker` [zone'unun](term:firewalld-zone) target'ı ACCEPT olduğu için ek bir izin gerekmiyor.

> [!note]
> Mailler `@example.com` adresinden gidecekse alan adı iRedAdmin'e eklenmeli ve DNS'te [SPF](term:spf), [DKIM](term:dkim) ve [DMARC](term:dmarc) kayıtları girilmeli (bkz. [2.2 Mail Sunucusu Yeni Alan Adı Ekleme](/self-hosting/mail-server-new-domain/)). Alternatif olarak `xenonly.com` altında açılmış bir hesaptan gönderilebilir.

### Güncellemeler

- **WordPress, tema ve eklentiler:** Dosyalar `html` dizininde duruyor; yönetim panelinden veya otomatik güncellemelerle güncelleniyor. İmaj güncellemesi WordPress'i güncellemiyor.
- **PHP ve Apache:** Site dizininde `sudo docker compose pull && sudo docker compose up -d`.
- **PHP sürümünü yükseltme:** Compose dosyasındaki imaj etiketini değiştirmek yeterli (ör. `php8.4-apache` → `php8.5-apache`). Önce eklentilerin yeni sürümle uyumluluğuna bakılmalı.
- **MariaDB:** MariaDB dizininde `sudo docker compose pull && sudo docker compose up -d`. İmaj etiketi `11.4` olduğu için 11.4 sürümü içinde kalıyor.
