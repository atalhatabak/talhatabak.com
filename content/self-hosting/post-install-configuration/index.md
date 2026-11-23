---
title: "Post-Install Configuration"
description: "First checks and basic settings on a freshly installed Rocky Linux 10 server."
date: 2026-11-21T00:01:00+03:00
chapter: "1"
tags: ["rocky-linux", "ssh"]
---
> [!abstract] Requirements
> - A server (VPS) with Rocky Linux 10 installed and open to the internet
> - A normal user with `sudo` rights, created during the installation, and an SSH key added for this user
>
> **Assumptions**
> - You can connect to the server over SSH with this user and get root rights with `sudo`.
> - All commands are run on the server as this user. Commands that need root rights are written with `sudo`.

We have a freshly installed Rocky Linux 10 server. In this part we'll do the first checks and the basic settings on it.

## Installing the Basic Packages

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

## Recording Changes in /etc (etckeeper)

etckeeper keeps the `/etc` directory in a git repository. Every change to the configuration files is recorded: when it was made, by whom and how. A bad change can be undone. It also commits automatically on every package install and update done with dnf.

We install it first, so that all the changes the next steps make in `/etc` (the [iRedMail](term:iredmail) installation too) get recorded.

```bash
sudo dnf install etckeeper etckeeper-dnf
sudo etckeeper init
sudo etckeeper commit "Initial commit"
```

- **`etckeeper-dnf`:** The dnf plugin. Before every package operation it commits any uncommitted changes in `/etc`, and after the operation it commits the changes the packages made.
- **`etckeeper init`:** Creates the `/etc/.git` repository. The repository directory has `700` permissions, so only root can read it. The package's default VCS is git (`VCS="git"` in `/etc/etckeeper/etckeeper.conf`).

Let's commit the changes we make by hand, for example after editing a configuration file, together with a message:

```bash
sudo git -C /etc status
sudo git -C /etc diff
sudo etckeeper commit "sshd: disable root login"
```

The commits show the user who ran `sudo` as the author. To look at the history:

```bash
sudo git -C /etc log --oneline | head
sudo git -C /etc show <commit>
```

Changes we forget to commit are committed once a day with the message `daily autocommit`. For this the package brings both the `/etc/cron.daily/etckeeper` file and `etckeeper.timer`. If cron is running, we don't need to do anything else:

```bash
systemctl is-active crond   # active
```

If the output is not `active`, let's enable the timer:

```bash
sudo systemctl enable --now etckeeper.timer
```

> [!warning]
> The `/etc/.git` repository keeps a copy of everything in `/etc`: `/etc/shadow`, the database passwords of the services (for example `/etc/postfix/mysql/`), [TLS](term:tls) and WireGuard private keys. Since the repository is open only to root, it adds no extra risk on the server. But the repository must not be pushed to a remote server (`PUSH_REMOTE` must stay empty), and its backups must be stored with care. A password deleted from a file stays in the git history.

## Time Zone

```bash
sudo timedatectl set-timezone Europe/Istanbul
```

## Automatic Security Updates

Let's install security updates automatically every day. We'll do the other updates by hand, after checking them.

```bash
sudo dnf install dnf-automatic
sudo sed -i 's/^upgrade_type = default/upgrade_type = security/' /etc/dnf/automatic.conf
grep '^upgrade_type' /etc/dnf/automatic.conf   # upgrade_type = security
sudo systemctl enable --now dnf-automatic-install.timer
```

- **`upgrade_type = security`:** Only packages marked as security updates are installed.
- **`dnf-automatic-install.timer`:** The timer that downloads and installs the updates. It ignores the `download_updates` and `apply_updates` settings in `/etc/dnf/automatic.conf` and always downloads and installs. That's why we only changed `upgrade_type` in the file.

Let's look at when the timer will run and at the waiting security updates:

```bash
systemctl list-timers dnf-automatic-install.timer
sudo dnf updateinfo list --security
```

The timer runs on local time, so we set the time zone before this. After it runs, you can see what it installed with `sudo journalctl -u dnf-automatic-install.service`.

> [!note]
> dnf-automatic doesn't reboot the server. If an update that needs a reboot, like a new kernel, was installed, `sudo dnf needs-restarting -r` shows it; we'll do the reboot ourselves. Services that still use the old version of an updated library (for example OpenSSL) are listed with `sudo dnf needs-restarting -s`.

