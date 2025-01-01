#!/bin/bash
set -e

###############################################################################
# 0. Periksa Dependency (sgdisk atau parted)
###############################################################################
PARTITION_TOOL=""
if command -v sgdisk >/dev/null 2>&1; then
    PARTITION_TOOL="sgdisk"
elif command -v parted >/dev/null 2>&1; then
    PARTITION_TOOL="parted"
else
    echo "[ERROR] Tidak ditemukan 'sgdisk' atau 'parted'. Install untuk melanjutkan."
    exit 1
fi

###############################################################################
# Fungsi Bantuan
###############################################################################
info()  { echo -e "\e[32m[INFO]\e[0m $1"; }
error() { echo -e "\e[31m[ERROR]\e[0m $1"; exit 1; }

###############################################################################
# 1. Baca config.json
###############################################################################
CONFIG=$(cat config.json 2>/dev/null) || error "Gagal membaca config.json"
API_TOKEN=$(echo "$CONFIG" | jq -r '.api_token')
API_URL=$(echo "$CONFIG" | jq -r '.api_url')
POOL_NAME=$(echo "$CONFIG" | jq -r '.pool.name')
DISKS=($(echo "$CONFIG" | jq -r '.pool.disks[]'))

###############################################################################
# 2. Fungsi API + Polling Job
###############################################################################
api_request() {
    local endpoint="$1"
    local method="$2"
    local data="$3"
    local max_retries=5
    local retry_delay=5

    for ((i=1; i<=max_retries; i++)); do
        local resp
        resp=$(curl -s -k -X "$method" \
            -H "Authorization: Bearer $API_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$API_URL/$endpoint")

        # Cek apakah JSON valid
        if echo "$resp" | jq . >/dev/null 2>&1; then
            echo "$resp"
            return
        else
            info "Respons tidak valid JSON dari $endpoint (percobaan $i/$max_retries): $resp"
            [ "$i" -lt "$max_retries" ] && sleep "$retry_delay"
        fi
    done

    error "Respons API invalid setelah $max_retries percobaan."
}

wait_for_job() {
    local job_id="$1"
    local max_tries=10
    local delay=5
    for ((attempt=1; attempt<=max_tries; attempt++)); do
        local job_resp
        job_resp=$(api_request "core/get_jobs?id=$job_id" "GET" "")
        local state
        state=$(echo "$job_resp" | jq -r '.[0].state // ""')
        if [ "$state" = "SUCCESS" ]; then
            info "Job $job_id sukses."
            return 0
        elif [ "$state" = "FAILED" ]; then
            error "Job $job_id gagal."
        fi
        info "Menunggu job $job_id (percobaan $attempt/$max_tries)..."
        sleep "$delay"
    done
    error "Job $job_id tidak selesai setelah $max_tries percobaan."
}

###############################################################################
# 3. Hapus Pool Lama + Partisi
###############################################################################
info "Menghapus pool lama (jika ada): $POOL_NAME"
zpool destroy "$POOL_NAME" 2>/dev/null || true
sleep 3

