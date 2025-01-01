# Panduan Konfigurasi Jaringan MikroTik, TrueNAS, VM, dan Docker

Dokumentasi ini menjelaskan langkah-langkah lengkap untuk mengonfigurasi MikroTik, TrueNAS, VM, dan Docker agar dapat saling berkomunikasi melalui VLAN dan routing.

---

## 1. IP Alokasi Pada Proyek

| Subnet         | Deskripsi      |
|----------------|----------------|
| 172.16.10.0/24 | IP TrueNAS     |
| 172.16.30.0/28 | IP VM & Docker  |


---

## 2. Konfigurasi Jaringan MikroTik

### 2.1 Pengaturan VLAN di MikroTik

#### 2.1.1 Buat Bridge di MikroTik
```bash
/interface bridge
add name=docker-30
```

#### 2.1.2 Tambahkan VLAN 83 ke interface fisik MikroTik
```bash
/interface vlan
add name=vlan83 interface=docker-30 vlan-id=83
```

#### 2.1.3 Tambahkan VLAN 83 ke bridge
```bash
/interface bridge port
add bridge=docker-30 interface=vlan83
```

#### 2.1.4 Berikan IP pada bridge
```bash
/ip address
add address=172.16.30.1/28 interface=docker-30
```
> Biarkan bridge docker-31 tanpa client (ethernet/vlan, biarkan kosong)

### 2.2 Tambahkan Aturan Firewall

#### 2.2.1 Tambahkan Address List
```bash
/ip firewall address-list
add address=172.16.30.0/28 list=allowed-subnets
```

#### 2.2.2 Izinkan Traffic Antar-Subnet
```bash
/ip firewall filter
add chain=forward action=accept src-address-list=allowed-subnets 
add chain=input action=accept src-address-list=allowed-subnets
add chain=output action=accept dst-address-list=allowed-subnets
```

---

## 3. Konfigurasi IP Statis di TrueNAS Scale

1. Buka antarmuka web TrueNAS Scale dan masuk ke sistem.
2. Navigasi ke `Network` > `Interfaces`.
3. Pilih `Add` untuk menambahkan interface baru.
4. Pilih `Bridge` sebagai tipe interface.
5. Tambahkan interface fisik yang terhubung ke VLAN 83 sebagai anggota bridge.
6. Berikan IP statis pada bridge dengan konfigurasi berikut:
    - IP Address: `172.16.30.2/28`
    - Interface: `vlan83`
7. Simpan konfigurasi dan terapkan perubahan.

---

## 4. Membuat VM dengan OS Linux

### 4.1 Membuat Pool Data dengan Stripe

1. Buka antarmuka web TrueNAS Core dan masuk ke sistem.
2. Navigasi ke `Storage` > `Pools`.
3. Klik `Add` untuk membuat pool baru.
4. Pilih `Create new pool` dan klik `Create Pool`.
5. Masukkan nama pool sebagai `Data`.
6. Pilih dua disk yang akan digunakan untuk pool dan klik `Add Vdevs`.
7. Pilih `Stripe` sebagai tipe vdev karena hanya ada dua HDD.
8. Klik `Create` untuk membuat pool.

### 4.2 Membuat Dataset Backup

1. Navigasi ke `Storage` > `Pools`.
2. Klik pada pool `Data`.
3. Klik `Add Dataset`.
4. Masukkan nama dataset sebagai `Backup`.
5. Klik `Save` untuk membuat dataset.

### 4.3 Membuat Dataset Syslog

1. Navigasi ke `Storage` > `Pools`.
2. Klik pada pool `Data`.
3. Klik `Add Dataset`.
4. Masukkan nama dataset sebagai `Syslog`.
5. Klik `Save` untuk membuat dataset.

### 4.4 Membuat Dataset VMs

1. Navigasi ke `Storage` > `Pools`.
2. Klik pada pool `Data`.
3. Klik `Add Dataset`.
4. Masukkan nama dataset sebagai `VMs`.
5. Klik `Save` untuk membuat dataset.

### 4.5 Mengaktifkan SSH Server di TrueNAS Core

1. Buka antarmuka web TrueNAS Core dan masuk ke sistem.
2. Navigasi ke `Services`.
3. Temukan `SSH` dalam daftar layanan.
4. Klik tombol `Start` untuk mengaktifkan layanan SSH.
5. Klik ikon `Settings` (roda gigi) di sebelah `SSH`.
6. Centang opsi `Allow Password Authentication` jika belum dicentang.
7. Klik `Save` untuk menyimpan konfigurasi.

### 4.6 Buat VM baru dengan spesifikasi berikut:
- 4 vCPU
- 8 GB RAM
- Virtio 50 GB HDD
- Letakkan HDD VM di direktori `VMs`

### 4.7 Langkah-langkah pembuatan VM di TrueNAS Scale:

