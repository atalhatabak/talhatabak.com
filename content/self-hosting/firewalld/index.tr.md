---
title: "Firewalld Yapılandırma"
description: "Kurulum boyunca kapalı tuttuğumuz Firewalld'nin yapılandırılıp etkinleştirilmesi ve konteynerlerle VPN istemcilerinin dışarıya 25. porttan çıkışının engellenmesi."
date: 2026-11-21T00:11:00+03:00
chapter: "5"
tags: ["firewalld"]
---
> [!abstract] Gerekenler
> - [2 Mail Sunucu Kurulumu](/self-hosting/mail-server/), [3 NGINX Yapılandırması](/self-hosting/nginx/) ve [4 Docker Kurulumu](/self-hosting/docker/) tamamlanmış olmalı.
>
> **Varsayımlar**
> - Firewalld [1 Kurulum Sonrası Yapılandırma](/self-hosting/post-install-configuration/) bölümünde kapatılmış, iRedMail'in Firewalld yapılandırması da kurulumda uygulanmamıştır.
> - Dış ağ arayüzü `eth0`, SSH ise varsayılan port olan 22'de çalışmaktadır.
> - Komutlar sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır.

## Hangi Portları Açacağız

| Servis          | Port             | Neden                                                                                              |
| --------------- | ---------------- | -------------------------------------------------------------------------------------------------- |
| ssh             | 22/tcp           | SSH için varsayılan port. SSH başka bir portta çalışıyorsa `--add-port=<PORT>/tcp` ile eklenmeli |
| http / https    | 80/tcp, 443/tcp  | NGINX                                                                                              |
| smtp            | 25/tcp           | Diğer sunuculardan gelen mail                                                                      |
| smtp-submission | 587/tcp          | İstemcilerin mail göndermesi ([STARTTLS](term:starttls))                                                            |
| smtps           | 465/tcp          | İstemcilerin mail göndermesi ([TLS](term:tls))                                                                 |
| imap / imaps    | 143/tcp, 993/tcp | Mail okuma                                                                                         |

## Başlangıç Durumu

Başlangıç durumunu kontrol edelim:

```bash
sudo systemctl is-active firewalld
sudo firewall-offline-cmd --get-default-zone
sudo firewall-offline-cmd --zone=public --list-all
```

Aşağıdaki gibi bir çıktı vermeli:

```text
inactive
public
public (default)
 target: default
 ingress-priority: 0
 egress-priority: 0
 icmp-block-inversion: no
 interfaces:
 sources:
 services: cockpit dhcpv6-client ssh
 ports:
 protocols:
 forward: yes
 masquerade: no
 forward-ports:
 source-ports:
 icmp-blocks:
 rich rules:
```

Bu, varsayılan Firewalld yapılandırması. Firewalld şu an kapalı; bu şekilde devam ediyoruz.

## Public Zone Yapılandırması

Cockpit varsayılan olarak izinli geliyor; kullanmayacağımız için kaldıralım. Firewalld kapalı olduğu için `firewall-cmd` yerine `firewall-offline-cmd` kullanacağız.

```bash
sudo firewall-offline-cmd --zone=public --remove-service-from-zone=cockpit
```

Kullandığımız servisleri ekliyoruz:

```bash
sudo firewall-offline-cmd --zone=public \
 --add-service=ssh --add-service=http --add-service=https \
 --add-service=smtp --add-service=smtp-submission --add-service=smtps \
 --add-service=imap --add-service=imaps
```

`ssh` varsayılan olarak açık geldiği için `Warning: ALREADY_ENABLED: ssh` uyarısı normal. Devamında `success` çıktısı gelecek.

Eklediğimiz servisler NGINX'in kullanacağı `http` ve `https` ile mail servisi için gerekenler. POP3 kullanmayacağım için eklemedim.

Değişiklikleri kontrol edelim:

```bash
sudo firewall-offline-cmd --zone=public --list-all
```

