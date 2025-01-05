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
    # Pastikan folder NGINX_LOG_PATH ada
    if [ ! -d "${NGINX_LOG_PATH}" ]; then
        log_info "Folder ${NGINX_LOG_PATH} belum ada. Membuat folder..."
        mkdir -p "${NGINX_LOG_PATH}" || {
            log_error "Gagal membuat folder ${NGINX_LOG_PATH}!"
            exit 1
        }
    fi
    # Pastikan file log minimal ada
    if [ ! -f "${NGINX_LOG_PATH}/error.log" ]; then
        touch "${NGINX_LOG_PATH}/error.log"
    fi
    if [ ! -f "${NGINX_LOG_PATH}/access.log" ]; then
        touch "${NGINX_LOG_PATH}/access.log"
    fi
    chmod -R 777 "${NGINX_LOG_PATH}"
    log_info "Folder ${NGINX_LOG_PATH} siap untuk log Nginx."
}

decode_credentials() {
    log_info "Mendekode kredensial RTSP dari environment..."
    if [ -n "$RTSP_USER_BASE64" ] && [ -n "$RTSP_PASSWORD_BASE64" ]; then
        export RTSP_USER=$(echo "$RTSP_USER_BASE64" | base64 -d)
        export RTSP_PASSWORD=$(echo "$RTSP_PASSWORD_BASE64" | base64 -d)
    else
        log_error "Variabel RTSP_USER_BASE64 atau RTSP_PASSWORD_BASE64 tidak diset. Kredensial RTSP tidak dapat didekode."
    fi
}

cleanup_hls() {
    log_info "Membersihkan direktori HLS..."
    if [ -d "$HLS_PATH" ]; then
        rm -rf "${HLS_PATH:?}/"*
    fi
}

validate_and_log() {
    local channel=$1
    local rtsp_url="rtsp://${RTSP_USER}:${RTSP_PASSWORD}@${RTSP_IP}:554/cam/realmonitor?channel=${channel}&subtype=1"

    log_info "Memulai validasi RTSP untuk channel ${channel}..."

    set +e
    /app/streamserver/venv/bin/python /app/streamserver/scripts/validate_cctv.py "$rtsp_url" "$channel"
    RETVAL=$?
    set -e

    # Pastikan folder cctv log ada
    if [ ! -d "$CCTV_LOG_PATH" ]; then
        mkdir -p "$CCTV_LOG_PATH"
        chmod 777 "$CCTV_LOG_PATH"
    fi
    # Buat file cctv_status.log jika belum ada
    if [ ! -f "${CCTV_LOG_PATH}/cctv_status.log" ]; then
        touch "${CCTV_LOG_PATH}/cctv_status.log"
        chmod 666 "${CCTV_LOG_PATH}/cctv_status.log"
    fi

    # Simpan hasil validasi
    if [ $RETVAL -eq 0 ]; then
        echo "$(date '+%d-%m-%Y %H:%M:%S') - Channel ${channel}: Validasi berhasil." >> "${CCTV_LOG_PATH}/cctv_status.log"
    else
        echo "$(date '+%d-%m-%Y %H:%M:%S') - Channel ${channel}: Validasi gagal." >> "${CCTV_LOG_PATH}/cctv_status.log"
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

log_info "Memverifikasi user abdullah..."
if id abdullah &>/dev/null; then
    log_info "User abdullah tersedia."
else
    log_error "User abdullah tidak ditemukan!"
    exit 1
fi

# 1. Pastikan folder untuk Nginx logs
create_nginx_log_dir

# 2. Decode credential RTSP
decode_credentials

# 3. Bersihkan folder HLS
cleanup_hls

# 4. Validasi RTSP (opsional)
ENABLE_RTSP_VALIDATION=${ENABLE_RTSP_VALIDATION:-true}
if [ "$ENABLE_RTSP_VALIDATION" = "true" ]; then
    validate_all_channels
else
    log_info "RTSP validation dimatikan. Melewati proses validasi..."
fi

log_info "Menjalankan Nginx sebagai proses utama..."
# Opsional: sleep 1
exec "$@"