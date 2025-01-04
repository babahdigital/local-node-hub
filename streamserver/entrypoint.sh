#!/bin/bash
set -e

# === Variabel Utama ===
LOG_BASE_PATH="/mnt/Data/Syslog/rtsp"
NGINX_LOG_PATH="${LOG_BASE_PATH}/nginx"
STREAM_LOG_PATH="${LOG_BASE_PATH}/stream"
CCTV_LOG_PATH="/mnt/Data/Syslog/cctv"
TEMP_PATH="/app/streamserver/temp"
HLS_PATH="${STREAM_LOG_PATH}/hls"

# === Fungsi Logging Sederhana ===
log_info() {
    echo "$(date '+%d-%m-%Y %H:%M:%S') [INFO] $1"
}

log_error() {
    echo "$(date '+%d-%m-%Y %H:%M:%S') [ERROR] $1"
}

# === Fungsi Setup Direktori dan File Log ===
setup_directories() {
    local dirs=(
        "$NGINX_LOG_PATH"
        "$STREAM_LOG_PATH"
        "$CCTV_LOG_PATH"
        "${TEMP_PATH}/client_body_temp"
        "${TEMP_PATH}/proxy_temp"
        "${TEMP_PATH}/fastcgi_temp"
        "${TEMP_PATH}/scgi_temp"
        "${TEMP_PATH}/uwsgi_temp"
        "${TEMP_PATH}/stream"
    )

    # Membuat direktori yang diperlukan
    log_info "Membuat direktori log dan direktori sementara..."
    for d in "${dirs[@]}"; do
        mkdir -p "$d"
    done

    chmod -R 777 "$LOG_BASE_PATH"
    chmod -R 777 "$TEMP_PATH"

    # Pastikan file log utama tersedia
    local log_files=(
        "$STREAM_LOG_PATH/rtsp_validation.log"
        "$CCTV_LOG_PATH/cctv_status.log"
    )
    for log_file in "${log_files[@]}"; do
        if [ ! -f "$log_file" ]; then
            touch "$log_file"
            chmod 666 "$log_file"
        fi
    done

    log_info "Direktori log dan file log berhasil disiapkan."
}

# === Fungsi Dekode Kredensial RTSP ===
decode_credentials() {
    log_info "Mendekode kredensial RTSP dari environment..."
    export RTSP_IP=$(echo "$RTSP_IP" | base64 -d)
    export RTSP_USER=$(echo "$RTSP_USER_BASE64" | base64 -d)
    export RTSP_PASSWORD=$(echo "$RTSP_PASSWORD_BASE64" | base64 -d)
}

# === Fungsi Bersihkan Direktori HLS ===
cleanup_hls() {
    log_info "Membersihkan direktori HLS..."
    if [ -d "$HLS_PATH" ]; then
        rm -rf "${HLS_PATH:?}/"*
    fi
    mkdir -p "$HLS_PATH"
    chmod -R 777 "$HLS_PATH"
}

# === Fungsi Validasi RTSP Stream ===
validate_and_log() {
    local channel=$1
    local rtsp_url="rtsp://${RTSP_USER}:${RTSP_PASSWORD}@${RTSP_IP}:554/cam/realmonitor?channel=${channel}&subtype=1"

    log_info "Memulai validasi RTSP untuk channel ${channel}..."
    /app/streamserver/venv/bin/python /app/streamserver/scripts/validate_cctv.py "$rtsp_url" "$channel"
    if [ $? -eq 0 ]; then
        echo "$(date '+%d-%m-%Y %H:%M:%S') - Channel ${channel}: Validasi berhasil." >> "$STREAM_LOG_PATH/rtsp_validation.log"
    else
        echo "$(date '+%d-%m-%Y %H:%M:%S') - Channel ${channel}: Validasi gagal." >> "$STREAM_LOG_PATH/rtsp_validation.log"
    fi
}

# === Fungsi untuk validasi semua channel (1..32) ===
validate_all_channels() {
    log_info "Memulai validasi RTSP untuk semua channel..."
    for channel in {1..32}; do
        validate_and_log "$channel"
    done
    log_info "Validasi RTSP selesai. Cek log di $STREAM_LOG_PATH/rtsp_validation.log."
}

# === Fungsi Optional: Testing Stream Dummy ===
send_dummy_stream() {
    log_info "Mengirimkan stream dummy ke RTMP server untuk testing..."
    ffmpeg -re -f lavfi -i testsrc=duration=60:size=1280x720:rate=30 -f flv rtmp://localhost:1935/live/test &
}

# === MAIN ENTRYPOINT ===
setup_directories
decode_credentials
cleanup_hls
validate_all_channels

# Jalankan stream dummy jika diinginkan
if [ "$ENABLE_TEST_STREAM" == "true" ]; then
    send_dummy_stream
fi

# Jalankan Nginx sebagai proses utama
log_info "Menjalankan Nginx sebagai proses utama..."
exec "$@"