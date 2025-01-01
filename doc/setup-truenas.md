# Panduan Lengkap Otomatisasi TrueNAS Scale dengan Bash

Skrip ini menggunakan curl untuk berinteraksi dengan API TrueNAS Scale. Pastikan Anda memiliki akses API dan token API TrueNAS. Ganti API_TOKEN, API_URL, dan parameter lain yang sesuai.

## Langkah 1: Konfigurasi API Token

Ganti API_TOKEN dengan token API TrueNAS Anda, dan API_URL dengan URL server TrueNAS Anda.

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

## Langkah 2: Hapus Pool Lama dan Buat Pool Baru

```bash
# Hapus pool lama
POOL_NAME="Data"
POOL_ID=$(api_request "pool" "GET" | jq -r ".[] | select(.name==\"$POOL_NAME\").id")
if [ -n "$POOL_ID" ]; then
    api_request "pool/id/$POOL_ID" "DELETE"
    echo "Pool $POOL_NAME dihapus."
fi

# Buat pool baru
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

## Langkah 3: Buat Dataset

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

## Langkah 4: Konfigurasi Jaringan VLAN dan Bridge

```bash
# Buat VLAN 83
api_request "network/vlan" "POST" '{
  "name": "vlan83",
  "tag": 83,
  "parent_interface": "enp5s0"
}'
echo "VLAN 83 dibuat."

# Buat Bridge br0
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

## Langkah 5: Buat VM

```bash
# Unduh ISO Debian
wget -O /mnt/Data/VMs/debian.iso "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.8.0-amd64-netinst.iso"

# Buat VM
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

## Langkah 6: Instalasi Otomatis VM

Buat konfigurasi pra-pengaturan untuk instalasi Debian minimal dengan SSH, lalu tambahkan perintah untuk menyalakan VM dan menyelesaikan instalasi otomatis.

Skrip di atas adalah kerangka utama untuk otomatisasi TrueNAS Scale dengan bash. Pastikan perangkat dan konfigurasi sesuai dengan lingkungan Anda. Jika Anda membutuhkan penyesuaian lebih lanjut, beri tahu saya.