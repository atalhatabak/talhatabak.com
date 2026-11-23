---
title: "Mail Sunucu Kurulumu"
description: "Sunucunun ilk temel servisi: iRedMail ile mail servisinin kurulumu. Bu kurulum NGINX ve MariaDB kurulumunu da kapsıyor."
date: 2026-11-21T00:02:00+03:00
chapter: "2"
tags: ["mail", "iredmail", "dns"]
---
> [!abstract] Gerekenler
> - [1 Kurulum Sonrası Yapılandırma](/self-hosting/post-install-configuration/) tamamlanmış olmalı.
> - iRedMail sıfırdan kurulmuş bir sunucuya kurulmalı; bu bölüm sunucuya kurulan ilk servis.
>
> **Varsayımlar**
> - Mail sunucusunun adı (hostname) `mail.xenonly.com`, ilk mail alan adı `xenonly.com` olarak belirlenmiş ve uygulanmıştır.
> - `xenonly.com` ve `mail.xenonly.com` için `A` ve `AAAA` kayıtlarının girildiği varsayılmıştır. Mail için gereken diğer kayıtlar (MX, SPF, DKIM, DMARC, PTR) bu bölümde ekleniyor.
> - Komutlar sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır. `dig` ile yapılan DNS kontrolleri kişisel bilgisayardan yapılmıştır.

Mail işlevleri için temelde [Postfix](term:postfix) ve [Dovecot](term:dovecot) kullanacağız. Kurulum ve ilk yapılandırma için [iRedMail](term:iredmail) kurulum script'ini kullanacağız.

> [!important]
> iRedMail sıfırdan kurulmuş bir sunucuya kurulmalı. Bu yüzden sunucuyu kurduktan sonra ilk olarak iRedMail'i kuruyoruz. Diğer servisleri daha sonra ekleyeceğiz ve iRedMail ile çakışan servislerin yapılandırmalarını kendimize uygun hale getireceğiz.

## Ön Ayarlamalar

### Hostname Değiştirme

Mail sunucusunun adı olarak `mail.xenonly.com` kullanacağım. Sonradan eklenecek diğer alan adları da bu sunucu adını kullanarak mail gönderecek. Aşağıdaki komutla hostname'i değiştiriyoruz:

```bash
sudo hostnamectl set-hostname mail.xenonly.com
```

iRedMail, kurulum sırasında hostname'in tam alan adı ([FQDN](term:fqdn)) olarak çözülmesini bekliyor. Kontrol edelim:

```bash
hostname -f   # mail.xenonly.com
```

Çıktı `mail.xenonly.com` değilse `/etc/hosts` dosyasındaki `127.0.0.1` satırının başına sunucu adını ekleyelim:

```text {title="/etc/hosts"}
127.0.0.1   mail.xenonly.com mail localhost localhost.localdomain
```

### SELinux'u Kapatma

iRedMail, [SELinux](term:selinux) ile çalışmadığını belirtiyor ve kapatılmasını öneriyor. Rocky Linux 10'da önerilen kapatma yöntemi şu:

```bash
sudo grubby --update-kernel ALL --args selinux=0
```

SELinux'u bu komutla kapattıktan sonra sistemi yeniden başlatalım:

```bash
sudo reboot
```

## iRedMail'i İndirme ve Kurma

https://www.iredmail.org/download.html adresinden son sürümün indirme bağlantısını alıyoruz. Bu yazının yazıldığı tarihte (Kasım 2026) son sürüm 1.8.8.

```bash
cd /opt
sudo wget https://github.com/iredmail/iRedMail/archive/refs/tags/1.8.8.tar.gz
sudo tar zxf 1.8.8.tar.gz
cd iRedMail-1.8.8
sudo bash iRedMail.sh
```

> [!note]
> `cd` kabuğun kendi komutu olduğu için `sudo` ile değil, doğrudan çalıştırılıyor. Dosya yazan komutlar `sudo` ile çalıştığı için `/opt` altına yazabiliyor.

Bu komutlarla iRedMail kurulum dosyalarını indirip çalıştırıyoruz. Gerekli paketler kurulduktan sonra kurulum sihirbazı açılıyor:

