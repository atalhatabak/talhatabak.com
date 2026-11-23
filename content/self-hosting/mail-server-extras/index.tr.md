---
title: "Mail Sunucusu: Ekstra Ayarlamalar"
linkTitle: "Ekstra Ayarlamalar"
description: "Alias ekleme, Roundcube'da kullanıcı adını otomatik tamamlama, kurulumda düz metin olarak kalan parolaları temizleme ve hesaplara gönderim limiti koyma."
date: 2026-11-21T00:07:00+03:00
chapter: "2.5"
tags: ["mail", "iredmail", "roundcube"]
---
> [!abstract] Gerekenler
> - [2 Mail Sunucu Kurulumu](/self-hosting/mail-server/) tamamlanmış olmalı.
>
> **Varsayımlar**
> - Örnek alias olarak `abuse@xenonly.com` adresinin `info@xenonly.com` hesabına yönlendirilmesi alınmıştır.
> - Komutlar sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır.

Bu bölümde mail sunucusu için zorunlu olmayan ama işe yarayan birkaç ayarı yapacağız.

## Alias Ayarlama

Alias, kendi posta kutusu olmayan ve gelen postaları bir veya birden fazla hesaba yönlendiren bir adres. Örneğin `abuse@xenonly.com` adresine gelen postaların `info@xenonly.com` hesabına düşmesini istiyoruz.

> [!note]
> [iRedAdmin'in](term:iredadmin) açık kaynak sürümünde alias yönetimi yok (**Add → Alias** menüsü sadece iRedAdmin-Pro'da). Bu yüzden alias'ı doğrudan `vmail` veritabanına ekleyeceğiz.

Host'taki MariaDB'de `vmail` veritabanına bağlanalım:

```bash
sudo mariadb vmail
```

Alias'ı ve yönlendirileceği hesabı ekleyelim:

```sql
INSERT INTO alias (address, domain, active)
VALUES ('abuse@xenonly.com', 'xenonly.com', 1);

INSERT INTO forwardings (address, forwarding, domain, dest_domain, is_list, active)
VALUES ('abuse@xenonly.com', 'info@xenonly.com', 'xenonly.com', 'xenonly.com', 1, 1);

exit
```

- **`alias` tablosu:** Alias adresinin kendisi.
- **`forwardings` tablosu:** Alias'a gelen postaların gideceği adres. Birden fazla hesaba yönlendirmek için her hesap için ayrı bir satır eklenir.
- **`is_list = 1`:** Bu satırın bir alias üyeliği olduğunu belirtiyor.

> [!note]
> [Postfix](term:postfix) adresleri veritabanından sorguladığı için servisleri yeniden başlatmaya gerek yok.

`abuse@xenonly.com` adresine bir test postası gönderelim; posta `info@xenonly.com` hesabına düşmeli.

## Roundcube Kullanıcı Adını Otomatik Tamamlama

