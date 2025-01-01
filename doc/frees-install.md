# Tutorial Lengkap Penggunaan Skrip fresh-install.sh

Skrip ini digunakan untuk menginstal Docker, Docker Compose, serta alat jaringan dan konfigurasi tambahan pada sistem Debian. Berikut adalah langkah-langkah lengkap penggunaan skrip, termasuk hasil akhir yang diharapkan untuk dokumentasi.

## 1. Persiapan Awal

### 1.1. Pastikan Sistem Sudah Siap
- Sistem Anda harus berbasis Debian atau turunannya (seperti Ubuntu).
- Anda memerlukan akses root atau pengguna dengan hak administratif (sudo).

### 1.2. Update Sistem
Sebelum menjalankan skrip, perbarui sistem Anda:
```bash
sudo apt update && sudo apt upgrade -y
```

## 2. Membuat dan Menjalankan Skrip

### 2.1. Buat File Skrip
Buka terminal dan buat file baru untuk menyimpan skrip:
```bash
nano ./tool/fresh-install.sh
```
Salin isi skrip berikut ke editor (ini adalah versi lengkap yang Anda berikan atau modifikasi). Simpan dan keluar:
- Tekan `Ctrl + O`, lalu `Enter` untuk menyimpan.
- Tekan `Ctrl + X` untuk keluar dari editor.

### 2.2. Berikan Izin Eksekusi pada Skrip
Agar skrip dapat dijalankan, tambahkan izin eksekusi:
```bash
chmod +x ./tool/fresh-install.sh
```

### 2.3. Menjalankan Skrip
Jalankan skrip menggunakan sudo untuk memastikan semua langkah berjalan dengan hak akses root:
```bash
sudo ./tool/fresh-install.sh
```

## 3. Apa yang Dilakukan Skrip
Skrip ini secara otomatis melakukan langkah-langkah berikut:
- **Memperbarui Sistem dan Menginstal Alat Dasar**: Alat seperti curl, tcpdump, net-tools, vim, git, dan lainnya akan diinstal.
- **Menambahkan Repository Docker**: Repository resmi Docker ditambahkan untuk memastikan versi terbaru atau spesifik dapat diinstal.
- **Menginstal Docker**: Docker Engine, CLI, dan containerd diinstal.
- **Menginstal Docker Compose**: Versi Docker Compose yang Anda tentukan akan diinstal sebagai plugin Docker.
- **Konfigurasi Docker**: File konfigurasi daemon.json akan dibuat dengan pengaturan DNS, default-address-pools, dan fitur buildkit.
- **Mengonfigurasi Jaringan**: IP statis dan interface macvlan ditambahkan ke file `/etc/network/interfaces`. Forwarding IP diaktifkan untuk mendukung routing.
- **Mengonfigurasi SSH**: Login root diaktifkan, autentikasi password diaktifkan, dan port diubah ke 1983.
- **Konfigurasi Iptables**: Aturan iptables direset, dan kebijakan default diatur ke ACCEPT. Aturan iptables disimpan untuk persisten.
- **Menambahkan Pengguna ke Grup Docker**: Pengguna saat ini ditambahkan ke grup docker untuk memungkinkan penggunaan Docker tanpa sudo.
- **Reboot Otomatis**: Sistem akan reboot untuk menerapkan semua konfigurasi.

## 4. Verifikasi Setelah Reboot

### 4.1. Cek Versi Docker
Pastikan Docker terinstal dengan benar:
```bash
docker --version
```
Output yang Diharapkan:
```plaintext
Docker version 20.10.25, build abcdefg
```

### 4.2. Cek Versi Docker Compose
Verifikasi bahwa Docker Compose terinstal:
```bash
docker compose version
```
Output yang Diharapkan:
```plaintext
Docker Compose version v2.22.0
```

### 4.3. Tes Jalankan Docker
Pastikan Docker berjalan dengan baik dengan menjalankan container uji:
```bash
docker run hello-world
```
Output yang Diharapkan:
```plaintext
Hello from Docker!
This message shows that your installation appears to be working correctly.
```

## 5. Dokumentasi Hasil

### 5.1. Paket yang Terinstal
- Alat jaringan: curl, tcpdump, net-tools, dll.
- Alat pengembangan: git, vim, python3, dll.

### 5.2. Versi Docker dan Docker Compose
- **Docker**:
    ```bash
    docker --version
    ```
    Output:
    ```plaintext
    Docker version 20.10.25, build abcdefg
    ```
- **Docker Compose**:
    ```bash
    docker compose version
    ```
    Output:
    ```plaintext
    Docker Compose version v2.22.0
    ```

