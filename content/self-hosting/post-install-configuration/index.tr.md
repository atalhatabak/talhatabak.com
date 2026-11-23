---
title: "Kurulum Sonrası Yapılandırma"
description: "Yeni kurulmuş Rocky Linux 10 sunucunun ilk kontrolleri ve temel ayarları."
date: 2026-11-21T00:01:00+03:00
chapter: "1"
tags: ["rocky-linux", "ssh"]
---
> [!abstract] Gerekenler
> - Rocky Linux 10 kurulu ve internete açık bir sunucu (VPS)
> - Kurulumda oluşturulmuş, `sudo` yetkisi olan normal bir kullanıcı ve bu kullanıcı için eklenmiş SSH anahtarı
>
> **Varsayımlar**
> - Sunucuya bu kullanıcıyla SSH üzerinden bağlanılabildiği ve `sudo` ile root yetkisi alınabildiği varsayılmıştır.
> - Komutların tamamı sunucuda, bu kullanıcıyla çalıştırılmıştır. Root yetkisi gerekenler `sudo` ile yazılmıştır.

Sıfırdan kurulmuş bir Rocky Linux 10 sunucumuz var. Bu bölümde sunucunun ilk kontrollerini ve temel ayarlarını yapacağız.

## Temel Paketlerin Kurulumu

```bash
sudo dnf upgrade
sudo dnf install epel-release dnf-plugins-core
sudo dnf config-manager --set-enabled crb
sudo dnf install \
  unzip tar wget \
  vim-enhanced tmux nano \
  git rsync bash-completion \
  bind-utils traceroute nmap-ncat \
  tcpdump lsof whois \
  htop sysstat plocate \
  rsyslog logrotate \
  certbot
```

## /etc Değişikliklerini Kaydetme (etckeeper)

etckeeper, `/etc` dizinini bir git deposunda tutuyor. Yapılandırma dosyalarındaki her değişikliğin ne zaman, kim tarafından ve nasıl yapıldığı kayıt altına alınıyor; hatalı bir değişiklik geri alınabiliyor. dnf ile yapılan her paket kurulumunda ve güncellemesinde de otomatik commit atıyor.

İlk iş olarak kuruyoruz; böylece sonraki adımların ([iRedMail](term:iredmail) kurulumu dahil) `/etc`'de yaptığı bütün değişiklikler kaydedilecek.

```bash
sudo dnf install etckeeper etckeeper-dnf
sudo etckeeper init
sudo etckeeper commit "İlk commit"
```

- **`etckeeper-dnf`:** dnf eklentisi. Her paket işleminden önce `/etc`'de commit edilmemiş değişiklik varsa onları, işlemden sonra da paketlerin yaptığı değişiklikleri commit ediyor.
- **`etckeeper init`:** `/etc/.git` deposunu oluşturuyor. Depo dizininin izni `700`; sadece root okuyabiliyor. Paketin varsayılan VCS'i git (`/etc/etckeeper/etckeeper.conf` içinde `VCS="git"`).

Elle yaptığımız değişiklikleri, örneğin bir yapılandırma dosyasını düzenledikten sonra, açıklamasıyla birlikte commit edelim:

```bash
sudo git -C /etc status
sudo git -C /etc diff
sudo etckeeper commit "sshd: root girişi kapatıldı"
```

Commit'lerde yazar olarak `sudo`'yu çalıştıran kullanıcı görünüyor. Geçmişe bakmak için:

```bash
sudo git -C /etc log --oneline | head
sudo git -C /etc show <commit>
```

Commit etmeyi unuttuğumuz değişiklikler günde bir kez `daily autocommit` mesajıyla commit ediliyor. Paket bunun için hem `/etc/cron.daily/etckeeper` dosyasını hem de `etckeeper.timer`'ı getiriyor. cron çalışıyorsa ek bir şey yapmamıza gerek yok:

```bash
systemctl is-active crond   # active
```

Çıktı `active` değilse timer'ı etkinleştirelim:

```bash
sudo systemctl enable --now etckeeper.timer
```

