# Dokumentasi Pengaturan Macvlan di Docker

## 1. Apa Itu Macvlan?
Macvlan memungkinkan kontainer Docker untuk mendapatkan IP langsung dari subnet jaringan fisik Anda. Dengan Macvlan, setiap kontainer bertindak seolah-olah seperti perangkat fisik di jaringan, dengan IP unik yang diberikan.

## 2. Kebutuhan Awal
Sebelum mulai, pastikan:

- Anda memiliki akses ke jaringan fisik dengan informasi berikut:
    - Subnet: `172.16.30.0/28`
    - Gateway: `172.16.30.1`
    - Host Docker: `172.16.30.3`
    - IP untuk Macvlan pada Host: `172.16.30.14`
- Docker sudah terinstal di sistem Anda.

## 3. Membuat Macvlan Network

### 3.1. Buat Macvlan Secara Manual
Buat interface macvlan di host:

```bash
sudo ip link add macvlan0 link ens3 type macvlan mode bridge
```

Berikan IP pada interface:

```bash
sudo ip addr add 172.16.30.14/28 dev macvlan0
```

Aktifkan interface:

```bash
sudo ip link set macvlan0 up
```

Verifikasi interface:

```bash
ip addr show macvlan0
```

Anda akan melihat `macvlan0` dengan IP `172.16.30.14`.

### 3.2. Membuat Macvlan di Docker
Buat jaringan Macvlan di Docker:

```bash
docker network create \
        --driver macvlan \
        --subnet=172.16.30.0/28 \
        --gateway=172.16.30.1 \
        -o parent=macvlan0 macvlan_net
```

Verifikasi jaringan:

```bash
docker network ls
```

Anda akan melihat jaringan `macvlan_net` yang baru saja dibuat.

## 4. Menjalankan Kontainer di Macvlan
Jalankan kontainer dengan jaringan `macvlan_net`:

```bash
docker run -d --net=macvlan_net --ip=172.16.30.8 --name stream-server nginx
```

Verifikasi kontainer:

```bash
docker ps
```

Pastikan kontainer `stream-server` sedang berjalan.

Cek IP kontainer:

```bash
docker inspect stream-server | grep IPAddress
```

## 5. Pengujian
Ping dari Host ke Kontainer: Pastikan Anda menggunakan interface `macvlan0`:

```bash
ping -I macvlan0 172.16.30.8
```

Ping dari Kontainer ke Gateway: Masuk ke dalam kontainer dan uji konektivitas ke gateway:

```bash
docker exec -it stream-server /bin/bash
ping 172.16.30.1
```

Akses Layanan Kontainer: Jika kontainer menjalankan layanan seperti HTTP, coba akses IP kontainer:

```bash
curl http://172.16.30.8
```

## 6. Konfigurasi Permanen
Agar pengaturan tetap ada setelah reboot, ikuti langkah berikut:

### 6.1. Konfigurasi Macvlan di File Jaringan
Edit file `/etc/network/interfaces` dan tambahkan konfigurasi berikut:

```plaintext
# Macvlan network interface
auto macvlan0
iface macvlan0 inet static
        address 172.16.30.14/28
        pre-up ip link add macvlan0 link ens3 type macvlan mode bridge
        post-down ip link del macvlan0
```

Restart jaringan:

```bash
sudo systemctl restart networking
```

### 6.2. Konfigurasi Jaringan Docker
Tambahkan konfigurasi berikut ke file `/etc/docker/daemon.json`:

```json
{
        "default-address-pools": [
                {
                        "base": "172.16.30.0/16",
                        "size": 28
                }
        ]
}
```

Restart Docker:

```bash
sudo systemctl restart docker
```

## 7. Troubleshooting

### 7.1. Masalah Koneksi
- Pastikan IP kontainer unik dan tidak konflik dengan perangkat lain di subnet.
- Gunakan `tcpdump` untuk memeriksa lalu lintas di `macvlan0`:

```bash
sudo tcpdump -i macvlan0
```

### 7.2. Masalah Firewall
Pastikan firewall tidak memblokir subnet `172.16.30.0/28` atau protokol ICMP (ping):

```bash
sudo iptables -L -v -n
```

## 8. Referensi IP dalam Subnet
Dalam subnet `172.16.30.0/28`, IP yang tersedia adalah:

- `172.16.30.1`: Gateway
- `172.16.30.2`: Perangkat lain (misalnya, NAS)
- `172.16.30.3`: Host Docker
- `172.16.30.8`: Kontainer 1
- `172.16.30.14`: IP Macvlan pada Host