[Roundcube'a](term:roundcube) giriş yaparken kullanıcı adı olarak e-posta adresinin tamamını yazmak gerekiyor. Sadece `info` yazıldığında adresin `info@xenonly.com` olarak tamamlanması için `/opt/www/roundcubemail/config/config.inc.php` dosyasının sonuna aşağıdaki satırı ekleyelim:

```php {title="/opt/www/roundcubemail/config/config.inc.php"}
$config['username_domain'] = 'xenonly.com';
```

> [!note]
> Bu ayar sadece Roundcube'un giriş ekranı için geçerli. Başka bir alan adındaki kullanıcılar (ör. `info@example.com`) adresin tamamını yazmaya devam etmeli. [IMAP](term:imap) istemcilerinde de kullanıcı adı her zaman adresin tamamı (bkz. [2.3 İstemci Kullanmak](/self-hosting/mail-clients/)).

PHP yapılandırmayı her istekte okuduğu için servisleri yeniden başlatmaya gerek yok.

## Açık Parola Kontrolü

Kurulum sihirbazında iki parola giriyoruz: **MariaDB root parolası** ve **postmaster parolası**. Bunlara ek olarak [iRedMail](term:iredmail), servislerin veritabanı kullanıcıları için kendi parolalarını rastgele üretiyor. Kurulum script'i bu parolaların hepsini birkaç yere düz metin olarak yazıyor.

Bu kısımda hangi parolanın nerede tutulduğuna, hangi servisin onu gerçekten kullandığına ve düz metin kopyalardan nasıl kurtulacağımıza bakacağız.

### Parolalar Nerede Tutuluyor

| Yer                                                                                                   | İçerik                                        | Bir servis kullanıyor mu?                                                                                                          |
| ----------------------------------------------------------------------------------------------------- | --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `/opt/iRedMail-1.8.8/iRedMail.tips`                                                                   | Tüm parolalar                                 | Hayır, sadece bilgi amaçlı                                                                                                         |
| `/opt/iRedMail-1.8.8/config`                                                                          | Sihirbazın cevapları ve tüm parolalar         | Hayır. Kurulum script'i aynı dizinde tekrar çalıştırılırsa soruları yeniden sormamak için okuyor; kurulum bittikten sonra gereksiz |
| Postmaster posta kutusundaki **Details of this iRedMail installation** maili                          | `iRedMail.tips` dosyasının içeriği            | Hayır                                                                                                                              |
| `/root/.iredmail/kv/`                                                                                 | Her parola için ayrı bir dosya                | Hayır, iRedMail'in hiçbir bileşeni bu dizini okumuyor                                                                              |
| `/root/.my.cnf`                                                                                       | Sadece MariaDB root parolası                  | **Evet**, aşağıda                                                                                                                  |
| `/root/.my.cnf-<kullanıcı>`                                                                           | Servis veritabanı kullanıcılarının parolaları | Hayır, root'un bu kullanıcılarla kolayca bağlanabilmesi için                                                                       |
| Servislerin yapılandırma dosyaları (`/etc/postfix/mysql/`, Roundcube, iRedAdmin, [Amavis](term:amavis), [iRedAPD](term:iredapd) vb.) | Sadece o servisin kendi veritabanı parolası   | **Evet**, servisler parolayı bu dosyalardan okuyor                                                                                 |

### Hangi Parola Nerede Kullanılıyor

**Postmaster parolası:** Sadece giriş için kullanılıyor (Roundcube, iRedAdmin, IMAP/[SMTP](term:smtp)). Veritabanında [hash](term:hash) olarak tutuluyor; hiçbir servis bu parolanın düz metin haline ihtiyaç duymuyor. Düz metin kopyaları:

- `iRedMail.tips`
- `config`
- `/root/.iredmail/kv/first_domain_admin_password`
- Kurulum maili

**MariaDB root parolası:** Hiçbir mail servisi bu parolayı kullanmıyor; her servisin kendi veritabanı kullanıcısı var. Parolayı sadece `/root/.my.cnf` üzerinden şunlar kullanıyor:

- Root yetkisiyle çalıştırılan `mariadb` ve `mariadb-dump` komutları (ör. bu bölümdeki ve [2.4 Mail Sunucusu Taşınması](/self-hosting/mail-server-migration/) bölümündeki `sudo mariadb` komutları)
- Her gece 03:30'da çalışan veritabanı yedekleme script'i (`/var/vmail/backup/backup_mysql.sh`)

Düz metin kopyaları: `iRedMail.tips`, `config`, `/root/.iredmail/kv/sql_user_root`, kurulum maili ve `/root/.my.cnf`.

**Servis parolaları:** `vmail`, `vmailadmin`, `roundcube`, `amavisd`, `iredadmin`, `iredapd` ve `fail2ban` veritabanı kullanıcılarının parolaları, Roundcube'un şifreleme anahtarı (`roundcube_des_key`) ve iRedAPD'nin SRS anahtarı (`iredapd_srs_secret`). Hepsi rastgele üretiliyor ve servislerin kendi yapılandırma dosyalarında kullanılıyor; bunlara dokunmuyoruz.

> [!note]
> Sihirbaz MariaDB root parolasını ve postmaster parolasını ayrı ayrı soruyor ve ikisinde de rastgele bir örnek parola öneriyor. İkisine aynı parola girildiyse `/root/.my.cnf` dosyasında postmaster parolası görünür, ama dosyadaki parola MariaDB root parolasıdır.

### Temizleme

#### 1. Bilgi Amaçlı Kopyaları Silme

Gerekiyorsa parolaları bir parola yöneticisine (ör. [9 Vaultwarden Kurulumu](/self-hosting/vaultwarden/)) kaydettikten sonra kurulum dizinindeki dosyaları silelim:

```bash
sudo rm /opt/iRedMail-1.8.8/iRedMail.tips /opt/iRedMail-1.8.8/config
sudo chmod 700 /opt/iRedMail-1.8.8
sudo rm /opt/1.8.8.tar.gz
```

`/root/.iredmail/kv/` dizininden elle girdiğimiz iki parolanın kopyalarını silelim:

```bash
sudo rm /root/.iredmail/kv/first_domain_admin_password /root/.iredmail/kv/sql_user_root
```

> [!note]
> Dizinde kalan dosyalar rastgele üretilmiş servis parolaları. Başka bir yerde kullanılmadıkları ve dosyaları sadece root okuyabildiği için bırakıyoruz; ileride bir servisin veritabanı parolasına ihtiyaç olursa buradan bakılabilir.

Roundcube'a `postmaster@xenonly.com` ile giriş yapıp **Details of this iRedMail installation** konulu maili silelim ve çöp kutusunu boşaltalım. Mailin sunucudan tamamen silindiğini kontrol edelim:

```bash
sudo find /var/vmail -name 'details.eml*'   # çıktı boş olmalı
```

#### 2. MariaDB Root Parolasını Değiştirme

MariaDB root parolası rastgele üretilmediyse (ör. postmaster parolasıyla aynıysa veya başka bir yerde de kullandığımız bir parolaysa) değiştirilmeli. Bu parolayı sadece `/root/.my.cnf` kullandığı için yeni bir parolayı rastgele üretip veritabanında ve bu dosyada güncellememiz yeterli.

Önce root kullanıcısının hangi host'lar için tanımlı olduğuna bakalım:

```bash
sudo mariadb -e "SELECT user, host FROM mysql.user WHERE user='root';"
```

Çıktıda sadece `root | localhost` satırı olmalı. Başka satırlar varsa aşağıdaki `SET PASSWORD` komutu her biri için tekrarlanmalı.

```bash
PW=$(openssl rand -hex 24)
sudo mariadb -e "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('$PW');"
sudo sed -i "s/^password=.*/password=\"$PW\"/" /root/.my.cnf
unset PW
```

- Komut geçmişine parolanın kendisi değil `$PW` yazıldığı için yeni parola geçmişte görünmüyor.
- Sıra önemli: İkinci komut eski parolayla (`/root/.my.cnf` üzerinden) bağlanıp parolayı değiştiriyor, üçüncü komut dosyayı yeni parolayla güncelliyor.

> [!note]
> Yeni parolayı bir yere kaydetmemize gerek yok. Root kullanıcısı MariaDB'ye `/root/.my.cnf` üzerinden bağlanıyor; parolaya ihtiyaç olursa `sudo cat /root/.my.cnf` ile bakılabilir.

Root'un hâlâ bağlanabildiğini ve yedekleme script'inin çalıştığını kontrol edelim:

```bash
sudo mariadb -e "SELECT CURRENT_USER();"     # root@localhost
sudo bash /var/vmail/backup/backup_mysql.sh  # hata vermeden yedek almalı
```

Yedekler `/var/vmail/backup/mysql/<yıl>/<ay>/<gün>/` dizinine yazılıyor.

## Gönderim Limiti (Throttle)

SMTP girişi yapabilen her hesap, kendi adresinden istediği kadar mail gönderebiliyor. Parolası çalınmış bir hesap ya da ele geçirilmiş bir [konteynerdeki](term:container) servis hesabı, kısa sürede binlerce spam gönderebilir. Bütün alan adları aynı IP'den gönderdiği için zarar o hesapla sınırlı kalmaz: IP [kara listelere](term:dnsbl) girer ve bütün alan adlarının mailleri reddedilmeye başlar.

iRedMail ile kurulan iRedAPD'nin `throttle` eklentisi, bir hesabın belirli bir sürede gönderebileceği mail sayısını sınırlıyor. Bu kısımda bütün hesaplar için varsayılan bir limit koyacağız.

> [!note]
> iRedAdmin'in açık kaynak sürümünde throttle ayarları yok; bu ayarlar sadece iRedAdmin-Pro'da var. Bu yüzden ayarları doğrudan `iredapd` veritabanına ekleyeceğiz.

### 1. Ön Kontroller

Throttle eklentisinin açık olduğunu kontrol edelim:

```bash
sudo grep '^plugins' /opt/iredapd/settings.py
```

Listede `throttle` olmalı. Yoksa listeye ekleyip iRedAPD'yi yeniden başlatalım (`sudo systemctl restart iredapd`).

Eklenti, gönderilen mailleri mail tamamen alındıktan sonra (END-OF-MESSAGE aşamasında) sayıyor. Bunun için Postfix'in iRedAPD'ye bu aşamada da sorması gerekiyor:

```bash
sudo postconf smtpd_end_of_data_restrictions   # check_policy_service ... 127.0.0.1 ... 7777
sudo postconf -P | grep -E '^(submission|smtps)/.*end_of_data'   # çıktı boş olmalı
```

- **İlk komut:** Çıktıda iRedAPD'nin adresi (`127.0.0.1`, port `7777`) görünmeli. Boşsa limit hiçbir maile uygulanmaz.
- **İkinci komut:** `master.cf`'te 587 (`submission`) veya 465 (`smtps`) servisinin bu ayarı ezip ezmediğine bakıyor. Ezerse istemcilerin gönderdiği maillere limit uygulanmaz.

Mevcut throttle ayarlarına bakalım:

```bash
sudo mariadb iredapd -e "SELECT * FROM throttle;"
```

Temiz kurulumda tablo boş geliyor. Yani hiçbir hesap için limit tanımlı değil.

### 2. Varsayılan Limiti Ekleme

Host'taki MariaDB'de `iredapd` veritabanına bağlanalım:

```bash
sudo mariadb iredapd
```

Bütün hesaplar için günde 300 maillik bir limit ekleyelim:

```sql
INSERT INTO throttle (account, kind, priority, period, max_msgs)
VALUES ('@.', 'outbound', 0, 86400, 300);

exit
```

- **`account = '@.'`:** Bütün hesaplar. Sondaki nokta gerekli. Limit her hesaba ayrı ayrı uygulanıyor; bir hesabın gönderdiği mailler diğer hesapların limitinden düşmüyor.
- **`kind = 'outbound'`:** Giriş yaparak ([SASL](term:sasl)) gönderilen mailler. Thunderbird gibi istemciler, Roundcube ve konteynerler 587 veya 465 portundan giriş yaparak gönderdiği için hepsini kapsıyor.
- **`period = 86400`:** Süre, saniye cinsinden (1 gün). Süre hesabın ilk mailiyle başlıyor; süre dolunca sayaç sıfırlanıyor.
- **`max_msgs = 300`:** Bu sürede gönderilebilecek mail sayısı. Alıcı başına sayılıyor: 10 alıcılı bir mail 10 mail sayılıyor.
- **`priority = 0`:** Bir hesaba birden fazla ayar uyuyorsa önceliği yüksek olan uygulanıyor. Hesaba özel ayarları `100` ile ekleyeceğiz.
- **Eklemediğimiz sütunlar (`msg_size`, `max_quota`, `max_rcpts`):** `-1` olarak kalıyor. `-1`, değerin daha düşük öncelikli bir ayardan alınacağı anlamına geliyor. Daha düşük öncelikli bir ayar olmadığı için bu limitler uygulanmıyor. Mail boyutunu zaten Postfix'in `message_size_limit` ayarı sınırlıyor.

> [!note]
> Aynı alan adındaki adreslere giden mailler sayılmıyor (`THROTTLE_BYPASS_SAME_DOMAIN`, varsayılanı `True`). Örneğin `info@xenonly.com`'dan `abuse@xenonly.com`'a giden mail limitten düşmüyor. Spam dışarıya gönderildiği için bu bir açık oluşturmuyor.

iRedAPD ayarları her mailde veritabanından okuduğu için servisi yeniden başlatmaya gerek yok.

> [!note]
> 300, kişisel kullanım için seçilmiş bir değer. Parolası çalınmış bir hesap bu limitle günde en fazla 300 alıcıya mail gönderebilir. Hesap fark edilmeden kalsa bile IP'nin kara listeye girme ihtimali çok düşüyor. Daha fazla göndermesi gereken hesaplara aşağıdaki gibi ayrı bir limit verilebilir.

### 3. Hesaba Özel Limit

Servis hesapları (ör. [9 Vaultwarden Kurulumu](/self-hosting/vaultwarden/) bölümündeki `vaultwarden@xenonly.com`) günde birkaç mail gönderiyor. Bunlara daha düşük bir limit verelim:

```sql
INSERT INTO throttle (account, kind, priority, period, max_msgs)
VALUES ('vaultwarden@xenonly.com', 'outbound', 100, 86400, 50);
```

`priority = 100` olduğu için bu hesapta varsayılan ayarın yerine bu ayar uygulanıyor. Daha fazla göndermesi gereken bir hesaba da aynı şekilde daha yüksek bir limit verilebilir. Bir hesabın limitini tamamen kaldırmak için `max_msgs = 0` yazılır.

Var olan bir limiti değiştirmek için:

```sql
UPDATE throttle SET max_msgs = 100
WHERE account = 'vaultwarden@xenonly.com' AND kind = 'outbound';
```

Limitini dolduran bir hesabın sayacını süre dolmadan sıfırlamak için:

```bash
sudo mariadb iredapd -e "DELETE FROM throttle_tracking WHERE account = 'info@xenonly.com';"
```

### 4. Test

Limitin çalıştığını düşük bir limitle test edelim. `info@xenonly.com` için geçici olarak saatte 2 maillik bir limit ekleyelim:

```bash
sudo mariadb iredapd -e "INSERT INTO throttle (account, kind, priority, period, max_msgs) VALUES ('info@xenonly.com', 'outbound', 100, 3600, 2);"
```

Roundcube'dan `info@xenonly.com` ile **başka bir alan adındaki** bir adrese (ör. kişisel Gmail adresimize) tek tek üç mail gönderelim. İlk iki mail gitmeli, üçüncüsünde Roundcube hata vermeli.

> [!important]
> Test başka bir alan adına yapılmalı. Aynı alan adındaki adreslere giden mailler sayılmadığı için `xenonly.com` adreslerine gönderilen mailler limiti doldurmuyor.

Reddedilen maili iRedAPD logunda ve hesabın sayacında görebiliriz:

```bash
sudo grep -i exceeded /var/log/iredapd/iredapd.log | tail -n 3
sudo mariadb iredapd -e "SELECT account, cur_msgs, FROM_UNIXTIME(init_time) FROM throttle_tracking;"
```

Testten sonra geçici limiti ve sayacını silelim:

```bash
sudo mariadb iredapd -e "
DELETE FROM throttle_tracking WHERE tid = (SELECT id FROM throttle WHERE account = 'info@xenonly.com' AND kind = 'outbound');
DELETE FROM throttle WHERE account = 'info@xenonly.com' AND kind = 'outbound';"
```

> [!note]
> Sayaç tablosu (`throttle_tracking`) [foreign key](term:foreign-key) ile ayar tablosuna bağlı. Önce sayaç silinmezse ayar silinemiyor.
