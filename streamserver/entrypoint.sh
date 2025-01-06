#!/bin/bash
set -Eeuo pipefail

LOG_BASE_PATH="/mnt/Data/Syslog/rtsp"
NGINX_LOG_PATH="${LOG_BASE_PATH}/nginx"
CCTV_LOG_PATH="${LOG_BASE_PATH}/cctv"
HLS_PATH="/app/hls"

log_info() {
    echo "$(date '+%d-%m-%Y %H:%M:%S') [INFO] $*"
}

log_error() {
    echo "$(date '+%d-%m-%Y %H:%M:%S') [ERROR] $*" >&2
}

create_nginx_log_dir() {
    if [ ! -d "$NGINX_LOG_PATH" ]; then
        log_info "Folder $NGINX_LOG_PATH belum ada. Membuat folder..."
        mkdir -p "$NGINX_LOG_PATH" || {
            log_error "Gagal membuat folder $NGINX_LOG_PATH!"
            exit 1
        }
    fi
    [ ! -f "$NGINX_LOG_PATH/error.log" ] && touch "$NGINX_LOG_PATH/error.log"
    [ ! -f "$NGINX_LOG_PATH/access.log" ] && touch "$NGINX_LOG_PATH/access.log"
    chmod -R 750 "$NGINX_LOG_PATH"
    log_info "Folder $NGINX_LOG_PATH siap untuk log Nginx."
}

source /app/config/credentials.sh

decode_credentials() {
    log_info "Mendekode kredensial RTSP..."
    if [ -n "${RTSP_USER_BASE64:-}" ] && [ -n "${RTSP_PASSWORD_BASE64:-}" ]; then
        export RTSP_USER=$(echo "$RTSP_USER_BASE64" | base64 -d || true)
        export RTSP_PASSWORD=$(echo "$RTSP_PASSWORD_BASE64" | base64 -d || true)
        if [ -z "$RTSP_USER" ] || [ -z "$RTSP_PASSWORD" ]; then
            log_error "Kredensial RTSP gagal didekode."
            exit 1
        fi
        log_info "Kredensial RTSP berhasil didekode."
    else
        log_error "Variabel RTSP_USER_BASE64 atau RTSP_PASSWORD_BASE64 tidak diset!"
        exit 1
    fi
}

validate_environment() {
    log_info "Memvalidasi variabel lingkungan..."

    if [ -z "${RTSP_IP:-}" ]; then
        log_error "RTSP_IP tidak diset!"
        exit 1
    fi

    if [ "${TEST_CHANNEL:-off}" != "off" ]; then
        log_info "TEST_CHANNEL diatur: $TEST_CHANNEL, mengabaikan CHANNELS."
    else
        if [[ "${CHANNELS:-1}" =~ ^[0-9]+$ ]]; then
            log_info "CHANNELS diatur sebagai angka: $CHANNELS."
        else
            log_error "CHANNELS harus berupa angka (contoh: 8, 16, 32)."
            exit 1
        fi
    fi

    log_info "Semua variabel lingkungan valid."
}

cleanup_hls() {
    log_info "Membersihkan direktori HLS..."
    if [ -d "$HLS_PATH" ]; then
        rm -rf "${HLS_PATH:?}/"*
        log_info "Direktori HLS berhasil dibersihkan."
    else
        log_info "Direktori HLS tidak ditemukan. Tidak ada yang dibersihkan."
    fi
}

generate_channels() {
    if [ "${TEST_CHANNEL:-off}" != "off" ]; then
        IFS=',' read -ra channels <<< "$TEST_CHANNEL"
    else
        channels=($(seq 1 "$CHANNELS"))
    fi
    echo "${channels[@]}"
}

start_hls_stream() {
    local channel_name=$1
    local folder_name="ch${channel_name}" # Folder format ch<n>
    local rtsp_url="rtsp://${RTSP_USER}:${RTSP_PASSWORD}@${RTSP_IP}:554/cam/realmonitor?channel=${channel_name}&subtype=${RTSP_SUBTYPE}"
    local hls_output="$HLS_PATH/${folder_name}/live.m3u8"

    log_info "Memulai proses FFmpeg untuk channel: $channel_name (folder: $folder_name)..."
    
    mkdir -p "$HLS_PATH/$folder_name"

    ffmpeg -i "$rtsp_url" \
        -c:v copy -c:a aac \
        -f hls -hls_time 4 -hls_list_size 5 -hls_flags delete_segments \
        "$hls_output" &
    
    log_info "Proses FFmpeg berjalan di latar belakang untuk channel: $channel_name."
}

start_hls_streams() {
    local channels
    channels=$(generate_channels)
    for channel in $channels; do
        start_hls_stream "$channel"
    done
}

log_info "Memverifikasi user abdullah..."
if ! id abdullah &>/dev/null; then
    log_error "User abdullah tidak ditemukan!"
    exit 1
fi
log_info "User abdullah tersedia."

validate_environment
create_nginx_log_dir
decode_credentials
cleanup_hls

ENABLE_RTSP_VALIDATION="${ENABLE_RTSP_VALIDATION:-true}"
if [ "$ENABLE_RTSP_VALIDATION" = "true" ]; then
    validate_rtsp
else
    log_info "RTSP validation dimatikan."
fi

start_hls_streams
log_info "Menjalankan Nginx sebagai proses utama..."
exec "$@"