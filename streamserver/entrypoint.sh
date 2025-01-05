#!/bin/bash
set -e

LOG_BASE_PATH="/mnt/Data/Syslog/rtsp"
NGINX_LOG_PATH="${LOG_BASE_PATH}/nginx"
CCTV_LOG_PATH="${LOG_BASE_PATH}/cctv"
HLS_PATH="/app/hls"

log_info() {
    echo "$(date '+%d-%m-%Y %H:%M:%S') [INFO] $1"
}

log_error() {
    echo "$(date '+%d-%m-%Y %H:%M:%S') [ERROR] $1"
}

create_nginx_log_dir() {
    if [ ! -d "${NGINX_LOG_PATH}" ]; then
        log_info "Folder ${NGINX_LOG_PATH} belum ada. Membuat folder..."
        mkdir -p "${NGINX_LOG_PATH}" || {
            log_error "Gagal membuat folder ${NGINX_LOG_PATH}!"
            exit 1
        }
    fi
    [ ! -f "${NGINX_LOG_PATH}/error.log" ] && touch "${NGINX_LOG_PATH}/error.log"
    [ ! -f "${NGINX_LOG_PATH}/access.log" ] && touch "${NGINX_LOG_PATH}/access.log"
    chmod -R 750 "${NGINX_LOG_PATH}"
    log_info "Folder ${NGINX_LOG_PATH} siap untuk log Nginx."
}

decode_credentials() {
    log_info "Mendekode kredensial RTSP dari Docker Secrets..."
    if [ -f /run/secrets/rtsp_user ] && [ -f /run/secrets/rtsp_password ]; then
        export RTSP_USER=$(cat /run/secrets/rtsp_user)
        export RTSP_PASSWORD=$(cat /run/secrets/rtsp_password)
        log_info "Kredensial berhasil dibaca dari secrets."
    else
        log_error "Secrets tidak ditemukan! Pastikan secrets tersedia di /run/secrets."
        exit 1
    fi
}

validate_environment() {
    log_info "Memvalidasi variabel lingkungan..."
    if [ -z "$RTSP_IP" ]; then
        log_error "RTSP_IP tidak diset! Pastikan RTSP_IP diatur dalam konfigurasi."
        exit 1
    fi
    log_info "Semua variabel lingkungan valid."
}

cleanup_hls() {
    log_info "Membersihkan direktori HLS..."
    if [ -d "$HLS_PATH" ]; then
        rm -rf "${HLS_PATH:?}/"*
        log_info "Direktori HLS berhasil dibersihkan."
    else
        log_info "Direktori HLS tidak ditemukan. Tidak ada yang perlu dibersihkan."
    fi
}

validate_rtsp() {
    log_info "Memulai validasi RTSP menggunakan validate_cctv.py..."
    /app/streamserver/venv/bin/python /app/streamserver/scripts/validate_cctv.py || {
        log_error "Validasi RTSP gagal. Periksa log untuk detail lebih lanjut."
        exit 1
    }
    log_info "Validasi RTSP selesai. Cek log di ${CCTV_LOG_PATH}/cctv_status.log."
}

start_hls_stream() {
    local rtsp_url="rtsp://${RTSP_USER}:${RTSP_PASSWORD}@${RTSP_IP}:554/cam/realmonitor?channel=1&subtype=1"
    log_info "Memulai proses FFmpeg untuk menghasilkan HLS dari RTSP stream..."
    ffmpeg -i "$rtsp_url" \
           -c:v copy -c:a aac \
           -f hls \
           -hls_time 4 \
           -hls_list_size 5 \
           -hls_flags delete_segments \
           "${HLS_PATH}/live.m3u8" &
    log_info "Proses FFmpeg untuk HLS berjalan di latar belakang."
}

log_info "Memverifikasi user abdullah..."
if id abdullah &>/dev/null; then
    log_info "User abdullah tersedia."
else
    log_error "User abdullah tidak ditemukan!"
    exit 1
fi

# 1. Validasi variabel lingkungan
validate_environment

# 2. Pastikan folder untuk Nginx logs
create_nginx_log_dir

# 3. Decode credential RTSP
decode_credentials

# 4. Bersihkan folder HLS
cleanup_hls

# 5. Validasi RTSP
ENABLE_RTSP_VALIDATION=${ENABLE_RTSP_VALIDATION:-true}
if [ "$ENABLE_RTSP_VALIDATION" = "true" ]; then
    validate_rtsp
else
    log_info "RTSP validation dimatikan. Melewati proses validasi..."
fi

# 6. Mulai proses HLS
start_hls_stream

log_info "Menjalankan Nginx sebagai proses utama..."
exec "$@"