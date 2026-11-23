---
title: "Vault Kurulumu"
description: "HashiCorp Vault ile secret'ların (API anahtarı, token, parola) merkezi ve şifreli olarak saklanması."
date: 2026-11-21T00:17:00+03:00
chapter: "8"
tags: ["vault", "nginx"]
---
> [!abstract] Gerekenler
> - [3 NGINX Yapılandırması](/self-hosting/nginx/) ve [7.2 Servisleri VPN Arkasına Almak](/self-hosting/services-behind-vpn/) tamamlanmış olmalı (`vpn-only` şablonu kullanılıyor).
>
> **Varsayımlar**
> - Vault'a `vault.xenonly.com` adresinden, sadece VPN üzerinden erişilmektedir. Bu alan adı için `A` ve `AAAA` kayıtlarının girildiği varsayılmıştır.
> - Kurulum komutları sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır. `vault` CLI komutları ise sunucuda normal kullanıcıyla çalıştırılmıştır.

## Nedir

Vault, secret'ları (parola, API anahtarı, sertifika, token) merkezi ve şifreli olarak saklayan, kimin neye eriştiğini kontrol eden ve her erişimi kayıt altına alan bir servis. Sadece bir "şifreli kasa" değil; birçok secret'ı kendisi üretebiliyor ve süresi dolunca kendisi iptal edebiliyor.

## Kurulum

Aşağıdaki komutlarla HashiCorp deposunu ekleyip Vault'u kuralım:

```bash
sudo dnf config-manager --add-repo https://rpm.releases.hashicorp.com/RHEL/hashicorp.repo
sudo dnf install vault
```

### Depolama Yöntemi

Servisi başlatmadan önce yapılandırmayı düzenleyeceğiz. Vault'ta veri saklamak için iki seçenek var:

- **File:** Kurulumda varsayılan olarak geliyor. Vault verileri doğrudan diskteki bir dizine (`/opt/vault/data`) şifreli dosyalar olarak yazılıyor. Kurulumu ve yapılandırması en basit yöntem. Sadece tek sunucuda çalışıyor, yüksek erişilebilirlik (HA) desteklemiyor.
- **Raft (Integrated Storage):** Vault'un kendi içinde gelen dağıtık depolama yöntemi. Veriler yine diskte şifreli tutuluyor. Birden fazla sunucuyla cluster kurulabiliyor ve HA sağlıyor. Vault çalışırken `vault operator raft snapshot save` komutuyla yedek alınabiliyor. Yapılandırması biraz daha fazla (`api_addr`, `cluster_addr`, 8201 portu). Sunucu adresi değişirse elle kurtarma gerekebiliyor.

Bu kurulum tek sunuculu ve kişisel kullanım amaçlı olduğu için `File` yöntemiyle kuracağım.

### Yapılandırma

`/etc/vault.d/vault.hcl` dosyasındaki `HTTPS listener` bölümünü yorum satırı yapalım ve `HTTP listener` bölümünü açalım. İlgili kısım aşağıdaki gibi olmalı:

```hcl {title="/etc/vault.d/vault.hcl"}
# HTTP listener
listener "tcp" {
  address = "127.0.0.1:8200"
  tls_disable = 1
  x_forwarded_for_authorized_addrs   = "127.0.0.1"
  x_forwarded_for_reject_not_present = false
}

# HTTPS listener
#listener "tcp" {
#  address       = "0.0.0.0:8200"
#  tls_cert_file = "/opt/vault/tls/tls.crt"
#  tls_key_file  = "/opt/vault/tls/tls.key"
#}
```

> [!note]
> Vault sadece `127.0.0.1` adresini dinliyor ve dışarıya NGINX üzerinden açılacak. HTTPS'i NGINX sağladığı için sunucunun içinde Vault'un ayrıca HTTPS kullanmasına gerek yok.

> [!note]
> `x_forwarded_for_*` ayarları, NGINX'in gönderdiği `X-Forwarded-For` başlığından istemcinin gerçek IP adresini almasını sağlıyor; [audit loglarında](term:audit-log) NGINX'in adresi yerine istemcinin adresi görünüyor.

Dizin sahipliğini ve yapılandırma dosyasının izinlerini düzenleyelim:

```bash
sudo chown -R vault:vault /opt/vault
sudo chmod 640 /etc/vault.d/vault.hcl
```

Servisi etkinleştirip başlatalım:

```bash
sudo systemctl enable --now vault
sudo systemctl status vault
```

CLI'dan Vault'u kullanabilmek için normal kullanıcımızın kabuğunda Vault'un adresini tanımlayalım:

```bash
echo 'export VAULT_ADDR=http://127.0.0.1:8200' >> ~/.bashrc && source ~/.bashrc
vault -autocomplete-install
vault status
```

## Initialize ve Unseal

```bash
vault operator init -key-shares=1 -key-threshold=1
```

- **`-key-shares`:** Oluşturulacak [unseal](term:seal) key sayısı.
- **`-key-threshold`:** Vault'u açmak için gereken unseal key sayısı.

> [!note]
> Kişisel kullanım olduğu için ben 1 ve 1 seçtim, ama üretim ortamında 5 ve 3 gibi değerler seçmek daha mantıklı.

