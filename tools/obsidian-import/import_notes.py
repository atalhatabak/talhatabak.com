#!/usr/bin/env python3
"""Import the Self Hosting notes from Obsidian into content/self-hosting/.

For every note listed in DOCS below, writes content/self-hosting/<slug>/:
  index.tr.md  the Obsidian note (Turkish) with only these changes:
               front matter, links to other notes -> site links, the
               "Sonraki bölüm" line removed, "> **Gerekenler**" and other
               "> " notes -> callouts, file names on code blocks, glossary
               links on the first use of each term
  index.md     the English body from en/<slug>.md, with the same changes;
               each "@@code@@" line takes the next Turkish code block, so
               code is written once (placeholders and comments translated)

Every run rewrites these files, so edit the note or en/<slug>.md, not the
files in content/. A post's date is kept; a new post gets the current time."""
import argparse, datetime, json, pathlib, re, sys, urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
SECTION = "self-hosting"
OUT = HERE.parents[1] / "content" / SECTION
EN_DIR = HERE / "en"

EPILOG = """\
adding a new note:
  1. add a line to DOCS: chapter, slug (folder and URL), tags, Turkish
     title / linkTitle / description, English title / linkTitle / description
  2. optional: callout types in NOTE_TYPES (default "note"), code block
     titles in FENCES, glossary terms in TERMS (define them in
     data/glossary.yaml), code comment translations in CODE_TR
  3. run the script; without en/<slug>.md only the Turkish post is written
  4. for English: write en/<slug>.md with the same notes and headings, a
     "@@code@@" line for each code block, then run the script again

The note's file name must start with its chapter ("2.1 Mail ... .md").
Check the result with `git diff content/` and `hugo server -D`.

example:
  python3 tools/obsidian-import/import_notes.py ~/Notes/SelfHostv2"""

