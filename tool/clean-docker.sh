#!/bin/bash

# Pastikan script dijalankan sebagai root
if [ "$(id -u)" -ne 0 ]; then
    echo "Script ini harus dijalankan sebagai root!"
    exit 1
fi

echo "===> [1/9] Mematikan container yang masih berjalan..."
docker ps -q | xargs -r docker kill

echo "===> [2/9] Menghapus semua container..."
docker ps -aq | xargs -r docker rm -f

echo "===> [3/9] Menghapus semua images..."
docker images -aq | xargs -r docker rmi -f

echo "===> [4/9] Menghapus semua network (kecuali default)..."
# Hati-hati, jika Anda menghapus bridge/host/networks bawaan Docker, bisa bermasalah.
# Biasanya cukup jalankan prune saja:
docker network prune -f

echo "===> [5/9] Menghapus semua volume..."
# Cara agresif: hapus semua volume yang terdaftar
docker volume ls -q | xargs -r docker volume rm -f

echo "===> [6/9] Membersihkan builder cache..."
docker builder prune -f

echo "===> [7/9] Membersihkan Swarm (jika aktif)..."
# Jika node ini manager dan dalam keadaan swarm aktif, pakai --force
docker swarm leave --force 2>/dev/null || true

echo "===> [8/9] Menjalankan Docker System Prune umum..."
# Akan menghapus apapun yang masih tersisa, termasuk unused volume, image, dsb.
docker system prune -a -f --volumes

echo "===> [9/9] Selesai membersihkan Docker."