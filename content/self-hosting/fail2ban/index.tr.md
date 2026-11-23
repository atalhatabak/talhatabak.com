---
title: "Fail2Ban Yapılandırma"
description: "iRedMail ile gelen Fail2Ban'a tekrar eden saldırganlar için artan ban süresi eklenmesi."
date: 2026-11-21T00:12:00+03:00
chapter: "6"
tags: ["fail2ban"]
---
> [!abstract] Gerekenler
> - [2 Mail Sunucu Kurulumu](/self-hosting/mail-server/) tamamlanmış olmalı (Fail2Ban iRedMail ile birlikte kuruluyor).
>
> **Varsayımlar**
> - VPN ağı olarak [7 WireGuard Kurulumu](/self-hosting/wireguard/) bölümündeki `10.8.0.0/24` ve `fd42:8::/64` ağlarının kullanıldığı varsayılmıştır; bu ağlar ban dışı bırakılıyor.
> - Komutlar sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır.

[iRedMail](term:iredmail) kurulumuyla birlikte Fail2Ban da kuruldu. Üzerine işe yarar birkaç ek yapılandırma ekleyelim.

## Tekrar Edenlere Artan Ban Süresi

`/etc/fail2ban/jail.d/99-local.local` dosyasını aşağıdaki içerikle oluşturalım.

> [!note]
> Fail2Ban dosyaları şu sırayla okuyor: `jail.conf` → `jail.d/*.conf` → `jail.local` → `jail.d/*.local` (alfabetik). `99-local.local` en son okunduğu için içindeki `[DEFAULT]` ayarları önceki dosyalardaki `[DEFAULT]` ayarlarını ezer. Ancak [jail](term:jail) bölümlerinde (ör. `[sshd]`) tanımlanmış ayarlar `[DEFAULT]`'tan önceliklidir; bu dosya onları değiştirmez.

```ini {title="/etc/fail2ban/jail.d/99-local.local"}
[DEFAULT]
bantime.increment = true
bantime.factor    = 2
bantime.maxtime   = 1w
ignoreip = 127.0.0.1/8 ::1 10.8.0.0/24 fd42:8::/64
```

> [!note]
> `ignoreip`: Sadece localhost ve VPN ağı ban dışı bırakılıyor. Localhost'u çıkaramayız; [Roundcube](term:roundcube) ve [iRedAdmin](term:iredadmin), [Dovecot'a](term:dovecot) ve [Postfix'e](term:postfix) 127.0.0.1'den bağlanıyor. VPN ağı ban dışında kalıyor, çünkü [7.2 Servisleri VPN Arkasına Almak](/self-hosting/services-behind-vpn/) bölümünden sonra SSH'a sadece VPN'den erişiliyor; VPN adresimiz banlanırsa sunucuya erişimimizi kaybederiz.

> [!note]
> Docker ağını (`172.20.0.0/16`) bilerek ban dışında bırakmıyoruz. [Konteynerler](term:container) host'taki portlara 172.20.x.x adresinden bağlanıyor; ele geçirilmiş bir konteyner mail parolalarını denerse banlanmalı. Ban sadece o konteyneri etkiliyor. [SMTP](term:smtp) parolası yanlış girilmiş bir konteyner de banlanabilir; bu durumda parolayı düzeltip `sudo fail2ban-client unban <IP>` ile banı kaldırmak yeterli.

`fail2ban.conf` içinde `dbpurgeage = 1d` tanımlı; yani Fail2Ban bir IP'yi veritabanında en fazla 1 gün hatırlıyor. Artan ban süresi, bir IP'nin önceki banlarını bu veritabanından okuduğu için `dbpurgeage` değeri `bantime.maxtime`'dan kısa olmamalı. Aksi halde 1 günden eski banlar unutulur ve süre artmaz.

`fail2ban.conf`'u değiştirmeden `/etc/fail2ban/fail2ban.local` dosyasını aşağıdaki içerikle oluşturalım (dosya zaten varsa `[Definition]` bölümüne `dbpurgeage` satırını ekleyelim):

```ini {title="/etc/fail2ban/fail2ban.local"}
[Definition]
dbpurgeage = 1w
```

## Uygulama ve Kontrol

```bash
sudo fail2ban-client -t                  # OK: configuration test is successful
sudo systemctl restart fail2ban
sudo fail2ban-client get sshd bantime    # 3600
sudo fail2ban-client get dbpurgeage      # 604800 (1 hafta)
```