**Bu komutun çıktısında unseal key ve root token var ve bu çıktı sadece bir kez gösteriliyor. Unseal key ve root token sunucu dışında güvenli bir yerde saklanmalı.**

> [!note]
> Sistem veya servis yeniden başladığında Vault sealed (kilitli) olarak başlıyor ve `vault operator unseal` komutuyla key'leri girerek elle unseal etmemiz gerekiyor. Bunu otomatikleştiren yöntemler var, ama bu sealing'i anlamsız hale getiriyor. Bu yüzden bu işi gerektiğinde elle yapacağım ve sistemde sürekli çalışan servisleri Vault'a bağımlı yapmamaya çalışacağım.

Aşağıdaki komutla unseal key'i girerek Vault'u açabiliriz:

```bash
vault operator unseal
```

## NGINX Reverse Proxy

Vault şu an dışarıya açık değil; erişmek için NGINX kullanacağız.

Sertifikayı alalım:

```bash
sudo certbot certonly --webroot -w /opt/www/well_known -d vault.xenonly.com
```

`/etc/nginx/vhost.d/vhost_vault.xenonly.com.conf` dosyasını aşağıdaki gibi oluşturalım:

```nginx {title="/etc/nginx/vhost.d/vhost_vault.xenonly.com.conf"}
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name vault.xenonly.com;

    ssl_certificate     /etc/letsencrypt/live/vault.xenonly.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vault.xenonly.com/privkey.pem;
    include /etc/nginx/templates/vpn-only.tmpl;

    location / {
        proxy_pass http://127.0.0.1:8200;

        proxy_set_header Host            $host;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
}
```

NGINX yapılandırmasını test edip yeniden yükleyelim:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Vault arayüzü artık `https://vault.xenonly.com` adresinden kullanılabilir.

> [!note]
> `vpn-only` şablonu kullanıldığı için Vault'a sadece VPN bağlantısıyla erişilebiliyor. [Split tunnel](term:split-tunnel) ile erişmek için kişisel bilgisayardaki `hosts` dosyasına `10.8.0.1 vault.xenonly.com` kaydı eklenmeli (bkz. [7.3 Olası Problemler](/self-hosting/wireguard-troubleshooting/)).

## Masaüstünden CLI Kullanmak

Kişisel bilgisayarımıza sunucudakine yakın bir sürümde Vault kurmamız gerekiyor. Ardından kullandığımız kabuğun (bash, zsh, fish) yapılandırmasına aşağıdaki satırı eklememiz yeterli:

```bash
export VAULT_ADDR=https://vault.xenonly.com
```

## Kurulum Sonrası İlk Yapılandırma

Vault'u unseal ediyoruz ve `vault login` komutuyla root token'ı girerek giriş yapıyoruz.

### Secrets Engine

Mevcut secrets engine'leri listeleyelim:

```bash
vault secrets list
```

```text
Path               Type              Accessor                   Description
----               ----              --------                   -----------
agent-registry/    agent_registry    agent-registry_4d63d95d    agent registry
cubbyhole/         cubbyhole         cubbyhole_76e2bfaf         per-token private secret storage
identity/          identity          identity_331ce865          identity store
sys/               system            system_5d30d32d            system endpoints used for control, policy and debugging
```

Listede `kv` tipinde bir engine yoksa aşağıdaki komutla `kv-v2` tipinde bir secrets engine bağlayalım:

```bash
vault secrets enable -path=secret kv-v2
```

- **`kv-v2`:** Anahtar-değer (key-value) tipinde veri tutan secrets engine. Veri kalıcı, silinene kadar orada kalıyor.
- **`cubbyhole`:** Her token'ın kendine ait özel alanı. Token'ın süresi dolunca bu alan da siliniyor.
- **`-path=secret`:** Bağlama noktasının adı, istenen bir değer verilebilir.

### Loglama

Aşağıdaki komutla audit loglarını servisin standart çıktısına, yani [journald'ye](term:journald) gönderiyoruz:

```bash
vault audit enable file file_path=stdout
```

### Admin Policy ve Kullanıcı

Root token yerine kullanmak için yönetici yetkili bir policy ve kullanıcı oluşturalım:

```bash
vault policy write admin - <<'EOF'
path "*" {
  capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"]
}
EOF

vault auth enable userpass
read -rs PW
vault write auth/userpass/users/<USERNAME> password="$PW" policies=admin token_ttl=8h token_max_ttl=24h
unset PW
```

> [!note]
> `read -rs`: Parolayı ekranda göstermeden okuyor ve parola komut geçmişine yazılmıyor.

> [!note]
> Bu policy pratikte root ile aynı yetkileri veriyor. Farkı: token en fazla 24 saat geçerli, iptal edilebiliyor ve yapılan işlemler audit logda kendi kullanıcı adımızla görünüyor.

Yeni kullanıcıyla giriş yapılabildiğini kontrol edelim:

```bash
vault login -method=userpass username=<USERNAME>
vault token lookup       # policies: [admin default], ttl: ~8h
```

> [!tip]
> Arayüzde giriş yöntemi olarak `userpass` seçilerek de giriş yapılabilir.

Yeni kullanıcı çalışıyorsa root token'ı iptal edelim:

```bash
vault token revoke <ROOT_TOKEN>
```

> [!note]
> CLI kullanımı ve policy'ler ayrıca araştırılmalı, burada bunlara değinmeyeceğim.