# chapter, slug, tags, TR title, TR linkTitle, TR description, EN title, EN linkTitle, EN description
DOCS = [
    ("0", "planning-and-architecture", ["rocky-linux"],
     "Planlama ve Mimari", "", "Seri boyunca kullanılan sunucu, varsayımlar ve standartlar; serinin yol haritası.",
     "Planning and Architecture", "", "The server used in this series, the assumptions and conventions, and the roadmap of the series."),
    ("1", "post-install-configuration", ["rocky-linux", "ssh"],
     "Kurulum Sonrası Yapılandırma", "", "Yeni kurulmuş Rocky Linux 10 sunucunun ilk kontrolleri ve temel ayarları.",
     "Post-Install Configuration", "", "First checks and basic settings on a freshly installed Rocky Linux 10 server."),
    ("2", "mail-server", ["mail", "iredmail", "dns"],
     "Mail Sunucu Kurulumu", "", "Sunucunun ilk temel servisi: iRedMail ile mail servisinin kurulumu. Bu kurulum NGINX ve MariaDB kurulumunu da kapsıyor.",
     "Mail Server Setup", "", "The first main service on the server: a mail server with iRedMail. This setup also installs NGINX and MariaDB."),
    ("2.1", "mail-server-ssl", ["mail", "ssl", "certbot"],
     "Mail Sunucusu için SSL Ayarlama", "", "mail.xenonly.com için Let's Encrypt sertifikası alma ve sertifikanın otomatik yenilenmesi.",
     "Setting Up SSL for the Mail Server", "", "Getting a Let's Encrypt certificate for mail.xenonly.com and renewing it automatically."),
    ("2.2", "mail-server-new-domain", ["mail", "dns", "dkim"],
     "Mail Sunucusu Yeni Alan Adı Ekleme", "", "Mail sunucusuna yeni bir alan adı ekleme: iRedAdmin, DKIM anahtarı ve DNS kayıtları.",
     "Adding a New Domain to the Mail Server", "", "Adding a new domain to the mail server: iRedAdmin, a DKIM key and DNS records."),
    ("2.3", "mail-clients", ["mail", "imap"],
     "Mail Sunucusu: İstemci Kullanmak", "İstemci Kullanmak", "Thunderbird gibi IMAP destekleyen e-posta istemcileriyle mail hesaplarına bağlanma.",
     "Mail Server: Using a Mail Client", "Using a Mail Client", "Connecting to the mail accounts with any mail client that supports IMAP, like Thunderbird."),
    ("2.4", "mail-server-migration", ["mail", "iredmail", "mariadb"],
     "Mail Sunucusu Taşınması", "", "Mail servisini veritabanı, Maildir ve DKIM anahtarlarıyla birlikte başka bir sunucuya taşıma.",
     "Moving the Mail Server", "", "Moving the mail service to another server together with its database, Maildir and DKIM keys."),
    ("2.5", "mail-server-extras", ["mail", "iredmail", "roundcube"],
     "Mail Sunucusu: Ekstra Ayarlamalar", "Ekstra Ayarlamalar", "Alias ekleme, Roundcube'da kullanıcı adını otomatik tamamlama, kurulumda düz metin olarak kalan parolaları temizleme ve hesaplara gönderim limiti koyma.",
     "Mail Server: Extra Settings", "Extra Settings", "Adding an alias, auto-completing the username in Roundcube, cleaning up the passwords the installer left in plain text and limiting how much mail an account can send."),
    ("3", "nginx", ["nginx"],
     "NGINX Yapılandırması", "", "iRedMail'in kurduğu NGINX yapılandırmasını, birden fazla servisi ve virtual host'u sunabilecek hale getirme.",
     "NGINX Configuration", "", "Turning the NGINX setup that iRedMail installed into one that can serve many services and virtual hosts."),
    ("4", "docker", ["docker"],
     "Docker Kurulumu", "", "Docker'ın kurulumu ve konteynerlerin sadece localhost üzerinden erişilebilir olacak şekilde yapılandırılması.",
     "Docker Setup", "", "Installing Docker and setting it up so that containers are reachable only over localhost."),
    ("4.1", "docker-template", ["docker", "nginx"],
     "Docker Konteynerleri için Hazır Şablon", "", "Konteynerler için port planı ve NGINX'te WebSocket destekli ortak bir proxy şablonu.",
     "A Ready Template for Docker Containers", "", "A port plan for the containers and a shared NGINX proxy template with WebSocket support."),
    ("5", "firewalld", ["firewalld"],
     "Firewalld Yapılandırma", "", "Kurulum boyunca kapalı tuttuğumuz Firewalld'nin yapılandırılıp etkinleştirilmesi ve konteynerlerle VPN istemcilerinin dışarıya 25. porttan çıkışının engellenmesi.",
     "Firewalld Configuration", "", "Configuring and turning on Firewalld, which we kept off during the setup, and blocking containers and VPN clients from sending out on port 25."),
    ("6", "fail2ban", ["fail2ban"],
     "Fail2Ban Yapılandırma", "", "iRedMail ile gelen Fail2Ban'a tekrar eden saldırganlar için artan ban süresi eklenmesi.",
     "Fail2Ban Configuration", "", "Adding longer and longer ban times for repeat attackers to the Fail2Ban that comes with iRedMail."),
    ("7", "wireguard", ["wireguard", "vpn", "firewalld"],
     "WireGuard Kurulumu", "", "VPN sunucusu: istemcileri VPN üzerinden internete çıkarma, istemciler arası iletişim ve bazı servisleri sadece VPN üzerinden erişilebilir yapma.",
     "WireGuard Setup", "", "A VPN server: sending clients to the internet through the VPN, letting clients talk to each other and making some services reachable only over the VPN."),
    ("7.1", "wireguard-clients", ["wireguard", "vpn"],
     "WireGuard İstemci Eklemek", "", "WireGuard'a elle ve bir script ile istemci ekleme; masaüstü ve mobil istemciler.",
     "Adding WireGuard Clients", "", "Adding WireGuard clients by hand and with a script; desktop and mobile clients."),
    ("7.2", "services-behind-vpn", ["wireguard", "vpn", "nginx", "ssh"],
     "Servisleri VPN Arkasına Almak", "", "SSH'ı ve NGINX virtual host'larını sadece VPN üzerinden erişilebilir yapma.",
     "Putting Services Behind the VPN", "", "Making SSH and NGINX virtual hosts reachable only over the VPN."),
    ("7.3", "wireguard-troubleshooting", ["wireguard", "vpn"],
     "WireGuard: Olası Problemler", "Olası Problemler", "Split tunnel ile VPN arkasındaki servislere erişim ve iki VPN profili aynı anda açıkken yaşanan erişim sorunu.",
     "WireGuard: Possible Problems", "Possible Problems", "Reaching services behind the VPN with a split tunnel, and the access problem when two VPN profiles are on at the same time."),
    ("8", "vault", ["vault", "nginx"],
     "Vault Kurulumu", "", "HashiCorp Vault ile secret'ların (API anahtarı, token, parola) merkezi ve şifreli olarak saklanması.",
     "Vault Setup", "", "Keeping secrets (API keys, tokens, passwords) in one central, encrypted place with HashiCorp Vault."),
    ("9", "vaultwarden", ["vaultwarden", "docker"],
     "Vaultwarden Kurulumu", "", "Bitwarden uyumlu parola yöneticisi Vaultwarden'ın kurulumu.",
     "Vaultwarden Setup", "", "Installing Vaultwarden, a Bitwarden-compatible password manager."),
    ("10", "wordpress", ["wordpress", "docker", "mariadb"],
     "WordPress Kurulumu", "", "Her sitenin kendi konteynerinde çalıştığı, ortak bir MariaDB konteyneri kullanan WordPress yapısı.",
     "WordPress Setup", "", "A WordPress setup where every site runs in its own container and all sites share one MariaDB container."),
    ("10.1", "wordpress-migration", ["wordpress", "mariadb"],
     "Eski WordPress'i Mevcut Yapıya Taşımak", "", "Eski bir sunucudaki WordPress sitesini veritabanı ve dosyalarıyla bu yapıya taşıma.",
     "Moving an Old WordPress Site into This Setup", "", "Moving a WordPress site from an old server into this setup, with its database and files."),
    ("11", "memos", ["memos", "docker"],
     "Usememos Kurulumu", "", "Self-host edilebilen not uygulaması Memos'un kurulumu.",
     "Usememos Setup", "", "Installing Memos, a note app you can host yourself."),
    ("12", "syncthing", ["syncthing"],
     "Syncthing Kurulumu", "", "Cihazlar arasında dosya senkronizasyonu için Syncthing; sunucu her zaman açık olan ortak eş olarak kullanılıyor.",
     "Syncthing Setup", "", "Syncthing for syncing files between devices; the server is the shared peer that is always on."),
]

