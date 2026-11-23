---
title: "Mail Sunucusu için SSL Ayarlama"
description: "mail.xenonly.com için Let's Encrypt sertifikası alma ve sertifikanın otomatik yenilenmesi."
date: 2026-11-21T00:03:00+03:00
chapter: "2.1"
tags: ["mail", "ssl", "certbot"]
---
> [!abstract] Gerekenler
> - [2 Mail Sunucu Kurulumu](/self-hosting/mail-server/) tamamlanmış olmalı.
>
> **Varsayımlar**
> - `mail.xenonly.com` için `A` ve `AAAA` kayıtlarının sunucuyu gösterdiği varsayılmıştır.
> - Sunucunun 80 portu (HTTP) internetten erişilebilir durumdadır (Firewalld henüz kapalı).
> - Komutlar sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır.

Mail sunucusu kurulumunu tamamladık. Sistem şu an [iRedMail](term:iredmail) kurulumunda oluşturulan [self-signed sertifikayı](term:self-signed) kullanıyor. Bunun yerine `mail.xenonly.com` için bir [Let's Encrypt](term:lets-encrypt) sertifikası alıp sistemin onu kullanmasını sağlayacağız.

## Let's Encrypt ile Sertifika Alma

`certbot` [1 Kurulum Sonrası Yapılandırma](/self-hosting/post-install-configuration/) bölümünde kuruldu. Sertifikayı `webroot` yöntemiyle alacağız. Bu yöntem için alan adının `A` kaydının sunucuyu göstermesi ve sunucunun 80 portunu (HTTP) dinlemesi gerekiyor.

NGINX, iRedMail kurulumunda kuruldu ve Let's Encrypt ([ACME](term:acme)) doğrulaması için yapılandırılmış durumda:

```bash
sudo grep well_known /etc/nginx/sites-enabled/00-default.conf   # root /opt/www/well_known;
```

Sertifika almak için aşağıdaki komutu çalıştırmamız yeterli.

> [!note]
> İlk çalıştırmada e-posta adresi ve kullanım koşullarının onayı istenecek.

```bash
sudo certbot certonly --webroot -w /opt/www/well_known -d mail.xenonly.com
```

```text
Certificate is saved at: /etc/letsencrypt/live/mail.xenonly.com/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/mail.xenonly.com/privkey.pem
```

iRedMail'in kullandığı self-signed sertifikalar aşağıdaki yollarda bulunuyor:

```text
SSL cert keys (size: 4096):
    - /etc/pki/tls/certs/iRedMail.crt
    - /etc/pki/tls/private/iRedMail.key
```

Eski sertifikaları yedekleyelim:

```bash
sudo mv /etc/pki/tls/certs/iRedMail.crt /etc/pki/tls/certs/iRedMail.crt.bak

sudo mv /etc/pki/tls/private/iRedMail.key /etc/pki/tls/private/iRedMail.key.bak
```

Ardından aşağıdaki komutlarla yeni sertifika için sembolik bağlantılar oluşturalım:

```bash
sudo ln -s /etc/letsencrypt/live/mail.xenonly.com/fullchain.pem \
  /etc/pki/tls/certs/iRedMail.crt

sudo ln -s /etc/letsencrypt/live/mail.xenonly.com/privkey.pem \
  /etc/pki/tls/private/iRedMail.key
```

ve ilgili servisleri yeniden başlatalım:

```bash
sudo systemctl restart postfix dovecot nginx
```

## Sertifika Yenileme

Let's Encrypt sertifikaları 90 gün geçerli. [certbot](term:certbot) paketi yenileme için bir [systemd](term:systemd) zamanlayıcısıyla (`certbot-renew.timer`) geliyor. Zamanlayıcının etkin olduğundan emin olalım:

```bash
sudo systemctl enable --now certbot-renew.timer
sudo systemctl is-enabled certbot-renew.timer   # enabled
```

Ek olarak, sertifika yenilendiğinde servisleri yeniden yükleyecek bir hook oluşturacağız. `/etc/letsencrypt/renewal-hooks/deploy/reload-mail.sh` dosyasını aşağıdaki içerikle oluşturalım:

```bash {title="/etc/letsencrypt/renewal-hooks/deploy/reload-mail.sh"}
#!/bin/bash
set -e

systemctl reload postfix dovecot

if nginx -t; then
    systemctl reload nginx
else
    echo "Nginx config test failed, reload skipped" >&2
    exit 1
fi
```

> [!note]
> `renewal-hooks/deploy/` altındaki hook'lar sadece mail sertifikası için değil, **yenilenen her sertifika için** çalışır. Bu işimize yarıyor: ilerleyen bölümlerde alacağımız diğer sertifikalar (ör. `iredadmin.xenonly.com`) yenilendiğinde NGINX'in yeniden yüklenmesini de bu hook sağlıyor. [Postfix](term:postfix) ve [Dovecot'un](term:dovecot) sadece mail sertifikası yenilendiğinde yeniden yüklenmesi istenirse, certbot'un hook'a verdiği `$RENEWED_DOMAINS` değişkeni kontrol edilebilir.

Hook'a çalıştırma izni verelim:

```bash
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-mail.sh
```

Yenilemenin ve hook'un çalıştığını test edelim:

```bash
sudo certbot renew --dry-run
sudo /etc/letsencrypt/renewal-hooks/deploy/reload-mail.sh
```

> [!note]
> `--dry-run` deploy hook'larını çalıştırmadığı için hook'u ayrıca elle çalıştırarak test ediyoruz.