- **Yes** diyerek devam ediyoruz ve mail depolama dizinini varsayılan değer olan **/var/vmail** olarak bırakıyoruz.
- Web sunucusu → **Nginx**
- Mail hesapları için veritabanı → **MariaDB**
- MariaDB root kullanıcısı için bir parola belirliyoruz. Bu parola `/root/.my.cnf` dosyasına yazılıyor ve root'un veritabanı komutlarıyla yedekleme script'i tarafından kullanılıyor; rastgele olmalı ve postmaster parolasından farklı olmalı.
- İlk mail alan adı → **xenonly.com**. Buradaki önemli nokta: bu değer sunucunun hostname'i (`mail.xenonly.com`) olmamalı.
- `postmaster@xenonly.com` adresi için bir parola belirliyoruz. Bu adres ve parola yönetici hesabı olarak kullanılacak.

> [!warning]
> İki parola için de rastgele üretilmiş güçlü parolalar kullanılması öneriliyor; sihirbaz her iki ekranda da rastgele bir örnek parola gösteriyor. Kurulumda girilen parolalar kurulum sonrasında sunucudaki birkaç dosyaya düz metin olarak yazılıyor. Bunların nerede tutulduğu ve nasıl temizleneceği [2.5 Ekstra Ayarlamalar](/self-hosting/mail-server-extras/) bölümünde.

Devamında isteğe bağlı kurulacak bileşenleri seçiyoruz:

- Webmail → **[Roundcube](term:roundcube)**
- Yönetim paneli → **[iRedAdmin](term:iredadmin)**
- Güvenlik → **Fail2ban**

Bunlar zaten varsayılan olarak seçili geliyor. Ek olarak sistem izleme servisi olan **Netdata**'yı kaldırıyorum.

Kurulum sihirbazı bitince aşağıdaki gibi bir özet gösteriyor:

```text
********************** Review your settings *****************************
*************************************************************************

* Storage base directory:               /var/vmail
* Mailboxes:
* Daily backup of SQL/LDAP databases:
* Store mail accounts in:               MariaDB
* Web server:                           Nginx
* First mail domain name:               xenonly.com
* Mail domain admin:                    postmaster@xenonly.com
* Additional components:                Roundcubemail iRedAdmin Fail2ban
```

**y** seçeneğiyle devam ediyoruz ve kurulum başlıyor. Kurulum sırasında yapılandırmayla ilgili sorular gelecek.

```text
< Question > Would you like to use firewall rules provided by iRedMail?
< Question > File: /etc/firewalld/zones/iredmail.xml, with SSHD ports: 22. [Y|n]
```

Bu soruya `n` cevabını veriyorum. Firewall ayarlarını [5 Firewalld Yapılandırma](/self-hosting/firewalld/) bölümünde kendim yapacağım.

```text
< Question > Would you like to use MySQL configuration file shipped within iRedMail now?
< Question > File: /etc/my.cnf. [Y|n]
```

Bu soruya `Y` cevabıyla onay veriyoruz.

Kurulum aşağıdaki gibi bir çıktıyla tamamlanıyor:

```text
********************************************************************
* URLs of installed web applications:
*
* - Roundcube webmail: https://mail.xenonly.com/mail/
*
* - Web admin panel (iRedAdmin): https://mail.xenonly.com/iredadmin/
*
* You can login to above links with below credential:
*
* - Username: postmaster@xenonly.com
* - Password: ***
*
********************************************************************
* Congratulations, mail server setup completed successfully. Please
* read below file for more information:
*
*   - /opt/iRedMail-1.8.8/iRedMail.tips
*
* And it's sent to your mail account postmaster@xenonly.com.
*
********************* WARNING **************************************
*
* Please reboot your system to enable all mail services.
*
********************************************************************
```

Ardından sistemi yeniden başlatıyoruz:

```bash
sudo reboot
```

## Kurulum Sonrası Ayarlamalar

### DNS Ayarları

DNS kayıtlarını eklemek için alan adının DNS'ini yönettiğimiz sağlayıcının paneline gidiyoruz.

Bu aşamada `xenonly.com` için mail sunucusunda gereken DNS kayıtlarını gireceğiz. Kayıtlar kabaca aşağıdaki gibi olacak.
`<DKIM_ANAHTARI>` değerini aşağıdaki [DKIM](term:dkim) Kaydı kısmında alacağız.

