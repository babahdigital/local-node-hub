#!/bin/bash
set -e

# === Variabel Utama ===
LOG_BASE_PATH="/mnt/Data/Syslog/rtsp"
NGINX_LOG_PATH="${LOG_BASE_PATH}/nginx"
#NGINX_LOG_PATH="/app/streamserver/nginx_logs"
STREAM_LOG_PATH="${LOG_BASE_PATH}/stream"
CCTV_LOG_PATH="/mnt/Data/Syslog/cctv"
HLS_PATH="/app/streamserver/hls"

# Fungsi Logging
log_info() {
    echo "$(date '+%d-%m-%Y %H:%M:%S') [INFO] $1"
}

log_error() {
    echo "$(date '+%d-%m-%Y %H:%M:%S') [ERROR] $1"
}

setup_directories() {
    local dirs=(
        "$NGINX_LOG_PATH"
        "$STREAM_LOG_PATH"
        "$CCTV_LOG_PATH"
        "$HLS_PATH"
    )
    log_info "Membuat direktori log dan direktori sementara..."
    for d in "${dirs[@]}"; do
        mkdir -p "$d"
    done

    chmod -R 777 "$LOG_BASE_PATH"
    chmod -R 777 "$NGINX_LOG_PATH"
    chmod -R 777 "$HLS_PATH"
    #chown -R nobody:nobody "$NGINX_LOG_PATH"
    chown -R nobody:nobody "$HLS_PATH"

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

decode_credentials() {
    log_info "Mendekode kredensial RTSP dari environment..."
    export RTSP_IP=$(echo "$RTSP_IP" | base64 -d)
    export RTSP_USER=$(echo "$RTSP_USER_BASE64" | base64 -d)
    export RTSP_PASSWORD=$(echo "$RTSP_PASSWORD_BASE64" | base64 -d)
}

cleanup_hls() {
    log_info "Membersihkan direktori HLS..."
    if [ -d "$HLS_PATH" ]; then
        rm -rf "${HLS_PATH:?}/"*
    fi
    mkdir -p "$HLS_PATH"
    chmod -R 777 "$HLS_PATH"
}

validate_and_log() {
    local channel=$1
    local rtsp_url="rtsp://${RTSP_USER}:${RTSP_PASSWORD}@${RTSP_IP}:554/cam/realmonitor?channel=${channel}&subtype=1"

    log_info "Memulai validasi RTSP untuk channel ${channel}..."

    set +e
    /app/streamserver/venv/bin/python /app/streamserver/scripts/validate_cctv.py "$rtsp_url" "$channel"
    RETVAL=$?
    set -e

    if [ $RETVAL -eq 0 ]; then
        echo "$(date '+%d-%m-%Y %H:%M:%S') - Channel ${channel}: Validasi berhasil." >> "$STREAM_LOG_PATH/rtsp_validation.log"
    else
        echo "$(date '+%d-%m-%Y %H:%M:%S') - Channel ${channel}: Validasi gagal." >> "$STREAM_LOG_PATH/rtsp_validation.log"
    fi
}

validate_all_channels() {
    local total_channels=${CHANNELS:-1}
    log_info "Memulai validasi RTSP untuk semua channel (1..$total_channels)..."
    for (( ch=1; ch<=$total_channels; ch++ )); do
        validate_and_log "$ch"
    done
    log_info "Validasi RTSP selesai. Cek log di $STREAM_LOG_PATH/rtsp_validation.log."
}

send_dummy_stream() {
    log_info "Mengirimkan stream dummy ke RTMP server untuk testing..."
    ffmpeg -re -f lavfi -i testsrc=duration=60:size=800x600:rate=30 -f flv rtmp://localhost:1935/live/test &
}

# === MAIN ENTRYPOINT ===
setup_directories
decode_credentials
cleanup_hls

# Tambahkan ENV untuk mengatur validasi
ENABLE_RTSP_VALIDATION=${ENABLE_RTSP_VALIDATION:-true}
if [ "$ENABLE_RTSP_VALIDATION" = "true" ]; then
    validate_all_channels
else
    log_info "RTSP validation dimatikan. Melewati proses validasi..."
fi

if [ "$ENABLE_TEST_STREAM" == "true" ]; then
    send_dummy_stream
fi

log_info "Menjalankan Nginx sebagai proses utama..."
exec "$@"