> [!warning]
> `/etc/.git` deposu `/etc`'deki her şeyin kopyasını tutuyor: `/etc/shadow`, servislerin veritabanı parolaları (ör. `/etc/postfix/mysql/`), [TLS](term:tls) ve WireGuard özel anahtarları. Depo sadece root'a açık olduğu için sunucuda ek bir risk oluşturmuyor. Ancak depo uzak bir sunucuya gönderilmemeli (`PUSH_REMOTE` boş kalmalı) ve yedekleri dikkatli saklanmalı. Bir dosyadan silinen parola git geçmişinde kalmaya devam ediyor.

## Zaman Dilimi Ayarı

```bash
sudo timedatectl set-timezone Europe/Istanbul
```

## Otomatik Güvenlik Güncellemeleri

Güvenlik güncellemelerini her gün otomatik kuralım. Diğer güncellemeleri elle, kontrol ederek yapacağız.

```bash
sudo dnf install dnf-automatic
sudo sed -i 's/^upgrade_type = default/upgrade_type = security/' /etc/dnf/automatic.conf
grep '^upgrade_type' /etc/dnf/automatic.conf   # upgrade_type = security
sudo systemctl enable --now dnf-automatic-install.timer
```

- **`upgrade_type = security`:** Sadece güvenlik güncellemesi olarak işaretlenmiş paketler kuruluyor.
- **`dnf-automatic-install.timer`:** Güncellemeleri indirip kuran timer. `/etc/dnf/automatic.conf` içindeki `download_updates` ve `apply_updates` ayarlarını yok sayıp her zaman indirip kuruyor. Bu yüzden dosyada sadece `upgrade_type`'ı değiştirdik.

Timer'ın ne zaman çalışacağına ve bekleyen güvenlik güncellemelerine bakalım:

```bash
systemctl list-timers dnf-automatic-install.timer
sudo dnf updateinfo list --security
```

Timer yerel saate göre çalıştığı için zaman dilimini bundan önce ayarladık. Çalıştıktan sonra ne kurduğu `sudo journalctl -u dnf-automatic-install.service` ile görülebilir.

> [!note]
> dnf-automatic sunucuyu yeniden başlatmıyor. Çekirdek gibi yeniden başlatma gerektiren bir güncelleme kurulduysa `sudo dnf needs-restarting -r` bunu gösteriyor; yeniden başlatmayı biz yapacağız. Güncellenen kütüphaneleri (ör. OpenSSL) hâlâ eski haliyle kullanan servisler `sudo dnf needs-restarting -s` ile listeleniyor.

> [!note]
> Çoğu servis paketi güncellenince kendi servisini yeniden başlatıyor (ör. [Postfix](term:postfix), MariaDB). Bu, güncelleme sırasında birkaç saniyelik bir kesinti demek.

## Bash Ayarları

Bash istemini ve komut geçmişini bütün kullanıcılar için tek bir dosyadan ayarlayacağız. Bash, `/etc/profile.d/` altındaki `.sh` dosyalarını hem giriş yapılan oturumlarda (SSH, `sudo -i`) hem de `sudo -s` gibi giriş yapılmayan oturumlarda okuyor. Böylece normal kullanıcının ve root'un `.bashrc` dosyalarını ayrı ayrı düzenlememize gerek kalmıyor.

```bash
sudo tee /etc/profile.d/zz-custom.sh > /dev/null <<'EOF'
# Sadece etkileşimli bash oturumlarında çalış
[ -n "$BASH_VERSION" ] || return
case $- in *i*) ;; *) return ;; esac

# İstem: root kırmızı, normal kullanıcı yeşil
if [ "$EUID" -eq 0 ]; then
    PS1='\[\e[1;31m\]\u\[\e[0;37m\]@\[\e[1;36m\]\h \[\e[0;33m\]\w\[\e[0m\]\$ '
else
    PS1='\[\e[1;32m\]\u\[\e[0;37m\]@\[\e[1;36m\]\h \[\e[0;33m\]\w\[\e[0m\]\$ '
fi

# Komut geçmişi
HISTTIMEFORMAT='%F %T  '
HISTSIZE=50000
HISTFILESIZE=100000
HISTCONTROL=ignoreboth
shopt -s histappend
PROMPT_COMMAND="history -a${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
EOF

source /etc/profile.d/zz-custom.sh
```

