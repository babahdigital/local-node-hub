#!/bin/bash
set -e

# === Variabel Utama ===
LOG_BASE_PATH="/mnt/Data/Syslog/rtsp"
NGINX_LOG_PATH="${LOG_BASE_PATH}/nginx"
CCTV_LOG_PATH="/mnt/Data/Syslog/cctv"
HLS_PATH="/app/streamserver/hls"
ENV_FILE="/app/streamserver/.env" # Lokasi file .env

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
    chown -R nobody:nobody "$HLS_PATH"

    local log_files=(
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

secure_env_file() {
    if [ -f "$ENV_FILE" ]; then
        log_info "Mengamankan file .env dengan chmod 600..."
        chmod 600 "$ENV_FILE"
    else
        log_error "File .env tidak ditemukan di $ENV_FILE!"
    fi
}

decode_credentials() {
    log_info "Mendekode kredensial RTSP dari environment..."
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
        echo "$(date '+%d-%m-%Y %H:%M:%S') - Channel ${channel}: Validasi berhasil." >> "$CCTV_LOG_PATH/cctv_status.log"
    else
        echo "$(date '+%d-%m-%Y %H:%M:%S') - Channel ${channel}: Validasi gagal." >> "$CCTV_LOG_PATH/cctv_status.log"
    fi
}

validate_all_channels() {
    local total_channels=${CHANNELS:-1}
    log_info "Memulai validasi RTSP untuk semua channel (1..$total_channels)..."
    for (( ch=1; ch<=$total_channels; ch++ )); do
        validate_and_log "$ch"
    done
    log_info "Validasi RTSP selesai. Cek log di $CCTV_LOG_PATH/cctv_status.log."
}

# === MAIN ENTRYPOINT ===
setup_directories
secure_env_file
decode_credentials
cleanup_hls

# Jalankan validasi jika diaktifkan
ENABLE_RTSP_VALIDATION=${ENABLE_RTSP_VALIDATION:-true}
if [ "$ENABLE_RTSP_VALIDATION" = "true" ]; then
    validate_all_channels
else
    log_info "RTSP validation dimatikan. Melewati proses validasi..."
fi

log_info "Menjalankan Nginx sebagai proses utama..."
exec "$@"