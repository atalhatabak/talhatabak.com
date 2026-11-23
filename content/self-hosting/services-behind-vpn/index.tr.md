---
title: "Servisleri VPN Arkasına Almak"
description: "SSH'ı ve NGINX virtual host'larını sadece VPN üzerinden erişilebilir yapma."
date: 2026-11-21T00:15:00+03:00
chapter: "7.2"
tags: ["wireguard", "vpn", "nginx", "ssh"]
---
> [!abstract] Gerekenler
> - [7 WireGuard Kurulumu](/self-hosting/wireguard/) ve [7.1 WireGuard İstemci Eklemek](/self-hosting/wireguard-clients/) tamamlanmış olmalı; kişisel bilgisayardan VPN'e bağlanılabiliyor olmalı.
> - NGINX kısmı için [3 NGINX Yapılandırması](/self-hosting/nginx/) tamamlanmış olmalı.
>
> **Varsayımlar**
> - VPN ağı `10.8.0.0/24` ve `fd42:8::/64`, sunucunun VPN adresi `10.8.0.1` olarak alınmıştır.
> - `vpn` zone'unda SSH'a izin verildiği varsayılmıştır ([7 WireGuard Kurulumu](/self-hosting/wireguard/)).
> - Sunucu komutları sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır. `ssh` ve `curl` ile yapılan testler kişisel bilgisayardan yapılmıştır.

Sunucuda çalışan ve sadece bizim erişmek istediğimiz servisleri ([iRedAdmin](term:iredadmin) paneli, vault, SSH vb.) sadece VPN bağlantısı varken erişilebilir hale getireceğiz.

Kabaca yapmamız gereken, ilgili servisin yapılandırmasında sadece aşağıdaki adreslerden gelen isteklere izin vermek:

- `10.8.0.0/24` (IPv4) ve `fd42:8::/64` (IPv6)

## SSH Servisine Sadece VPN Üzerinden Erişmek

