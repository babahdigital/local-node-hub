# Konfigurasi Jaringan MikroTik, VM, dan Docker

Dokumentasi ini menjelaskan langkah-langkah lengkap untuk mengonfigurasi MikroTik, VM, dan Docker agar dapat saling berkomunikasi melalui VLAN dan routing.

---

## 1. IP Alokasi Pada Projek

| Subnet         | Deskripsi      |
|----------------|----------------|
| 172.16.10.0/24 | IP TrueNAS     |
| 172.16.30.0/28 | IP VM TrueNAS  |
| 172.16.31.0/24 | IP Container   |
| 10.5.0.0/24    | IP Docker      |

---

## 2. Konfigurasi Jaringan Docker

### 1. Menyiapkan IP Docker `docker0`

#### a. Instalasi paket json
```bash
sudo apt update
sudo apt install -y jq
```

#### b. Cek versi aplikasi
```bash
jq --version
```

### 2. Edit `/etc/docker/daemon.json`

#### a. Edit file json
```bash
nano /etc/docker/daemon.json
```

#### b. Copy paste script di bawah ini
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

### 3. Restart Docker Service
```bash
systemctl restart docker
```

### 4. Verifikasi
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

## 3. Konfigurasi Jaringan MikroTik dan Docker

### 1. Pengaturan VLAN di MikroTik

#### a. Tambahkan VLAN 83 ke interface fisik MikroTik
```bash
/interface vlan
add name=vlan83 interface=bridge1 vlan-id=83
```
> Ganti **`bridge1`** dengan nama interface fisik yang terhubung ke TrueNAS (misalnya **bridge1/ether1**).

#### b. Berikan IP pada VLAN 83
```bash
/ip address
add address=172.16.30.1/28 interface=vlan83
```

---

### 2. Buat Bridge di MikroTik

#### a. Buat bridge untuk menyatukan VLAN 83 dengan subnet lainnya
```bash
/interface bridge
add name=br-docker
```

#### b. Tambahkan VLAN 83 ke bridge
```bash
/interface bridge port
add bridge=br-docker interface=vlan83
```

#### c. Berikan IP pada bridge
```bash
/ip address
add address=172.16.30.1/28 interface=br-docker
```

---

### 3. Tambahkan Routing ke Subnet Docker

#### a. Tambahkan route untuk subnet Docker (172.16.31.0/28)
```bash
/ip route
add dst-address=172.16.31.0/28 gateway=172.16.30.2
```

---

### 4. Tambahkan Aturan Firewall

#### a. Izinkan traffic antara subnet Docker (172.16.31.0/28) dan subnet MikroTik (172.16.10.0/24)
```bash
/ip firewall filter
add chain=forward action=accept src-address=172.16.31.0/28 dst-address=172.16.10.0/24
add chain=forward action=accept src-address=172.16.10.0/24 dst-address=172.16.31.0/28
```

#### b. Izinkan traffic antara subnet Docker (172.16.31.0/28) dan host Docker (172.16.30.0/28)
```bash
/ip firewall filter
add chain=forward action=accept src-address=172.16.30.0/28 dst-address=172.16.31.0/28
add chain=forward action=accept src-address=172.16.31.0/28 dst-address=172.16.30.0/28
```

---

### 5. Tambahkan Logging untuk Traffic Antar-Subnet

#### a. Logging untuk traffic dari Docker ke MikroTik
```bash
/ip firewall filter
add chain=forward action=log src-address=172.16.31.0/28 dst-address=172.16.10.0/24 log-prefix="Docker-to-MikroTik: "
```

#### b. Logging untuk traffic dari MikroTik ke Docker
```bash
/ip firewall filter
add chain=forward action=log src-address=172.16.10.0/24 dst-address=172.16.31.0/28 log-prefix="MikroTik-to-Docker: "
```

#### c. Logging untuk traffic antara Docker dan host Docker
```bash
/ip firewall filter
add chain=forward action=log src-address=172.16.30.0/28 dst-address=172.16.31.0/28 log-prefix="Host-to-Docker: "
add chain=forward action=log src-address=172.16.31.0/28 dst-address=172.16.30.0/28 log-prefix="Docker-to-Host: "
```

---

### 6. Konfigurasi di VM

#### a. Aktifkan IP forwarding di VM (sementara)
```bash
echo 1 > /proc/sys/net/ipv4/ip_forward
```

#### b. Jadikan IP forwarding permanen

- Edit file `/etc/sysctl.conf`
```bash
net.ipv4.ip_forward = 1
```
- Terapkan perubahan
```bash
sysctl -p
```

#### c. Tambahkan route ke subnet Docker
```bash
ip route add 172.16.31.0/28 via 172.16.30.3
```

---

### 7. Coba Jalankan di Docker

#### a. Jalankan container untuk menguji koneksi
```bash
docker run -it --rm alpine ping 172.16.10.1
```

#### b. Periksa container yang berjalan
```bash
docker ps -a
```

#### c. Hapus container yang tidak diperlukan
```bash
docker rm <CONTAINER_ID_OR_NAME>
```

---

### 8. Backup Konfigurasi MikroTik

#### a. Backup konfigurasi MikroTik
```bash
/export file=mikrotik-config-backup
```
> File akan disimpan di direktori default MikroTik.

---

## Catatan Tambahan

> Pengujian Log: Periksa log untuk traffic antar-subnet di MikroTik: `/log print where message~"Docker"`
> Pastikan Semua Subnet Terhubung: Lakukan ping antar-subnet untuk memastikan semua konfigurasi berjalan dengan baik.