Aşağıdaki gibi bir çıktı vermeli:

```text
public (default)
 target: default
 ingress-priority: 0
 egress-priority: 0
 icmp-block-inversion: no
 interfaces:
 sources:
 services: dhcpv6-client http https imap imaps smtp smtp-submission smtps ssh
 ports:
 protocols:
 forward: yes
 masquerade: no
 forward-ports:
 source-ports:
 icmp-blocks:
 rich rules:
```

## Kurtarma Zamanlayıcısı ve Başlatma

Firewalld etkinleştikten sonra bir sorun çıkar ve SSH ile bağlanamazsak diye önlem olarak, Firewalld'yi 10 dakika sonra durduran bir zamanlayıcı kuralım:

```bash
sudo systemd-run --on-active=10min --unit=fw-rescue systemctl stop firewalld
```

Ardından Firewalld'yi etkinleştirip başlatabiliriz:

```bash
sudo systemctl enable --now firewalld
sudo firewall-cmd --get-active-zones
```

Firewalld açıldığında mevcut SSH oturumu kopmaz, çünkü zaten kurulmuş bağlantılara izin verilmeye devam eder. Bu yüzden testi **yeni bir terminalden yeni bir SSH bağlantısı** açarak yapalım. Bağlantı kurulabiliyorsa zamanlayıcıyı iptal edebiliriz:

```bash
sudo systemctl stop fw-rescue.timer
```

## Docker Entegrasyonu

Docker'ı Firewalld yapılandırmasından önce kurduğumuz için Docker kendi Firewalld ayarlarını (`docker` [zone'u](term:firewalld-zone) ve `docker-forwarding` [policy'si](term:firewalld-policy)) oluşturamadı. Bunun için Docker'ı yeniden başlatmamız yeterli:

```bash
sudo systemctl restart docker
```

### Kontrol

```bash
sudo firewall-cmd --get-active-zones
```

```text
docker
 interfaces: docker0
public (default)
 interfaces: eth0
```

```bash
sudo firewall-cmd --zone=docker --list-all
```

```text
docker (active)
 target: ACCEPT
 ingress-priority: 0
 egress-priority: 0
 icmp-block-inversion: no
 interfaces: docker0
 sources:
 services:
 ports:
 protocols:
 forward: yes
 masquerade: no
 forward-ports:
 source-ports:
 icmp-blocks:
 rich rules:
```

```bash
sudo firewall-cmd --get-policies
```

```text
allow-host-ipv6 docker-forwarding gateway-dmz-to-HOST gateway-lan-to-HOST gateway-lan-to-work gateway-lan-to-world gateway-world-to-HOST
```

Çıktılarda `docker` zone'u ve `docker-forwarding` policy'si görünüyorsa Docker'ın Firewalld yapılandırması başarıyla yapılmış demektir.

## Dışarıya 25. Porttan Çıkışı Engelleme

Sunucunun üzerinden internete çıkan her şey, yani [konteynerler](term:container) ve [7 WireGuard Kurulumu](/self-hosting/wireguard/) bölümünde kuracağımız VPN istemcileri, mail sunucusuyla aynı IP adreslerini kullanıyor. Bu adreslerin [PTR kaydı](term:ptr-record) `mail.xenonly.com`'u gösteriyor. Ele geçirilmiş bir konteyner ya da VPN'e bağlı bir cihaz dışarıya 25. porttan doğrudan spam gönderirse [kara listeye](term:dnsbl) mail sunucumuzun IP'si girer.

Mail sunucuları birbirleriyle 25. port üzerinden konuşuyor ve dışarıya bu porttan sadece host'taki [Postfix'in](term:postfix) çıkması gerekiyor. Konteynerler maillerini kendi mail sunucumuza 587 portundan, kimlik doğrulamasıyla gönderiyor. Bu bağlantı yönlendirilmiyor, doğrudan host'a geliyor; bu yüzden engelden etkilenmiyor.

