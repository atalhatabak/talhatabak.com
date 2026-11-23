---
title: "Mail Sunucusu Taşınması"
description: "Mail servisini veritabanı, Maildir ve DKIM anahtarlarıyla birlikte başka bir sunucuya taşıma."
date: 2026-11-21T00:06:00+03:00
chapter: "2.4"
tags: ["mail", "iredmail", "mariadb"]
---
> [!abstract] Gerekenler
> - Yeni sunucuda [2 Mail Sunucu Kurulumu](/self-hosting/mail-server/) tamamlanmış olmalı.
> - Eski sunucuya root yetkisiyle erişilebiliyor olmalı.
>
> **Varsayımlar**
> - Eski sunucunun da iRedMail ile (MariaDB + `/var/vmail`) kurulduğu varsayılmıştır.
> - Yeni sunucuda henüz değerli bir veri yoktur; yeni kurulumdaki `vmail` veritabanının üzerine yazılabilir.
> - Komutlar root yetkisiyle (`sudo`) çalıştırılmıştır. Her komutun hangi sunucuda çalıştırıldığı başında belirtilmiştir.

Bu bölümde daha önce kurulmuş bir mail servisini başka bir sunucuya taşırken veya yedekten geri yüklerken neyin nereye konması gerektiğini inceleyeceğiz.

> [!warning]
> Taşıma işlemi dikkatli ve kontrollü yapılmalı. Bu doküman benim kendi taşımamda uyguladığım adımları içeriyor. Farklı şekilde kurulmuş ya da sürüm farkı olan sistemlerde farklı işlemler gerekebilir.

## Kurduğumuz Yapıyı Anlama

Kurduğumuz sistemde e-posta verileri iki yerde tutuluyor: MariaDB veritabanında ve dosya sisteminde ([Maildir](term:maildir)).

- **Veritabanında:** Alan adları, kullanıcılar, mailbox yolları, alias'lar, yönlendirmeler vb. bilgiler.
- **Dosya sisteminde (`/var/vmail`):** E-postaların kendisi. Gelen kutusu, gönderilmiş öğeler vb. tüm klasörler ve kullanıcıların [Sieve](term:sieve) filtreleri.

Ben yeni bir sunucuya sıfırdan mail servisi kurduğum için yeni mail servisinde değerli bir veri bulunmuyor. Bu yüzden taşıma planım: eski sunucudaki `vmail` veritabanının tamamını ve `/var/vmail/vmail1` dizinini yeni sunucuya taşımak.

