# Panduan Lengkap Konfigurasi Jaringan MikroTik, TrueNAS, VM, dan Docker dengan Macvlan

Dokumentasi ini memberikan langkah-langkah konfigurasi dari awal hingga akhir untuk memungkinkan komunikasi antara MikroTik, TrueNAS, Virtual Machine (VM), dan Docker melalui VLAN, IP routing, dan Macvlan.

## Daftar Isi
1. [Alokasi IP pada Proyek](#alokasi-ip-pada-proyek)
2. [Konfigurasi Jaringan MikroTik](#konfigurasi-jaringan-mikrotik)
     1. [Pengaturan VLAN di MikroTik](#pengaturan-vlan-di-mikrotik)
          1. [Buat Bridge di MikroTik](#buat-bridge-di-mikrotik)
          2. [Tambahkan VLAN 83 ke Interface Fisik](#tambahkan-vlan-83-ke-interface-fisik)
          3. [Tambahkan VLAN 83 ke Bridge](#tambahkan-vlan-83-ke-bridge)
          4. [Berikan IP pada Bridge](#berikan-ip-pada-bridge)
     2. [Tambahkan Aturan Firewall](#tambahkan-aturan-firewall)
          1. [Tambahkan Address List](#tambahkan-address-list)
          2. [Izinkan Traffic Antar-Subnet](#izinkan-traffic-antar-subnet)
3. [Konfigurasi IP Statis di TrueNAS Scale](#konfigurasi-ip-statis-di-truenas-scale)
4. [Membuat dan Mengonfigurasi VM dengan OS Linux](#membuat-dan-mengonfigurasi-vm-dengan-os-linux)
     1. [Membuat Pool Data dengan Stripe](#membuat-pool-data-dengan-stripe)
     2. [Membuat Dataset Backup](#membuat-dataset-backup)
     3. [Membuat Dataset Syslog](#membuat-dataset-syslog)
     4. [Membuat Dataset VMs](#membuat-dataset-vms)
     5. [Mengaktifkan SSH Server di TrueNAS Core](#mengaktifkan-ssh-server-di-truenas-core)
     6. [Buat VM Baru](#buat-vm-baru)
     7. [Langkah-langkah Pembuatan VM di TrueNAS Scale](#langkah-langkah-pembuatan-vm-di-truenas-scale)
     8. [Instalasi Debian](#instalasi-debian)
5. [Konfigurasi di VM](#konfigurasi-di-vm)
     1. [Aktifkan IP Forwarding di VM (sementara)](#aktifkan-ip-forwarding-di-vm-sementara)
     2. [Jadikan IP Forwarding Permanen](#jadikan-ip-forwarding-permanen)
6. [Konfigurasi Jaringan Docker](#konfigurasi-jaringan-docker)
     1. [Menyiapkan IP Docker docker0](#menyiapkan-ip-docker-docker0)
     2. [Edit /etc/docker/daemon.json](#edit-etcdockerdaemonjson)
     3. [Restart Docker Service](#restart-docker-service)
     4. [Verifikasi](#verifikasi)
7. [Konfigurasi Macvlan di Docker](#konfigurasi-macvlan-di-docker)
     1. [Membuat Interface Macvlan Secara Manual](#membuat-interface-macvlan-secara-manual)
     2. [Membuat Jaringan Macvlan di Docker](#membuat-jaringan-macvlan-di-docker)
8. [Backup Konfigurasi MikroTik](#backup-konfigurasi-mikrotik)
9. [Catatan Tambahan](#catatan-tambahan)
10. [Referensi IP dalam Subnet](#referensi-ip-dalam-subnet)

## 1. Alokasi IP pada Proyek

Berikut adalah alokasi IP yang digunakan dalam proyek ini:

| Subnet          | Deskripsi                |
|-----------------|--------------------------|
| 172.16.10.0/24  | IP untuk TrueNAS         |
| 172.16.30.0/28  | IP untuk VM dan Docker   |
| 172.16.30.0/28  | Jaringan Docker Bridge   |
| 172.16.30.0/28  | Jaringan Macvlan Docker  |

## 2. Konfigurasi Jaringan MikroTik

### 2.1. Pengaturan VLAN di MikroTik

#### 2.1.1. Buat Bridge di MikroTik

```shell
/interface bridge
add name=docker-30
```

#### 2.1.2. Tambahkan VLAN 83 ke Interface Fisik

```shell
/interface vlan
add name=vlan83 interface=docker-30 vlan-id=83
```

#### 2.1.3. Tambahkan VLAN 83 ke Bridge

```shell
/interface bridge port
add bridge=docker-30 interface=vlan83
```

#### 2.1.4. Berikan IP pada Bridge

```shell
/ip address
add address=172.16.30.1/28 interface=docker-30
```

Catatan: Jangan tambahkan client langsung ke bridge ini (biarkan kosong).

### 2.2. Tambahkan Aturan Firewall

#### 2.2.1. Tambahkan Address List

```shell
/ip firewall address-list
add address=172.16.30.0/28 list=allowed-subnets
```

#### 2.2.2. Izinkan Traffic Antar-Subnet

```shell
/ip firewall filter
add chain=forward action=accept src-address-list=allowed-subnets
add chain=input action=accept src-address-list=allowed-subnets
add chain=output action=accept dst-address-list=allowed-subnets
```

## 3. Konfigurasi IP Statis di TrueNAS Scale

1. Masuk ke Antarmuka Web TrueNAS Scale.
2. Navigasi ke Network > Interfaces.
3. Pilih Add untuk menambahkan interface baru.
4. Pilih Bridge sebagai tipe interface.
5. Tambahkan interface fisik yang terhubung ke VLAN 83 sebagai anggota bridge.
6. Berikan IP statis pada bridge dengan konfigurasi berikut:
     - IP Address: 172.16.30.2/28
     - Interface: vlan83
7. Simpan dan Terapkan Perubahan.

## 4. Membuat dan Mengonfigurasi VM dengan OS Linux

### 4.1. Membuat Pool Data dengan Stripe

1. Buka antarmuka web TrueNAS Core dan masuk ke sistem.
2. Navigasi ke Storage > Pools.
3. Klik Add untuk membuat pool baru.
4. Pilih Create new pool dan klik Create Pool.
5. Masukkan nama pool sebagai Data.
6. Pilih dua disk yang akan digunakan untuk pool dan klik Add Vdevs.
7. Pilih Stripe sebagai tipe vdev karena hanya ada dua HDD.
8. Klik Create untuk membuat pool.

### 4.2. Membuat Dataset Backup

1. Navigasi ke Storage > Pools.
2. Klik pada pool Data.
3. Klik Add Dataset.
4. Masukkan nama dataset sebagai Backup.
5. Klik Save untuk membuat dataset.

### 4.3. Membuat Dataset Syslog

1. Navigasi ke Storage > Pools.
2. Klik pada pool Data.
3. Klik Add Dataset.
4. Masukkan nama dataset sebagai Syslog.
5. Klik Save untuk membuat dataset.

### 4.4. Membuat Dataset VMs

1. Navigasi ke Storage > Pools.
2. Klik pada pool Data.
3. Klik Add Dataset.
4. Masukkan nama dataset sebagai VMs.
5. Klik Save untuk membuat dataset.

### 4.5. Mengaktifkan SSH Server di TrueNAS Core

1. Buka antarmuka web TrueNAS Core dan masuk ke sistem.
2. Navigasi ke Services.
3. Temukan SSH dalam daftar layanan.
4. Klik tombol Start untuk mengaktifkan layanan SSH.
5. Klik ikon Settings (roda gigi) di sebelah SSH.
6. Centang opsi Allow Password Authentication jika belum dicentang.
7. Klik Save untuk menyimpan konfigurasi.

### 4.6. Buat VM Baru

Spesifikasi VM:
- CPU: 4 vCPU
- RAM: 8 GB
- HDD: Virtio 50 GB
- IP: 172.16.30.3/28

### 4.7. Langkah-langkah Pembuatan VM di TrueNAS Scale

1. Buka antarmuka web TrueNAS Scale dan masuk ke sistem.
2. Navigasi ke Virtualization > VMs.
3. Klik Add untuk membuat VM baru.
4. Masukkan nama VM dan pilih direktori penyimpanan VMs untuk HDD.
5. Pilih ISO Debian sebagai media instalasi.
6. Atur jumlah CPU menjadi 4 vCPU.
7. Atur jumlah RAM menjadi 8 GB.
8. Pilih Virtio sebagai tipe HDD dan atur ukuran menjadi 50 GB.
9. Pilih Virtio sebagai adapter type.
10. Pilih Passthrough sebagai CPU Mode.
11. Centang opsi Display.
12. Masukkan password 12345.
13. Pilih Ensure Display Device.
14. Jangan centang opsi Hide from MSR.
15. Selesaikan wizard pembuatan VM dan mulai instalasi Debian.

### 4.8. Instalasi Debian

1. Boot VM menggunakan ISO Debian. Anda dapat mengunduh ISO Debian di sini.
2. Ikuti langkah-langkah instalasi Debian:
     - Pilih bahasa dan lokasi.
     - Konfigurasi jaringan:
       - IP Statis: 172.16.30.3
       - Subnet Mask: 255.255.255.240
       - Gateway: 172.16.30.1
       - DNS: 8.8.8.8
     - Buat pengguna dan atur password.
     - Partisi disk sesuai kebutuhan.
     - Pada bagian pemilihan perangkat lunak, hanya centang SSH server dan Standard system utilities untuk instalasi minimal tanpa GUI.
3. Setelah instalasi selesai, reboot VM dan login ke sistem.

## 5. Konfigurasi di VM

### 5.1. Aktifkan IP Forwarding di VM (sementara)

```shell
echo 1 > /proc/sys/net/ipv4/ip_forward
```

### 5.2. Jadikan IP Forwarding Permanen

Edit file `/etc/sysctl.conf`:

```shell
sudo nano /etc/sysctl.conf
```

Tambahkan atau ubah baris berikut:

```ini
net.ipv4.ip_forward = 1
```

Terapkan perubahan:

```shell
sudo sysctl -p
```

## 6. Konfigurasi Jaringan Docker

### 6.1. Menyiapkan IP Docker docker0

Instalasi paket `jq`:

```shell
sudo apt update
sudo apt install -y jq
```

Cek versi aplikasi:

```shell
jq --version
```

### 6.2. Edit `/etc/docker/daemon.json`

Buka file `daemon.json`:

```shell
sudo nano /etc/docker/daemon.json
```

Copy-paste script berikut:

```json
{
       "default-address-pools": [
                {
                          "base": "172.16.30.0/28",
                          "size": 28
                }
       ]
}
```

Catatan: Jika file kosong, copy-paste saja script di atas.

### 6.3. Restart Docker Service

```shell
sudo systemctl restart docker
```

### 6.4. Verifikasi

```shell
docker network inspect bridge
```

Output akan menunjukkan subnet baru yang telah diterapkan, kurang lebih seperti di bawah ini:

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
                                          "Subnet": "172.16.30.0/28",
                                          "Gateway": "172.16.30.1"
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

## 7. Konfigurasi Macvlan di Docker

### 7.1. Membuat Interface Macvlan Secara Manual

Buat Macvlan:

```shell
sudo ip link add macvlan0 link ens3 type macvlan mode bridge
```

Berikan IP:

```shell
sudo ip addr add 172.16.30.14/28 dev macvlan0
```

Aktifkan Interface:

```shell
sudo ip link set macvlan0 up
```

### 7.2. Membuat Jaringan Macvlan di Docker

Buat Jaringan:

```shell
docker network create \
       --driver macvlan \
       --subnet=172.16.30.0/28 \
       --gateway=172.16.30.1 \
       -o parent=macvlan0 macvlan_net
```

Jalankan Kontainer:

```shell
docker run -d --net=macvlan_net --ip=172.16.30.8 --name stream-server nginx
```

## 8. Backup Konfigurasi MikroTik

### 8.1. Backup Konfigurasi MikroTik

```shell
/export file=mikrotik-config-backup
```

File akan disimpan di direktori default MikroTik.

## 9. Catatan Tambahan

Pengujian Log: Periksa log untuk traffic antar-subnet di MikroTik:

```shell
/log print where message~"Docker"
```

Pastikan Semua Subnet Terhubung: Lakukan ping antar-subnet untuk memastikan semua konfigurasi berjalan dengan baik.

Gunakan `tcpdump` untuk memonitor trafik:

```shell
sudo tcpdump -i macvlan0
```

## 10. Referensi IP dalam Subnet

| IP Address      | Deskripsi                |
|-----------------|--------------------------|
| 172.16.30.1     | Gateway                  |
| 172.16.30.2     | TrueNAS                  |
| 172.16.30.3     | Host VM                  |
| 172.16.30.14    | IP Macvlan pada Host Docker |

Dokumentasi ini dirancang untuk mempermudah pengaturan jaringan kompleks. Pastikan setiap langkah diikuti dengan hati-hati untuk menghindari konflik konfigurasi.