Yapmamız gereken, güvenlik duvarında public [zone'dan](term:firewalld-zone) SSH'ı kaldırmak; VPN zone'unda zaten izin verilmiş durumda.

### Ön Kontrol

#### Firewalld

```bash
sudo firewall-cmd --zone=vpn --list-all
```

Bu komutla VPN zone'unda SSH'ın olduğundan emin olalım.

> [!warning]
> Ayrıca root'un veya normal kullanıcının parolasının olduğundan ve bu parolayı bildiğimizden emin olalım. VPN'de bir sorun olursa sunucuya erişmenin tek yolu sağlayıcının verdiği [VNC](term:vnc) konsolu olacak ve oradan kullanıcı adı ve parolayla giriş yapmak gerekecek.

#### VPN Bağlantısı

Kişisel bilgisayarımızdan VPN'e (split veya [full tunnel](term:full-tunnel)) bağlanalım ve aşağıdaki komutla VPN üzerinden SSH bağlantısı kurabildiğimizden emin olalım:

```bash
ssh <KULLANICI>@10.8.0.1
```

#### Kurtarma Zamanlayıcısı ve Geçici (Runtime) Değişiklik

Bir sorun çıkar da SSH bağlantısı kuramazsak diye bir geri alma zamanlayıcısı kuralım:

```bash
sudo systemd-run --on-active=10min --unit=ssh-rescue firewall-cmd --reload
```

Firewalld'de yapacağımız değişikliklerde `--permanent` kullanmayacağımız için, zamanlayıcıyı iptal etmezsek 10 dakika sonra çalışacak, Firewalld'yi reload edip kalıcı (eski) ayarları tekrar yükleyecek.

### Uygulama

Aşağıdaki komutla public zone'dan SSH servisini kaldıralım:

```bash
sudo firewall-cmd --zone=public --remove-service=ssh
```

#### Doğrulama

Kişisel bilgisayarımızdan, **[split tunnel](term:split-tunnel)** profili bağlıyken test edelim:

```bash
ssh <KULLANICI>@10.8.0.1                              # bağlanmalı, VPN üzerinden gidiyor
ssh -o ConnectTimeout=5 <KULLANICI>@<SUNUCU_IPV4>     # internetten, bağlanamamalı
ssh -o ConnectTimeout=5 <KULLANICI>@<SUNUCU_IPV6>     # IPv6, bağlanamamalı
```

> [!warning]
> Bu test full tunnel bağlıyken yapılırsa yanıltıcı olur: sunucunun public IP'sine giden trafik de tünelden geçip `wg0` üzerinden geldiği için VPN zone'unun kurallarına tabi oluyor ve bağlantı kuruluyor.

#### Kalıcı Hale Getirme

Bir sorun yoksa, 10 dakika dolmadan aşağıdaki komutlarla değişikliği kalıcı hale getirelim:

```bash
sudo firewall-cmd --permanent --zone=public --remove-service=ssh
sudo systemctl stop ssh-rescue.timer
sudo firewall-cmd --reload
```

```bash
sudo firewall-cmd --zone=public --list-services   # ssh listede olmamalı
```

### SSH Yapılandırmasını Düzenleme

SSH bağlantısını her zaman VPN üzerinden yapacağımız ve sunucunun VPN ağındaki IP adresi sabit olduğu için, kolaylık olması açısından kişisel bilgisayarımızdaki `~/.ssh/config` dosyasını aşağıdaki gibi düzenleyebiliriz:

```ssh-config {title="~/.ssh/config"}
Host <SUNUCU_ADI>
    HostName 10.8.0.1
    User <KULLANICI>
    IdentityFile ~/.ssh/<SSH_ANAHTARI>
    IdentitiesOnly yes
```

> [!note]
> `HostName` olarak alan adı yerine `10.8.0.1` yazmamızın sebebi split tunnel: alan adı sunucunun public IP'sine çözüleceği için trafik internetten gider ve public zone'da SSH kapalı olduğu için bağlantı kurulamaz. Full tunnel'da bu sorun yaşanmaz.

> [!note]
> sshd'yi `ListenAddress` ile sadece `10.8.0.1` adresini dinleyecek şekilde de yapılandırabilirdik. Ama güvenlik duvarı dışarıdan gelen bağlantıları zaten engellediği ve bu durumda SSH servisi WireGuard'a bağımlı hale geleceği için buna gerek duymadım. Bu tercihle kabul ettiğimiz tek risk, güvenlik duvarı kapanırsa SSH'ın internete açık hale gelmesi.

## NGINX Virtual Host'larını VPN Arkasına Almak

iRedAdmin gibi web servisleri zaten NGINX arkasında çalışıyor. Bu yüzden sadece VPN üzerinden erişmek istediğimiz servislere NGINX yapılandırmasında kısıtlama koyacağız.

`/etc/nginx/templates` dizininde hâlihazırda kullandığımız şablonlar var. Bunlara `/etc/nginx/templates/vpn-only.tmpl` şablonunu aşağıdaki içerikle ekleyelim:

```nginx {title="/etc/nginx/templates/vpn-only.tmpl"}
allow 10.8.0.0/24;
allow fd42:8::/64;
deny  all;
```

Bundan sonra yapmamız gereken, sadece VPN ile erişilmesini istediğimiz [virtual host'ların](term:virtual-host) `server` bloğuna `include /etc/nginx/templates/vpn-only.tmpl;` satırını eklemek.

### iRedAdmin Panelini VPN Arkasına Almak

`/etc/nginx/vhost.d/vhost_iredadmin.xenonly.com.conf` dosyasını açalım ve `server` bloğuna `vpn-only` şablonunu include edelim. Dosya aşağıdaki gibi olacak:

```nginx {title="/etc/nginx/vhost.d/vhost_iredadmin.xenonly.com.conf"}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name iredadmin.xenonly.com;

    ssl_certificate     /etc/letsencrypt/live/iredadmin.xenonly.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/iredadmin.xenonly.com/privkey.pem;
    include /etc/nginx/templates/vpn-only.tmpl;
    include /etc/nginx/templates/misc.tmpl;
    include /etc/nginx/templates/iredadmin-subdomain.tmpl;
}
```

NGINX yapılandırmasını test edip yeniden yükleyelim:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

#### Doğrulama

Kişisel bilgisayarımızdan, VPN'e bağlı değilken:

```bash
curl -sI https://iredadmin.xenonly.com | head -1   # HTTP/2 403
```

VPN'e bağlıyken (full tunnel ile ya da [7.3 Olası Problemler](/self-hosting/wireguard-troubleshooting/) bölümündeki `hosts` kaydıyla split tunnel ile) aynı komut `403` dışında bir yanıt (ör. `200` veya bir yönlendirme) döndürmeli.

#### NGINX Location Mirası

> [!note]
> `vpn-only` şablonunun `server` bloğunun hangi kısmına eklendiğinin bir önemi yok.

Burada dikkat edilmesi gereken nokta NGINX location bloklarının davranışı.

NGINX'te ayarlar iç içe bloklarda tanımlanıyor: http → server → location. Alt blok, üst bloğun ayarlarını miras alıyor. Ama bir kural var:

> [!important]
> Alt blok aynı türden tek bir direktif bile tanımlarsa, üst bloktan gelen o türdeki direktiflerin hepsi o alt blok için geçersiz olur.

Biz `server` bloğuna `vpn-only` şablonunu ekleyerek VPN ağından gelen isteklere izin veriyor, kalan istekleri reddediyoruz. Ama ayrı bir location bloğunda (belki include ile gelen) `allow` veya `deny` kuralı varsa, o location için bizim kurallarımız çalışmıyor.

Ayrıca `return` ve `rewrite` direktifleri, isteğin işlenmesinde erişim kontrolünden (`allow`/`deny`) önceki aşamada çalışıyor. `return` ile yanıt veren (ya da `rewrite` ile yönlendirme yapan) bir location, `deny` kuralına hiç ulaşmadan yanıt dönüyor.

Bu yüzden mevcut yapılandırmamızı kontrol edelim:

```bash
sudo grep -RnE 'allow|deny|return|rewrite' /etc/nginx
```

- `roundcube-subdomain.tmpl` içinde birçok location için `deny all` tanımlı; bu bir sorun oluşturmuyor.
- `00-default.conf` içindeki `return 301` sadece 80 portundaki HTTP isteklerini HTTPS'e yönlendiriyor; asıl istek 443 portundaki virtual host'a geldiğinde kısıt uygulanıyor.
- `misc.tmpl` ve `00-default.conf` içindeki `allow all` direktifleri `.well-known` location'ında tanımlı. Bu, bizim kuralımızı eziyor ama istediğimiz bir davranış: `.well-known` dizininde [Let's Encrypt'in](term:lets-encrypt) sertifika doğrulaması sırasında geçici olarak oluşturduğu dosyalar bulunuyor.

> [!note]
> Sertifika yenileme bu kısıttan etkilenmiyor: Let's Encrypt doğrulaması 80 portundaki `00-default.conf` üzerinden yapılıyor ve orada bir VPN kısıtı yok.