| Name             | Type | Content                                                                                             | Ne Anlama Geliyor                                                                          |
| ---------------- | ---- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| xenonly.com      | A    | `<SUNUCU_IPV4>`                                                                                     | Alan adı için IPv4 kaydı                                                                   |
| xenonly.com      | AAAA | `<SUNUCU_IPV6>`                                                                                     | Alan adı için IPv6 kaydı                                                                   |
| mail.xenonly.com | A    | `<SUNUCU_IPV4>`                                                                                     | Mail sunucusu için IPv4 kaydı                                                              |
| mail.xenonly.com | AAAA | `<SUNUCU_IPV6>`                                                                                     | Mail sunucusu için IPv6 kaydı                                                              |
| xenonly.com      | [MX](term:mx-record)   | `mail.xenonly.com`                                                                                  | Gelen e-postaların hangi mail sunucusuna yönlendirileceğini belirtir                       |
| dkim._domainkey  | TXT  | `<DKIM_ANAHTARI>`                                                                                   | [Amavis](term:amavis) tarafından imzalanan e-postaların doğrulanmasını sağlar                             |
| _dmarc           | TXT  | `"v=DMARC1; p=quarantine; sp=quarantine; np=reject; adkim=s; aspf=s; rua=mailto:dmarc@xenonly.com"` | [SPF](term:spf) veya DKIM doğrulamasından geçemeyen e-postalara ne yapılacağını belirtir               |
| xenonly.com      | TXT  | `"v=spf1 mx a ip4:<SUNUCU_IPV4> ip6:<SUNUCU_IPV6> ~all"`                                            | Hangi sunucuların bu alan adı adına mail göndermeye yetkili olduğunu belirtir              |
| mail.xenonly.com | TXT  | `"v=spf1 a -all"`                                                                                   | Sunucunun [HELO](term:helo) adı için SPF; gönderici adresi boş olan [bounce'lar](term:bounce) bu adla kontrol ediliyor |

> [!note]
> `Name` sütunundaki `dkim._domainkey` ve `_dmarc` değerleri alan adına göre yazılmıştır; tam halleri `dkim._domainkey.xenonly.com` ve `_dmarc.xenonly.com`.

### DMARC Kaydı

Örnek kayıt:

```text
v=DMARC1; p=quarantine; sp=quarantine; np=reject; adkim=s; aspf=s; rua=mailto:dmarc@xenonly.com
```

| Parametre       | Anlamı                                                                                                                                                                                                                                          |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `v=DMARC1`      | Sürüm. Her zaman en başta olmalı.                                                                                                                                                                                                               |
| `p=quarantine`  | Doğrulamadan geçemeyen postalar spam klasörüne gönderilir. Diğer seçenekler: `none` (sadece rapor gönderilir, posta etkilenmez) ve `reject` (posta tamamen reddedilir).                                                                        |
| `sp=quarantine` | Aynı kural alt alan adları için (ör. `x.xenonly.com`). Yazılmazsa `p` değeri geçerli olur. Hiçbir alt alan adından posta gönderilmiyorsa `reject` da kullanılabilir.                                                                           |
| `np=reject`     | DNS'te hiç var olmayan alt alan adları (ör. `random.xenonly.com`) adına gönderilen postalar reddedilir. Bu adlardan gerçek bir posta gelemeyeceği için en sıkı ayar güvenle kullanılabilir. Görece yeni bir parametre olduğu için henüz tanımayan sunucular olabilir, ama eklemenin bir zararı yok. |
| `adkim=s`       | DKIM için sıkı eşleşme: imzadaki alan adının gönderen adresteki alan adıyla birebir aynı olması gerekir. `r` (gevşek) seçilirse alt alan adları da kabul edilir.                                                                                |
| `aspf=s`        | SPF için sıkı eşleşme. Mantığı yukarıdakiyle aynı.                                                                                                                                                                                              |
| `rua=mailto:…`  | Günlük toplu raporların gönderileceği adres.                                                                                                                                                                                                    |

> [!note]
> [DMARC](term:dmarc) raporlarının gönderileceği `dmarc@xenonly.com` adresi için bir posta hesabı oluşturmamız gerekiyor. Bunu aşağıda, DMARC Raporları için Hesap kısmında yapacağız.

### PTR Kaydı

[PTR](term:ptr-record) (Reverse DNS) kaydı, bir IP adresinin hangi alan adına karşılık geldiğini gösterir ve [VPS](term:vps) sağlayıcısının yönetim panelinden ayarlanır. Paneldeki rDNS/PTR kısmında sunucunun IPv4 adresi için `mail.xenonly.com`, varsa IPv6 adresi için de yine `mail.xenonly.com` giriyoruz.

> [!warning]
> PTR değeri `xenonly.com` değil, sunucunun hostname'i olan `mail.xenonly.com` olmalı.

> [!warning]
> Sunucuda IPv6 varsa mailler büyük ihtimalle IPv6 üzerinden gönderilmeye çalışılacak. IPv6 için PTR eşleşmezse Gmail gibi sağlayıcılar maili doğrudan reddeder.

Kayıtları kişisel bilgisayarımızdan aşağıdaki komutlarla kontrol edebiliriz:

```bash
dig +short A mail.xenonly.com      # <SUNUCU_IPV4>
dig +short AAAA mail.xenonly.com   # <SUNUCU_IPV6>
dig +short -x <SUNUCU_IPV4>        # mail.xenonly.com.
dig +short -x <SUNUCU_IPV6>        # mail.xenonly.com.
```

### DKIM Kaydı

**Nedir:** Gönderilen e-postaların gerçekten yetkili alan adından çıktığını ve yolda değiştirilmediğini doğrulayan bir dijital imza standardı.

#### Nasıl Çalışıyor

- `/var/lib/dkim/` dizininde her alan adı için bir private key bulunuyor.
- `/etc/amavisd/amavisd.conf` dosyasında Amavis servisi için alan adı ve anahtar tanımlanıyor.
- `dkim._domainkey` DNS kaydında ise public key bulunuyor.

> [!note]
> Kurulumda ilk alan adı olarak `xenonly.com` verdiğimiz için bu alan adının anahtarları otomatik olarak oluşturulmuş durumda.

Mevcut anahtarları görmek için:

```bash
sudo amavisd showkeys
```

DNS kaydına doğrudan eklenecek biçimde tek satırlık çıktı almak için:

```bash
sudo amavisd showkeys xenonly.com | awk -F'"' '/^[[:space:]]*"/ {printf "%s", $2} END {print ""}'
```

> [!note]
> DNS'e eklenen değer tek satır olmalı. `amavisd showkeys` anahtarı birden çok satıra bölerek yazıyor, yukarıdaki komut bu satırları birleştiriyor.

Bu çıktıyı DNS'e aşağıdaki gibi ekliyoruz:

| Name            | Type | Content           | Ne Anlama Geliyor                                              |
| --------------- | ---- | ----------------- | -------------------------------------------------------------- |
| dkim._domainkey | TXT  | `<DKIM_ANAHTARI>` | Amavis tarafından imzalanan e-postaların doğrulanmasını sağlar |

Bu noktada sunucumuz `xenonly.com` adına mail gönderebilir ve alabilir.

## iRedAdmin'de Kullanıcı Oluşturma

> [!note]
> iRedMail kurulumundan gelen NGINX yapılandırmasında iRedAdmin `/iredadmin`, Roundcube ise `/mail` yolunda bulunuyor. Bu adresler [3 NGINX Yapılandırması](/self-hosting/nginx/) bölümünde alt alan adlarına (`iredadmin.xenonly.com` ve `mail.xenonly.com`) taşınacak.

> [!note]
> Sunucu şu an iRedMail'in oluşturduğu [self-signed sertifikayı](term:self-signed) kullandığı için tarayıcı sertifika uyarısı verecek. [Let's Encrypt](term:lets-encrypt) sertifikasını [2.1 Mail Sunucusu için SSL Ayarlama](/self-hosting/mail-server-ssl/) bölümünde alacağız.