> [!note]
> Most service packages restart their own service when they are updated (for example [Postfix](term:postfix), MariaDB). This means a few seconds of downtime during the update.

## Bash Settings

We'll set the bash prompt and the command history for all users from a single file. Bash reads the `.sh` files under `/etc/profile.d/` both in login sessions (SSH, `sudo -i`) and in non-login sessions like `sudo -s`. So we don't need to edit the `.bashrc` files of the normal user and root one by one.

```bash
sudo tee /etc/profile.d/zz-custom.sh > /dev/null <<'EOF'
# Run only in interactive bash sessions
[ -n "$BASH_VERSION" ] || return
case $- in *i*) ;; *) return ;; esac

# Prompt: root in red, normal users in green
if [ "$EUID" -eq 0 ]; then
    PS1='\[\e[1;31m\]\u\[\e[0;37m\]@\[\e[1;36m\]\h \[\e[0;33m\]\w\[\e[0m\]\$ '
else
    PS1='\[\e[1;32m\]\u\[\e[0;37m\]@\[\e[1;36m\]\h \[\e[0;33m\]\w\[\e[0m\]\$ '
fi

# Command history
HISTTIMEFORMAT='%F %T  '
HISTSIZE=50000
HISTFILESIZE=100000
HISTCONTROL=ignoreboth
shopt -s histappend
PROMPT_COMMAND="history -a${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
EOF

source /etc/profile.d/zz-custom.sh
```

- **The first two checks:** Files in `/etc/profile.d/` can also be read by `sh` and by scripts. The settings are applied only in interactive bash sessions.
- **`PS1`:** The `\$` at the end of the prompt shows `#` for root and `$` for a normal user. The `if` block only changes the color of the username: red for root, green for a normal user.
- **`HISTTIMEFORMAT`:** Shows the date and time of every command in the `history` output. The time is written to `~/.bash_history` as lines like `#1795210585`. For commands saved before this setting, the real time is unknown.
- **`HISTSIZE`, `HISTFILESIZE`:** The number of commands kept in the session and in the history file. The Rocky Linux default is 1000.
- **`HISTCONTROL=ignoreboth`:** Doesn't save a command repeated right after itself, or commands that **start with a space**. To keep a command with a password in it out of the history, put a space in front of it.
- **`histappend`:** When a session closes, its history is added to the end of the file instead of overwriting it. Sessions open at the same time don't delete each other's history.
- **`history -a`:** Writes the history to the file right after every command. If the SSH connection drops or the session is killed, the history is not lost.

Let's check it in a new session:

```bash
history | tail -n 3   # every line should show the date and time
```

> [!note]
> The command history is under the user's own control; the user can delete it or turn it off. So it is there for convenience, not for auditing. Commands run with `sudo` are also logged to the journal: `sudo journalctl _COMM=sudo`.

## Checking the SSH Service

Let's run the command below:

```bash
sudo sshd -T | grep -Ei \
'^(port|permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|gssapiauthentication|x11forwarding|usepam|allowtcpforwarding|allowagentforwarding) '
```

Let's check that the values in the output are as below:

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

To change the values that are different, let's create the file `/etc/ssh/sshd_config.d/00-hardening.conf` with the content below:

```text {title="/etc/ssh/sshd_config.d/00-hardening.conf"}
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
GSSAPIAuthentication no
X11Forwarding no
```

> [!note]
> sshd reads the files under `sshd_config.d` in alphabetical order and uses the **first** value it finds for a setting. On Rocky Linux, `50-redhat.conf` (and `01-permitrootlogin.conf` if root login over SSH was allowed during the installation) sets some of these options, so the file name must start with `00-`.

Let's test the configuration and reload the service:

```bash
sudo sshd -t && sudo systemctl reload sshd
```

## Turning Off Firewalld for Now

I'll keep Firewalld off during the setup. After installing all the services, I'll configure it and turn it back on in [5 Firewalld Configuration](/self-hosting/firewalld/).

```bash
sudo systemctl disable --now firewalld
```

> [!warning]
> While Firewalld is off, every port the server listens on is open to the internet. Keeping this time short, or not turning Firewalld off at all and adding the needed services from the start, is the safer option. You can check the listening ports with `sudo ss -tulpn`.