Önce sorunu görelim. Bir konteynerden Gmail'in mail sunucusuna 25. porttan bağlanmayı deneyelim:

```bash
sudo docker run --rm alpine nc -v -w 5 gmail-smtp-in.l.google.com 25
```

```text
gmail-smtp-in.l.google.com (64.233.167.26:25) open
```

`open` satırı, konteynerin dışarıdaki bir mail sunucusuna 25. porttan doğrudan bağlanabildiğini gösteriyor.

Sunucunun üzerinden geçen (forward edilen) ve dışarıda 25. porta giden trafiği reddeden bir policy oluşturalım:

```bash
# no-smtp-out adında yeni ve boş bir policy oluşturur.
sudo firewall-cmd --permanent --new-policy=no-smtp-out

# Herhangi bir zone'dan (ANY) gelip public zone'una (internete) yönlendirilen trafiğe uygulanır.
# ANY, sunucunun kendi trafiğini (HOST) kapsamıyor; Postfix etkilenmiyor.
sudo firewall-cmd --permanent --policy=no-smtp-out --add-ingress-zone=ANY
sudo firewall-cmd --permanent --policy=no-smtp-out --add-egress-zone=public

# Policy'nin zone kurallarından ve diğer policy'lerden önce değerlendirilmesini sağlar.
sudo firewall-cmd --permanent --policy=no-smtp-out --set-priority=-10

# 25. porta giden bağlantıları reddeder. Log kaydını dakikada 3 ile sınırlar.
sudo firewall-cmd --permanent --policy=no-smtp-out \
    --add-rich-rule='rule port port="25" protocol="tcp" log prefix="SMTP-OUT-BLOCK: " level="warning" limit value="3/m" reject'

sudo firewall-cmd --reload
```

> [!note]
> Policy'ler `priority` değerine göre sırayla değerlendiriliyor; küçük değer önce. Negatif priority'li policy'ler zone kurallarından önce çalışıyor. `-10`, bu policy'nin `docker` zone'unun ACCEPT target'ından ve 7. bölümde oluşturacağımız `vpn-internet` policy'sinden (`-1`) önce değerlendirilmesini sağlıyor.

> [!note]
> Policy'nin target'ını değiştirmedik; varsayılan değer `CONTINUE`. 25 dışındaki portlara giden trafik bir sonraki kurala geçiyor ve eskisi gibi çalışıyor. Rich rule'da `family` belirtmediğimiz için kural hem IPv4 hem IPv6'ya uygulanıyor.

> [!note]
> Ingress zone olarak `ANY` kullandığımız için kural, sonradan eklenecek zone'lara da (ör. 7. bölümdeki `vpn` zone'u) kendiliğinden uygulanıyor.

Policy'yi kontrol edelim:

```bash
sudo firewall-cmd --info-policy=no-smtp-out
```

Çıktıda `priority: -10`, `ingress-zones: ANY`, `egress-zones: public` ve eklediğimiz [rich rule](term:rich-rule) görünmeli.

Testi tekrarlayalım:

```bash
sudo docker run --rm alpine nc -v -w 5 gmail-smtp-in.l.google.com 25
```

Bu sefer `open` satırı görünmemeli; `nc` bir bağlantı hatası yazmalı. Engellenen denemeler kernel loguna düşüyor:

```bash
sudo journalctl -k -g SMTP-OUT-BLOCK
```

> [!note]
> Logdaki `SRC=` alanı, 25. porttan çıkmaya çalışan konteynerin ya da VPN istemcisinin IP adresini gösteriyor. Burada beklenmedik bir kayıt varsa o konteyner veya cihaz ele geçirilmiş olabilir.

Postfix'in etkilenmediğini görmek için bir Gmail adresine mail gönderelim ve Postfix'in logunda `status=sent` satırını arayalım:

```bash
sudo journalctl -t postfix/smtp -n 20
```
