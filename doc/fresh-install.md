# Dokumentasi Lengkap Skrip Setup Debian dengan Docker, Docker Compose, dan NFS

## Pendahuluan
Skrip ini digunakan untuk mengotomatiskan instalasi dan konfigurasi Docker, Docker Compose, pengaturan jaringan, SSH, iptables, serta integrasi NFS pada sistem berbasis Debian. Skrip ini dirancang untuk memudahkan proses instalasi dengan penanganan kesalahan otomatis, fleksibilitas versi perangkat lunak, dan kompatibilitas yang luas.

## Bagian 1: Instalasi Docker dan Docker Compose

### Fitur Utama Skrip Docker

#### Instalasi Paket Dasar
Menginstal alat jaringan dan sistem seperti curl, nfs-common, vim, tmux, htop, dan lainnya.

#### Repository Docker
Menambahkan repository resmi Docker untuk memastikan instalasi versi terbaru atau spesifik.

#### Instalasi Docker
Menginstal Docker Engine, CLI, dan runtime containerd.

#### Instalasi Docker Compose
Mendukung versi v2 sebagai plugin CLI Docker.

#### Konfigurasi Docker
Membuat file `daemon.json` untuk pengaturan default address pools, DNS, dan buildkit.

### Langkah-Langkah Penggunaan Skrip

1. **Menyiapkan Skrip**
  - Buat direktori dan file skrip:
    ```bash
    mkdir -p ./tool
    nano ./tool/setup-debian.sh
    ```
  - Salin dan tempelkan isi skrip lengkap ke file tersebut, simpan (Ctrl + O, Enter), lalu keluar (Ctrl + X).

2. **Memberikan Izin Eksekusi**
  - Tambahkan izin eksekusi ke skrip:
    ```bash
    chmod +x ./tool/setup-debian.sh
    ```

3. **Menjalankan Skrip**
  - Jalankan skrip menggunakan sudo:
    ```bash
    sudo ./tool/setup-debian.sh
    ```

### Apa yang Dilakukan Skrip

1. **Instalasi dan Konfigurasi Docker**
  - **Instalasi Docker**:
    - Menambahkan repository Docker dan menginstal paket:
    ```bash
    apt-get install docker-ce docker-ce-cli containerd.io
    ```
  - **Konfigurasi Docker**:
    - Membuat file `/etc/docker/daemon.json` dengan konfigurasi berikut:
    ```json
    {
      "dns": ["8.8.8.8", "1.1.1.1"],
      "default-address-pools": [
        {"base": "172.16.30.0/16", "size": 28}
      ],
      "features": {"buildkit": true}
    }
    ```
  - **Instalasi Docker Compose**:
    - Mengunduh dan menginstal Docker Compose versi v2.22.0 dari repository resmi GitHub.

2. **Konfigurasi Jaringan**
  - **Aktivasi IP Forwarding**:
    - Mengaktifkan forwarding untuk IPv4 dan IPv6:
    ```bash
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
    echo "net.ipv6.conf.all.forwarding=1" >> /etc/sysctl.conf
    sysctl -p
    ```

3. **Konfigurasi SSH**
  - Mengaktifkan login root dan autentikasi password:
    ```plaintext
    Port 1983
    PermitRootLogin yes
    PasswordAuthentication yes
    ```

4. **Konfigurasi iptables**
  - Membersihkan aturan lama:
    ```bash
    iptables -F
    iptables -t nat -F
    iptables -t mangle -F
    iptables -X
    ```
  - Menyimpan aturan dengan iptables-persistent:
    ```bash
    iptables-save > /etc/iptables/rules.v4
    ip6tables-save > /etc/iptables/rules.v6
    ```

5. **Konfigurasi dan Mount NFS**
  - Menambahkan entri NFS ke `/etc/fstab`:
    ```plaintext
    172.16.30.2:/mnt/Data/Syslog /mnt/Data/Syslog nfs4 defaults,_netdev 0 0
    ```
  - Membuat direktori mount:
    ```bash
    mkdir -p /mnt/Data/Syslog
    ```
  - Melakukan mount:
    ```bash
    mount -a
    ```

## Bagian 2: Verifikasi Setelah Reboot

1. **Verifikasi Docker**
  - Periksa versi Docker:
    ```bash
    docker --version
    ```
  - Output yang diharapkan:
    ```plaintext
    Docker version 20.10.25, build abcdefg
    ```

2. **Verifikasi Docker Compose**
  - Periksa versi Docker Compose:
    ```bash
    docker compose version
    ```
  - Output yang diharapkan:
    ```plaintext
    Docker Compose version v2.22.0
    ```

3. **Verifikasi NFS**
  - Periksa mount NFS:
    ```bash
    mount | grep nfs
    ```

## Bagian 3: Troubleshooting

1. **Docker Tidak Berjalan**
  - Periksa status layanan Docker:
    ```bash
    sudo systemctl status docker
    ```
  - Restart layanan Docker:
    ```bash
    sudo systemctl restart docker
    ```

2. **Masalah NFS**
  - Pastikan server NFS aktif:
    ```bash
    exportfs -v
    ```
  - Cek konektivitas ke server:
    ```bash
    ping 172.16.30.2
    ```

3. **Masalah Jaringan**
  - Periksa forwarding IP:
    ```bash
    sysctl net.ipv4.ip_forward
    ```
  - Jika tidak aktif, aktifkan:
    ```bash
    sudo sysctl -w net.ipv4.ip_forward=1
    ```

## Bagian 4: Penentuan Versi Docker dan Docker Compose

1. **Default - Versi Terbaru**
  - Biarkan kosong untuk menggunakan versi terbaru:
    ```bash
    DOCKER_VERSION=""
    ```

2. **Versi Spesifik**
  - Periksa versi yang tersedia:
    ```bash
    apt-cache madison docker-ce
    ```
  - Pilih versi dan tambahkan ke skrip:
    ```bash
    DOCKER_VERSION="5:20.10.25~3-0~debian-bullseye"
    ```

## Kesimpulan
Skrip ini mencakup semua langkah yang diperlukan untuk menginstal Docker, Docker Compose, mengonfigurasi jaringan, SSH, iptables, dan integrasi NFS pada Debian. Dengan dokumentasi ini, Anda dapat dengan mudah mengotomatiskan tugas konfigurasi server dan memastikan semua komponen terinstal dan terkonfigurasi dengan benar. Reboot otomatis di akhir memastikan semua perubahan diterapkan dengan sempurna.
