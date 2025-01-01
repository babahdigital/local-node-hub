# Panduan Lengkap Otomatisasi TrueNAS Scale dengan Bash

Panduan ini menggunakan skrip Bash dan curl untuk berinteraksi dengan API TrueNAS Scale. Pastikan Anda memiliki akses API dan token API TrueNAS. Ganti API_TOKEN, API_URL, dan parameter lain yang sesuai dengan lingkungan Anda.

## Langkah 1: Membuat API Token di TrueNAS Scale

1. **Login ke TrueNAS Scale Web Interface:**
    - Masukkan IP address TrueNAS Scale Anda di browser.
    - Login dengan kredensial admin Anda.

2. **Navigasi ke API Keys:**
    - Klik pada menu "Credentials" di sidebar.
    - Pilih "API Keys".

3. **Buat API Key:**
    - Klik tombol "Add" atau "+" untuk membuat API Key baru.
    - Beri nama API Key Anda untuk identifikasi, misalnya, AutomationKey.
    - Klik "Save". TrueNAS akan menampilkan token API Anda.

4. **Simpan API Key:**
    - Salin token API tersebut. Pastikan Anda menyimpannya di tempat aman, karena token ini hanya akan ditampilkan sekali.
    - Gunakan token ini pada variabel API_TOKEN dalam skrip bash Anda.

## Langkah 2: Mengaktifkan API di TrueNAS (Opsional)

API biasanya sudah diaktifkan secara default di TrueNAS Scale. Namun, Anda dapat memeriksa atau mengaktifkannya dengan langkah berikut:

1. **Periksa Konfigurasi API:**
    - Masuk ke menu "System Settings".
    - Pilih "Advanced".
    - Pastikan "API Key authentication" diaktifkan.

2. **Cek Dokumentasi API TrueNAS:**
    - Akses dokumentasi bawaan API TrueNAS dengan mengunjungi URL:
      ```
      https://<your_truenas_ip>/api/docs/
      ```
    - Di sini Anda dapat melihat endpoint, metode HTTP, dan parameter yang didukung.

## Langkah 3: Skrip Bash Dasar

### Skrip Utama: `truenas_automation.sh`

Buat file Bash dan masukkan kode berikut:

```bash
#!/bin/bash

API_TOKEN="your_api_token_here"
API_URL="https://your_truenas_url_here/api/v2.0"

# Fungsi untuk membuat permintaan API
api_request() {
    local endpoint=$1
    local method=$2
    local data=$3
    curl -s -k -X $method \
        -H "Authorization: Bearer $API_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$data" \
        "$API_URL/$endpoint"
}
```

### Cara Menjalankan Skrip

1. Simpan skrip dengan nama `truenas_automation.sh`.
2. Beri izin eksekusi:
    ```bash
    chmod +x truenas_automation.sh
    ```
3. Jalankan skrip:
    ```bash
    ./truenas_automation.sh
    ```

## Langkah 4: Hapus Pool Lama dan Buat Pool Baru

Tambahkan ke dalam skrip:

```bash
POOL_NAME="Data"
POOL_ID=$(api_request "pool" "GET" | jq -r ".[] | select(.name==\"$POOL_NAME\").id")
if [ -n "$POOL_ID" ]; then
    api_request "pool/id/$POOL_ID" "DELETE"
    echo "Pool $POOL_NAME dihapus."
fi

api_request "pool" "POST" '{
  "name": "Data",
  "topology": {
    "data": [
      {
        "type": "STRIPE",
        "disks": ["da1", "da2"]
      }
    ]
  },
  "compression": "GZIP-9",
  "sync": "STANDARD"
}'
echo "Pool Data dibuat dengan konfigurasi STRIPE dan GZIP-9."
```

## Langkah 5: Buat Dataset

Tambahkan dataset sesuai kebutuhan:

```bash
# Dataset Backup
api_request "pool/dataset" "POST" '{
  "name": "Data/Backup",
  "compression": "OFF",
  "sync": "DISABLED"
}'
echo "Dataset Backup dibuat."

# Dataset Syslog
api_request "pool/dataset" "POST" '{
  "name": "Data/Syslog",
  "compression": "OFF",
  "sync": "STANDARD"
}'
echo "Dataset Syslog dibuat."

# Dataset VMs
api_request "pool/dataset" "POST" '{
  "name": "Data/VMs",
  "compression": "LZ4",
  "sync": "STANDARD"
}'
echo "Dataset VMs dibuat."
```

## Langkah 6: Konfigurasi Jaringan VLAN dan Bridge

Tambahkan konfigurasi jaringan berikut:

```bash
# Buat VLAN
api_request "network/vlan" "POST" '{
  "name": "vlan83",
  "tag": 83,
  "parent_interface": "enp5s0"
}'
echo "VLAN 83 dibuat."

# Buat Bridge
api_request "network/interface" "POST" '{
  "name": "br0",
  "type": "BRIDGE",
  "bridge_members": ["vlan83"]
}'
echo "Bridge br0 dibuat."

# Set IP Address untuk br0
api_request "network/configuration" "PUT" '{
  "interfaces": [
    {
      "name": "br0",
      "ipv4_dhcp": false,
      "ipv4_addresses": ["172.16.30.2/28"]
    }
  ]
}'
echo "IP 172.16.30.2/28 diset pada br0."
```

## Langkah 7: Buat VM dengan Instalasi Otomatis

### Unduh ISO Debian

```bash
wget -O /mnt/Data/VMs/debian.iso "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.8.0-amd64-netinst.iso"
```

### Buat VM

```bash
api_request "vm" "POST" '{
  "name": "DebianVM",
  "description": "VM Debian untuk testing",
  "vcpus": 2,
  "memory": 2048,
  "bootloader": "UEFI",
  "devices": [
    {
      "dtype": "DISK",
      "attributes": {
        "path": "/mnt/Data/VMs/debian.img",
        "type": "VIRTIO",
        "size": 50
      }
    },
    {
      "dtype": "NIC",
      "attributes": {
        "type": "VIRTIO",
        "nic_attach": "br0"
      }
    },
    {
      "dtype": "CDROM",
      "attributes": {
        "path": "/mnt/Data/VMs/debian.iso"
      }
    }
  ]
}'
echo "VM Debian dibuat."
```

## Langkah 8: Instalasi Otomatis VM dengan Preseed

### Buat File Preseed

Buat file `preseed.cfg` dengan konfigurasi otomatis Debian.

### Host File Preseed

Host file ini menggunakan server HTTP:

```bash
python3 -m http.server 8000 --directory /mnt/Data/VMs/
```

### Integrasikan ke ISO atau Boot Parameter

Tambahkan parameter preseed:

```bash
auto=true priority=critical url=http://<truenas_ip>:8000/preseed.cfg
```

### Jalankan VM

```bash
VM_ID=$(api_request "vm" "GET" | jq -r '.[] | select(.name=="DebianVM").id')
api_request "vm/id/$VM_ID/start" "POST"
echo "VM Debian dinyalakan."
```

Dengan skrip ini, semua langkah mulai dari konfigurasi TrueNAS Scale hingga pembuatan dan instalasi VM Debian bisa diotomatisasi sepenuhnya. Jika ada bagian yang masih perlu penyesuaian, beri tahu saya!