#!/bin/bash
set -e

# Baca kredensial dari environment
source /app/config/credentials.sh
export RTSP_IP=$(echo $RTSP_IP | base64 -d)
export RTSP_USER=$(echo $RTSP_USER_BASE64 | base64 -d)
export RTSP_PASSWORD=$(echo $RTSP_PASSWORD_BASE64 | base64 -d)

# Validasi RTSP Stream
validate_and_log() {
    python /app/validate_stream.py "rtsp://${RTSP_USER}:${RTSP_PASSWORD}@${RTSP_IP}:554/cam/realmonitor?channel=$1&subtype=1" $1
}

# Deteksi channel dan validasi
for channel in {1..32}; do
    validate_and_log $channel
done

# Jalankan Nginx
exec "$@"