# Callout type of the plain "> " notes, by their index in the document
# (see scan.py). Default "note"; None keeps a plain blockquote.
W, I, T, P = "warning", "important", "tip", None
NOTE_TYPES = {
    "1": {0: W, 5: W},
    "2": {0: I, 2: W, 5: W, 6: W, 12: T},
    "2.2": {1: I, 3: T},
    "2.4": {0: W, 2: W, 5: W, 7: W},
    "2.5": {9: I},
    # 3: the short descriptions of the template / config files stay plain quotes
    "3": {**{i: P for i in range(1, 13)}, 16: P, 17: P, 18: W, 20: T, 23: T},
    "4.1": {1: W},
    "7.1": {1: I, 2: W, 3: I, 4: W},
    "7.2": {0: W, 1: W, 5: I},
    "7.3": {0: "info"},
    "8": {7: T},
    "9": {1: I, 4: W, 5: W, 8: T, 10: T},
    "10.1": {0: W, 2: W, 10: I, 12: W, 16: T},
    "12": {5: W, 8: W},
}

# Code block header (file name) and language fixes, by fence index.
FENCES = {
    "1": {13: {"title": "/etc/ssh/sshd_config.d/00-hardening.conf"}},
    "2": {2: {"title": "/etc/hosts"}},
    "2.1": {8: {"title": "/etc/letsencrypt/renewal-hooks/deploy/reload-mail.sh"}},
    "2.2": {1: {"title": "/etc/amavisd/amavisd.conf"}},
    "2.5": {2: {"title": "/opt/www/roundcubemail/config/config.inc.php"}},
    "3": {3: {"title": "/etc/nginx/nginx.conf"}, 8: {"title": "/etc/nginx/conf.d/cache.conf"},
          9: {"title": "/etc/nginx/conf.d/headers.conf"}, 10: {"title": "/etc/nginx/vhost.d/00-default.conf"},
          11: {"title": "/etc/nginx/vhost.d/00-default-ssl.conf"},
          12: {"title": "/etc/nginx/vhost.d/vhost_mail.xenonly.com.conf"},
          14: {"title": "/etc/nginx/vhost.d/vhost_iredadmin.xenonly.com.conf"}},
    "4": {3: {"title": "/etc/docker/daemon.json"}},
    "4.1": {2: {"title": "/etc/nginx/conf.d/websocket.conf"}, 3: {"title": "/etc/nginx/templates/proxy.tmpl"}},
    "6": {0: {"title": "/etc/fail2ban/jail.d/99-local.local", "lang": "ini"},
          1: {"title": "/etc/fail2ban/fail2ban.local", "lang": "ini"}},
    "7": {4: {"title": "/etc/sysctl.d/90-wireguard.conf"}, 6: {"title": "/etc/wireguard/wg0.conf"},
          18: {"title": "/etc/docker/daemon.json", "lang": "json"}, 19: {"title": "/etc/docker/daemon.json"}},
    "7.1": {2: {"title": "desktop.conf"}, 3: {"title": "/etc/wireguard/wg0.conf"},
            7: {"title": "/usr/local/sbin/wg-peer"}, 10: {"title": "/etc/sudoers.d/secure_path"}},
    "7.2": {7: {"title": "~/.ssh/config"}, 8: {"title": "/etc/nginx/templates/vpn-only.tmpl"},
            9: {"title": "/etc/nginx/vhost.d/vhost_iredadmin.xenonly.com.conf"}},
    "8": {1: {"title": "/etc/vault.d/vault.hcl"}, 8: {"title": "/etc/nginx/vhost.d/vhost_vault.xenonly.com.conf"}},
    "9": {1: {"title": "/opt/docker/vaultwarden/.env"}, 3: {"title": "/opt/docker/vaultwarden/compose.yaml"},
          6: {"title": "/etc/nginx/vhost.d/vhost_password.xenonly.com.conf"},
          9: {"title": "/etc/fail2ban/filter.d/vaultwarden.local"}, 10: {"title": "/etc/fail2ban/jail.d/vaultwarden.local"}},
    "10": {2: {"title": "/opt/docker/mariadb/compose.yaml"}, 9: {"title": "/opt/docker/wp-example/.env"},
           11: {"title": "/opt/docker/wp-example/php.ini"}, 12: {"title": "/opt/docker/wp-example/compose.yaml"},
           15: {"title": "/etc/nginx/vhost.d/vhost_example.com.conf"}},
    "10.1": {11: {"title": "/opt/docker/wp-example/html/wp-config.php"}, 12: {"title": "/opt/docker/wp-example/html/wp-config.php"},
             15: {"title": "/opt/docker/wp-example/php.ini"}, 16: {"title": "/opt/docker/wp-example/compose.yaml"},
             20: {"title": "/etc/nginx/vhost.d/vhost_example.com.conf"}},
    "11": {1: {"title": "/opt/docker/memos/compose.yaml"}, 4: {"title": "/etc/nginx/vhost.d/vhost_memos.xenonly.com.conf"}},
    "12": {6: {"title": "/etc/nginx/vhost.d/vhost_sync.xenonly.com.conf"}},
}

