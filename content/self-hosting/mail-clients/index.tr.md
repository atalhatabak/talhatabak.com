---
title: "Mail Sunucusu: İstemci Kullanmak"
linkTitle: "İstemci Kullanmak"
description: "Thunderbird gibi IMAP destekleyen e-posta istemcileriyle mail hesaplarına bağlanma."
date: 2026-11-21T00:05:00+03:00
chapter: "2.3"
tags: ["mail", "imap"]
---
> [!abstract] Gerekenler
> - [2 Mail Sunucu Kurulumu](/self-hosting/mail-server/) ve [2.1 Mail Sunucusu için SSL Ayarlama](/self-hosting/mail-server-ssl/) tamamlanmış olmalı.
>
> **Varsayımlar**
> - Mail sunucusunun adı `mail.xenonly.com`, örnek kullanıcı `info@xenonly.com` olarak alınmıştır.
> - Bu bölümdeki ayarlar sunucuda değil, kişisel bilgisayardaki veya telefondaki e-posta istemcisinde yapılmıştır.

Mail sunucumuz kurulmuş ve çalışıyor durumda. Oluşturduğumuz kullanıcılarla [Roundcube](term:roundcube) Webmail üzerinden giriş yapabiliyoruz: [3 NGINX Yapılandırması](/self-hosting/nginx/) öncesinde `https://xenonly.com/mail`, sonrasında `https://mail.xenonly.com`.

Ayrıca posta hesaplarına Thunderbird, Outlook, iOS Mail, Android için Thunderbird gibi [IMAP](term:imap) destekleyen herhangi bir e-posta istemcisiyle de bağlanabiliriz.

## Bağlantı Bilgileri

> [!note]
> Hangi alan adı kullanılırsa kullanılsın sunucu adresi her zaman `mail.xenonly.com`.

|                  | Sunucu             | Port | Güvenlik | Kimlik Doğrulama |
| ---------------- | ------------------ | ---- | -------- | ---------------- |
| **Gelen (IMAP)** | `mail.xenonly.com` | 993  | SSL/[TLS](term:tls)  | Normal parola    |
| **Giden ([SMTP](term:smtp))** | `mail.xenonly.com` | 587  | [STARTTLS](term:starttls) | Normal parola    |

- **Kullanıcı adı:** E-posta adresinin tamamı (ör. `info@xenonly.com`). Sadece `info` yazılırsa giriş başarısız olur.
- **Parola:** Hesabın parolası.

> [!note]
> POP3 portları güvenlik duvarında açılmadığı için ([5 Firewalld Yapılandırma](/self-hosting/firewalld/)) IMAP kullanıyoruz. IMAP'te postalar sunucuda kalır ve tüm cihazlarda aynı görünür.

### Thunderbird ile Hesap Ekleme

1. **Hesap Ayarları → Hesap Eylemleri → E-posta Hesabı Ekle** yolunu izliyoruz.
2. Ad, e-posta adresi ve parolayı girip **Devam**'a tıklıyoruz.
3. Thunderbird ayarları otomatik bulmaya çalışıyor. Bulamazsa ya da bulduğu ayarlar yukarıdaki tabloyla uyuşmuyorsa **Elle yapılandır**'a tıklayıp bilgileri tablodaki gibi giriyoruz.
4. **Yeniden Test Et**'e, ardından **Bitti**'ye tıklıyoruz.

### Sık Karşılaşılan Sorunlar

- **Sertifika uyarısı:** Sunucu adresi olarak `mail.xenonly.com` dışında bir ad (ör. `mail.example.com`) girilmiş olabilir. Sertifika sadece `mail.xenonly.com` için geçerli.
- **Kimlik doğrulama hatası:** Kullanıcı adı olarak e-posta adresinin tamamının girildiğinden emin olalım.
- **Posta gönderilemiyor:** Giden sunucu için 25 numaralı port seçilmiş olabilir. Bu port sunucular arası iletişim için; istemciler 587'yi kullanmalı.