> [!note]
> [Roundcube'un](term:roundcube) kendi veritabanı (`roundcubemail`: adres defterleri, kimlikler, imzalar, kullanıcı ayarları) bu plana dahil değil. Kullanıcıların bu verileri de korunmak isteniyorsa `roundcubemail` veritabanı da aynı yöntemle taşınmalı. Roundcube sürümleri farklıysa şema güncellemesi de gerekebilir.

> [!warning]
> Taşıma süresince eski sunucuya gelen postalar yeni sunucuya aktarılmaz. Bunu önlemek için taşımaya başlamadan önce eski sunucuda `sudo systemctl stop postfix dovecot` ile mail servisleri durdurulabilir ya da tüm adımlardan sonra rsync bir kez daha çalıştırılarak son farklar aktarılabilir.

## Eski Verileri Taşıma

### Veritabanı Şemasını Karşılaştırma

Sürüm farkından dolayı eski ve yeni `vmail` veritabanlarının şemasında değişiklik var mı kontrol edelim.

*Eski sunucuda:*

```bash
sudo mariadb-dump --no-data --skip-comments --skip-dump-date \
  --result-file=/root/vmail-old-schema.sql vmail
```

*Yeni sunucuda:*

```bash
sudo mariadb-dump --no-data --skip-comments --skip-dump-date \
  --result-file=/root/vmail-new-schema.sql vmail
```

> [!note]
> Çıktıyı `> /root/...` ile yönlendirmek yerine `--result-file` kullanıyoruz. Yönlendirmeyi `sudo` değil normal kullanıcının kabuğu yaptığı için `/root` dizinine yazılamaz.

Bu komutlarla veritabanı şemalarını aldık. Ardından `scp` ile veya uygun başka bir yöntemle iki dosyayı aynı yere alalım ve farklarına bakalım:

```bash
diff -u vmail-old-schema.sql vmail-new-schema.sql
```

Benim senaryomda herhangi bir fark yoktu, bu yüzden veritabanını tamamen taşımaya karar verdim.

### Veritabanını Taşıma

*Eski sunucuda* veritabanının dökümünü alıyoruz:

```bash
sudo mariadb-dump --single-transaction \
  --routines --triggers --events \
  --result-file=/root/vmail-old.sql \
  --databases vmail
```

`/root/vmail-old.sql` dosyasını yeni sunucuya aktarıyoruz.

*Yeni sunucuda* önce mevcut veritabanının yedeğini alıyoruz:

```bash
sudo mariadb-dump --single-transaction \
  --routines --triggers --events \
  --result-file=/root/vmail-backup.sql \
  --databases vmail
```

Ardından eski veritabanını içe aktarıyoruz:

```bash
sudo sh -c 'mariadb < /root/vmail-old.sql'
```

> [!note]
> Girdi yönlendirmesi de normal kullanıcının kabuğunda yapıldığı için `/root` altındaki dosyayı okuyamaz. Bu yüzden komutu `sudo sh -c` ile tek bir root kabuğunda çalıştırıyoruz.

Aşağıdaki komutlarla doğrulama yapabiliriz:

```bash
sudo mariadb -e "SELECT domain FROM vmail.domain;"

sudo mariadb -e "
SELECT username, domain, maildir
FROM vmail.mailbox;
"
```

### Maildir'i Taşıma

*Eski sunucuda* rsync ile Maildir'i yeni sunucuya gönderiyoruz:

```bash
sudo rsync -aHAX --numeric-ids --info=progress2 /var/vmail/vmail1/ root@<YENI_SUNUCU_IP>:/var/vmail/vmail1/
```

> [!warning]
> `--numeric-ids`, dosya sahipliğini kullanıcı adı yerine uid/gid numarasıyla aktarır. Bu yüzden `vmail` kullanıcısının uid/gid değeri iki sunucuda aynı olmalı; iki sunucuda da `id vmail` ile kontrol edilebilir.

> [!note]
> Kullanıcıların Sieve filtreleri kendi mailbox dizinlerinde (`~/sieve`) tutulduğu için `vmail1` ile birlikte taşınıyor. `/var/vmail` altında taşınması gereken başka bir dizin olup olmadığı eski sunucuda `ls /var/vmail` ile kontrol edilebilir.

> [!warning]
> Rsync dosyaları SSH üzerinden root kullanıcısıyla gönderiyor. [1 Kurulum Sonrası Yapılandırma](/self-hosting/post-install-configuration/) bölümündeki `PermitRootLogin no` ayarı yüzünden root SSH ile giriş yapamıyor. Bu işleme özel olarak yeni sunucuda `/etc/ssh/sshd_config.d/00-hardening.conf` dosyasında geçici olarak `PermitRootLogin prohibit-password` yapılmalı ve eski sunucudaki root'un public key'i `/root/.ssh/authorized_keys` dosyasına eklenmeli. Aktarımdan sonra ikisi de geri alınmalı.

> [!note]
> Bu yöntem, SSH'ın internetten erişilebilir olduğu durumda çalışır. [7.2 Servisleri VPN Arkasına Almak](/self-hosting/services-behind-vpn/) sonrasında SSH sadece VPN'den erişilebildiği için eski sunucu yeni sunucuya bağlanamaz; o durumda [10.1 Eski WordPress'i Mevcut Yapıya Taşımak](/self-hosting/wordpress-migration/) bölümündeki gibi veriler yeni sunucudan çekilmeli.

### DKIM Anahtarlarını Taşıma

Eski sunucudaki alan adlarının [DKIM](term:dkim) anahtarlarını da taşımamız gerekiyor:

1. Eski sunucudaki `/var/lib/dkim/*.pem` dosyalarını yeni sunucuda aynı dizine kopyalıyoruz ve izinlerini düzenliyoruz (`chown amavis:amavis`, `chmod 0400`).
2. Her alan adını [2.2 Mail Sunucusu Yeni Alan Adı Ekleme](/self-hosting/mail-server-new-domain/) bölümünde anlatıldığı gibi `/etc/amavisd/amavisd.conf` dosyasına ekliyoruz.

### Servisleri Yeniden Başlatma

*Yeni sunucuda* servisleri yeniden başlatalım:

```bash
sudo systemctl restart postfix dovecot amavisd
```

### Mailbox Kotalarını Yeniden Hesaplama

```bash
sudo doveadm quota recalc -A
```

Bu komutla mailbox'ların mevcut kullanımını yeniden hesaplıyoruz.

## Son Kontroller

- Her alan adı için sunucudaki DKIM public key'inin DNS'teki kayıtla eşleştiği doğrulanmalı:

  ```bash
  sudo amavisd showkeys <ALAN_ADI> | awk -F'"' '/^[[:space:]]*"/ {printf "%s", $2} END {print ""}'
  ```

- Taşınan alan adlarının DNS kayıtları yeni sunucuya göre güncellenmeli:
  - [SPF](term:spf) kayıtlarındaki IP adresleri yeni sunucunun IP adresleri olmalı.
  - [MX](term:mx-record) kayıtları yeni mail sunucusunu (`mail.xenonly.com`) göstermeli.
  - Yeni sunucunun [PTR kaydı](term:ptr-record) ayarlanmış olmalı (bkz. [2 Mail Sunucu Kurulumu](/self-hosting/mail-server/)).