# Glossary terms (data/glossary.yaml): key, TR pattern, EN pattern, docs to skip.
# The first match outside code, links, headings and the requirements box
# becomes [match](term:key).
S = r"(?:'\w+)?"  # Turkish suffix after an apostrophe: SELinux'u, VPS'in
TERMS = [
    ("vps", rf"\bVPS{S}\b", r"\bVPS\b", ()),
    ("rhel", r"\bRHEL\b", r"\bRHEL\b", ()),
    ("epel", r"\bEPEL\b", r"\bEPEL\b", ()),
    ("fqdn", r"\bFQDN\b", r"\bFQDN\b", ()),
    ("iredmail", rf"\biRedMail{S}\b", r"\biRedMail(?:'s)?\b", ()),
    ("postfix", rf"\bPostfix{S}\b", r"\bPostfix(?:'s)?\b", ()),
    ("dovecot", rf"\bDovecot{S}\b", r"\bDovecot(?:'s)?\b", ()),
    ("amavis", rf"\bAmavis{S}\b", r"\bAmavis(?:'s)?\b", ()),
    ("roundcube", rf"\bRoundcube{S}\b", r"\bRoundcube(?:'s)?\b", ()),
    ("iredadmin", rf"\biRedAdmin{S}\b(?!-)", r"\biRedAdmin(?:'s)?\b(?!-)", ()),
    ("iredapd", rf"\biRedAPD{S}\b", r"\biRedAPD(?:'s)?\b", ()),
    ("imap", rf"\bIMAP{S}\b", r"\bIMAP\b", ()),
    ("smtp", rf"\bSMTP{S}\b(?![-_])", r"\bSMTP\b(?![-_])", ()),
    ("starttls", r"\bSTARTTLS\b", r"\bSTARTTLS\b", ()),
    ("sasl", r"\bSASL\b", r"\bSASL\b", ()),
    ("helo", r"\bHELO\b", r"\bHELO\b", ()),
    ("bounce", rf"\bbounce{S}", r"\bbounces?\b", ()),
    ("maildir", rf"\bMaildir{S}\b", r"\bMaildir\b", ()),
    ("sieve", r"\bSieve\b", r"\bSieve\b", ()),
    ("mx-record", r"\bMX(?: kayd\w*)?\b", r"\bMX(?: records?)?\b", ()),
    ("ptr-record", r"\bPTR(?: kayd\w*)?\b", r"\bPTR(?: records?)?\b", ()),
    ("spf", rf"\bSPF{S}\b", r"\bSPF\b", ()),
    ("dkim", rf"\bDKIM{S}\b(?!_)", r"\bDKIM\b(?!_)", ()),
    ("dmarc", rf"\bDMARC{S}\b", r"\bDMARC\b", ()),
    ("dnsbl", r"\b[Kk]ara liste\w*", r"\bblocklists?\b", ()),
    ("ttl", rf"\bTTL{S}\b", r"\bTTL\b", ()),
    ("acme", r"\bACME\b", r"\bACME\b", ()),
    ("http-01", r"\bHTTP-01\b", r"\bHTTP-01\b", ()),
    ("dns-01", r"\bDNS-01\b", r"\bDNS-01\b", ()),
    ("lets-encrypt", rf"\bLet's Encrypt{S}", r"\bLet's Encrypt\b", ()),
    ("certbot", rf"\b[Cc]ertbot{S}\b(?!-)", r"\b[Cc]ertbot(?:'s)?\b(?!-)", ()),
    ("self-signed", r"\bself-signed sertifika\w*", r"\bself-signed certificates?\b", ()),
    ("tls", rf"\bTLS{S}\b", r"\bTLS\b", ()),
    ("sni", r"\bSNI\b", r"\bSNI\b", ()),
    ("certificate-transparency", r"\bCertificate Transparency\b", r"\bCertificate Transparency\b", ()),
    ("hsts", rf"\bHSTS{S}\b", r"\bHSTS\b", ()),
    ("csp", rf"\bCSP{S}\b", r"\bCSP\b", ()),
    ("xss", rf"\bXSS{S}\b", r"\bXSS\b", ()),
    ("mime", r"\bMIME\b", r"\bMIME\b", ()),
    ("reverse-proxy", r"\b[Rr]everse proxy\b", r"\b[Rr]everse proxy\b", ()),
    ("virtual-host", rf"\b[Vv]irtual host\w*{S}", r"\b[Vv]irtual hosts?\b", ()),
    ("websocket", rf"\bWebSocket{S}\b", r"\bWebSocket\b", ()),
    ("long-polling", r"\blong polling\b", r"\blong polling\b", ()),
    ("dns-rebinding", r"\bDNS rebinding\b", r"\bDNS rebinding\b", ()),
    ("php-fpm", rf"\bPHP-FPM{S}", r"\bPHP-FPM\b", ()),
    ("wp-cli", rf"\bWP-CLI{S}", r"\bWP-CLI\b", ()),
    ("serialization", r"\bserialize edilmiş\b", r"\bserialized\b", ()),
    ("waf", r"\bWAF\b", r"\bWAF\b", ()),
    ("brute-force", r"\bbrute force\b", r"\bbrute force\b", ()),
    ("ddos", r"\bDDoS\b", r"\bDDoS\b", ()),
    ("container", r"\b[Kk]onteyner\w*", r"\b[Cc]ontainers?\b", ()),
    ("image", r"\b[İi]maj\w*", r"\b[Ii]mages?\b", ()),
    ("docker-compose", rf"\bDocker Compose{S}\b", r"\bDocker Compose\b", ()),
    ("systemd", rf"\bsystemd{S}\b(?![-@.])", r"\bsystemd(?:'s)?\b(?![-@.])", ()),
    ("journald", rf"\bjournald{S}\b", r"\bjournald\b", ()),
    ("selinux", rf"\bSELinux{S}\b", r"\bSELinux\b", ()),
    ("networkmanager", rf"\bNetworkManager{S}\b", r"\bNetworkManager(?:'s)?\b", ()),
    ("firewalld-zone", rf"\b[Zz]one\b{S}", r"(?<![Tt]ime )\b[Zz]ones?\b", ()),
    ("firewalld-policy", rf"\b[Pp]olicy\b{S}", r"\b[Pp]olic(?:y|ies)\b", ("2", "2.2", "8")),
    ("rich-rule", rf"\brich rule\w*{S}", r"\brich rules?\b", ()),
    ("iptables", rf"\b(?:iptables|nftables){S}\b", r"\b(?:iptables|nftables)\b", ()),
    ("ip-forwarding", rf"\bIP forwarding\w*{S}", r"\bIP forwarding\b", ()),
    ("slaac", r"\bRouter Advertisement\b", r"\bRouter Advertisements?\b", ()),
    ("jail", rf"\bjail\w*{S}", r"\bjails?\b", ()),
    ("peer", rf"\bpeer\b{S}", r"\bpeers?\b", ("0", "12")),
    ("preshared-key", r"\bpreshared key\w*", r"\bpreshared keys?\b", ()),
    ("handshake", rf"\bhandshake\w*{S}", r"\bhandshakes?\b", ("3",)),
    ("full-tunnel", rf"\b[Ff]ull tunnel\w*{S}", r"\b[Ff]ull tunnel\b", ()),
    ("split-tunnel", rf"\b[Ss]plit tunnel\w*{S}", r"\b[Ss]plit tunnel\b", ()),
    ("mtu", rf"\bMTU{S}\b", r"\bMTU\b", ()),
    ("quic", r"\bQUIC\b", r"\bQUIC\b", ()),
    ("vnc", r"\bVNC\b", r"\bVNC\b", ()),
    ("seal", r"\b[Uu]nseal\b|\bsealed\b", r"\b[Uu]nseal(?:ed)?\b|\bsealed\b", ()),
    ("audit-log", r"\baudit log\w*", r"\baudit logs?\b", ()),
    ("2fa", rf"\b2FA{S}\b", r"\b2FA\b", ()),
    ("webauthn", r"\bWebAuthn\b", r"\bWebAuthn\b", ()),
    ("hash", rf"\b[Hh]ash{S}\b", r"\b[Hh]ash(?:es|ed)?\b", ()),
    ("salt", r"(?<=\()salt(?=\))", r"\bsalts?\b", ()),
    ("sqlite", rf"\bSQLite{S}\b", r"\bSQLite\b", ()),
    ("collation", r"\bcollation\b", r"\bcollation\b", ()),
    ("foreign-key", r"\bforeign key\b", r"\bforeign key\b", ()),
]

