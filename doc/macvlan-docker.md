# Panduan Lengkap Konfigurasi Jaringan MikroTik, TrueNAS, VM, dan Docker dengan Macvlan

Dokumentasi ini memberikan langkah-langkah konfigurasi dari awal hingga akhir untuk memungkinkan komunikasi antara MikroTik, TrueNAS, Virtual Machine (VM), dan Docker melalui VLAN, IP routing, dan Macvlan.

## Daftar Isi
1. [Alokasi IP pada Proyek](#alokasi-ip-pada-proyek)
2. [Konfigurasi Jaringan MikroTik](#konfigurasi-jaringan-mikrotik)
    1. [Pengaturan VLAN di MikroTik](#pengaturan-vlan-di-mikrotik)
    2. [Tambahkan Aturan Firewall](#tambahkan-aturan-firewall)
3. [Konfigurasi IP Statis di TrueNAS Scale](#konfigurasi-ip-statis-di-truenas-scale)
4. [Membuat dan Mengonfigurasi VM dengan OS Linux](#membuat-dan-mengonfigurasi-vm-dengan-os-linux)
    1. [Membuat VM di TrueNAS Scale](#membuat-vm-di-truenas-scale)
5. [Konfigurasi di VM](#konfigurasi-di-vm)
6. [Konfigurasi Jaringan Docker](#konfigurasi-jaringan-docker)
7. [Konfigurasi Macvlan di Docker](#konfigurasi-macvlan-di-docker)
    1. [Membuat Interface Macvlan Secara Manual](#membuat-interface-macvlan-secara-manual)
    2. [Membuat Jaringan Macvlan di Docker](#membuat-jaringan-macvlan-di-docker)
8. [Backup Konfigurasi MikroTik](#backup-konfigurasi-mikrotik)
9. [Catatan Tambahan](#catatan-tambahan)
10. [Referensi IP dalam Subnet](#referensi-ip-dalam-subnet)

## 1. Alokasi IP pada Proyek

Berikut adalah alokasi IP yang digunakan dalam proyek ini:

| Subnet         | Deskripsi              |
|----------------|------------------------|
| 172.16.10.0/24 | IP untuk TrueNAS       |
| 172.16.30.0/28 | IP untuk VM dan Docker |
| 172.16.30.0/28 | Jaringan Docker Bridge |
| 172.16.30.0/28 | Jaringan Macvlan Docker|

## 2. Konfigurasi Jaringan MikroTik

### 2.1. Pengaturan VLAN di MikroTik

Buat Bridge di MikroTik:
```bash
/interface bridge
add name=docker-30
```

Tambahkan VLAN 83 ke Interface Fisik:
```bash
/interface vlan
add name=vlan83 interface=docker-30 vlan-id=83
```

Tambahkan VLAN 83 ke Bridge:
```bash
/interface bridge port
add bridge=docker-30 interface=vlan83
```

Berikan IP pada Bridge:
```bash
/ip address
add address=172.16.30.1/28 interface=docker-30
```
Catatan: Jangan tambahkan client langsung ke bridge ini (biarkan kosong).

### 2.2. Tambahkan Aturan Firewall

Tambahkan Address List:
```bash
/ip firewall address-list
add address=172.16.30.0/28 list=allowed-subnets
```

Izinkan Traffic Antar-Subnet:
```bash
/ip firewall filter
add chain=forward action=accept src-address-list=allowed-subnets
add chain=input action=accept src-address-list=allowed-subnets
add chain=output action=accept dst-address-list=allowed-subnets
```

## 3. Konfigurasi IP Statis di TrueNAS Scale

Masuk ke Antarmuka Web TrueNAS Scale. Tambahkan IP Statis pada Bridge:
- IP Address: 172.16.30.2/28
- Interface: vlan83

Simpan dan Terapkan Perubahan.

## 4. Membuat dan Mengonfigurasi VM dengan OS Linux

### 4.1. Membuat VM di TrueNAS Scale

Konfigurasi VM:
- CPU: 4 vCPU
- RAM: 8 GB
- HDD: Virtio 50 GB
- IP: 172.16.30.3/28

Instal Debian pada VM:
- Konfigurasi jaringan:
  - IP Statis: 172.16.30.3
  - Gateway: 172.16.30.1
  - DNS: 8.8.8.8

## 5. Konfigurasi di VM

Aktifkan IP Forwarding:
```bash
echo 1 > /proc/sys/net/ipv4/ip_forward
```

Jadikan IP Forwarding Permanen:
```bash
sudo nano /etc/sysctl.conf
net.ipv4.ip_forward = 1
sudo sysctl -p
```

## 6. Konfigurasi Jaringan Docker

Edit File `/etc/docker/daemon.json`:
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

## 7. Konfigurasi Macvlan di Docker

### 7.1. Membuat Interface Macvlan Secara Manual

Buat Macvlan:
```bash
sudo ip link add macvlan0 link ens3 type macvlan mode bridge
```

Berikan IP:
```bash
sudo ip addr add 172.16.30.14/28 dev macvlan0
```

Aktifkan Interface:
```bash
sudo ip link set macvlan0 up
```

### 7.2. Membuat Jaringan Macvlan di Docker

Buat Jaringan:
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

## 8. Backup Konfigurasi MikroTik

Backup Konfigurasi MikroTik:
```bash
/export file=mikrotik-config-backup
```

## 9. Catatan Tambahan

Gunakan tcpdump untuk memonitor trafik:
```bash
sudo tcpdump -i macvlan0
```
Pastikan setiap subnet dapat berkomunikasi dengan baik.

## 10. Referensi IP dalam Subnet

| IP Address     | Deskripsi              |
|----------------|------------------------|
| 172.16.30.1    | Gateway                |
| 172.16.30.2    | TrueNAS                |
| 172.16.30.3    | Host VM                |
| 172.16.30.8    | Kontainer (stream-server)|
| 172.16.30.14   | IP Macvlan pada Host Docker|

Dokumentasi ini dirancang untuk mempermudah pengaturan jaringan kompleks. Pastikan setiap langkah diikuti dengan hati-hati untuk menghindari konflik konfigurasi.