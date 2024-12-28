#!/bin/bash

# Konfigurasi
NFS_SERVER="172.16.30.2" # IP server NFS (TrueNAS)
CLIENT_IP="172.16.30.3"  # IP klien
SHARES=( "/mnt/Data/Syslog" "/mnt/Data/Backup" ) # Daftar share di NFS server
MOUNT_POINTS=( "/mnt/Data/Syslog" "/mnt/Data/Backup" ) # Lokasi mount di klien
FSTYPE="nfs4" # Tipe filesystem NFS

# Pastikan script dijalankan sebagai root
if [ "$(id -u)" -ne 0 ]; then
    echo "Script ini harus dijalankan sebagai root!"
    exit 1
fi

# Instal paket nfs-common jika belum terinstal
echo "Memeriksa paket nfs-common..."
if ! command -v mount.nfs &> /dev/null; then
    echo "Menginstal paket nfs-common..."
    apt-get update && apt-get install -y nfs-common
fi

# Membuat direktori mount point jika belum ada
echo "Membuat direktori mount point..."
for MOUNT_POINT in "${MOUNT_POINTS[@]}"; do
    if [ ! -d "$MOUNT_POINT" ]; then
        echo "Membuat direktori: $MOUNT_POINT"
        mkdir -p "$MOUNT_POINT"
    else
        echo "Direktori $MOUNT_POINT sudah ada."
    fi
done

# Menambahkan entri ke /etc/fstab jika belum ada
echo "Memeriksa entri di /etc/fstab..."
for i in "${!SHARES[@]}"; do
    SHARE="${SHARES[$i]}"
    MOUNT_POINT="${MOUNT_POINTS[$i]}"
    FSTAB_ENTRY="$NFS_SERVER:$SHARE $MOUNT_POINT $FSTYPE defaults,_netdev 0 0"

    if ! grep -q "$MOUNT_POINT" /etc/fstab; then
        echo "Menambahkan entri untuk $MOUNT_POINT ke /etc/fstab."
        echo "$FSTAB_ENTRY" >> /etc/fstab
    else
        echo "Entri untuk $MOUNT_POINT sudah ada di /etc/fstab."
    fi
done

# Melakukan mount semua share
echo "Melakukan mount semua share..."
mount -a

# Verifikasi hasil mount
echo "Memverifikasi mount point..."
for MOUNT_POINT in "${MOUNT_POINTS[@]}"; do
    if mountpoint -q "$MOUNT_POINT"; then
        echo "Mount berhasil untuk $MOUNT_POINT."
    else
        echo "Mount gagal untuk $MOUNT_POINT. Periksa konfigurasi dan coba lagi."
    fi
done

echo "Proses selesai."