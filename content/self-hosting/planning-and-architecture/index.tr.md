---
title: "Planlama ve Mimari"
description: "Seri boyunca kullanılan sunucu, varsayımlar ve standartlar; serinin yol haritası."
date: 2026-11-21T00:00:00+03:00
chapter: "0"
tags: ["rocky-linux"]
---
Bu seride bir [VPS](term:vps) üzerinde self-host olarak neler yapılabileceğini ve nasıl yapılabileceğini teknik ve uygulamalı olarak ele alacağım.

## Sunucu ve Ortam Bilgileri

Bu dokümanı hazırlarken kullandığım sunucu şu şekilde:

```text
İşletim Sistemi: Rocky Linux 10.2
İşlemci: AMD EPYC™ 9645, 4 adanmış çekirdek
RAM: 8 GB
Depolama: 256 GB NVMe
```

Ayrıca bir alan adı (domain) gerekiyor. Ben uygulama için `xenonly.com` alan adını kullanacağım.

## Varsayımlar ve Standartlar

### Alan Adları

Kullanacağım alan adı `xenonly.com`. Mail sunucusu `mail.xenonly.com` adını kullanacak, diğer servisleri de `xenonly.com`'un alt alan adlarında (ör. `iredadmin.xenonly.com`) sunacağım.

Seri boyunca kullanılan alan adı ve alt alan adları için DNS kayıtlarının girildiği varsayılıyor. Bu adım, özel kayıt gerektiren durumlar ([MX](term:mx-record), [SPF](term:spf), [DKIM](term:dkim), [DMARC](term:dmarc), [PTR](term:ptr-record)) dışında ayrıca anlatılmayacak.

> [!note]
> Temel olarak yapılması gereken, alan adının ve alt alan adlarının (istenirse `*.xenonly.com`) `A` ve `AAAA` kayıtlarının girilmesi.

### Bölüm Başı Notları

Her bölümün başında o bölüm için **gerekenler** (önce tamamlanmış olması gereken bölümler) ve **varsayımlar** (kullanılan alan adları, komutların nerede ve hangi yetkiyle çalıştırıldığı vb.) kısaca belirtiliyor.

### Kod Blokları

Komutların çoğu root yetkisi gerektiriyor. Bunu belirtmek ve komutları doğrudan kopyalanabilir tutmak için root için `#`, normal kullanıcı için `$` istemi kullanmak yerine komutları `sudo ...` şeklinde yazacağım. `sudo` olmadan yazılan komutlar normal kullanıcıyla çalıştırılıyor.

Komutların beklenen çıktıları ayrı bir `text` bloğunda ya da komutun yanında `#` ile başlayan yorum olarak veriliyor.

### Yer Tutucular

`<SUNUCU_IPV4>` gibi büyük harfle ve açılı ayraç içinde yazılan değerler kendi değerlerimizle değiştirilmeli. `<server.key>` gibi dosya adı içeren ifadeler ise o dosyanın içeriğini gösteriyor.

## Yol Haritası

### [1 Kurulum Sonrası Yapılandırma](/self-hosting/post-install-configuration/)

Yeni kurulmuş Rocky Linux 10 sunucunun ilk kontrolleri ve temel ayarları.

### [2 Mail Sunucu Kurulumu](/self-hosting/mail-server/)

Sunucunun ilk temel servisi mail servisi olacak. Sunucu kurulduktan hemen sonra [iRedMail](https://www.iredmail.org/) ile mail servisini kuracağız. Bu kurulum NGINX ve MariaDB kurulumunu da kapsıyor.

- [2.1 Mail Sunucusu için SSL Ayarlama](/self-hosting/mail-server-ssl/)
- [2.2 Mail Sunucusu Yeni Alan Adı Ekleme](/self-hosting/mail-server-new-domain/)
- [2.3 İstemci Kullanmak](/self-hosting/mail-clients/)
- [2.4 Mail Sunucusu Taşınması](/self-hosting/mail-server-migration/)
- [2.5 Ekstra Ayarlamalar](/self-hosting/mail-server-extras/)

### [3 NGINX Yapılandırması](/self-hosting/nginx/)

[iRedMail'in](term:iredmail) kurduğu NGINX yapılandırmasını, birden fazla servisi ve [virtual host'u](term:virtual-host) sunabilecek hale getirme.

### [4 Docker Kurulumu](/self-hosting/docker/)

Docker'ın kurulumu ve [konteynerlerin](term:container) sadece localhost üzerinden erişilebilir olacak şekilde yapılandırılması.

- [4.1 Docker Konteynerleri için Hazır Şablon](/self-hosting/docker-template/)

### [5 Firewalld Yapılandırma](/self-hosting/firewalld/)

Kurulum boyunca kapalı tuttuğumuz Firewalld'nin yapılandırılıp etkinleştirilmesi ve konteynerlerle VPN istemcilerinin dışarıya 25. porttan çıkışının engellenmesi.

### [6 Fail2Ban Yapılandırma](/self-hosting/fail2ban/)

iRedMail ile gelen Fail2Ban'a tekrar eden saldırganlar için artan ban süresi eklenmesi.

### [7 WireGuard Kurulumu](/self-hosting/wireguard/)

VPN sunucusu: istemcileri VPN üzerinden internete çıkarma, istemciler arası iletişim ve bazı servisleri sadece VPN üzerinden erişilebilir yapma.

- [7.1 WireGuard İstemci Eklemek](/self-hosting/wireguard-clients/)
- [7.2 Servisleri VPN Arkasına Almak](/self-hosting/services-behind-vpn/)
- [7.3 Olası Problemler](/self-hosting/wireguard-troubleshooting/)

### [8 Vault Kurulumu](/self-hosting/vault/)

HashiCorp Vault ile secret'ların (API anahtarı, token, parola) merkezi ve şifreli olarak saklanması.

### [9 Vaultwarden Kurulumu](/self-hosting/vaultwarden/)

Bitwarden uyumlu parola yöneticisi Vaultwarden'ın kurulumu. 

### [10 WordPress Kurulumu](/self-hosting/wordpress/)

Her sitenin kendi konteynerinde çalıştığı, ortak bir MariaDB konteyneri kullanan WordPress yapısı.

- [10.1 Eski WordPress'i Mevcut Yapıya Taşımak](/self-hosting/wordpress-migration/)

### [11 Usememos Kurulumu](/self-hosting/memos/)

Self-host edilebilen not uygulaması Memos'un kurulumu.

### [12 Syncthing Kurulumu](/self-hosting/syncthing/)

Cihazlar arasında dosya senkronizasyonu için Syncthing; sunucu her zaman açık olan ortak eş olarak kullanılıyor.

### 13 Hugo Blog Kurulumu

Coming Soon

### 14 Log Yönetimi ve İzleme

Coming Soon

### 15 Yedekleme Stratejisi

Coming Soon