LINK_MD = re.compile(r"\]\(([^)\s]+?\.md)(#[^)]*)?\)")
FENCE = re.compile(r"^(\s*(?:>\s?)?\s*)```(\S*)(.*)$")
PROTECT = re.compile(r"`[^`]*`|\[[^\]]*\]\([^)]*\)|<https?://[^>]+>|https?://\S+")
MARK = re.compile(r"^(\s*(?:>\s?)?\s*)@@code@@\s*$")

# EN code blocks are copied from TR (an "@@code@@" line in the EN body takes
# the next TR block), so only placeholders and comments are translated.
PLACEHOLDERS = {
    "<SUNUCU_IPV4>": "<SERVER_IPV4>", "<SUNUCU_IPV6>": "<SERVER_IPV6>", "<SUNUCU_ADI>": "<SERVER_NAME>",
    "<SUNUCU_ALAN_ADI>": "<SERVER_DOMAIN>", "<YENI_SUNUCU_IP>": "<NEW_SERVER_IP>", "<ALAN_ADI>": "<DOMAIN>",
    "<BAGLANTI_ADI>": "<CONNECTION_NAME>", "<DB_PAROLASI>": "<DB_PASSWORD>", "<DOSYA>": "<FILE>",
    "<ESKI_DB>": "<OLD_DB>", "<ESKI_KULLANICI>": "<OLD_USER>", "<ESKI_SUNUCU>": "<OLD_SERVER>",
    "<KULLANICI>": "<USER>", "<SMTP_PAROLASI>": "<SMTP_PASSWORD>", "<SSH_ANAHTARI>": "<SSH_KEY>",
    "<YEDEK_DIZINI>": "<BACKUP_DIR>",
}
CODE_TR = {
    "0": [("İşletim Sistemi:", "Operating system:"), ("İşlemci: AMD EPYC™ 9645, 4 adanmış çekirdek", "CPU: AMD EPYC™ 9645, 4 dedicated cores"),
          ("Depolama:", "Storage:")],
    "1": [('"İlk commit"', '"Initial commit"'), ('"sshd: root girişi kapatıldı"', '"sshd: disable root login"'),
          ("# Sadece etkileşimli bash oturumlarında çalış", "# Run only in interactive bash sessions"),
          ("# İstem: root kırmızı, normal kullanıcı yeşil", "# Prompt: root in red, normal users in green"),
          ("# Komut geçmişi", "# Command history"),
          ("# her satırda tarih ve saat görünmeli", "# every line should show the date and time")],
    "2.5": [("# çıktı boş olmalı", "# output should be empty"), ("# hata vermeden yedek almalı", "# should take a backup without errors")],
    "3": [("→ Gereken yerlerde vhost içine include edilecek", "→ Will be included in the vhosts that need it"),
          ("→ conf.d'ye taşınacak", "→ Will be moved to conf.d"), ("→ Alt alan adında sunulacak", "→ Will be served on a subdomain"),
          ("→ Kullanılmayacak", "→ Not used"),
          ("# Eğer varsa, mevcut durumda kullanılmıyor zaten", "# If it exists; it isn't used right now anyway")],
    "4.1": [("# çıktı boş olmalı", "# output should be empty")],
    "5": [("# no-smtp-out adında yeni ve boş bir policy oluşturur.", "# Creates a new, empty policy named no-smtp-out."),
          ("# Herhangi bir zone'dan (ANY) gelip public zone'una (internete) yönlendirilen trafiğe uygulanır.",
           "# Applies to traffic forwarded from any zone (ANY) to the public zone (the internet)."),
          ("# ANY, sunucunun kendi trafiğini (HOST) kapsamıyor; Postfix etkilenmiyor.",
           "# ANY doesn't include the server's own traffic (HOST), so Postfix is not affected."),
          ("# Policy'nin zone kurallarından ve diğer policy'lerden önce değerlendirilmesini sağlar.",
           "# Makes the policy run before the zone rules and the other policies."),
          ("# 25. porta giden bağlantıları reddeder. Log kaydını dakikada 3 ile sınırlar.",
           "# Rejects connections to port 25. Logs at most 3 lines per minute.")],
    "6": [("# 604800 (1 hafta)", "# 604800 (1 week)")],
    "7": [("# vpn adında yeni ve boş bir zone oluşturur", "# Creates a new, empty zone named vpn"),
          ("# wg0 arayüzünü bu zone'a bağlar. Bundan sonra WireGuard tünelinden gelen tüm trafik public zone'un değil, vpn zone'unun kurallarıyla değerlendirilir.",
           "# Binds the wg0 interface to this zone. From now on, all traffic from the WireGuard tunnel is checked against the rules of the vpn zone, not the public zone."),
          ("# VPN'den gelen trafik için sunucudaki hangi servislere izin verileceğini belirler:",
           "# Sets which services on the server the traffic from the VPN may reach:"),
          ("# Aynı zone içindeki trafiğin yönlendirilmesine izin verir. İstemcilerin birbiriyle konuşabilmesini sağlar.",
           "# Allows forwarding inside the same zone, so clients can talk to each other."),
          ("# vpn-internet adında yeni ve boş bir policy oluşturur.", "# Creates a new, empty policy named vpn-internet."),
          ("# Policy'nin yönünü belirler. Trafik vpn zone'undan (wg0) gelip public zone'una (dış arayüz, yani internet) gidiyorsa bu policy uygulanır.",
           "# Sets the direction of the policy. It applies when traffic comes from the vpn zone (wg0) and goes to the public zone (the outside interface, so the internet)."),
          ("# Bu yöndeki trafiği kabul eder. VPN istemcisi internette istediği adrese gidebilir; 25. port, 5. bölümdeki no-smtp-out policy'siyle engelli.",
           "# Accepts traffic in this direction. A VPN client can go to any address on the internet; port 25 is blocked by the no-smtp-out policy from part 5."),
          ("# NAT'ı etkinleştirir.", "# Turns on NAT."),
          ("# --add-masquerade sadece IPv4 için uygulanıyor, IPv6 için ayrı bir rich rule gerekiyor",
           "# --add-masquerade only applies to IPv4, IPv6 needs a separate rich rule"),
          ("# Hangi arayüzün hangi zone'da olduğunu gösterir", "# Shows which interface is in which zone"),
          ("# Policy'nin ayarlarını gösterir", "# Shows the settings of the policy")],
    "7.1": [("# yanıt gelmeli", "# should answer"),
            ("# full tunnel'da sunucunun IPv4 adresi", "# with the full tunnel, the server's IPv4 address"),
            ("# full tunnel'da sunucunun IPv6 adresi", "# with the full tunnel, the server's IPv6 address")],
    "7.2": [("# bağlanmalı, VPN üzerinden gidiyor", "# should connect, goes through the VPN"),
            ("# internetten, bağlanamamalı", "# over the internet, should not connect"),
            ("# IPv6, bağlanamamalı", "# IPv6, should not connect"),
            ("# ssh listede olmamalı", "# ssh should not be in the list")],
    "7.3": [("İç paket:  10.8.0.3 → 10.8.0.1              (gönderdiğimiz paket)",
             "Inner packet: 10.8.0.3 → 10.8.0.1           (the packet we send)"),
            ("Dış paket: ev IP'si → SUNUCU IP'si:51820 UDP (iç paketin şifrelenmiş hali)",
             "Outer packet: home IP → SERVER IP:51820 UDP (the inner packet, encrypted)"),
            ("# \"dev xenternet\" çıkıyorsa xentranet'in dış paketleri tünelin içine giriyor",
             "# if it says \"dev xenternet\", xentranet's outer packets go into the tunnel"),
            ("# normal ağ arayüzü (wlan0 / eth0), xenternet değil", "# the normal network interface (wlan0 / eth0), not xenternet"),
            ("# fwmark: 0xca6c, latest handshake güncel", "# fwmark: 0xca6c, latest handshake is recent")],
    "9": [("# İlk hesap oluşturulana kadar, sonra kaldırılacak", "# Until the first account is created, remove afterwards"),
          ("# zaman damgası dönmeli", "# should return a timestamp"), ("# 403 dönmeli", "# should return 403")],
    "10": [("İnternet → NGINX:443", "Internet → NGINX:443"), ("db ağı (internal)", "db network (internal)"),
           ("wp-diger ", "wp-other "),
           ("# Kurulum sihirbazı tamamlanana kadar, sonra kaldırılacak", "# Until the setup wizard is finished, remove afterwards")],
    "10.1": [("← veritabanı dökümü, içe aktarıldıktan sonra silinecek", "← database dump, deleted after the import"),
             ("← eski sitenin tüm dosyaları, konteynerde /var/www/html", "← all files of the old site, /var/www/html in the container")],
    "11": [("# İlk hesap oluşturulana kadar, sonra kaldırılacak", "# Until the first account is created, remove afterwards")],
    "12": [("# bağlanmalı", "# should connect")],
}