info "Menghapus leftover partisi dengan $PARTITION_TOOL..."
for disk in "${DISKS[@]}"; do
    [[ "$disk" != /dev/* ]] && disk="/dev/$disk"
    info "Membersihkan label disk $disk"

    if [ "$PARTITION_TOOL" = "sgdisk" ]; then
        sgdisk --zap-all "$disk" || true
    else
        # parted approach
        parted -s "$disk" mklabel gpt || true
    fi

    # Hapus 10MB awal
    dd if=/dev/zero of="$disk" bs=1M count=10 conv=notrunc oflag=direct || true
    sync
done
sleep 5

###############################################################################
# 4. Buat Pool Baru (Job)
###############################################################################
info "Membuat pool $POOL_NAME..."
POOL_CONFIG=$(echo "$CONFIG" | jq -c '{
  "name": .pool.name,
  "topology": {
    "data": [
      {"type": "STRIPE", "disks": .pool.disks}
    ]
  }
}')

POOL_RESP=$(api_request "pool" "POST" "$POOL_CONFIG")

# Ada kalanya API mengembalikan literal numerik, jadi tangani kedua kasus:
if [[ "$POOL_RESP" =~ ^[0-9]+$ ]]; then
    # API mungkin mengembalikan langsung job_id numerik
    JOB_ID="$POOL_RESP"
else
    # API mengembalikan objek JSON
    JOB_ID=$(echo "$POOL_RESP" | jq -r '.id // empty')
fi

[ -z "$JOB_ID" ] && error "Gagal mendapatkan job_id pembuatan pool."
wait_for_job "$JOB_ID"

###############################################################################
# 5. Buat Dataset
###############################################################################
DATASETS=$(echo "$CONFIG" | jq -c '.datasets[]?')
for data_item in $DATASETS; do
    ds_resp=$(api_request "pool/dataset" "POST" "$data_item")
    if echo "$ds_resp" | jq -e '.error' >/dev/null 2>&1; then
        error "Gagal membuat dataset $(echo "$data_item" | jq -r '.name')"
    fi
    info "Dataset $(echo "$data_item" | jq -r '.name') dibuat."
done

###############################################################################
# 6. VLAN (Opsional)
###############################################################################
USE_VLAN=$(echo "$CONFIG" | jq -r '.network.use_vlan // false')
if [ "$USE_VLAN" = "true" ]; then
    VLAN_CONFIG=$(echo "$CONFIG" | jq -c '.network.vlan')
    VLAN_NAME=$(echo "$VLAN_CONFIG" | jq -r '.name')
    exist_vlan=$(api_request "network/vlan" "GET")
    old_vlan_id=$(echo "$exist_vlan" | jq -r ".[] | select(.name==\"$VLAN_NAME\").id")
    if [ -n "$old_vlan_id" ] && [ "$old_vlan_id" != "null" ]; then
        info "Menghapus VLAN $VLAN_NAME (ID: $old_vlan_id)..."
        api_request "network/vlan/id/$old_vlan_id" "DELETE" ""
        sleep 3
    fi
    info "Membuat VLAN $VLAN_NAME..."
    api_request "network/vlan" "POST" "$VLAN_CONFIG"
fi

###############################################################################
# 7. Bridge
###############################################################################
BRIDGE_CONFIG=$(echo "$CONFIG" | jq -c '.network.bridge')
BRIDGE_NAME=$(echo "$BRIDGE_CONFIG" | jq -r '.name')
old_bridge_id=$(api_request "network/interface" "GET" | jq -r ".[] | select(.name==\"$BRIDGE_NAME\").id")
if [ -n "$old_bridge_id" ] && [ "$old_bridge_id" != "null" ]; then
    info "Menghapus bridge $BRIDGE_NAME (ID: $old_bridge_id)..."
    api_request "network/interface/id/$old_bridge_id" "DELETE" ""
    sleep 3
fi
info "Membuat bridge $BRIDGE_NAME..."
api_request "network/interface" "POST" "$BRIDGE_CONFIG"

###############################################################################
# 8. Download ISO Debian (jika perlu)
###############################################################################
VM_CONFIG=$(echo "$CONFIG" | jq -c '.vm')
ISO_PATH=$(echo "$VM_CONFIG" | jq -r '.iso_path')
ISO_URL="https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.8.0-amd64-netinst.iso"
if [ ! -f "$ISO_PATH" ]; then
    info "Mengunduh ISO Debian..."
    mkdir -p "$(dirname "$ISO_PATH")"
    wget -q -O "$ISO_PATH" "$ISO_URL" || error "Gagal mengunduh ISO"
fi

###############################################################################
# 9. Persiapan Payload VM + Pembuatan
###############################################################################
info "Menyiapkan VM..."
VM_DISK=$(echo "$VM_CONFIG" | jq -c '{
  "dtype": "DISK",
  "attributes": {
    "path": .disk_path,
    "type": "VIRTIO",
    "size": .disk_size
  }
}')
VM_NIC=$(echo "$VM_CONFIG" | jq -c '{
  "dtype": "NIC",
  "attributes": {
    "type": "VIRTIO",
    "nic_attach": .nic_attach
  }
}')
VM_CDROM=$(echo "$VM_CONFIG" | jq -c '{
  "dtype": "CDROM",
  "attributes": {
    "path": .iso_path
  }
}')

VM_DEVICES=$(
  jq -n --argjson disk "$VM_DISK" \
        --argjson nic "$VM_NIC" \
        --argjson cdrom "$VM_CDROM" \
  '[$disk, $nic, $cdrom]'
)
VM_PAYLOAD=$(echo "$VM_CONFIG" | jq -c --argjson devices "$VM_DEVICES" '. + {devices: $devices}')

VM_NAME=$(echo "$VM_CONFIG" | jq -r '.name')
info "Membuat VM $VM_NAME..."
VM_RESP=$(api_request "vm" "POST" "$VM_PAYLOAD")
if echo "$VM_RESP" | jq -e '.error' >/dev/null 2>&1; then
    error "Gagal membuat VM $VM_NAME"
fi
info "VM $VM_NAME berhasil dibuat."

info "Proses otomasi selesai. Silakan periksa GUI TrueNAS Scale."