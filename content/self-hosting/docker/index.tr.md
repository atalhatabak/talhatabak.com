---
title: "Docker Kurulumu"
description: "Docker'ın kurulumu ve konteynerlerin sadece localhost üzerinden erişilebilir olacak şekilde yapılandırılması."
date: 2026-11-21T00:09:00+03:00
chapter: "4"
tags: ["docker"]
---
> [!abstract] Gerekenler
> - [1 Kurulum Sonrası Yapılandırma](/self-hosting/post-install-configuration/) tamamlanmış olmalı.
>
> **Varsayımlar**
> - Konteynerlere [3 NGINX Yapılandırması](/self-hosting/nginx/) bölümünde yapılandırılan NGINX üzerinden erişileceği varsayılmıştır.
> - Firewalld hâlâ kapalıdır. Docker'ın Firewalld entegrasyonu [5 Firewalld Yapılandırma](/self-hosting/firewalld/) bölümünde tamamlanıyor.
> - Komutlar sunucuda, root yetkisiyle (`sudo`) çalıştırılmıştır.

## Kontrol ve Kurulum

[RHEL](term:rhel) tabanlı sistemlerde Podman, Buildah ve runc kurulu gelebiliyor. Docker'ın kendi paketleriyle çakışma ihtimaline karşı bunları kaldıralım ve Docker'ı kendi deposundan kuralım:

```bash
sudo dnf remove podman buildah runc
```

Docker deposunu ekleyip kuralım:

```bash
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo

sudo dnf install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Docker'ı başlatmadan önce `/etc/docker/daemon.json` dosyasına yapılandırmamızı yazalım. Dizin henüz yoksa önce oluşturalım:

```bash
sudo mkdir -p /etc/docker
```

```json {title="/etc/docker/daemon.json"}
{
  "ip": "127.0.0.1",
  "default-network-opts": {
    "bridge": { "com.docker.network.bridge.host_binding_ipv4": "127.0.0.1" }
  },
  "log-driver": "journald",
  "live-restore": true,
  "default-address-pools": [
    { "base": "172.20.0.0/16", "size": 24 }
  ]
}
```

Her satırın neden eklendiği:

1. **`"ip"` ve `"default-network-opts"`:** Docker, `-p 8080:80` gibi IP adresi belirtilmeden yayınlanan portları varsayılan olarak `0.0.0.0`'a bağlıyor ve kurallarını kendisi yazıyor. Bu portlara gelen trafik Firewalld'nin [zone](term:firewalld-zone) kurallarına takılmadan [konteynere](term:container) iletiliyor; Firewalld açık olsa bile port internete açık kalıyor. Erişilmesi gereken servislere NGINX üzerinden erişileceği için hiçbir konteynerin internete açık olmasına gerek yok; localhost üzerinden erişilmesi yeterli. `"ip"` ayarı sadece varsayılan `bridge` ağı (`docker run`) için geçerli. Compose'un oluşturduğu ağlar için aynı varsayılanı `default-network-opts` ile veriyoruz. Bu ayar ağ oluşturulurken uygulanıyor; sonradan eklenirse mevcut ağları etkilemiyor. Yine de compose dosyalarında portları `127.0.0.1:8080:80` şeklinde açıkça yazacağız.
2. **`"log-driver": "journald"`:** Varsayılan loglama `json-file` sürücüsüyle dosyaya yapılıyor. Loglara tek merkezden erişmek ve onları tek yerden yönetmek için loglamayı [journald'ye](term:journald) veriyoruz. `docker logs` komutu çalışmaya devam ediyor.
3. **`"live-restore": true`:** Docker servisi yeniden başlatıldığında veya güncellendiğinde konteynerlerin durmamasını sağlıyor.
4. **`"default-address-pools"`:** Konteyner ağlarının hangi aralıktan IP alacağını belirliyor.

Servisi başlatabiliriz:

```bash
sudo systemctl enable --now docker
```

Docker'ın çalıştığını aşağıdaki komutla kontrol edebiliriz:

```bash
sudo docker run --rm hello-world
```

Çıktıda aşağıdaki satırlar görünmeli:

```text
Hello from Docker!
This message shows that your installation appears to be working correctly.
```

IP adresi yazılmadan yayınlanan bir portun Compose'un kullandığı türden bir ağda da sadece localhost'a bağlandığını kontrol edelim:

```bash
sudo docker network create porttest
sudo docker network inspect porttest --format '{{json .Options}}'
sudo docker run -d --rm --name porttest --network porttest -p 18080:80 alpine sleep 60
sudo ss -tln | grep 18080
sudo docker rm -f porttest && sudo docker network rm porttest
```

`inspect` çıktısında `"com.docker.network.bridge.host_binding_ipv4":"127.0.0.1"`, `ss` çıktısında sadece `127.0.0.1:18080` görünmeli; `0.0.0.0` veya `[::]` görünmemeli.

## Dikkat Edilmesi Gerekenler

1. Normal kullanıcıyı `docker` grubuna eklemek, o kullanıcının parola sormadan root olabilmesi anlamına geldiği için eklemiyoruz.
2. NGINX'ten konteynere proxy yaparken `X-Forwarded-For` ve `X-Real-IP` başlıklarını göndermeliyiz. Yoksa uygulamalar her ziyaretçiyi 172.20.x.x olarak görür. Bunun için [4.1 Docker Konteynerleri için Hazır Şablon](/self-hosting/docker-template/) bölümünde ortak bir şablon oluşturacağız.
