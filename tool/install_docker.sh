#!/bin/bash

# Skrip untuk menginstal Docker CE, Docker Compose v2, dan alat jaringan tambahan di Debian 12

set -e

# Tambahkan /usr/sbin ke PATH
export PATH=$PATH:/usr/sbin

# Fungsi untuk menampilkan pesan informasi
info() {
  echo -e "\e[32m[INFO]\e[0m $1"
}

# Fungsi untuk menampilkan pesan kesalahan dan keluar
error_exit() {
  echo -e "\e[31m[ERROR]\e[0m $1"
  exit 1
}

# Pastikan skrip dijalankan sebagai root
if [ "$EUID" -ne 0 ]; then
  error_exit "Skrip ini harus dijalankan sebagai root. Gunakan sudo."
fi

# Update daftar paket
info "Memperbarui daftar paket..."
apt-get update -y || error_exit "Gagal menjalankan apt-get update."

# Instal paket yang diperlukan termasuk net-tools, telnet, dan nmap
info "Menginstal paket yang diperlukan (ca-certificates, curl, gnupg, lsb-release, net-tools, telnet, nmap)..."
apt-get install -y ca-certificates curl gnupg lsb-release net-tools telnet nmap || error_exit "Gagal menginstal paket yang diperlukan."

# Tambahkan GPG key Docker
info "Menambahkan Docker GPG key..."
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg || error_exit "Gagal menambahkan GPG key Docker."

# Tambahkan repository Docker
info "Menambahkan repository Docker..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null || error_exit "Gagal menambahkan repository Docker."

# Update kembali daftar paket setelah menambahkan repository Docker
info "Memperbarui daftar paket setelah menambahkan repository Docker..."
apt-get update -y || error_exit "Gagal menjalankan apt-get update setelah menambahkan repository Docker."

# Instal Docker Engine, CLI, dan containerd
info "Menginstal Docker Engine, Docker CLI, dan containerd..."
apt-get install -y docker-ce docker-ce-cli containerd.io || error_exit "Gagal menginstal Docker."

# Verifikasi instalasi Docker
info "Verifikasi instalasi Docker..."
if ! command -v docker &> /dev/null; then
  error_exit "Docker tidak ditemukan setelah instalasi."
fi

# Instal Docker Compose sebagai plugin Docker
info "Menginstal Docker Compose versi terbaru sebagai plugin Docker..."

# Tentukan versi terbaru Docker Compose menggunakan GitHub API
DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d '"' -f 4)

if [ -z "$DOCKER_COMPOSE_VERSION" ]; then
  error_exit "Gagal mendapatkan versi Docker Compose terbaru."
fi

info "Versi Docker Compose yang akan diinstal: $DOCKER_COMPOSE_VERSION"

# Tentukan arsitektur
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
  ARCH="x86_64"
elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
  ARCH="arm64"
else
  error_exit "Arsitektur $ARCH tidak didukung."
fi

# Tentukan path yang benar untuk plugin Docker Compose di Debian
DOCKER_COMPOSE_BINARY="/usr/lib/docker/cli-plugins/docker-compose"

# Buat direktori jika belum ada
mkdir -p /usr/lib/docker/cli-plugins

# Unduh Docker Compose dari repositori yang benar
info "Mengunduh Docker Compose..."
curl -SL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-${ARCH}" -o "$DOCKER_COMPOSE_BINARY" || error_exit "Gagal mengunduh Docker Compose."

# Berikan izin eksekusi
chmod +x "$DOCKER_COMPOSE_BINARY" || error_exit "Gagal memberikan izin eksekusi pada Docker Compose."

# Verifikasi instalasi Docker Compose
info "Verifikasi instalasi Docker Compose..."
DOCKER_COMPOSE_VER=$(docker compose version --short 2>/dev/null) || error_exit "Docker Compose tidak ditemukan setelah instalasi."

info "Docker Compose versi $DOCKER_COMPOSE_VER telah berhasil diinstal."

# Tentukan nama pengguna untuk ditambahkan ke grup docker
if [ -n "$SUDO_USER" ]; then
  USER_TO_ADD="$SUDO_USER"
else
  # Jika $SUDO_USER kosong, coba gunakan logname
  USER_TO_ADD=$(logname 2>/dev/null) || USER_TO_ADD=""
  if [ -z "$USER_TO_ADD" ]; then
    # Jika logname juga gagal, minta input pengguna
    read -p "Masukkan nama pengguna yang ingin ditambahkan ke grup 'docker': " USER_TO_ADD
  fi
fi

# Pastikan USER_TO_ADD tidak kosong dan pengguna ada
if [ -n "$USER_TO_ADD" ]; then
  if id "$USER_TO_ADD" &>/dev/null; then
    info "Menambahkan pengguna '$USER_TO_ADD' ke grup docker..."
    usermod -aG docker "$USER_TO_ADD" || error_exit "Gagal menambahkan pengguna ke grup docker."
    info "Pengguna '$USER_TO_ADD' telah ditambahkan ke grup docker. Silakan logout dan login kembali agar perubahan ini berlaku."
  else
    error_exit "Pengguna '$USER_TO_ADD' tidak ditemukan. Tidak dapat menambahkan ke grup docker."
  fi
else
  info "Tidak ada pengguna yang ditentukan untuk ditambahkan ke grup 'docker'."
fi

# Mulai dan aktifkan layanan Docker
info "Memulai dan mengaktifkan layanan Docker..."
systemctl start docker || error_exit "Gagal memulai layanan Docker."
systemctl enable docker || error_exit "Gagal mengaktifkan layanan Docker."

# Verifikasi status Docker
info "Memeriksa status Docker..."
DOCKER_STATUS=$(systemctl is-active docker)
DOCKER_ENABLED=$(systemctl is-enabled docker)

if [ "$DOCKER_STATUS" = "active" ] && [ "$DOCKER_ENABLED" = "enabled" ]; then
  info "Docker sedang berjalan dan diatur untuk start secara otomatis saat reboot."
else
  error_exit "Docker tidak berjalan atau tidak diatur untuk start secara otomatis."
fi

# Jalankan kontainer test
info "Menjalankan kontainer test 'hello-world'..."
docker run hello-world || error_exit "Gagal menjalankan kontainer test Docker."

info "Docker telah berhasil diinstal dan diuji!"
info "Docker Compose telah berhasil diinstal."
info "Alat jaringan tambahan (net-tools, telnet, nmap) telah diinstal."

# Jalankan verifikasi Docker Compose versi v2
info "Menjalankan verifikasi versi Docker Compose..."
docker compose version
