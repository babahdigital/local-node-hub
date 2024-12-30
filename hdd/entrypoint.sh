#!/bin/bash
set -e

# Pastikan direktori dan file log tersedia
LOG_DIR="/mnt/Data/Syslog/hdd"
LOG_FILE="$LOG_DIR/hdd_monitor.log"

if [ ! -d "$LOG_DIR" ]; then
    echo "Membuat direktori log: $LOG_DIR"
    mkdir -p "$LOG_DIR"
fi

if [ ! -f "$LOG_FILE" ]; then
    echo "Membuat file log: $LOG_FILE"
    touch "$LOG_FILE"
fi

# Jalankan aplikasi utama
exec gunicorn --bind 0.0.0.0:5000 hdd_monitor:app