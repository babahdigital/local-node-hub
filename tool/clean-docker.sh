#!/bin/bash

# Pastikan script dijalankan sebagai root
if [ "$(id -u)" -ne 0 ]; then
    echo "Script ini harus dijalankan sebagai root!"
    exit 1
fi

echo "===> Menghentikan semua container..."
docker ps -q | xargs -r docker stop

echo "===> Menghapus semua container..."
docker ps -a -q | xargs -r docker rm

echo "===> Menghapus semua images..."
docker images -q | xargs -r docker rmi -f

echo "===> Membersihkan semua volume yang tidak digunakan..."
docker volume prune -f

echo "===> Membersihkan semua network yang tidak digunakan..."
docker network prune -f

echo "===> Membersihkan builder cache..."
docker builder prune -f

echo "===> Membersihkan sistem Docker (container, images, volumes, networks)..."
docker system prune -a -f --volumes

echo "Pembersihan Docker selesai."