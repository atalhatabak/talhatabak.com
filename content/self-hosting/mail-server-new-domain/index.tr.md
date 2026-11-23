---
title: "Mail Sunucusu Yeni Alan Adı Ekleme"
description: "Mail sunucusuna yeni bir alan adı ekleme: iRedAdmin, DKIM anahtarı ve DNS kayıtları."
date: 2026-11-21T00:04:00+03:00
chapter: "2.2"
tags: ["mail", "dns", "dkim"]
---
> [!abstract] Gerekenler
> - [2 Mail Sunucu Kurulumu](/self-hosting/mail-server/) tamamlanmış olmalı.
>
> **Varsayımlar**
> - Ana mail sunucusu `mail.xenonly.com`; örnek olarak eklenecek alan adı `example.com`.
> - `example.com`'un DNS kayıtlarının düzenlenebildiği varsayılmıştır. Gereken mail kayıtları bu bölümde anlatılıyor.
> - iRedAdmin'e [3 NGINX Yapılandırması](/self-hosting/nginx/) öncesinde `https://xenonly.com/iredadmin`, sonrasında `https://iredadmin.xenonly.com` adresinden ([7.2 Servisleri VPN Arkasına Almak](/self-hosting/services-behind-vpn/) sonrasında sadece VPN üzerinden) erişilmektedir.
> - Komutlar sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır.

Mevcut yapıda `mail.xenonly.com` bu sunucunun mail sunucusu adı, `xenonly.com` ise sunucunun mail gönderip aldığı ilk alan adı. Bunu sağlayan ayarlar iki grupta toplanıyor.

**Sunucu kimliği** (`mail.xenonly.com`, tüm alan adları için ortak):

- `A` ve `AAAA` kayıtları
- IPv4 ve IPv6 için `Reverse DNS (PTR)` kaydı

**Alan adı kimliği** (`xenonly.com`, her alan adı için ayrı):

- `MX` kaydı
- `SPF` kaydı
- `DKIM` kaydı
- `DMARC` kaydı

> [!note]
> Her alan adına ayrı bir mail sunucusu kimliği (kendi sunucu adı, [PTR kaydı](term:ptr-record) ve IPv4 adresi) vermek, tek bir [VPS](term:vps) üzerinde ek IP adresi ve fazladan yapılandırma gerektirir. Bunu gerektiren özel bir sebep yoksa tercih edilmez.

Bizim tasarımımızda ana mail sunucusu `mail.xenonly.com`. Sonradan eklenen alan adları da posta alıp gönderirken bu sunucuyu kullanıyor. Bu alan adlarının her biri için sadece kendi [MX](term:mx-record), [SPF](term:spf), [DKIM](term:dkim) ve [DMARC](term:dmarc) kayıtları tanımlanıyor.

## Her Alan Adı için Yapılması Gerekenler

1. Alan adının [iRedAdmin](term:iredadmin) üzerinden sunucuya eklenmesi
2. Sunucuda DKIM anahtarının oluşturulması, [Amavis](term:amavis) yapılandırmasına ve DNS'e eklenmesi
3. MX kaydının eklenmesi
4. SPF kaydının eklenmesi
5. DMARC kaydının eklenmesi ve rapor hesabının oluşturulması

## Uygulama

### 1. Alan Adının iRedAdmin Üzerinden Sunucuya Eklenmesi

iRedAdmin paneline giriş yapıyoruz ve **Add → Domain** yolunu izleyerek `example.com` alan adını ekliyoruz.

Ardından **Add → User** yolunu izleyerek `example.com` için en az bir kullanıcı (ör. `info@example.com`) oluşturuyoruz. Bu hesabı en sonda test postası göndermek için kullanacağız.

### 2. Sunucuda DKIM Anahtarının Oluşturulması, Amavis Yapılandırmasına ve DNS'e Eklenmesi

#### DKIM Anahtarı Oluşturma

Aşağıdaki komutlarla DKIM anahtarını oluşturalım:

```bash
sudo amavisd genrsa /var/lib/dkim/example.com.pem 2048
sudo chown amavis:amavis /var/lib/dkim/example.com.pem
sudo chmod 0400 /var/lib/dkim/example.com.pem
```

#### Amavis Yapılandırmasını Düzenleme

`/etc/amavisd/amavisd.conf` dosyasını açıyoruz:

- `# Add dkim_key here` kısmına, belirtilen formatta yeni anahtarımızı ekliyoruz. Birincil alan adının anahtarı kurulumda otomatik olarak eklenmiş durumda.
- `@dkim_signature_options_bysender_maps` altındaki `catch-all` kısmını yorum satırı yapıyoruz.
- `Per-domain dkim key` kısmına, belirtilen formatta alan adlarımızı ekliyoruz.

> [!important]
> `catch-all` tanımı, tüm alan adlarının e-postalarını ilk alan adının anahtarıyla imzalıyor. Bu durumda `example.com`'dan giden e-postalar `d=xenonly.com` ile imzalanır ve DMARC'taki `adkim=s` (sıkı eşleşme) kontrolünden geçemez. Bu yüzden her alan adını kendi anahtarıyla tanımlıyoruz.

Dosya kabaca aşağıdaki gibi görünmeli:

