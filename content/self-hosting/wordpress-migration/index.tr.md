---
title: "Eski WordPress'i Mevcut Yapıya Taşımak"
description: "Eski bir sunucudaki WordPress sitesini veritabanı ve dosyalarıyla bu yapıya taşıma."
date: 2026-11-21T00:20:00+03:00
chapter: "10.1"
tags: ["wordpress", "mariadb"]
---
> [!abstract] Gerekenler
> - [10 WordPress Kurulumu](/self-hosting/wordpress/) bölümündeki MariaDB konteyneri kurulmuş ve `db` ağı oluşturulmuş olmalı.
> - [4.1 Docker Konteynerleri için Hazır Şablon](/self-hosting/docker-template/) tamamlanmış olmalı (`proxy.tmpl` ve `websocket.conf`).
>
> **Varsayımlar**
> - Eski sunucuda WordPress ve veritabanı olarak MariaDB çalışmaktadır. Örnek site `example.com`, eski sunucudaki site dizini `/var/www/example` olarak alınmıştır.
> - Yeni sunucudaki kullanıcımızın SSH ile eski sunucuya bağlanabildiği (SSH anahtarının eski sunucuda yetkili olduğu) varsayılmıştır.
> - Taşınan site `8031` portunu kullanmaktadır (WordPress için ayrılan `8030`–`8049` aralığından boş bir port seçilmeli).
> - Her komutun hangi sunucuda çalıştırıldığı başında belirtilmiştir. Yeni sunucuda root yetkisi gerekenler `sudo` ile yazılmıştır.

Eski sunucuda çalışan WordPress sitelerini yeni sunucuya, [10 WordPress Kurulumu](/self-hosting/wordpress/) bölümündeki yapıya uyacak şekilde taşıyacağız.

## İhtiyacımız Olanlar

Eski sunucudan iki şey alacağız:

1. **Veritabanı dökümü:** Sitenin veritabanının `.sql` dosyası. Yazılar, sayfalar, kullanıcılar, yorumlar ve tüm ayarlar burada.
2. **Site dosyaları:** WordPress dizininin tamamı. `wp-config.php`, `wp-content` (temalar, eklentiler, yüklenen görseller) ve varsa `.htaccess` bu dizinde.

Yeni sunucuda dosyalar şu şekilde duracak:

```text
/opt/docker/wp-example/
├── compose.yaml
├── php.ini
├── example.sql    ← veritabanı dökümü, içe aktarıldıktan sonra silinecek
└── html/          ← eski sitenin tüm dosyaları, konteynerde /var/www/html
```

