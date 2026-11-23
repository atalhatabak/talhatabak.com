---
title: "NGINX Yapılandırması"
description: "iRedMail'in kurduğu NGINX yapılandırmasını, birden fazla servisi ve virtual host'u sunabilecek hale getirme."
date: 2026-11-21T00:08:00+03:00
chapter: "3"
tags: ["nginx"]
---
> [!abstract] Gerekenler
> - [2 Mail Sunucu Kurulumu](/self-hosting/mail-server/) ve [2.1 Mail Sunucusu için SSL Ayarlama](/self-hosting/mail-server-ssl/) tamamlanmış olmalı.
>
> **Varsayımlar**
> - NGINX'in iRedMail tarafından kurulduğu ve yapılandırıldığı varsayılmıştır (Rocky Linux 10 deposundaki 1.26 sürümü).
> - `mail.xenonly.com` ve `iredadmin.xenonly.com` için `A` ve `AAAA` kayıtlarının girildiği varsayılmıştır.
> - Komutlar sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır.

## Mevcut Yapılandırmayı Anlama

### iRedMail'in Varsayılan Tasarımı

Sistemdeki NGINX'i [iRedMail](term:iredmail) kurdu ve yapılandırmasını değiştirdi.

> [!note]
> `/etc/nginx/nginx.conf` içindeki `include` direktifi normal [RHEL](term:rhel) kurulumlarında `conf.d` dizinini içerir. iRedMail tüm dağıtımlarda aynı dizin yapısını kullandığı için kurulumda `nginx.conf`'u yeniden yazıyor ve `sites-enabled` ile `conf-enabled` dizinlerini include ediyor.

Ben bu yapıyı uygulama kısmında şu şekilde değiştireceğim:

- Yapılandırma dosyaları için `conf.d`
- [Virtual host](term:virtual-host) tanımları için `vhost.d`

### Şablonlar (/etc/nginx/templates)

`/etc/nginx/templates` altında iRedMail'in getirdiği varsayılan şablonlar var. `netdata.tmpl`, `netdata-subdomain.tmpl`, `sogo.tmpl`, `sogo-subdomain.tmpl` ve `adminer.tmpl` şablonları kullanılmayacak, bunları uygulama kısmında sileceğiz.

Diğer şablonları inceleyelim.

#### fastcgi_php.tmpl

