#!/bin/bash
set -e

# Buat folder log dan sementara untuk Nginx
mkdir -p /app/streamserver/temp/client_body_temp
mkdir -p /app/streamserver/temp/proxy_temp
mkdir -p /app/streamserver/temp/fastcgi_temp
mkdir -p /app/streamserver/temp/scgi_temp
mkdir -p /app/streamserver/temp/uwsgi_temp
mkdir -p /app/streamserver/temp/stream
mkdir -p /app/streamserver/logs

chmod -R 777 /app/streamserver/temp
chmod -R 777 /app/streamserver/logs

echo "Direktori sementara dan log untuk Nginx berhasil dibuat."

# Baca kredensial dari environment
source /app/streamserver/config/credentials.sh
export RTSP_IP=$(echo $RTSP_IP | base64 -d)
export RTSP_USER=$(echo $RTSP_USER_BASE64 | base64 -d)
export RTSP_PASSWORD=$(echo $RTSP_PASSWORD_BASE64 | base64 -d)

# Buat Folder dan File
if [ ! -d /mnt/Data/Syslog/cctv ]; then
    mkdir -p /mnt/Data/Syslog/cctv
fi

if [ ! -f /mnt/Data/Syslog/cctv/cctv_status.log ]; then
    touch /mnt/Data/Syslog/cctv/cctv_status.log
fi

if [ ! -f ./scripts/__init__.py ]; then
    touch ./scripts/__init__.py
fi

chmod -R 755 /mnt/Data/Syslog
chmod -R 755 ./scripts

# Fungsi untuk validasi RTSP Stream
validate_and_log() {
    local channel=$1
    echo "Memulai validasi RTSP untuk channel ${channel}..."
    python /app/streamserver/scripts/validate_cctv.py \
      "rtsp://${RTSP_USER}:${RTSP_PASSWORD}@${RTSP_IP}:554/cam/realmonitor?channel=${channel}&subtype=1" \
      "${channel}"
    if [ $? -eq 0 ]; then
        echo "Channel ${channel}: Validasi berhasil." >> /mnt/Data/Syslog/cctv/cctv_status.log
    else
        echo "Channel ${channel}: Validasi gagal." >> /mnt/Data/Syslog/cctv/cctv_status.log
    fi
}

# Loop untuk memvalidasi semua channel
for channel in {1..32}; do
    validate_and_log $channel
done

# Jalankan Nginx sebagai proses utama
exec "$@"