def code_blocks(lines):
    """Raw code blocks of a TR body: lists of lines without their list / quote prefix."""
    blocks, cur, prefix = [], None, ""
    for ln in lines:
        m = FENCE.match(ln)
        if m and cur is None:
            prefix, cur = m.group(1), []
        if cur is not None:
            cur.append(ln[len(prefix):] if ln.startswith(prefix) else ln[len(prefix.rstrip()):])
            if m and len(cur) > 1:
                blocks.append(cur)
                cur = None
    return blocks


def fill_code(text, blocks, ch):
    """Replace the @@code@@ lines of an EN body with the translated TR blocks."""
    pairs = CODE_TR.get(ch, [])
    used, out, k = set(), [], 0
    for ln in text.split("\n"):
        m = MARK.match(ln)
        if not m:
            out.append(ln)
            continue
        for cl in blocks[k]:
            for i, (a, b) in enumerate(pairs):
                if a in cl:
                    cl, _ = cl.replace(a, b), used.add(i)
            for a, b in PLACEHOLDERS.items():
                cl = cl.replace(a, b)
            out.append(m.group(1) + cl if cl else m.group(1).rstrip())
        k += 1
    if k != len(blocks):
        sys.exit(f"{ch}: EN has {k} code markers, TR has {len(blocks)} code blocks")
    if len(used) != len(pairs):
        sys.exit(f"{ch}: unused code translations: {[pairs[i][0] for i in range(len(pairs)) if i not in used]}")
    return "\n".join(out)