```perl {title="/etc/amavisd/amavisd.conf"}
# Add dkim_key here.
dkim_key('example.com', 'dkim', '/var/lib/dkim/example.com.pem');
dkim_key('xenonly.com', 'dkim', '/var/lib/dkim/xenonly.com.pem');

@dkim_signature_options_bysender_maps = ({
   # 'd' defaults to a domain of an author/sender address,
   # 's' defaults to whatever selector is offered by a matching key

   # Per-domain dkim key
   #"domain.com"  => { d => "domain.com", a => 'rsa-sha256', ttl => 10*24*3600 },
   "example.com" => { d => "example.com", a => 'rsa-sha256', ttl => 10*24*3600 },
   "xenonly.com" => { d => "xenonly.com", a => 'rsa-sha256', ttl => 10*24*3600 },

   # catch-all (one dkim key for all domains)
   #'.' => {d => 'xenonly.com',
   #        a => 'rsa-sha256',
   #        c => 'relaxed/simple',
   #        ttl => 30*24*3600 },
});
```

Düzenlemeden sonra servisi yeniden başlatalım:

```bash
sudo systemctl restart amavisd.service
```

#### DKIM Anahtarını DNS'e Ekleme

Mevcut anahtarları görmek için:

```bash
sudo amavisd showkeys
```

DNS kaydına doğrudan eklenecek biçimde tek satırlık çıktı almak için:

```bash
sudo amavisd showkeys example.com | awk -F'"' '/^[[:space:]]*"/ {printf "%s", $2} END {print ""}'
```

> [!note]
> DNS'e eklenen değer tek satır olmalı. `amavisd showkeys` anahtarı birden çok satıra bölerek yazıyor, yukarıdaki komut bu satırları birleştiriyor.

Bu çıktıyı `example.com`'un DNS'ine aşağıdaki gibi ekliyoruz:

| Name            | Type | Content           | Ne Anlama Geliyor                                              |
| --------------- | ---- | ----------------- | -------------------------------------------------------------- |
| dkim._domainkey | TXT  | `<DKIM_ANAHTARI>` | Amavis tarafından imzalanan e-postaların doğrulanmasını sağlar |

DNS kaydı yayıldıktan sonra sunucudaki anahtarın DNS'teki kayıtla eşleştiğini kontrol edelim. Çıktıda `=> pass` görünmeli:

```bash
sudo amavisd testkeys example.com
```

### 3. MX Kaydının Eklenmesi

`example.com`'un DNS'ini yönettiğimiz sağlayıcının panelinden aşağıdaki `MX` kaydını ekleyelim:

| Name        | Type | Content            |
| ----------- | ---- | ------------------ |
| example.com | MX   | `mail.xenonly.com` |

### 4. SPF Kaydının Eklenmesi

Aynı panelden aşağıdaki `SPF` kaydını ekleyelim:

| Name        | Type | Content                                                  |
| ----------- | ---- | -------------------------------------------------------- |
| example.com | TXT  | `"v=spf1 mx a ip4:<SUNUCU_IPV4> ip6:<SUNUCU_IPV6> ~all"` |

> [!tip]
> `a` mekanizması, `example.com`'un `A` kaydındaki sunucuyu da mail göndermeye yetkili kılar. `example.com`'un web sitesi başka bir sunucudaysa o sunucuya da yetki verilmiş olur; bu durumda `a` kayıttan çıkarılabilir.

### 5. DMARC Kaydının Eklenmesi ve Rapor Hesabının Oluşturulması

Aynı panelden aşağıdaki `DMARC` kaydını ekleyelim:

| Name   | Type | Content                                                                                             |
| ------ | ---- | --------------------------------------------------------------------------------------------------- |
| _dmarc | TXT  | `"v=DMARC1; p=quarantine; sp=quarantine; np=reject; adkim=s; aspf=s; rua=mailto:dmarc@example.com"` |

DMARC kaydındaki `dmarc@example.com` adresine raporların ulaşabilmesi için iRedAdmin'de **Add → User** yolunu izleyerek `example.com` için `dmarc` kullanıcısını oluşturuyoruz.

## Kontrol

### `example.com` için Örnek DNS Kayıtları

DNS kayıtları kabaca şu şekilde olmalı:

| Name            | Type | Content                                                                                             | Ne Anlama Geliyor                                                             |
| --------------- | ---- | --------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| example.com     | MX   | `mail.xenonly.com`                                                                                  | Gelen e-postaların hangi mail sunucusuna yönlendirileceğini belirtir          |
| dkim._domainkey | TXT  | `<DKIM_ANAHTARI>`                                                                                   | Amavis tarafından imzalanan e-postaların doğrulanmasını sağlar                |
| _dmarc          | TXT  | `"v=DMARC1; p=quarantine; sp=quarantine; np=reject; adkim=s; aspf=s; rua=mailto:dmarc@example.com"` | SPF veya DKIM doğrulamasından geçemeyen e-postalara ne yapılacağını belirtir  |
| example.com     | TXT  | `"v=spf1 mx a ip4:<SUNUCU_IPV4> ip6:<SUNUCU_IPV6> ~all"`                                            | Hangi sunucuların bu alan adı adına mail göndermeye yetkili olduğunu belirtir |

### Test Postası ile SPF, DKIM ve DMARC Kontrolü

[Roundcube'a](term:roundcube) `info@example.com` kullanıcısıyla giriş yapalım ve <https://www.mail-tester.com/> adresinde verilen adrese bir test maili gönderelim. Beklenen sonuç:

```text
Your lovely total: 10/10
```