<https://xenonly.com/iredadmin> adresine gidip yönetici hesabıyla (`postmaster@xenonly.com`) giriş yapıyoruz.

> [!note]
> `xenonly.com` alan adı kurulumda ilk alan adı olarak oluşturulduğu için ayrıca eklememize gerek yok.

**Add → User** yolunu izleyerek `xenonly.com` için `info` adında bir kullanıcı oluşturuyoruz.

> [!tip]
> Var olan alan adları için istenildiği kadar kullanıcı oluşturulabilir. Yeni alan adı eklemek için bkz. [2.2 Mail Sunucusu Yeni Alan Adı Ekleme](/self-hosting/mail-server-new-domain/).

### DMARC Raporları için Hesap

DMARC kaydındaki `rua=mailto:dmarc@xenonly.com` adresine raporların ulaşabilmesi için yine **Add → User** yolunu izleyerek `xenonly.com` için `dmarc` adında bir kullanıcı oluşturuyoruz.

> [!note]
> Her alan adı için, o alan adının DMARC kaydında belirtilen rapor adresine ait bir posta hesabı oluşturulmalı.

## Test ve Kontrol

<https://xenonly.com/mail> adresinden Roundcube'a gidip `info@xenonly.com` kullanıcısıyla giriş yapalım.

<https://www.mail-tester.com/> adresinde verilen adrese bir test maili gönderelim. Beklenen sonuç:

```text
Your lovely total: 10/10
```