### 5.3. File Konfigurasi
- **Konfigurasi Docker (/etc/docker/daemon.json)**:
    ```json
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
    ```
- **Konfigurasi Jaringan (/etc/network/interfaces)**:
    ```bash
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
    ```
- **Konfigurasi SSH (/etc/ssh/sshd_config)**:
    ```yaml
    Port 1983
    PermitRootLogin yes
    PasswordAuthentication yes
    ```

## 6. Troubleshooting

### Docker Tidak Berjalan
Pastikan layanan Docker aktif:
```bash
sudo systemctl status docker
```
Jika tidak berjalan, coba restart:
```bash
sudo systemctl restart docker
```

### Masalah Jaringan
Pastikan IP forwarding aktif:
```bash
sysctl net.ipv4.ip_forward
```
Output harus 1.

## Kesimpulan
Skrip ./tool/fresh-install.sh mengotomatiskan proses instalasi Docker, Docker Compose, dan konfigurasi jaringan pada sistem Debian. Dengan dokumentasi ini, Anda dapat dengan mudah mengulang langkah-langkah instalasi dan memverifikasi hasilnya.

## Menentukan Versi Docker

### 1. Tidak Mengisi (Default - Versi Terbaru)
Jika Anda meninggalkan variabel DOCKER_VERSION kosong seperti ini:
```bash
DOCKER_VERSION=""
```
Skrip akan secara otomatis menginstal versi Docker terbaru yang tersedia di repository Docker. Tidak perlu melakukan perubahan apa pun jika Anda ingin menggunakan versi terbaru.

### 2. Menentukan Versi Docker
Untuk menginstal versi Docker tertentu, isi variabel DOCKER_VERSION dengan versi yang Anda inginkan. Misalnya:
```bash
DOCKER_VERSION="5:20.10.25~3-0~debian-bullseye"
```
Anda bisa mendapatkan versi Docker yang tersedia dengan menjalankan perintah berikut di terminal:
```bash
apt-cache madison docker-ce
```
Outputnya akan seperti ini:
```plaintext
docker-ce | 5:20.10.25~3-0~debian-bullseye | https://download.docker.com/linux/debian bullseye/stable amd64 Packages
docker-ce | 5:20.10.24~3-0~debian-bullseye | https://download.docker.com/linux/debian bullseye/stable amd64 Packages
```
Pilih versi yang Anda inginkan dari daftar output tersebut dan masukkan ke dalam variabel DOCKER_VERSION.

### Langkah-Langkah untuk Menggunakan
1. Buka Skrip untuk Diedit:
    ```bash
    nano ./tool/fresh-install.sh
    ```
2. Temukan dan Ubah Baris DOCKER_VERSION:
    Baris tersebut biasanya ada di bagian awal skrip:
    ```bash
    DOCKER_VERSION=""
    ```
    Jika Anda ingin menginstal versi tertentu, ubah menjadi, misalnya:
    ```bash
    DOCKER_VERSION="5:20.10.25~3-0~debian-bullseye"
    ```
3. Simpan Perubahan dan Keluar:
    - Tekan `Ctrl + O`, lalu `Enter` untuk menyimpan.
    - Tekan `Ctrl + X` untuk keluar dari editor.
4. Jalankan Skrip: Setelah mengubah versi Docker, jalankan skrip seperti biasa:
    ```bash
    sudo ././tool/fresh-install.sh
    ```

### Apa yang Terjadi di Skrip
Skrip akan memeriksa apakah DOCKER_VERSION kosong atau tidak:
- Jika Kosong (DOCKER_VERSION=""):
    Perintah berikut akan digunakan untuk menginstal versi terbaru:
    ```bash
    apt-get install -y docker-ce docker-ce-cli containerd.io
    ```
- Jika Berisi Versi Tertentu (DOCKER_VERSION="5:20.10.25~3-0~debian-bullseye"):
    Skrip akan menjalankan perintah ini untuk menginstal versi yang spesifik:
    ```bash
    apt-get install -y docker-ce="${DOCKER_VERSION}" docker-ce-cli="${DOCKER_VERSION}" containerd.io
    ```

### Kesimpulan
- Biarkan DOCKER_VERSION kosong untuk menginstal versi terbaru.
- Isi DOCKER_VERSION dengan versi spesifik jika Anda membutuhkan versi Docker tertentu.
- Pastikan versi yang Anda masukkan valid dengan memeriksa daftar versi melalui:
    ```bash
    apt-cache madison docker-ce
    ```