> [!warning]
> Döküm dosyasını `html` dizininin dışında tutuyoruz. `html` sitenin kök dizini; içine konan her dosya internetten indirilebilir. Dökümün içinde kullanıcı bilgileri ve parola [hash'leri](term:hash) var.

## Adımlar

1. Eski sunucudan veritabanı dökümünü ve site dosyalarını almak
2. MariaDB'de site için veritabanı ve kullanıcı oluşturup dökümü içe aktarmak
3. `wp-config.php` dosyasını yeni yapıya göre düzenlemek ve [konteyneri](term:container) başlatmak
4. DNS'i değiştirmeden önce siteyi test etmek
5. DNS'i yeni sunucuya yönlendirip sertifika ve NGINX ayarlarını yapmak

## Hazırlık

*Eski sunucuda* sitenin veritabanı bilgilerini, tablo önekini ve varsa sabitlenmiş site adresini `wp-config.php` dosyasından alalım:

```bash
grep -E "DB_(NAME|USER|HOST|CHARSET)|table_prefix|WP_(HOME|SITEURL)" /var/www/example/wp-config.php
```

PHP ve MariaDB sürümlerine bakalım:

```bash
php -v
mariadb --version
```

> [!note]
> Konteynerde PHP 8.4 kullanacağız. Eski sunucu PHP 7.x kullanıyorsa eski tema ve eklentiler hata verebilir. Böyle bir durumda geçici olarak `php8.3-apache` [imajı](term:image) kullanılabilir (Aralık 2027'ye kadar destekleniyor), ama asıl çözüm eklentileri güncellemek.

> [!warning]
> Taşıma sırasında eski sitede yeni içerik (yazı, yorum, sipariş) oluşmamalı. Dökümden sonra eklenenler yeni sunucuya gelmez.

## Eski Sunucudan Verileri Alma

*Eski sunucuda* veritabanı dökümünü alalım:

```bash
(
umask 077
mariadb-dump --single-transaction --default-character-set=utf8mb4 -u <ESKI_KULLANICI> -p <ESKI_DB> > ~/example.sql
)
```

- **`umask 077`:** Döküm dosyası sadece bizim okuyabileceğimiz şekilde oluşsun. Parantez içindeki alt kabukta çalıştığı için oturumun geri kalanını etkilemiyor.
- **`--single-transaction`:** Site çalışırken tutarlı bir döküm alıyor, tabloları kilitlemiyor.
- **`--databases` kullanmıyoruz:** Bu parametre döküme eski veritabanının adıyla `CREATE DATABASE` ve `USE` satırları ekliyor. İçe aktarırken tablolar `wp_example` yerine eski isimli yeni bir veritabanına gider.

> [!note]
> MariaDB 10.4'ten eski sürümlerde komutun adı `mysqldump`.

*Yeni sunucuda* site dizinini oluşturalım ve dosyaları çekelim.

Yeni sunucunun SSH'ına sadece VPN'den erişilebildiği için eski sunucu yeni sunucuya bağlanamıyor. Bu yüzden yeni sunucudan eski sunucuya bağlanıp verileri çekiyoruz:

```bash
sudo mkdir -p /opt/docker/wp-example/html
sudo chown -R "$USER": /opt/docker/wp-example
cd /opt/docker/wp-example
rsync -a --info=progress2 <KULLANICI>@<ESKI_SUNUCU>:/var/www/example/ html/
scp <KULLANICI>@<ESKI_SUNUCU>:example.sql .
```

> [!note]
> Dosyaları normal kullanıcımızın SSH anahtarıyla çekebilmek için dizini geçici olarak kendi kullanıcımıza veriyoruz. Sahiplikleri aşağıda düzelteceğiz.

- `rsync` eski sunucuda da kurulu olmalı.
- Kaynak dizinin sonundaki `/` önemli; dizinin kendisini değil içeriğini `html` dizinine kopyalıyor.
- `<KULLANICI>` site dosyalarının hepsini okuyabilmeli. Okuyamıyorsa ve eski sunucuda sudo yetkisi varsa `rsync` komutuna `--rsync-path="sudo rsync"` eklenebilir.
- Eski sunucunun SSH portu farklıysa `rsync -e 'ssh -p <PORT>'` ve `scp -P <PORT>` kullanılmalı.
- Önbellek eklentisi kullanılıyorsa önbellek dizinini taşımaya gerek yok: `--exclude 'wp-content/cache/'`

## Veritabanı ve Kullanıcı

*Yeni sunucuda* site için bir veritabanı parolası oluşturalım:

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
> Dökümdeki tablolar kendi karakter seti ve [collation](term:collation) bilgileriyle oluşturuluyor; veritabanının varsayılanı sadece sonradan oluşturulacak tablolar için geçerli.

## Veritabanını İçe Aktarma

```bash
cd /opt/docker/wp-example
sudo docker exec -i mariadb sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" wp_example' < example.sql
```

> [!note]
> `-it` yerine `-i` kullanıyoruz. Döküm dosyasını konteynerin girdisine yönlendirdiğimiz için terminal (`-t`) açılmamalı.

Tabloların geldiğini kontrol edelim:

```bash
sudo docker exec -it mariadb sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" -e "SHOW TABLES" wp_example'
```

Tablolar eski sitenin tablo önekiyle (`wp_` veya farklı bir önek) listelenmeli.

## Dosyalar ve wp-config.php

Dosyaların sahipliğini düzenleyelim:

```bash
sudo chown -R 33:33 /opt/docker/wp-example/html
sudo chown root:root /opt/docker/wp-example
```

> [!note]
> Konteynerde Apache `www-data` (UID 33) kullanıcısıyla çalışıyor. Eklenti güncelleme, görsel yükleme gibi işlemler için dosyaların sahibi o olmalı. Site dizinini de tekrar root'a veriyoruz.

`/opt/docker/wp-example/html/wp-config.php` dosyasını açalım ve veritabanı bilgilerini yeni yapıya göre değiştirelim:

```php {title="/opt/docker/wp-example/html/wp-config.php"}
define( 'DB_NAME', 'wp_example' );
define( 'DB_USER', 'wp_example' );
define( 'DB_PASSWORD', '<DB_PAROLASI>' );
define( 'DB_HOST', 'mariadb' );
```

> [!note]
> `$table_prefix` değerine dokunmuyoruz; dökümdeki tablolar bu önekle oluşturuldu.

Aynı dosyada `/* That's all, stop editing! */` satırının üstüne aşağıdaki satırları ekleyelim:

```php {title="/opt/docker/wp-example/html/wp-config.php"}
if ( isset( $_SERVER['HTTP_X_FORWARDED_PROTO'] ) && strpos( $_SERVER['HTTP_X_FORWARDED_PROTO'], 'https' ) !== false ) {
    $_SERVER['HTTPS'] = 'on';
}
```

> [!important]
> Yeni kurulumda imajın oluşturduğu `wp-config.php` bunu zaten içeriyor. Taşınan sitenin kendi `wp-config.php` dosyası olduğu için imaj ona dokunmuyor, elle eklememiz gerekiyor. Eklenmezse WordPress NGINX'ten gelen isteği HTTP sanıyor ve sürekli HTTPS'e yönlendiriyor; tarayıcı "too many redirects" hatası veriyor.

Bazı eklentiler (önbellek, güvenlik ve [WAF](term:waf) eklentileri) eski sunucunun dizin yolunu dosyalara yazıyor. Eski yolun geçtiği dosyaları bulalım:

```bash
sudo grep -rlF '/var/www/example' /opt/docker/wp-example/html --include='*.php' --include='.htaccess' --include='.user.ini'
```

> [!note]
> Konteynerin içinde yeni yol `/var/www/html`. Bulunan dosyalarda yol düzeltilmeli veya ilgili eklentinin ayarları sıfırlanmalı.

`.htaccess` dosyasında PHP'yi farklı bir şekilde çalıştıran satırlar var mı bakalım:

```bash
sudo grep -nE 'AddHandler|SetHandler' /opt/docker/wp-example/html/.htaccess
```

> [!warning]
> Eski sunucuya veya hosting paneline özel `AddHandler` / `SetHandler` satırları, konteynerdeki Apache'de PHP'nin çalışmasını engelliyor. Bu durumda `.php` dosyaları çalıştırılmak yerine düz metin olarak sunulabilir ve `wp-config.php` içindeki parolalar açığa çıkar. Böyle satırlar varsa silinmeli.

> [!note]
> Eski sunucu [PHP-FPM](term:php-fpm) kullanıyorduysa `.user.ini` dosyasındaki PHP ayarları konteynerde okunmuyor. Gerekli ayarlar `php.ini` dosyasına taşınmalı.

## PHP Ayarları ve Compose

`/opt/docker/wp-example/php.ini` dosyasını aşağıdaki içerikle oluşturalım:

```ini {title="/opt/docker/wp-example/php.ini"}
upload_max_filesize = 64M
post_max_size = 64M
memory_limit = 256M
max_execution_time = 300
```

`/opt/docker/wp-example/compose.yaml` dosyasını aşağıdaki gibi oluşturalım:

```yaml {title="/opt/docker/wp-example/compose.yaml"}
services:
  wordpress:
    image: wordpress:php8.4-apache
    container_name: wp-example
    restart: unless-stopped
    ports:
      - "127.0.0.1:8031:80"
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

> [!note]
> Yeni kurulumdan farkı `environment` bölümünün olmaması. Veritabanı bilgileri `wp-config.php` dosyasında, `.env` dosyasına da gerek yok.

> [!note]
> `html` dizini dolu olduğu için imaj WordPress'i kopyalamıyor ve mevcut `wp-config.php` dosyasına dokunmuyor.

Konteyneri başlatalım:

```bash
sudo docker compose up -d
sudo docker logs wp-example 2>&1 | tail -5
```

## DNS'i Değiştirmeden Önce Test

DNS hâlâ eski sunucuyu gösterirken siteyi sunucunun içinden test edebiliriz. NGINX'in göndereceği başlıkları kendimiz göndererek konteynere doğrudan istek atalım:

```bash
curl -sI -H 'Host: example.com' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8031/
curl -s -H 'Host: example.com' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8031/ | grep -io '<title>.*</title>'
```

- `HTTP/1.1 200 OK` ve sitenin başlığı geliyorsa veritabanı bağlantısı ve `wp-config.php` doğru.
- `Error establishing a database connection` veya `500` hatası alıyorsak `wp-config.php`'deki veritabanı bilgileri ve `sudo docker logs wp-example` çıktısı kontrol edilmeli.
- Sürekli `https://example.com/` adresine `301` alıyorsak `wp-config.php`'ye HTTPS satırları eklenmemiş.
- Sitenin adresi `www` ile ayarlıysa (`https://www.example.com`) `Host` başlığında `www.example.com` kullanılmalı; yoksa `www` adresine bir yönlendirme dönmesi normal.

## DNS, Sertifika ve NGINX

Sertifikayı webroot yöntemiyle aldığımız için [Let's Encrypt](term:lets-encrypt) alan adını doğrularken yeni sunucuya ulaşmalı. Bu yüzden önce DNS'i değiştiriyoruz.

DNS'te `example.com` ve `www.example.com` için `A` ve `AAAA` kayıtlarını yeni sunucunun adresleriyle değiştirelim. `dig +short example.com` yeni IP adresini döndürdüğünde sertifikayı alalım:

```bash
sudo certbot certonly --webroot -w /opt/www/well_known -d example.com -d www.example.com
```

> [!tip]
> DNS kaydının [TTL](term:ttl) değeri yüksekse değişikliğin yayılması uzun sürebilir. Taşımadan bir gün önce TTL'i düşük bir değere (ör. 300) çekmek bu süreyi kısaltır.

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

    location = /xmlrpc.php {
        deny all;
    }

    location / {
        proxy_pass http://127.0.0.1:8031;
        include /etc/nginx/templates/proxy.tmpl;
    }
}
```

> [!note]
> Site zaten kurulu olduğu için kurulum sihirbazı adımı ve `vpn-only` satırı yok. Satırların açıklamaları [10 WordPress Kurulumu](/self-hosting/wordpress/) bölümündeki **Sertifika ve NGINX Reverse Proxy** kısmında.

NGINX yapılandırmasını test edip yeniden yükleyelim:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

> [!note]
> DNS değişikliği yayılana kadar bazı ziyaretçiler eski sunucuya gitmeye devam eder; eski siteyi birkaç gün kapatmayalım.

## Alan Adı veya Adres Değiştiyse

Site eski sunucuda `http://` ile çalışıyorduysa veya alan adı değiştiyse veritabanındaki adresleri değiştirmemiz gerekiyor.

Bunun için döküm dosyası üzerinde `sed` kullanmıyoruz. WordPress bazı ayarları [serialize edilmiş](term:serialization) şekilde, yani metnin karakter sayısıyla birlikte saklıyor. `sed` ile adresin uzunluğu değişince bu veriler bozuluyor. [WP-CLI](term:wp-cli) değiştirirken karakter sayılarını da düzeltiyor.

```bash
sudo docker run --rm --user 33:33 --volumes-from wp-example --network container:wp-example \
    wordpress:cli wp search-replace 'http://eski.com' 'https://example.com' --all-tables --skip-columns=guid --dry-run
```

- **`--dry-run`:** Değişiklik yapmadan kaç kaydın değişeceğini gösteriyor. Sonuç mantıklıysa `--dry-run` olmadan tekrar çalıştıralım.
- **`--volumes-from` ve `--network container:`:** WP-CLI konteyneri sitenin dosyalarını ve ağını kullanıyor; `wp-config.php`'deki bilgilerle MariaDB'ye bağlanıyor.
- **`--user 33:33`:** WP-CLI imajı Alpine tabanlı ve varsayılan kullanıcısının UID'i farklı (82). Dosyalara site konteyneriyle aynı kullanıcıyla erişsin.
- **`--skip-columns=guid`:** Yazıların `guid` değeri kalıcı kimlik olarak kullanılıyor; RSS okuyucular eski yazıları yeni yazı sanmasın diye değiştirmiyoruz.

> [!note]
> `wp-config.php`'de `WP_HOME` veya `WP_SITEURL` tanımlıysa (Hazırlık kısmındaki `grep` çıktısı) site adresi veritabanından değil bu satırlardan geliyor; onlar da güncellenmeli.

Site adresini kontrol edelim:

```bash
sudo docker run --rm --user 33:33 --volumes-from wp-example --network container:wp-example \
    wordpress:cli wp option get siteurl
```

> [!note]
> [10 WordPress Kurulumu](/self-hosting/wordpress/) bölümündeki gibi sıfırdan kurulmuş sitelerde `wp-config.php` veritabanı bilgilerini ortam değişkenlerinden okuyor. O sitelerde WP-CLI'a da aynı değişkenler verilmeli (`-e WORDPRESS_DB_HOST=mariadb -e WORDPRESS_DB_NAME=... -e WORDPRESS_DB_USER=... -e WORDPRESS_DB_PASSWORD=...`).

## Son Kontroller

- Ana sayfa, yazı sayfaları ve görseller açılıyor mu?
- Yazı sayfalarında 404 alıyorsak **Ayarlar → Kalıcı Bağlantılar → Değişiklikleri Kaydet**. WordPress `.htaccess` dosyasını yeniden yazıyor. Eski sunucu NGINX kullanıyorduysa `.htaccess` dosyası yoktur ve bu adım gerekli.
- **Ayarlar → Genel** sayfasında WordPress Adresi ve Site Adresi `https://example.com` olmalı.
- **Araçlar → Site Sağlığı** sayfasında kritik bir sorun olmamalı.
- Önbellek eklentisi varsa önbelleği temizleyelim.
- İletişim formu ve şifre sıfırlama mailleri gidiyor mu? Gitmiyorsa [10 WordPress Kurulumu](/self-hosting/wordpress/) bölümündeki **Mail Gönderimi** kısmına bakılmalı. Eski sitede bir [SMTP](term:smtp) eklentisi eski mail sunucusuna göre ayarlıysa ayarları güncellenmeli.

Döküm dosyalarını silelim; içlerinde kullanıcı bilgileri ve parola hash'leri var.

*Yeni sunucuda:*

```bash
sudo rm /opt/docker/wp-example/example.sql
```

*Eski sunucuda:*

```bash
rm ~/example.sql
```
