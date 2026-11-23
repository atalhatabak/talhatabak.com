---
title: "Docker Konteynerleri için Hazır Şablon"
description: "Konteynerler için port planı ve NGINX'te WebSocket destekli ortak bir proxy şablonu."
date: 2026-11-21T00:10:00+03:00
chapter: "4.1"
tags: ["docker", "nginx"]
---
> [!abstract] Gerekenler
> - [3 NGINX Yapılandırması](/self-hosting/nginx/) ve [4 Docker Kurulumu](/self-hosting/docker/) tamamlanmış olmalı.
>
> **Varsayımlar**
> - Konteyner portlarının compose dosyalarında `127.0.0.1:<HOST_PORT>:<KONTEYNER_PORT>` şeklinde yayınlandığı ve dışarıya sadece NGINX üzerinden açıldığı varsayılmıştır. [4 Docker Kurulumu](/self-hosting/docker/) bölümündeki ayarlar, IP adresi yazılmadan yayınlanan portları da `127.0.0.1`'e bağlıyor.
> - Komutlar sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır.

Kuracağımız [konteynerleri](term:container) standart bir yapıya oturtalım.

[Docker Compose](term:docker-compose) dosyalarını tek bir yerde tutalım:

```bash
sudo mkdir /opt/docker
```

## Port Planı

Konteynerler portlarını sadece `127.0.0.1` üzerinde açıyor ve NGINX bu portlara yönlendiriyor. Çakışma olmaması için seri boyunca kurulan servislerin portları şu şekilde:

| Servis                                                   | Port              | Not                                        |
| -------------------------------------------------------- | ----------------- | ------------------------------------------ |
| [8 Vault Kurulumu](/self-hosting/vault/)              | `127.0.0.1:8200`  | Docker değil, host'ta servis olarak çalışıyor |
| [9 Vaultwarden Kurulumu](/self-hosting/vaultwarden/)  | `127.0.0.1:8004`  |                                            |
| [10 WordPress Kurulumu](/self-hosting/wordpress/)    | `127.0.0.1:8030`–`8049` | Her site için bir port               |
| [11 Usememos Kurulumu](/self-hosting/memos/)      | `127.0.0.1:8001`  |                                            |
| [12 Syncthing Kurulumu](/self-hosting/syncthing/)    | `127.0.0.1:8384`, `22000` | Docker değil, host'ta servis olarak çalışıyor |

Kullanılan portlar `sudo ss -tlnp | grep docker-proxy` ile kontrol edilebilir.

## NGINX Ayarları

### WebSocket Desteği

Önce `$connection_upgrade` değişkeninin daha önce tanımlanıp tanımlanmadığını kontrol edelim. Aynı map iki kez tanımlanırsa NGINX hata verir.

```bash
sudo grep -rn connection_upgrade /etc/nginx/   # çıktı boş olmalı
```

Çıktı boşsa `/etc/nginx/conf.d/websocket.conf` dosyasını aşağıdaki gibi oluşturalım:

```nginx {title="/etc/nginx/conf.d/websocket.conf"}
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}
```

### Proxy Şablonu

`/etc/nginx/templates/proxy.tmpl` dosyasını aşağıdaki gibi oluşturalım:

```nginx {title="/etc/nginx/templates/proxy.tmpl"}
proxy_http_version 1.1;

proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $remote_addr;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host  $host;

proxy_set_header Upgrade           $http_upgrade;
proxy_set_header Connection        $connection_upgrade;
```

> [!note]
> [Reverse proxy](term:reverse-proxy) için temel yapılandırma; konteynerlere yönlendirme yapan çoğu [virtual host'ta](term:virtual-host) bunu kullanacağız.

> [!warning]
> `proxy_set_header` da `add_header` gibi miras alınıyor: bir location bloğunda tek bir `proxy_set_header` bile tanımlanırsa, üst bloktan gelenlerin hepsi o blokta geçersiz olur. Bu yüzden şablonu `proxy_pass` ile aynı location bloğuna include etmek en güvenli yol.