1. Buka antarmuka web TrueNAS Scale dan masuk ke sistem.
2. Navigasi ke `Virtualization` > `VMs`.
3. Klik `Add` untuk membuat VM baru.
4. Masukkan nama VM dan pilih direktori penyimpanan `VMs` untuk HDD.
5. Pilih ISO Debian sebagai media instalasi.
6. Atur jumlah CPU menjadi 4 vCPU.
7. Atur jumlah RAM menjadi 8 GB.
8. Pilih Virtio sebagai tipe HDD dan atur ukuran menjadi 50 GB.
9. Pilih `Virtio` sebagai adapter type.
10. Pilih `Passthrough` sebagai CPU Mode.
11. Centang opsi `Display`.
12. Masukkan password `12345`.
13. Pilih `Ensure Display Device`.
14. Jangan centang opsi `Hide from MSR`.
15. Selesaikan wizard pembuatan VM dan mulai instalasi Debian.

### 4.8 Instalasi Debian:

1. Boot VM menggunakan ISO Debian. Anda dapat mengunduh ISO Debian dari [sini](https://www.debian.org/distrib/netinst).
2. Ikuti langkah-langkah instalasi Debian:
    - Pilih bahasa dan lokasi.
    - Konfigurasi jaringan, masukkan IP statis `172.16.30.3`, subnet mask `255.255.255.240`, gateway `172.16.30.1`, dan DNS `8.8.8.8`.
    - Buat pengguna dan atur password.
    - Partisi disk sesuai kebutuhan.
    - Pada bagian pemilihan perangkat lunak, hanya centang `SSH server` dan `standard system utilities` untuk instalasi minimal tanpa GUI.
3. Setelah instalasi selesai, reboot VM dan login ke sistem.

---

## 5. Konfigurasi di VM

### 5.1 Aktifkan IP forwarding di VM (sementara)
```bash
echo 1 > /proc/sys/net/ipv4/ip_forward
```

### 5.2 Jadikan IP forwarding permanen

1. Edit file `/etc/sysctl.conf`
```bash
net.ipv4.ip_forward = 1
```

2. Terapkan perubahan
```bash
sysctl -p
```

---

## 6. Konfigurasi Jaringan Docker

### 6.1 Menyiapkan IP Docker `docker0`

1. Instalasi paket json
```bash
sudo apt update
sudo apt install -y jq
```

2. Cek versi aplikasi
```bash
jq --version
```

### 6.2 Edit `/etc/docker/daemon.json`

1. Edit file json
```bash
nano /etc/docker/daemon.json
```

2. Copy paste script di bawah ini
```json
{
     "default-address-pools": [
          {
                "base": "10.5.0.0/16",
                "size": 24
          }
     ]
}
```
> Bila kosong normal, copy paste saja script di atas

### 6.3 Restart Docker Service
```bash
systemctl restart docker
```

### 6.4 Verifikasi
```bash
docker network inspect bridge
```
> Output akan menunjukkan subnet baru yang telah diterapkan, kurang lebih seperti di bawah ini.
```json
[
     {
          "Name": "bridge",
          "Id": "abf5306c696dc39e7bdf74f3ff32141dfa37aacfd0fa208b80bb166a426e2072",
          "Created": "2024-12-28T10:07:20.388725497-05:00",
          "Scope": "local",
          "Driver": "bridge",
          "EnableIPv6": false,
          "IPAM": {
                "Driver": "default",
                "Options": null,
                "Config": [
                     {
                          "Subnet": "10.5.0.0/24",
                          "Gateway": "10.5.0.1"
                     }
                ]
          },
          "Internal": false,
          "Attachable": false,
          "Ingress": false,
          "ConfigFrom": {
                "Network": ""
          },
          "ConfigOnly": false,
          "Containers": {},
          "Options": {
                "com.docker.network.bridge.default_bridge": "true",
                "com.docker.network.bridge.enable_icc": "true",
                "com.docker.network.bridge.enable_ip_masquerade": "true",
                "com.docker.network.bridge.host_binding_ipv4": "0.0.0.0",
                "com.docker.network.bridge.name": "docker0",
                "com.docker.network.driver.mtu": "1500"
          },
          "Labels": {}
     }
]
```

---

## 7. Coba Jalankan di Docker

### 7.1 Jalankan container untuk menguji koneksi
```bash
docker run -it --rm alpine ping 172.16.10.1
```

### 7.2 Periksa container yang berjalan
```bash
docker ps -a
```

### 7.3 Hapus container yang tidak diperlukan
```bash
docker rm <CONTAINER_ID_OR_NAME>
```

---

## 8. Backup Konfigurasi MikroTik

### 8.1 Backup konfigurasi MikroTik
```bash
/export file=mikrotik-config-backup
```
> File akan disimpan di direktori default MikroTik.

---

## Catatan Tambahan

> Pengujian Log: Periksa log untuk traffic antar-subnet di MikroTik: `/log print where message~"Docker"`
> Pastikan Semua Subnet Terhubung: Lakukan ping antar-subnet untuk memastikan semua konfigurasi berjalan dengan baik.
