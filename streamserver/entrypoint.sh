#!/bin/bash
set -Eeuo pipefail

# === Konstanta Direktori dan File ===
LOG_BASE_PATH="/mnt/Data/Syslog/rtsp"
NGINX_LOG_PATH="${LOG_BASE_PATH}/nginx"
CCTV_LOG_PATH="${LOG_BASE_PATH}/cctv"
HLS_PATH="/app/hls"

# === Fungsi Logging ===
log_info() {
    echo "$(date '+%d-%m-%Y %H:%M:%S') [INFO] $*"
}

log_error() {
    echo "$(date '+%d-%m-%Y %H:%M:%S') [ERROR] $*" >&2
}

# === Membuat Direktori Log Nginx ===
create_nginx_log_dir() {
    log_info "Memeriksa dan membuat folder log Nginx jika belum ada..."
    mkdir -p "$NGINX_LOG_PATH" || {
        log_error "Gagal membuat folder $NGINX_LOG_PATH!"
        exit 1
    }
    touch "$NGINX_LOG_PATH/error.log" "$NGINX_LOG_PATH/access.log"
    chmod -R 750 "$NGINX_LOG_PATH"
    log_info "Folder $NGINX_LOG_PATH siap digunakan."
}

# === Dekode Kredensial RTSP ===
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

# === Validasi Variabel Lingkungan ===
validate_environment() {
    log_info "Memvalidasi variabel lingkungan..."

    if [ -z "${RTSP_IP:-}" ]; then
        log_error "RTSP_IP tidak diset!"
        exit 1
    fi

    if [ "${TEST_CHANNEL:-off}" != "off" ]; then
        log_info "TEST_CHANNEL diatur: $TEST_CHANNEL, CHANNELS diabaikan."
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

# === Membersihkan Direktori HLS ===
cleanup_hls() {
    log_info "Membersihkan direktori HLS..."
    if [ -d "$HLS_PATH" ]; then
        rm -rf "${HLS_PATH:?}/"*
        log_info "Direktori HLS berhasil dibersihkan."
    else
        log_info "Direktori HLS tidak ditemukan. Tidak ada yang perlu dibersihkan."
    fi
}

# === Generate Daftar Channel ===
generate_channels() {
    if [ "${TEST_CHANNEL:-off}" != "off" ]; then
        IFS=',' read -ra channels <<< "$TEST_CHANNEL"
    else
        channels=($(seq 1 "$CHANNELS"))
    fi
    echo "${channels[@]}"
}

# === Validasi RTSP Stream ===
validate_rtsp() {
    log_info "Memulai validasi RTSP stream..."

    local channels
    channels=$(generate_channels)

    for channel in $channels; do
        local rtsp_url="rtsp://${RTSP_USER}:${RTSP_PASSWORD}@${RTSP_IP}:554/cam/realmonitor?channel=${channel}&subtype=${RTSP_SUBTYPE}"
        if ffprobe -v error -show_entries stream=codec_name -of default=noprint_wrappers=1 "$rtsp_url" &>/dev/null; then
            log_info "Channel $channel: RTSP stream valid."
        else
            log_error "Channel $channel: RTSP stream tidak valid."
        fi
    done

    log_info "Validasi RTSP selesai."
}

# === Memulai Streaming HLS ===
start_hls_stream() {
    local channel_name=$1
    local folder_name="ch${channel_name}" # Format folder ch<n>
    local rtsp_url="rtsp://${RTSP_USER}:${RTSP_PASSWORD}@${RTSP_IP}:554/cam/realmonitor?channel=${channel_name}&subtype=${RTSP_SUBTYPE}"
    local hls_output="$HLS_PATH/${folder_name}/live.m3u8"

    log_info "Memulai proses FFmpeg untuk channel: $channel_name (folder: $folder_name)..."
    
    mkdir -p "$HLS_PATH/$folder_name"

    ffmpeg -i "$rtsp_url" \
        -c:v copy -c:a aac \
        -f hls -hls_time 4 -hls_list_size 5 -hls_flags delete_segments \
        "$hls_output" &>/dev/null &
}

start_hls_streams() {
    local channels
    channels=$(generate_channels)
    for channel in $channels; do
        start_hls_stream "$channel"
    done
}

# === Pemeriksaan User Abdullah ===
log_info "Memverifikasi user abdullah..."
if ! id abdullah &>/dev/null; then
    log_error "User abdullah tidak ditemukan!"
    exit 1
fi
log_info "User abdullah tersedia."

# === Eksekusi Utama ===
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