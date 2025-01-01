#!/bin/bash
set -e

########################################
# Pastikan script dijalankan sebagai root
########################################
if [ "$(id -u)" -ne 0 ]; then
    echo "Script ini harus dijalankan sebagai root!"
    exit 1
fi

########################################
# Variabel versi Docker & Docker Compose
########################################
# Ganti sesuai kebutuhan, misalnya:
# DOCKER_VERSION="5:20.10.25~3-0~debian-bullseye"
DOCKER_VERSION=""
DOCKER_COMPOSE_VERSION=${DOCKER_COMPOSE_VERSION:-"v2.22.0"}

########################################
# Fungsi bantuan
########################################
info() {
  echo -e "\e[32m[INFO]\e[0m $1"
}

error_exit() {
  echo -e "\e[31m[ERROR]\e[0m $1"
  exit 1
}

########################################
# 1. Update & Install Paket Dasar
########################################
info "Memperbarui repositori dan menginstal alat dasar..."
apt update && apt upgrade -y
apt update && apt install -y \
    curl nfs-common tcpdump jq net-tools openssh-server telnet netcat traceroute nmap dnsutils iputils-ping mtr whois iftop ethtool iperf3 \
    htop iotop sysstat git build-essential vim tmux python3 python3-pip strace lsof gdb ncdu zip unzip tree \
    ca-certificates gnupg lsb-release screen || error_exit "Gagal menginstal paket dasar."

########################################
# 2. Install Docker Engine
########################################
info "Menambahkan Docker GPG key..."
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg || error_exit "Gagal menambahkan GPG key Docker."

info "Menambahkan repository Docker..."
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
| tee /etc/apt/sources.list.d/docker.list > /dev/null || error_exit "Gagal menambahkan repository Docker."

info "Memperbarui daftar paket setelah menambahkan repository Docker..."
apt-get update -y || error_exit "Gagal menjalankan apt-get update."

info "Menginstal Docker Engine, Docker CLI, dan containerd..."
# Jika DOCKER_VERSION tidak kosong, maka gunakan versi tertentu, misalnya:
# apt-get install -y docker-ce=<versi> docker-ce-cli=<versi> containerd.io
if [ -n "$DOCKER_VERSION" ]; then
  apt-get install -y docker-ce="${DOCKER_VERSION}" docker-ce-cli="${DOCKER_VERSION}" containerd.io || error_exit "Gagal menginstal Docker versi $DOCKER_VERSION."
else
  apt-get install -y docker-ce docker-ce-cli containerd.io || error_exit "Gagal menginstal Docker versi terbaru."
fi

# Verifikasi Docker
info "Verifikasi instalasi Docker..."
if ! command -v docker &> /dev/null; then
  error_exit "Docker tidak ditemukan setelah instalasi."
fi

########################################
# 3. Konfigurasi Docker daemon.json
########################################
info "Mengonfigurasi Docker daemon.json..."
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

########################################
# 4. Install Docker Compose v2 (plugin)
########################################
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

curl -SL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-${ARCH}" -o "$DOCKER_COMPOSE_BINARY" \
  || error_exit "Gagal mengunduh Docker Compose."
chmod +x "$DOCKER_COMPOSE_BINARY"

info "Verifikasi instalasi Docker Compose..."
DOCKER_COMPOSE_VER=$(docker compose version --short 2>/dev/null) || error_exit "Docker Compose tidak ditemukan setelah instalasi."
info "Docker Compose versi $DOCKER_COMPOSE_VER telah berhasil diinstal."

########################################
# 5. Konfigurasi Jaringan (contoh)
########################################
info "Mengonfigurasi jaringan host..."
cat <<EOF > /etc/network/interfaces
# The loopback network interface
auto lo
iface lo inet loopback

# The primary network interface
allow-hotplug ens3
iface ens3 inet static
      address 172.16.30.3/28
      gateway 172.16.30.1
      dns-nameservers 8.8.8.8 1.1.1.1
      dns-search docker

# Macvlan network interface
auto macvlan0
iface macvlan0 inet static
      address 172.16.30.14/28
      pre-up ip link add macvlan0 link ens3 type macvlan mode bridge
      post-down ip link del macvlan0
EOF

info "Mengaktifkan IP forwarding..."
echo "net.ipv4.ip_forward=1" | tee -a /etc/sysctl.conf
sysctl -p

info "Restarting networking service..."
systemctl restart networking || info "Service networking mungkin tidak tersedia di Debian minimal."

########################################
# 6. Konfigurasi SSH
########################################
info "Mengonfigurasi SSH untuk login dengan password dan port 1983..."
sed -i 's/^#\?Port .*/Port 1983/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config

info "Restarting SSH service..."
systemctl restart sshd

########################################
# 7. Konfigurasi iptables
########################################
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

info "Mengaktifkan IP forwarding..."
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv6.conf.all.forwarding=1
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
echo "net.ipv6.conf.all.forwarding=1" >> /etc/sysctl.conf
sysctl -p

info "Instal iptables-persistent..."
apt-get install -y iptables-persistent

info "Menyimpan aturan iptables..."
iptables-save > /etc/iptables/rules.v4
ip6tables-save > /etc/iptables/rules.v6

info "Mengaktifkan iptables-persistent saat boot..."
systemctl enable netfilter-persistent

info "Verifikasi konfigurasi iptables..."
iptables -L -n -v
ip6tables -L -n -v

########################################
# 8. Tambahkan user ke grup docker
########################################
USER_TO_ADD="${SUDO_USER:-$(logname)}"
if id "$USER_TO_ADD" &>/dev/null; then
  info "Menambahkan pengguna '$USER_TO_ADD' ke grup docker..."
  usermod -aG docker "$USER_TO_ADD" || error_exit "Gagal menambahkan pengguna ke grup docker."
  info "Pengguna '$USER_TO_ADD' ditambahkan ke grup docker. Silakan logout dan login kembali."
fi

########################################
# 9. Uji Jalankan Docker
########################################
info "Memastikan layanan Docker aktif..."
systemctl start docker
systemctl enable docker

DOCKER_STATUS=$(systemctl is-active docker)
DOCKER_ENABLED=$(systemctl is-enabled docker)
if [ "$DOCKER_STATUS" = "active" ] && [ "$DOCKER_ENABLED" = "enabled" ]; then
  info "Docker berjalan dan aktif otomatis saat reboot."
else
  error_exit "Docker tidak berjalan atau tidak aktif otomatis."
fi

info "Menjalankan kontainer uji hello-world..."
docker run hello-world || error_exit "Gagal menjalankan kontainer hello-world."

########################################
# 10. Reboot Otomatis
########################################
info "Instalasi dan konfigurasi selesai. Sistem akan reboot dalam 5 detik..."
sleep 5
reboot