def front_matter(d, lang, date):
    ch, slug, tags = d[0], d[1], d[2]
    title, link, desc = d[3:6] if lang == "tr" else d[6:9]
    fm = {"title": title}
    if link:
        fm["linkTitle"] = link
    fm["description"] = desc
    q = lambda v: json.dumps(v, ensure_ascii=False)
    lines = [f"{k}: {q(v)}" for k, v in fm.items()]
    lines.append(f"date: {date}")
    lines.append(f"chapter: {q(ch)}")
    lines.append(f"tags: {q(tags)}")
    return "---\n" + "\n".join(lines) + "\n---\n"


def convert_links(text, slugs):
    def repl(m):
        name = urllib.parse.unquote(m.group(1)).removesuffix(".md")
        if name not in slugs:
            sys.exit(f"link to a note that is not in DOCS: {name}")
        return f"](/{SECTION}/{slugs[name]}/{m.group(2) or ''})"
    return LINK_MD.sub(repl, text)


def drop_next_part(text):
    text = re.sub(r"\n\*\*(Sonraki bölüm|Next part):\*\*.*\n?$", "\n", text.rstrip("\n") + "\n")
    return text.rstrip("\n") + "\n"


def transform_blocks(lines, ch, lang):
    """Callouts for > notes and attributes for code fences. Returns (lines, notes, fences)."""
    req = {"tr": "> **Gerekenler**", "en": "> **Requirements**"}[lang]
    types, attrs = NOTE_TYPES.get(ch, {}), FENCES.get(ch, {})
    out, note_i, fence_i, in_fence = [], 0, 0, False
    for i, ln in enumerate(lines):
        m = FENCE.match(ln)
        if m:
            if not in_fence:
                a = attrs.get(fence_i, {})
                lang_ = a.get("lang", m.group(2))
                extra = f' {{title="{a["title"]}"}}' if "title" in a else ""
                ln = f"{m.group(1)}```{lang_}{m.group(3)}{extra}"
                fence_i += 1
            in_fence = not in_fence
        elif not in_fence and ln.startswith(">") and (i == 0 or not lines[i - 1].startswith(">")):
            if ln.strip() == req:
                ln = f"> [!abstract] {req[4:-2]}"
            else:
                t = types.get(note_i, "note")
                if t:
                    lbl = re.match(r"^> \*\*([^*]+?):\*\*\s*(.*)$", ln)
                    ln = f"> [!{t}] {lbl.group(1)}\n> {lbl.group(2)}" if lbl else f"> [!{t}]\n{ln}"
                note_i += 1
        out.append(ln)
    return "\n".join(out).split("\n"), note_i, fence_i


