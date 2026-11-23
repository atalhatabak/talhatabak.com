---
title: "WireGuard: Olası Problemler"
linkTitle: "Olası Problemler"
description: "Split tunnel ile VPN arkasındaki servislere erişim ve iki VPN profili aynı anda açıkken yaşanan erişim sorunu."
date: 2026-11-21T00:16:00+03:00
chapter: "7.3"
tags: ["wireguard", "vpn"]
---
> [!abstract] Gerekenler
> - [7.1 WireGuard İstemci Eklemek](/self-hosting/wireguard-clients/) ve [7.2 Servisleri VPN Arkasına Almak](/self-hosting/services-behind-vpn/) tamamlanmış olmalı.
>
> **Varsayımlar**
> - Masaüstünde [7.1 WireGuard İstemci Eklemek](/self-hosting/wireguard-clients/) bölümünde oluşturulan iki profil vardır: `xenternet` (full tunnel) ve `xentranet` (split tunnel).
> - Bu bölümdeki komutlar NetworkManager kullanan Linux masaüstünde (istemcide) çalıştırılmıştır.

## Split Tunnel ile Erişim Problemi

VPN bağlantısını iki şekilde kurabiliyoruz. İstemci yapılandırmasındaki `AllowedIPs` değerini:

- `AllowedIPs = 0.0.0.0/0, ::/0` olarak ayarlarsak ([full tunnel](term:full-tunnel)) tüm trafik VPN üzerinden gider.
- `AllowedIPs = 10.8.0.0/24, fd42:8::/64` olarak ayarlarsak ([split tunnel](term:split-tunnel)) sadece VPN ağına giden trafik VPN üzerinden gider.

İki seçeneği de ihtiyacımıza göre kullanabiliriz. Burada şöyle bir problem çıkıyor:

Bağlantımız **full tunnel** ise ve sadece VPN ağından erişilebilen bir servise (ör. [iRedAdmin](term:iredadmin) paneli) erişmeye çalışıyorsak, iRedAdmin'in alan adını girdiğimizde DNS sorgusu dahil tüm trafik VPN üzerinden gider ve servise erişebiliriz.

Bağlantımız **split tunnel** ise ve iRedAdmin'e erişmeye çalışıyorsak:

- DNS sorgumuz public internet üzerinden yapılır ve sunucunun public IP adresine bağlanmaya çalışırız.
- Bağlantımız public internet üzerinden gittiği için sunucu, isteği VPN ağı dışından gelmiş sayar ve reddeder.

Bunu çözmek için DNS sorgusunun sunucunun public IP'sini değil, VPN ağındaki IP adresini (`10.8.0.1`) döndürmesi gerekiyor. Bu problemi şu yollarla çözebiliriz:

