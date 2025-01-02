#!/bin/bash
set -e

################################################################################
# 1. Pastikan skrip dijalankan sebagai root
################################################################################
if [ "$(id -u)" -ne 0 ]; then
    echo "Skrip ini harus dijalankan sebagai root!"
    exit 1
fi

################################################################################
# 2. Variabel Konfigurasi
################################################################################
DOCKER_VERSION=""
DOCKER_COMPOSE_VERSION=${DOCKER_COMPOSE_VERSION:-"v2.22.0"}
DOCKER_REPO_FILE="/etc/apt/sources.list.d/docker.list"
DOCKER_GPG_FILE="/usr/share/keyrings/docker-archive-keyring.gpg"

# Variabel Zona Waktu
TIMEZONE=${TIMEZONE:-"Asia/Makassar"}  # Ganti dengan "Asia/Jakarta" jika perlu

################################################################################
# 3. Fungsi bantuan
################################################################################
info() {
  echo -e "\e[32m[INFO]\e[0m $1"
}

error_exit() {
  echo -e "\e[31m[ERROR]\e[0m $1"
  exit 1
}

################################################################################
# 4. Update & Instal Paket Dasar (termasuk sudo, nfs-common)
################################################################################
info "Memperbarui sistem & menginstal paket dasar..."
apt-get update -y && apt-get upgrade -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  curl sudo nfs-common tcpdump jq net-tools openssh-server telnet traceroute nmap dnsutils iputils-ping mtr whois iftop ethtool iperf3 \
  htop iotop sysstat git build-essential vim tmux python3 python3-pip strace lsof gdb ncdu zip unzip tree \
  ca-certificates gnupg lsb-release screen iptables-persistent || error_exit "Gagal menginstal paket dasar."

################################################################################
# 5. Konfigurasi Zona Waktu
################################################################################
info "Mengatur zona waktu ke ${TIMEZONE}..."
if timedatectl list-timezones | grep -q "^${TIMEZONE}$"; then
    timedatectl set-timezone "${TIMEZONE}" || error_exit "Gagal mengatur zona waktu ke ${TIMEZONE}."
else
    error_exit "Zona waktu ${TIMEZONE} tidak valid. Periksa daftar zona waktu menggunakan 'timedatectl list-timezones'."
fi

################################################################################
# 6. Tambah user 'abdullah' ke grup 'sudo' (opsional, jika ada)
################################################################################
if id "abdullah" &>/dev/null; then
  info "Menambahkan user 'abdullah' ke grup sudo..."
  usermod -aG sudo abdullah || info "User sudah ada di grup sudo atau terjadi error."
fi

################################################################################
# 7. Instal Docker Engine (dengan pengecekan duplikasi)
################################################################################
if [ ! -f "$DOCKER_GPG_FILE" ]; then
  info "Menambahkan Docker GPG key..."
  curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o "$DOCKER_GPG_FILE" \
    || error_exit "Gagal menambahkan GPG key Docker."
else
  info "GPG key Docker sudah ada, melewati proses import."
fi

if ! grep -q "download.docker.com/linux/debian" "$DOCKER_REPO_FILE" 2>/dev/null; then
  info "Menambahkan repository Docker..."
  echo "deb [arch=$(dpkg --print-architecture) signed-by=$DOCKER_GPG_FILE] https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
    > "$DOCKER_REPO_FILE"
else
  info "Repository Docker sudah terdaftar, melewati penambahan repo."
fi

info "Memperbarui daftar paket (setelah menambahkan repo Docker)..."
apt-get update -y || error_exit "Gagal menjalankan apt-get update."

info "Menginstal Docker Engine, Docker CLI, dan containerd..."
if [ -n "$DOCKER_VERSION" ]; then
  apt-get install -y docker-ce="$DOCKER_VERSION" docker-ce-cli="$DOCKER_VERSION" containerd.io \
    || error_exit "Gagal menginstal Docker versi $DOCKER_VERSION."
else
  apt-get install -y docker-ce docker-ce-cli containerd.io || error_exit "Gagal menginstal Docker versi terbaru."
fi

info "Verifikasi instalasi Docker..."
if ! command -v docker &> /dev/null; then
  error_exit "Docker tidak ditemukan setelah instalasi."
fi

################################################################################
# 8. Konfigurasi Docker daemon.json
################################################################################
info "Mengonfigurasi /etc/docker/daemon.json..."
mkdir -p /etc/docker
cat <<EOF > /etc/docker/daemon.json
{
  "dns": [
    "8.8.8.8",
    "1.1.1.1"
  ],
  "default-address-pools": [
    {
      "base": "172.16.30.0/16",
      "size": 28
    }
  ],
  "features": {
    "buildkit": true
  }
}
EOF

info "Restarting Docker service..."
systemctl restart docker

################################################################################
# 9. Instal Docker Compose v2 (plugin)
################################################################################
info "Menginstal Docker Compose versi ${DOCKER_COMPOSE_VERSION} sebagai plugin..."

ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
  ARCH="x86_64"
elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
  ARCH="arm64"
