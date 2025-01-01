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

### 2.2. Tambahkan Aturan Firewall

#### Tambahkan Address List

```bash
/ip firewall address-list
add address=172.16.30.0/28 list=allowed-subnets
```

#### Izinkan Traffic Antar-Subnet

```bash
/ip firewall filter
add chain=forward action=accept src-address-list=allowed-subnets
add chain=input action=accept src-address-list=allowed-subnets
add chain=output action=accept dst-address-list=allowed-subnets
```

## 3. Konfigurasi IP Statis di TrueNAS Scale

1. Buka Web Interface TrueNAS Scale.
2. Navigasi ke Network > Interfaces.
3. Tambahkan interface baru dengan pengaturan berikut:
     - Tipe: Bridge
     - IP Address: 172.16.30.2/28
     - Gateway: 172.16.30.1
     - Interface: VLAN 83
4. Simpan dan terapkan perubahan.

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
echo 1 > /proc/sys/net/ipv4/ip_forward
sudo nano /etc/sysctl.conf
```

Tambahkan:

```ini
net.ipv4.ip_forward = 1
```

## 5. Konfigurasi Jaringan Docker

### 5.1. Jaringan docker0

Edit `/etc/docker/daemon.json`:

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

## 7. Referensi IP dalam Subnet

| IP Address      | Deskripsi                |
|-----------------|--------------------------|
| 172.16.30.1     | Gateway                  |
| 172.16.30.2     | TrueNAS                  |
| 172.16.30.3     | VM Host                  |
| 172.16.30.14    | IP Macvlan pada Host Docker |

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

Dokumentasi ini dirancang untuk memastikan integrasi sistem berjalan lancar dan dapat disesuaikan dengan kebutuhan spesifik proyek Anda. Pastikan setiap langkah diuji sebelum implementasi penuh di lingkungan produksi.
