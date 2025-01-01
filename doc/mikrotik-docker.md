# Panduan Lengkap Konfigurasi Jaringan MikroTik, TrueNAS, VM, dan Docker dengan Macvlan

Dokumentasi ini memberikan panduan langkah demi langkah untuk mengintegrasikan MikroTik, TrueNAS, Virtual Machine (VM), dan Docker menggunakan VLAN, routing IP, serta konfigurasi Macvlan. Panduan ini mencakup konfigurasi jaringan, alokasi IP, dan pengaturan layanan secara mendetail.

## Daftar Isi
1. [Alokasi IP pada Proyek](#alokasi-ip-pada-proyek)
2. [Konfigurasi Jaringan MikroTik](#konfigurasi-jaringan-mikrotik)
     1. [Pengaturan VLAN](#pengaturan-vlan)
     2. [Pengaturan Bridge dan IP](#pengaturan-bridge-dan-ip)
     3. [Aturan Firewall](#aturan-firewall)
3. [Konfigurasi IP Statis di TrueNAS Scale](#konfigurasi-ip-statis-di-truenas-scale)
4. [Membuat dan Mengonfigurasi VM dengan OS Linux](#membuat-dan-mengonfigurasi-vm-dengan-os-linux)
     1. [Pool dan Dataset](#pool-dan-dataset)
     2. [Instalasi Debian](#instalasi-debian)
5. [Konfigurasi Jaringan Docker](#konfigurasi-jaringan-docker)
     1. [Jaringan docker0](#jaringan-docker0)
     2. [Macvlan](#macvlan)
6. [Backup Konfigurasi MikroTik](#backup-konfigurasi-mikrotik)
7. [Referensi IP dalam Subnet](#referensi-ip-dalam-subnet)
8. [Catatan Tambahan](#catatan-tambahan)

## 1. Alokasi IP pada Proyek

| Subnet          | Deskripsi                |
|-----------------|--------------------------|
| 172.16.10.0/24  | IP untuk TrueNAS         |
| 172.16.30.0/28  | IP untuk VM dan Docker   |
| 172.16.30.0/28  | Jaringan Docker Bridge   |
| 172.16.30.0/28  | Jaringan Macvlan Docker  |

## 2. Konfigurasi Jaringan MikroTik

### 2.1. Pengaturan VLAN

VLAN (Virtual Local Area Network) adalah teknologi yang memungkinkan segmentasi jaringan secara logis dalam satu perangkat fisik. Tujuannya adalah untuk memisahkan lalu lintas jaringan untuk keamanan dan efisiensi.

#### Buat Bridge

```bash
/interface bridge
add name=docker-30
```

#### Tambahkan VLAN 83 ke Interface Fisik

```bash
/interface vlan
add name=vlan83 interface=docker-30 vlan-id=83
```

#### Tambahkan VLAN 83 ke Bridge

```bash
/interface bridge port
add bridge=docker-30 interface=vlan83
```

#### Berikan IP pada Bridge

```bash
/ip address
add address=172.16.30.1/28 interface=docker-30
```

#### Validasi Konfigurasi

```bash
/interface bridge print
/interface vlan print
```

### 2.2. Tambahkan Aturan Firewall

#### Tambahkan Address List

```bash
/ip firewall address-list
add address=172.16.30.0/28 list=docker
```

#### Izinkan Traffic Antar-Subnet

```bash
/ip firewall filter
add chain=input action=accept protocol=icmp comment="Allow ICMP (Ping)"
add chain=input action=drop comment="Drop all other input traffic"

/ip firewall filter
add chain=forward action=accept src-address-list=docker dst-address-list=docker comment="Allow traffic between Docker subnets"
add chain=forward action=drop comment="Drop other forward traffic"

/ip firewall filter
add chain=output action=accept src-address-list=docker comment="Allow output traffic to Docker subnets"
add chain=output action=drop comment="Drop all other output traffic"
```

#### Validasi Konfigurasi

```bash
/ip firewall filter print
```

## 3. Konfigurasi IP Statis di TrueNAS Scale

Bridge penting untuk menghubungkan beberapa jaringan dan gateway berfungsi sebagai pintu gerbang ke jaringan lain.

1. Buka Web Interface TrueNAS Scale.
2. Navigasi ke Network > Interfaces.
3. Tambahkan interface baru dengan pengaturan berikut:
     - Tipe: Bridge
     - IP Address: 172.16.30.2/28
     - Gateway: 172.16.30.1
     - Interface: VLAN 83
4. Simpan dan terapkan perubahan.
5. Verifikasi pengaturan dengan perintah `ping` atau `traceroute`.

## 4. Membuat dan Mengonfigurasi VM dengan OS Linux

### 4.1. Pool dan Dataset

1. Buat Pool Data dengan konfigurasi Stripe.
2. Tambahkan Dataset:
     - Backup
     - Syslog
     - VMs

### 4.2. Buat VM Baru

- CPU: 4 vCPU
- RAM: 8 GB
- HDD: Virtio 50 GB
- IP: 172.16.30.3/28

### 4.3. Instalasi Debian

1. Ikuti instalasi:
     - Pilih IP Statis: 172.16.30.3
     - Gateway: 172.16.30.1
     - DNS: 8.8.8.8
2. Aktifkan IP Forwarding:

```bash
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

3. Verifikasi IP statis setelah konfigurasi:

```bash
ip addr
```

## 5. Konfigurasi Jaringan Docker

### 5.1. Jaringan docker0

Edit `/etc/docker/daemon.json`:

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

Restart Docker:

```bash
sudo systemctl restart docker
```

### 5.2. Macvlan

#### Buat Macvlan Interface

```bash
sudo ip link add macvlan0 link ens3 type macvlan mode bridge
sudo ip addr add 172.16.30.14/28 dev macvlan0
sudo ip link set macvlan0 up
```

#### Konfigurasi di Docker

```bash
docker network create \
      --driver macvlan \
      --subnet=172.16.30.0/28 \
      --gateway=172.16.30.1 \
      -o parent=macvlan0 macvlan_net
```

Jalankan Kontainer:

```bash
docker run -d --net=macvlan_net --ip=172.16.30.8 --name stream-server nginx
```

#### Validasi Konfigurasi

```bash
docker network inspect macvlan_net
```

### 5.3. Konfigurasi di `/etc/network/interfaces`

Edit file:

```plaintext
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

## 6. Backup Konfigurasi MikroTik

Backup konfigurasi MikroTik:

```bash
/export file=mikrotik-config-backup
```

Simpan file konfigurasi ke perangkat lokal:

```bash
/tool fetch address=<ftp_server_ip> src-path=mikrotik-config-backup.rsc user=<username> password=<password>
```

## 7. Referensi IP dalam Subnet

| IP Address      | Deskripsi                |
|-----------------|--------------------------|
| 172.16.30.1     | Gateway                  |
| 172.16.30.2     | TrueNAS                  |
| 172.16.30.3     | VM Host                  |
| 172.16.30.4-14  | IP Macvlan Docker Host   |

## 8. Catatan Tambahan

### Pengujian Koneksi

- Uji koneksi antar-subnet menggunakan ping.
- Verifikasi routing menggunakan tcpdump:

```bash
sudo tcpdump -i macvlan0
```

### Monitoring Log MikroTik

```bash
/log print where message~"Docker"
```

### Troubleshooting

#### Tidak bisa ping antar subnet

1. Periksa aturan firewall di MikroTik.
2. Pastikan konfigurasi VLAN dan bridge sudah benar.

#### Docker container tidak dapat diakses dari jaringan lain

1. Verifikasi konfigurasi jaringan Docker.
2. Pastikan IP forwarding diaktifkan pada host.

Dokumentasi ini dirancang untuk memastikan integrasi sistem berjalan lancar dan dapat disesuaikan dengan kebutuhan spesifik proyek Anda. Pastikan setiap langkah diuji sebelum implementasi penuh di lingkungan produksi.

## Script Automasi Setup MikroTik

```plaintext
# -----------------------------------------------------------------------------
# Script Konfigurasi MikroTik untuk Integrasi TrueNAS, VM, dan Docker
# -----------------------------------------------------------------------------

# 1. Membuat Bridge untuk VLAN 83
/interface bridge
add name=docker-30 comment="Bridge untuk VLAN 83 (Docker, VM, Macvlan)"

# 2. Menambahkan VLAN 83 ke Interface Fisik
/interface vlan
add name=vlan83 interface=docker-30 vlan-id=83 comment="VLAN 83 untuk Docker, VM, dan Macvlan"

# 3. Menambahkan VLAN 83 ke Bridge
/interface bridge port
add bridge=docker-30 interface=vlan83 comment="Hubungkan VLAN 83 ke Bridge docker-30"

# 4. Memberikan IP Address ke Bridge
/ip address
add address=172.16.30.1/28 interface=docker-30 comment="IP Gateway untuk jaringan VLAN 83"

# 5. Tambahkan Address List untuk Jaringan Docker
/ip firewall address-list
add address=172.16.30.0/28 list=docker comment="Subnet untuk jaringan Docker, VM, dan Macvlan"

# 6. Tambahkan Aturan Firewall
# 6.1 Izinkan ICMP (Ping)
/ip firewall filter
add chain=input action=accept protocol=icmp comment="Allow ICMP (Ping)"

# 6.2 Izinkan Traffic Antar Subnet Docker
/ip firewall filter
add chain=forward action=accept src-address-list=docker dst-address-list=docker comment="Allow traffic between Docker subnets"

# 6.3 Drop Traffic Lainnya di Input
/ip firewall filter
add chain=input action=drop comment="Drop all other input traffic"

# 6.4 Drop Traffic Lainnya di Forward
/ip firewall filter
add chain=forward action=drop comment="Drop other forward traffic"

# 6.5 Izinkan Traffic Output ke Subnet Docker
/ip firewall filter
add chain=output action=accept src-address-list=docker comment="Allow output traffic to Docker subnets"

# 6.6 Drop Traffic Output Lainnya
/ip firewall filter
add chain=output action=drop comment="Drop all other output traffic"

# 7. Validasi Konfigurasi
:log info "Validasi Konfigurasi:"
/interface bridge print
/interface vlan print
/ip address print
/ip firewall filter print
/ip firewall address-list print

:log info "Konfigurasi MikroTik selesai."
```