- **İlk iki kontrol:** `/etc/profile.d/` dosyaları `sh` ve script'ler tarafından da okunabiliyor. Ayarlar sadece etkileşimli bash oturumlarında uygulanıyor.
- **`PS1`:** İstemin sonundaki `\$`, root için `#`, normal kullanıcı için `$` gösterir. `if` bloğu sadece kullanıcı adının rengini değiştiriyor: root için kırmızı, normal kullanıcı için yeşil.
- **`HISTTIMEFORMAT`:** `history` çıktısında her komutun tarihini ve saatini gösteriyor. Zaman bilgisi `~/.bash_history` dosyasına `#1795210585` gibi satırlar olarak yazılıyor. Bu ayardan önce kaydedilmiş komutların gerçek zamanı bilinmiyor.
- **`HISTSIZE`, `HISTFILESIZE`:** Oturumda ve geçmiş dosyasında tutulan komut sayısı. Rocky Linux'un varsayılanı 1000.
- **`HISTCONTROL=ignoreboth`:** Art arda tekrarlanan komutları ve **boşlukla başlayan** komutları kaydetmiyor. Parola içeren bir komutun geçmişe yazılmaması için komutun başına bir boşluk koymak yeterli.
- **`histappend`:** Oturum kapanırken geçmiş dosyasının üzerine yazmak yerine sonuna ekliyor. Aynı anda açık birden fazla oturum birbirinin geçmişini silmiyor.
- **`history -a`:** Her komuttan sonra geçmişi hemen dosyaya yazıyor. SSH bağlantısı koparsa veya oturum öldürülürse geçmiş kaybolmuyor.

Yeni bir oturumda kontrol edelim:

```bash
history | tail -n 3   # her satırda tarih ve saat görünmeli
```

> [!note]
> Komut geçmişi kullanıcının kendi kontrolünde; kullanıcı silebilir veya kapatabilir. Bu yüzden kolaylık içindir, denetim için değil. `sudo` ile çalıştırılan komutlar ayrıca journal'a kaydediliyor: `sudo journalctl _COMM=sudo`.

## SSH Servisinin Kontrolü

Aşağıdaki komutu çalıştıralım:

```bash
sudo sshd -T | grep -Ei \
'^(port|permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|gssapiauthentication|x11forwarding|usepam|allowtcpforwarding|allowagentforwarding) '
```

Çıktıdaki değerlerin aşağıdaki gibi olduğunu kontrol edelim:

```text
port 22
usepam yes
permitrootlogin no
pubkeyauthentication yes
gssapiauthentication no
passwordauthentication no
kbdinteractiveauthentication no
x11forwarding no
allowtcpforwarding yes
allowagentforwarding yes
```

Farklı olan değerleri değiştirmek için `/etc/ssh/sshd_config.d/00-hardening.conf` dosyasını aşağıdaki içerikle oluşturalım:

```text {title="/etc/ssh/sshd_config.d/00-hardening.conf"}
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
GSSAPIAuthentication no
X11Forwarding no
```

> [!note]
> sshd, `sshd_config.d` altındaki dosyaları alfabetik sırayla okur ve bir ayar için **ilk** bulduğu değeri kullanır. Rocky Linux'ta `50-redhat.conf` (ve kurulumda root'un SSH ile girişine izin verildiyse `01-permitrootlogin.conf`) bu ayarlardan bazılarını tanımladığı için dosya adının `00-` ile başlaması gerekiyor.

Yapılandırmayı test edip servisi yeniden yükleyelim:

```bash
sudo sshd -t && sudo systemctl reload sshd
```

## Firewalld'yi Geçici Olarak Kapatma

Kurulum sürecinde Firewalld'yi kapalı tutacağım. Tüm servisleri kurduktan sonra [5 Firewalld Yapılandırma](/self-hosting/firewalld/) bölümünde yapılandırıp tekrar etkinleştireceğim.

```bash
sudo systemctl disable --now firewalld
```

> [!warning]
> Firewalld kapalıyken sunucuda dinleyen her port internete açık olur. Bu süreyi kısa tutmak ya da Firewalld'yi hiç kapatmadan gereken servisleri baştan eklemek daha güvenli bir seçenek. Dinleyen portlar `sudo ss -tulpn` ile kontrol edilebilir.
