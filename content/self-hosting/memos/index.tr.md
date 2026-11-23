---
title: "Usememos Kurulumu"
description: "Self-host edilebilen not uygulaması Memos'un kurulumu."
date: 2026-11-21T00:21:00+03:00
chapter: "11"
tags: ["memos", "docker"]
---
> [!abstract] Gerekenler
> - [4.1 Docker Konteynerleri için Hazır Şablon](/self-hosting/docker-template/) ve [7.2 Servisleri VPN Arkasına Almak](/self-hosting/services-behind-vpn/) tamamlanmış olmalı.
>
> **Varsayımlar**
> - Memos'a `memos.xenonly.com` adresinden erişilmektedir. Bu alan adı için `A` ve `AAAA` kayıtlarının girildiği varsayılmıştır.
> - Memos konteyneri `127.0.0.1:8001` portunu kullanmaktadır.
> - Komutlar sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır.

## Nedir

[Memos](https://usememos.com/), web üzerinden kullanılan, self-host edilebilen hafif bir not uygulaması.

## Kurulum

[Docker Compose](term:docker-compose) ile kuracağız.

```bash
sudo mkdir /opt/docker/memos
```

`/opt/docker/memos/compose.yaml` dosyasını aşağıdaki gibi oluşturalım:

```yaml {title="/opt/docker/memos/compose.yaml"}
services:
  memos:
    image: neosmemo/memos:stable
    container_name: memos
    restart: unless-stopped
    ports:
      - "127.0.0.1:8001:5230"
    volumes:
      - ./data:/var/opt/memos
    environment:
      MEMOS_PORT: 5230
      MEMOS_DRIVER: sqlite
      MEMOS_INSTANCE_URL: "https://memos.xenonly.com"
      MEMOS_TRUSTED_PROXIES: "172.20.0.0/16"
```

[Konteyneri](term:container) başlatalım:

```bash
cd /opt/docker/memos
sudo docker compose up -d
```

## Sertifika ve NGINX Reverse Proxy

Sertifikayı alalım:

```bash
sudo certbot certonly --webroot -w /opt/www/well_known -d memos.xenonly.com
```

`/etc/nginx/vhost.d/vhost_memos.xenonly.com.conf` dosyasını aşağıdaki gibi oluşturalım:

```nginx {title="/etc/nginx/vhost.d/vhost_memos.xenonly.com.conf"}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name memos.xenonly.com;

    ssl_certificate     /etc/letsencrypt/live/memos.xenonly.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/memos.xenonly.com/privkey.pem;

    client_max_body_size 40m;

    # İlk hesap oluşturulana kadar, sonra kaldırılacak
    include /etc/nginx/templates/vpn-only.tmpl;

    location / {
        proxy_pass http://127.0.0.1:8001;
        include /etc/nginx/templates/proxy.tmpl;
    }
}
```

> [!note]
> `client_max_body_size 40m`: Notlara eklenen dosyalar için. [iRedMail'in](term:iredmail) tanımladığı 12m sınırı küçük kalıyor.

> [!note]
> `vpn-only.tmpl`: Memos'ta ilk kaydolan kullanıcı yönetici oluyor. Herkese açık bir adreste ilk hesabı başkası oluşturursa yönetici o olur. Bu yüzden ilk hesap oluşturulana kadar Memos'a sadece VPN'den erişilebilecek.

NGINX yapılandırmasını test edip yeniden yükleyelim:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## İlk Hesap ve Kayıtları Kapatma

1. VPN'e [full tunnel](term:full-tunnel) ile bağlanıp `https://memos.xenonly.com` adresinden kendi hesabımızı oluşturalım.
2. Yönetici hesabıyla **Settings → System → Disallow user registration** seçeneğini açarak yeni kullanıcı kaydını kapatalım.
3. [Virtual host'taki](term:virtual-host) `include /etc/nginx/templates/vpn-only.tmpl;` satırını silelim ve `sudo nginx -t && sudo systemctl reload nginx` ile NGINX'i yeniden yükleyelim.

> [!note]
> [Split tunnel'da](term:split-tunnel) alan adı sunucunun public IP'sine çözüldüğü için istek VPN'den geçmiyor ve 403 alınıyor (bkz. [7.3 Olası Problemler](/self-hosting/wireguard-troubleshooting/)).

## Kontrol

```bash
curl -sI https://memos.xenonly.com | head -1   # HTTP/2 200
```

## Yedekleme ve Güncellemeler

Memos'un tüm verisi ([SQLite](term:sqlite) veritabanı ve yüklenen dosyalar) `/opt/docker/memos/data` dizininde duruyor; yedeklenmesi gereken tek yer burası.

Güncellemek için:

```bash
cd /opt/docker/memos && sudo docker compose pull && sudo docker compose up -d
```