> PHP isteklerini [PHP-FPM'e](term:php-fpm) (`php_workers` → `127.0.0.1:9999`) iletmek için ortak ayarları içeriyor. [Roundcube](term:roundcube) ve diğer PHP blokları bu dosyayı include ediyor.

#### hsts.tmpl

> Tarayıcıya `Strict-Transport-Security` başlığı gönderiyor. Bu başlığı alan tarayıcı siteye 1 yıl boyunca sadece HTTPS üzerinden bağlanıyor.

Mevcut NGINX sürümü (1.26) `add_header_inherit` direktifini desteklemiyor. Bu yüzden bir virtual host'ta veya location bloğunda `add_header` tanımlanırsa `conf.d/headers.conf` içindeki başlıklar o blokta uygulanmıyor.

`hsts.tmpl` şablonu `roundcube-subdomain.tmpl`, `roundcube.tmpl` ve `iredadmin-subdomain.tmpl` şablonlarından include ediliyor.

Bu yüzden uygulama kısmında `hsts.tmpl` içindeki tanımı `headers.conf`'a ekleyeceğiz, bu üç şablondaki include satırlarını kaldıracağız ve `hsts.tmpl`'yi sileceğiz.

#### iredadmin-subdomain.tmpl

> iRedMail kurulumundan gelen yönetim panelini alt alan adı üzerinden sunmak için hazır yapılandırma. Biz de sistemde bunu kullanacağız.

#### iredadmin.tmpl

> iRedMail kurulumundan gelen yönetim paneli için; `/iredadmin` yoluna gelen istekleri [iRedAdmin'e](term:iredadmin) yönlendiriyor.

iRedAdmin'i alt alan adında sunacağımız için bunu uygulama kısmında sileceğiz.

#### misc.tmpl

- HTTPS üzerinden gelen `.well-known` isteklerini işliyor
- Gizli dosyalara erişimi engelliyor
- `favicon.ico` ve `robots.txt` isteklerinin loglanmasını kapatıyor

#### php-catchall.tmpl

> Önceki şablonlarda yakalanmayan tüm `.php` isteklerini PHP-FPM'e iletiyor.

Bu istediğimiz bir durum değil; neyin nerede çalışacağını kendimiz belirleyeceğiz. Bu yüzden buna ihtiyacımız yok, uygulama kısmında sileceğiz.

#### redirect_to_https.tmpl

> `sogo`, `iredadmin` ve `mail` yollarına gelen istekleri HTTPS'e yönlendiriyor.

Şu anki yapıda zaten gelen her istek HTTPS'e yönlendiriliyor. İhtiyacımız yok, uygulama kısmında sileceğiz.

#### roundcube-subdomain.tmpl

> Roundcube webmail'i alt alan adı üzerinden sunmak için hazır yapılandırma.

#### roundcube.tmpl

> Roundcube webmail için kullanılıyor; `/mail` yoluna gelen istekleri Roundcube'a yönlendiriyor.

Bu sistemde Roundcube alt alan adında sunulacak, ama farklı alan adları için `/mail` yolu üzerinden sunmamız gerekebilir. Bu yüzden silmeyeceğim.

#### ssl.tmpl

> HTTPS için standart SSL ayarları ve mail sunucusunu kurduğumuz iRedMail'in kullandığı SSL sertifikasının tanımı.

Bu sunucuyu birden fazla servis ve virtual host için kullanacağımızdan uygulama kısmında buradaki sertifika tanımını kaldıracağız.

Ayrıca `ssl.tmpl` içindeki tanımlar http seviyesinde de tanımlanabiliyor ve bu tanımları her virtual host için kullanacağız. Bu yüzden her virtual host yapılandırmasına include etmek yerine `conf.d` dizinine taşıyacağız.

#### stub_status.tmpl

> NGINX (`/stub_status`) ve PHP-FPM (`/status`) durum sayfalarını izleme araçları için sadece `localhost` üzerinden erişilecek şekilde sunuyor.

Kullanmayı düşünmüyorum, bu yüzden uygulama kısmında sileceğim.

### Yapılandırma Dosyaları (/etc/nginx/conf-available → conf.d)

> http {} seviyesinde uygulanıyor; virtual host veya location bloğunda özel olarak tanımlanmazsa her istekte geçerli oluyor.

Sadece değiştirilmesi gerekenleri inceleyeceğim.

#### Değiştirilecekler

##### cache.conf

Güncel JavaScript [MIME](term:mime) türlerini (`application/javascript`, `text/javascript`) ekleyeceğiz.

##### headers.conf

Artık kullanılmayan `X-XSS-Protection` ve `X-Download-Options` başlıklarını kaldıracağız ve `hsts.tmpl`'deki `Strict-Transport-Security` tanımını buraya ekleyeceğiz. iRedMail'in tanımladığı `Content-Security-Policy` başlığını da kaldıracağız.

### Virtual Host'lar (/etc/nginx/sites-available → vhost.d)

> Mevcut yapılandırmada sadece varsayılan virtual host tanımları ve bunların içine include edilen şablonlar bulunuyor.

#### 00-default.conf

Varsayılan hâli kabaca şunları yapıyor:

- 80 portunu (HTTP) dinliyor
- SSL için `.well-known/acme-challenge` isteklerini `/opt/www/well_known` dizininden sunuyor
- Gelen diğer tüm istekleri HTTPS'e yönlendiriyor

#### 00-default-ssl.conf

Varsayılan hâli kabaca şunları yapıyor:

- 443 portunu (HTTPS) dinliyor
- Kök dizin olarak `/var/www/html`, index olarak `index.php` tanımlı
- Ardından `templates` dizinindeki bir dizi şablonu include ediyor

Varsayılan olarak aşağıdaki dosyalar include ediliyor:

```text
misc.tmpl         → Gereken yerlerde vhost içine include edilecek
ssl.tmpl          → conf.d'ye taşınacak
iredadmin.tmpl    → Alt alan adında sunulacak
roundcube.tmpl    → Alt alan adında sunulacak
php-catchall.tmpl → Kullanılmayacak
stub_status.tmpl  → Kullanılmayacak
```

### Oluşturmak İstediğimiz Mimari

80 portuna (HTTP) gelen, `acme challenge` dışındaki her istek 443 (HTTPS)'e yönlendirilsin. `conf.d` dizini gelen her istek için varsayılan ayarları, `vhost.d` dizini de her virtual host'a özel yapılandırmaları barındırsın.

## Uygulama

### Dizin Yapısı

Anlama kısmında belirttiğimiz gibi yapılandırma dosyaları için `conf.d`, virtual host tanımları için `vhost.d` dizinlerini kullanacağız.

`conf-available` dizininin tamamı `conf.d` olacağı için, `conf-enabled` altında bağlantısı olmayan (yani şu an kullanılmayan) bir dosya varsa o da yüklenmeye başlar. Taşımadan önce iki dizini karşılaştıralım:

```bash
ls /etc/nginx/conf-available
ls -l /etc/nginx/conf-enabled
```

Ardından dizinleri düzenleyelim:

```bash
cd /etc/nginx
sudo rm -rf conf.d # Eğer varsa, mevcut durumda kullanılmıyor zaten
sudo mv conf-available conf.d
sudo mv sites-available vhost.d
sudo rm -rf sites-enabled conf-enabled
```

ve `nginx.conf` içindeki `conf-enabled` ve `sites-enabled` include satırlarını aşağıdaki gibi değiştirelim:

```nginx {title="/etc/nginx/nginx.conf"}
http {
    ...
    # Requires Nginx 1.25.1+.
    # http2 on;
    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/vhost.d/*.conf;
}
```

### Şablonlar

#### hsts.tmpl

Anlama kısmında belirttiğimiz gibi `hsts.tmpl` şablonu üç şablondan include ediliyor:

```bash
sudo grep -rn hsts.tmpl /etc/nginx/templates
```

```text
/etc/nginx/templates/iredadmin-subdomain.tmpl:4:include /etc/nginx/templates/hsts.tmpl;
/etc/nginx/templates/roundcube-subdomain.tmpl:19:    include /etc/nginx/templates/hsts.tmpl;
/etc/nginx/templates/roundcube-subdomain.tmpl:23:    include /etc/nginx/templates/hsts.tmpl;
/etc/nginx/templates/roundcube-subdomain.tmpl:28:    include /etc/nginx/templates/hsts.tmpl;
/etc/nginx/templates/roundcube.tmpl:27:    include /etc/nginx/templates/hsts.tmpl;
/etc/nginx/templates/roundcube.tmpl:32:    include /etc/nginx/templates/hsts.tmpl;
```

Bu üç şablondaki `include /etc/nginx/templates/hsts.tmpl;` satırlarını silelim:

```bash
sudo sed -i '/hsts.tmpl/d' /etc/nginx/templates/{iredadmin-subdomain,roundcube-subdomain,roundcube}.tmpl
```

`hsts.tmpl` içindeki tanımı aşağıda `headers.conf`'a ekleyeceğiz, şablonun kendisini ise kullanılmayan şablonlarla birlikte sileceğiz.

#### ssl.tmpl

`/etc/nginx/templates/ssl.tmpl` içinde `ssl_certificate` ve `ssl_certificate_key` ile başlayan satırları silelim ve dosyayı `conf.d` dizinine taşıyalım:

```bash
sudo sed -i '/^\s*ssl_certificate/d' /etc/nginx/templates/ssl.tmpl
sudo mv /etc/nginx/templates/ssl.tmpl /etc/nginx/conf.d/ssl.conf
```

### Yapılandırma Dosyaları

#### cache.conf

`/etc/nginx/conf.d/cache.conf` aşağıdaki gibi olacak:

```nginx {title="/etc/nginx/conf.d/cache.conf"}
map $sent_http_content_type $expires {
    default                     off;
    application/javascript      1d;
    text/javascript             1d;
    application/x-javascript    1d;
    text/css                    1d;
    ~image/                     1d;
}

expires $expires;
```

> [!note]
> `map` sadece `$expires` değişkenini tanımlıyor. Değişkenin kullanılması için en alttaki `expires $expires;` satırı gerekli; bu satır olmadan map hiçbir etki yapmaz.

#### headers.conf

`/etc/nginx/conf.d/headers.conf` dosyasını aşağıdaki gibi düzenleyelim:

```nginx {title="/etc/nginx/conf.d/headers.conf"}
add_header Strict-Transport-Security "max-age=31536000" always;
add_header X-Frame-Options sameorigin always;
add_header X-Content-Type-Options nosniff always;
add_header X-Permitted-Cross-Domain-Policies none always;
add_header Referrer-Policy strict-origin always;
```

> [!note]
> `always` parametresi olmadan NGINX başlıkları sadece başarılı ve yönlendirme yanıtlarına (200, 301, 304 vb.) ekliyor; 403, 404 ve 5xx yanıtlarında göndermiyor.

> [!note]
> iRedMail'in tanımladığı `Content-Security-Policy` başlığını kaldırdık. `default-src https: data: 'unsafe-inline' 'unsafe-eval'` değeri her HTTPS kaynağa, satır içi script'lere ve `eval`'a izin verdiği için [XSS'e](term:xss) karşı neredeyse hiçbir koruma sağlamıyor. Buna karşılık http seviyesinde tanımlandığı için NGINX arkasındaki tüm uygulamalara gidiyor ve `blob:` ile `wss:` kaynaklarını engellediği için uygulamaları bozabiliyor. [CSP'ye](term:csp) ihtiyaç duyan uygulamalar (ör. Vaultwarden) kendi başlığını gönderiyor.
### Virtual Host'lar

#### 00-default.conf

> Beklenen davranış: `acme challenge` dışındaki her isteği 443/HTTPS'e yönlendirmesi.

Mevcut yapılandırmadaki `listen 80` ve `listen [::]:80` direktiflerine `default_server` parametresini ekliyoruz:

```nginx {title="/etc/nginx/vhost.d/00-default.conf"}
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    # Allow ACME challenge to be served over HTTP (don't redirect to HTTPS).
    location ~* ^/.well-known/acme-challenge/ {
        root /opt/www/well_known;
        try_files $uri =404;
        allow all;
    }

    # Redirect all insecure http requests to https
    location / {
        return 301 https://$host$request_uri;
    }
}
```

#### 00-default-ssl.conf

> Beklenen davranış: Her virtual host için ayrı tanım olacağından, herhangi bir virtual host tarafından yakalanmayan istekleri karşılaması.

`/etc/nginx/vhost.d/00-default-ssl.conf` dosyasını aşağıdaki gibi düzenliyoruz:

```nginx {title="/etc/nginx/vhost.d/00-default-ssl.conf"}
server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;

    ssl_reject_handshake on;
}
```

Gelen bir istek için eşleşen bir `server_name` ([SNI](term:sni)) yoksa [TLS](term:tls) el sıkışması reddediliyor.

Anlama kısmında belirttiğimiz gibi daha önce burada include edilen şablonlar artık kullanılmıyor.

> [!warning]
> Bu yapılandırmadan sonra virtual host'u tanımlanmamış adlarla (ör. `https://xenonly.com` veya doğrudan IP adresiyle) yapılan HTTPS istekleri reddedilir. [2 Mail Sunucu Kurulumu](/self-hosting/mail-server/) bölümündeki `/mail` ve `/iredadmin` adresleri artık aşağıdaki alt alan adları üzerinden kullanılıyor.

#### vhost_mail.xenonly.com.conf

Roundcube Webmail'i sunmak için kullanacağız. `/etc/nginx/vhost.d/vhost_mail.xenonly.com.conf` dosyasını aşağıdaki gibi oluşturalım:

```nginx {title="/etc/nginx/vhost.d/vhost_mail.xenonly.com.conf"}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name mail.xenonly.com;

    ssl_certificate     /etc/letsencrypt/live/mail.xenonly.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mail.xenonly.com/privkey.pem;

    include /etc/nginx/templates/misc.tmpl;
    include /etc/nginx/templates/roundcube-subdomain.tmpl;
}
```

> [!note]
> Sertifikayı [2.1 Mail Sunucusu için SSL Ayarlama](/self-hosting/mail-server-ssl/) bölümünde aldığımız için tekrar almıyoruz.

> [!tip]
> Alt alan adı kullanımı tamamen kişisel tercih; `/mail` gibi bir yol üzerinden de sunulabilir.

> [!note]
> Birden fazla alan adına webmail arayüzü sunmamız gerekirse, her alan adının sertifikası ayrı olacağından ayrı bir virtual host oluşturmak veya bu dosyaya yeni bir `server` bloğu eklemek gerekir.

#### vhost_iredadmin.xenonly.com.conf

Önce sertifikayı alalım:

```bash
sudo certbot certonly --webroot -w /opt/www/well_known -d iredadmin.xenonly.com
```

> [!note]
> Sertifika yenilendiğinde NGINX'in yeniden yüklenmesini [2.1 Mail Sunucusu için SSL Ayarlama](/self-hosting/mail-server-ssl/) bölümünde oluşturduğumuz deploy hook sağlıyor.

Ardından `/etc/nginx/vhost.d/vhost_iredadmin.xenonly.com.conf` dosyasını aşağıdaki gibi oluşturalım:

```nginx {title="/etc/nginx/vhost.d/vhost_iredadmin.xenonly.com.conf"}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name iredadmin.xenonly.com;

    ssl_certificate     /etc/letsencrypt/live/iredadmin.xenonly.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/iredadmin.xenonly.com/privkey.pem;

    include /etc/nginx/templates/misc.tmpl;
    include /etc/nginx/templates/iredadmin-subdomain.tmpl;
}
```

> [!tip]
> Alt alan adı kullanımı tamamen kişisel tercih; `/iredadmin` yolu üzerinden de sunulabilir.

> [!note]
> Yönetim paneli olduğu ve dışarıdan erişime ihtiyaç olmadığı için sadece VPN üzerinden erişilebilir yapılabilir. Bunu [7.2 Servisleri VPN Arkasına Almak](/self-hosting/services-behind-vpn/) bölümünde yapacağız.

### Kullanılmayan Şablonları Silme

Anlama kısmında kullanılmayacağını belirttiğimiz şablonlar:

- netdata.tmpl
- netdata-subdomain.tmpl
- sogo.tmpl
- sogo-subdomain.tmpl
- adminer.tmpl
- stub_status.tmpl
- redirect_to_https.tmpl
- php-catchall.tmpl
- iredadmin.tmpl
- hsts.tmpl

```bash
cd /etc/nginx/templates
sudo rm -f netdata.tmpl netdata-subdomain.tmpl sogo.tmpl sogo-subdomain.tmpl adminer.tmpl
sudo rm -f stub_status.tmpl redirect_to_https.tmpl php-catchall.tmpl iredadmin.tmpl hsts.tmpl
```

> [!note]
> Şu an NGINX üzerinden sadece Roundcube webmail ve iRedAdmin paneli sunuluyor. İleride daha fazla site gelecek ve onların tanımlarını da yapacağız. Şimdilik bu kadar.

### Doğrulama

Yapılandırmayı doğrulayalım ve servisi yeniden başlatalım:

```bash
sudo nginx -t
sudo systemctl restart nginx
```

## Sorun Giderme

`nginx -t` hata veriyorsa, sorun büyük ihtimalle dokümandan kopyalanan yapılandırma metnine yapıştırma sırasında karışan görünmez veya biçimlendirilmiş karakterlerdir.

```bash
sudo cat -A /etc/nginx/vhost.d/<DOSYA>.conf | head
```

Bu komutla sorunun karakter biçimlendirmesinden kaynaklanıp kaynaklanmadığını kontrol edebiliriz. Bölünemez boşluk (NBSP) karakterleri satırlarda `M-BM-` olarak görünür.

```bash
sudo sed -i 's/\xC2\xA0/ /g' /etc/nginx/vhost.d/<DOSYA>.conf
```

Bu komutla da düzeltebiliriz.