else
  error_exit "Arsitektur $ARCH tidak didukung."
fi

DOCKER_COMPOSE_BINARY="/usr/lib/docker/cli-plugins/docker-compose"
mkdir -p "$(dirname "$DOCKER_COMPOSE_BINARY")"

if ! docker compose version --short &>/dev/null; then
  info "Mengunduh Docker Compose..."
  curl -SL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-${ARCH}" -o "$DOCKER_COMPOSE_BINARY" \
    || error_exit "Gagal mengunduh Docker Compose."
  chmod +x "$DOCKER_COMPOSE_BINARY"
else
  info "Docker Compose sudah terpasang, melewati proses unduh."
fi

info "Verifikasi instalasi Docker Compose..."
docker compose version --short &> /dev/null || error_exit "Docker Compose tidak ditemukan setelah instalasi."
info "Docker Compose versi $(docker compose version --short) berhasil diinstal."

################################################################################
# 10. Konfigurasi /etc/network/interfaces (Contoh) & IP forwarding
################################################################################
info "Mengonfigurasi /etc/network/interfaces..."
# Pastikan tidak double-write
IFACES_PATH="/etc/network/interfaces"
if ! grep -q "auto macvlan0" "$IFACES_PATH" 2>/dev/null; then
cat <<EOF >> "$IFACES_PATH"

# Penambahan Macvlan di akhir file
auto macvlan0
iface macvlan0 inet static
      address 172.16.30.14/28
      pre-up ip link add macvlan0 link ens3 type macvlan mode bridge
      post-down ip link del macvlan0
EOF
fi

info "Aktifkan IP forwarding..."
if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf; then
  echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
fi
if ! grep -q "net.ipv6.conf.all.forwarding=1" /etc/sysctl.conf; then
  echo "net.ipv6.conf.all.forwarding=1" >> /etc/sysctl.conf
fi

sysctl -p || info "Gagal memuat ulang sysctl (abaikan jika layanan minimal)."

info "Restarting networking service..."
systemctl restart networking || info "Service networking tidak selalu tersedia di Debian minimal."

################################################################################
# 11. Konfigurasi SSH
################################################################################
info "Mengonfigurasi SSH agar bisa login root & ubah port ke 1983..."
sed -i 's/^#\?Port .*/Port 1983/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config

info "Restarting SSH service..."
systemctl restart sshd

################################################################################
# 12. Konfigurasi iptables & iptables-persistent
################################################################################
info "Membersihkan semua aturan iptables..."
iptables -F
iptables -t nat -F
iptables -t mangle -F
iptables -X

ip6tables -F
ip6tables -t nat -F
ip6tables -t mangle -F
ip6tables -X

info "Mengatur kebijakan default ke ACCEPT..."
iptables -P INPUT ACCEPT
iptables -P FORWARD ACCEPT
iptables -P OUTPUT ACCEPT
ip6tables -P INPUT ACCEPT
ip6tables -P FORWARD ACCEPT
ip6tables -P OUTPUT ACCEPT

info "Aktifkan kembali IP forwarding..."
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv6.conf.all.forwarding=1
if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf; then
  echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
fi
if ! grep -q "net.ipv6.conf.all.forwarding=1" /etc/sysctl.conf; then
  echo "net.ipv6.conf.all.forwarding=1" >> /etc/sysctl.conf
fi
sysctl -p || info "Gagal memuat ulang sysctl (abaikan jika layanan minimal)."

info "Menyimpan aturan iptables..."
iptables-save > /etc/iptables/rules.v4
ip6tables-save > /etc/iptables/rules.v6

systemctl enable netfilter-persistent

################################################################################
# 13. Contoh Konfigurasi & Mount NFS4 (opsional)
################################################################################
info "Mengonfigurasi & melakukan mount NFS4..."
NFS_SERVER="172.16.30.2"
SHARE="/mnt/Data/Syslog"
MOUNT_POINT="/mnt/Data/Syslog"

mkdir -p "$MOUNT_POINT"
if ! grep -q "$MOUNT_POINT" /etc/fstab; then
  echo "$NFS_SERVER:$SHARE $MOUNT_POINT nfs4 defaults,_netdev 0 0" >> /etc/fstab
fi
mount -a || info "Pastikan server NFS mengekspor /mnt/Data/Syslog dengan NFS4."

################################################################################
# 14. Jalankan Tes Docker
################################################################################
info "Memastikan layanan Docker aktif..."
systemctl enable docker
systemctl start docker

if [ "$(systemctl is-active docker)" = "active" ] && [ "$(systemctl is-enabled docker)" = "enabled" ]; then
  info "Docker berjalan dan diaktifkan otomatis di reboot."
else
  error_exit "Docker tidak berjalan atau tidak diaktifkan otomatis."
fi

info "Menjalankan kontainer uji hello-world..."
docker run --rm hello-world || error_exit "Gagal menjalankan kontainer hello-world."

################################################################################
# 15. Reboot Otomatis
################################################################################
info "Instalasi & konfigurasi selesai. Sistem akan reboot dalam 5 detik..."
sleep 5
reboot