1. **DNS sağlayıcısında VPN IP'si:** Sadece VPN ile bağlanacağımız alan adlarının `A` kaydını sunucunun public IP'si yerine `10.8.0.1` olarak gireriz. DNS sorgusu nereden yapılırsa yapılsın `10.8.0.1` döner ve VPN bağlantısı varsa servise erişilir.
   Ama [Let's Encrypt](term:lets-encrypt) doğrulama sırasında bu adrese ulaşamayacağı için [HTTP-01](term:http-01) (webroot) yöntemiyle sertifika alınamaz, [DNS-01](term:dns-01) doğrulaması gerekir. Basit bir servise tekil erişim için pek ideal bir yöntem değil.
2. **`hosts` dosyası:** Kaydı istemci bilgisayardaki `hosts` dosyasına kendimiz ekleriz. Public DNS kaydı sadece sertifika alabilmek için kalır, erişim kısıtını NGINX sağlar. Kişisel kullanımda VPN arkasındaki servisler az sayıda ve belirli amaçlı olacağından (ör. SSH ve iRedAdmin paneline nadiren ve sadece VPN üzerinden bağlanılması) bu bir kerelik uğraş pek sorun olmaz.
   Dezavantajı: Mobil cihazlarda root yetkisi olmadan yapılamaz.
3. **Sunucuda DNS servisi:** Sunucuya hafif bir DNS servisi kurarız ve VPN istemci yapılandırmasındaki `DNS` değerine bu servisin adresini yazarız. Sunucudaki DNS servisi, VPN arkasındaki servisler için gelen sorgulara sunucunun VPN adresini döndürür, diğer sorguları public bir DNS sunucusuna sorar.
   Bu yöntem DNS sorgularında hafif bir gecikmeye sebep olabilir.

Ben VPN arkasına aldığım servislere sadece kendi bilgisayarımdan erişmeyi düşündüğüm ve diğerlerine göre daha basit bir çözüm olduğu için 2. yöntemi, yani `hosts` dosyasına kayıt eklemeyi kullanacağım:

```bash
echo "10.8.0.1 iredadmin.xenonly.com" | sudo tee -a /etc/hosts
```

## İki Profil Aktifken Erişim Problemi

### Ne Zaman Oluyor

Split tunnel profilinin (`xentranet`) her zaman açık kalmasını ve `10.8.0.0/24` ağına her zaman erişebilmeyi, full tunnel profilini (`xenternet`) ise sadece gerektiğinde açıp kapatmayı istiyorsak iki profil aynı anda bağlı kalıyor. Bu durumda `10.8.0.0/24` erişimimiz kesiliyor ve VPN arkasındaki servislere erişemiyoruz.

İki profil aynı anda bağlıyken internet çalışıyor ama `10.8.0.1`'e ping, SSH ve sadece VPN'den erişilebilen servisler çalışmıyor. Profiller tek tek bağlıyken sorun yok.

### Neden Oluyor

WireGuard'dan geçen her pakette iki katman var:

```text
İç paket:  10.8.0.3 → 10.8.0.1              (gönderdiğimiz paket)
Dış paket: ev IP'si → SUNUCU IP'si:51820 UDP (iç paketin şifrelenmiş hali)
```

Çekirdek bu iki paket için ayrı ayrı yönlendirme (routing) kararı veriyor:

1. [NetworkManager](term:networkmanager) full tunnel'da varsayılan route'u ayrı bir routing tablosuna koyuyor ve bir kural ekliyor: "işareti (fwmark) olmayan her paket bu tabloya". Full tunnel kendi paketlerini işaretlediği için onun paketleri tünele geri girmiyor.
2. İç paket doğru yoldan gidiyor. Çekirdek önce ana tabloya bakıyor (varsayılan route hariç). `xentranet`'in `10.8.0.0/24` route'u ana tabloda olduğu için ping `xentranet`'e giriyor.
3. `xentranet`'in dış paketi işaretsiz olduğu için `xenternet`'in kuralına takılıyor ve `xenternet` tünelinin içine giriyor.
4. Sunucu bu paketi `wg0` üzerinden alıyor ve VPN [zone'unun](term:firewalld-zone) kurallarıyla değerlendiriyor. Mevcut güvenlik duvarı yapılandırmamızda VPN zone'unda `wireguard` servisine izin verilmediği için paket reddediliyor ve `xentranet`'in [handshake'i](term:handshake) tamamlanmıyor.
5. WireGuard'da bağlantı durumu kavramı olmadığı için çekirdek tünelin çalışmadığını bilmiyor. `10.8.0.0/24` için en spesifik yol hâlâ `xentranet` olduğu için sunucuya erişim kesiliyor.

Profiller tek tek bağlıyken `xentranet`'in dış paketi normal internetten gidiyor ve sunucuya public zone'dan ulaşıyor. Public zone'da `wireguard` izinli olduğu için sorun çıkmıyor.

İki profil bağlıyken kontrol:

```bash
ip route get <SUNUCU_IPV4>   # "dev xenternet" çıkıyorsa xentranet'in dış paketleri tünelin içine giriyor
```

### Çözüm Yolları

| Yöntem                         | Ne Yapıyor                                                                      | Etkisi                                                                                                                                                                         |
| ------------------------------ | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Profiller arasında geçiş       | Aynı anda tek profil açık. Full tunnel `10.8.0.0/24`'ü de kapsıyor              | En basit yöntem. Geçiş sırasında açık bağlantılar kopar                                                                                                                        |
| VPN zone'unda `wireguard` izni | `xentranet`'in paketi `xenternet` tünelinin içinden sunucuya ulaşıyor           | Paket iki kez şifreleniyor ve iki kez çözülüyor. `xentranet`'in [MTU'su](term:mtu) düşürülmeli. Önerilmez                                                                                  |
| Metric ile öncelik             | `xenternet` açıkken `10.8.0.0/24` trafiği her zaman `xenternet`'ten gidiyor     | Güvenlik duvarına dokunulmuyor. `xenternet` açıldığında `xentranet` üzerinden açılmış bağlantılar kopuyor, çünkü sunucu `xentranet`'in IP'sini `xenternet` [peer'ından](term:peer) kabul etmiyor |
| **fwmark (seçilen)**           | `xentranet`'in dış paketleri de işaretli olduğu için normal internetten gidiyor | Paket tek kez şifreleniyor, bağlantılar kopmuyor, `xenternet` bağımsız olarak açılıp kapanabiliyor                                                                             |

### Uygulama: fwmark

> [!info] fwmark
> Çekirdeğin bir paketin üstüne koyduğu bir sayı. Sadece bilgisayarın belleğinde duruyor, ağa çıkmıyor ve portla bir ilgisi yok. `51820` wg-quick'ten gelen bir alışkanlık, herhangi bir sayı olabilir. NetworkManager bu sayıyı full tunnel'ın routing tablosu numarası olarak da kullanıyor.

İki profile aynı fwmark değerini verelim. Böylece `xenternet`'in kuralı "işareti 51820 olmayan paketler" olur ve `xentranet`'in paketleri bu kurala takılmaz.

```bash
nmcli con modify xenternet wireguard.fwmark 51820
nmcli con modify xentranet wireguard.fwmark 51820
nmcli con modify xentranet connection.autoconnect yes
nmcli con up xentranet
nmcli con up xenternet
```

İki profil bağlıyken kontrol:

```bash
ip route get 10.8.0.1                    # dev xentranet
ip route get <SUNUCU_IPV4> mark 51820    # normal ağ arayüzü (wlan0 / eth0), xenternet değil
sudo wg show xentranet                   # fwmark: 0xca6c, latest handshake güncel
```

Test: `xentranet` üzerinden sunucuya bir SSH oturumu açalım ve `xenternet`'i birkaç kez açıp kapatalım. Oturum kopmamalı.