def link_terms(lines, ch, lang):
    """Link the first occurrence of each glossary term."""
    skip = [False] * len(lines)
    in_fence = in_req = False
    for i, ln in enumerate(lines):
        if FENCE.match(ln):
            skip[i] = True
            in_fence = not in_fence
            continue
        if ln.startswith("> [!abstract]"):
            in_req = True
        elif not ln.startswith(">"):
            in_req = False
        skip[i] = in_fence or in_req or ln.startswith("#") or ln.startswith("> [!") or not ln.strip()
    used = []
    for key, tr, en, excl in TERMS:
        if ch in excl:
            continue
        rx = re.compile(tr if lang == "tr" else en)
        for i, ln in enumerate(lines):
            if skip[i]:
                continue
            pos, hit = 0, None
            for pm in list(PROTECT.finditer(ln)) + [None]:
                end = pm.start() if pm else len(ln)
                hit = rx.search(ln, pos, end)
                if hit:
                    break
                pos = pm.end() if pm else end
            if hit:
                lines[i] = f"{ln[:hit.start()]}[{hit.group(0)}](term:{key}){ln[hit.end():]}"
                used.append(key)
                break
    return lines, used


def post_date(folder):
    """The date of an existing post, so re-running never changes it; else now."""
    old = folder / "index.tr.md"
    if old.exists():
        m = re.search(r"^date: (.+)$", old.read_text(), re.M)
        if m:
            return m.group(1)
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def main():
    ap = argparse.ArgumentParser(description=__doc__, epilog=EPILOG,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=pathlib.Path, help="folder with the Obsidian notes (*.md)")
    src = ap.parse_args().source
    if not src.is_dir():
        sys.exit(f"not a folder: {src}")

    src_by_ch = {p.name.split(" ")[0]: p for p in src.glob("*.md")}
    for c, p in sorted(src_by_ch.items()):
        if c not in {d[0] for d in DOCS}:
            print(f"skipped (not in DOCS): {p.name}")
    for d in DOCS:
        if d[0] not in src_by_ch:
            sys.exit(f"no note for chapter {d[0]} in {src} (the file name must start with '{d[0]} ')")
    slugs = {src_by_ch[d[0]].stem: d[1] for d in DOCS}

    report = []
    for d in DOCS:
        ch, slug = d[0], d[1]
        tr = convert_links(drop_next_part(src_by_ch[ch].read_text()), slugs)
        tr_code = code_blocks(tr.split("\n"))
        tr_lines, tr_notes, tr_fences = transform_blocks(tr.split("\n"), ch, "tr")
        tr_lines, tr_terms = link_terms(tr_lines, ch, "tr")
        folder = OUT / slug
        folder.mkdir(exist_ok=True)
        date = post_date(folder)
        (folder / "index.tr.md").write_text(front_matter(d, "tr", date) + "\n".join(tr_lines).rstrip("\n") + "\n")
        line = f"{ch:>4} {slug:28} tr notes={tr_notes:<3} fences={tr_fences:<3} terms={len(tr_terms):<3}"
        en_src = EN_DIR / f"{slug}.md"
        if en_src.exists():
            en = fill_code(drop_next_part(en_src.read_text()), tr_code, ch)
            en_lines, en_notes, en_fences = transform_blocks(en.split("\n"), ch, "en")
            if (en_notes, en_fences) != (tr_notes, tr_fences):
                sys.exit(f"{slug}: EN has notes={en_notes} fences={en_fences}, TR has {tr_notes}/{tr_fences}")
            en_lines, en_terms = link_terms(en_lines, ch, "en")
            (folder / "index.md").write_text(front_matter(d, "en", date) + "\n".join(en_lines).rstrip("\n") + "\n")
            missing = sorted(set(tr_terms) ^ set(en_terms))
            line += f" en terms={len(en_terms):<3}" + (f" only in one language: {missing}" if missing else "")
        else:
            line += f" en: none (write {en_src.relative_to(HERE.parents[1])})"
        report.append(line)
    print("\n".join(report))


if __name__ == "__main__":
    main()
