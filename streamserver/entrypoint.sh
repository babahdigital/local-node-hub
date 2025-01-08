#!/bin/bash
set -Eeuo pipefail

###############################################################################
# KONSTANTA DAN KONFIGURASI
###############################################################################
LOG_BASE_PATH="/mnt/Data/Syslog/rtsp"
NGINX_LOG_PATH="${LOG_BASE_PATH}/nginx"
CCTV_LOG_PATH="${LOG_BASE_PATH}/cctv"
HLS_PATH="/app/hls"

# Jika Anda ingin mematikan validasi RTSP, set ENABLE_RTSP_VALIDATION=false
ENABLE_RTSP_VALIDATION="${ENABLE_RTSP_VALIDATION:-true}"

# Jika Anda ingin mem-skip cek user abdullah, set SKIP_ABDULLAH_CHECK=true
SKIP_ABDULLAH_CHECK="${SKIP_ABDULLAH_CHECK:-false}"

# Apakah script Python (validate_cctv.py) dijalankan secara loop atau single-run
# LOOP_ENABLE=true => loop di background
# LOOP_ENABLE=false => single-run
LOOP_ENABLE="${LOOP_ENABLE:-false}"

###############################################################################
# FUNGSI LOGGING SEDERHANA
###############################################################################
log_info() {
    echo "$(date '+%d-%m-%Y %H:%M:%S') [INFO] $*"
}

log_error() {
    echo "$(date '+%d-%m-%Y %H:%M:%S') [ERROR] $*" >&2
}

###############################################################################
# LOAD CREDENTIALS (OPTIONAL)
###############################################################################
if [ -f /app/config/credentials.sh ]; then
    source /app/config/credentials.sh
fi

###############################################################################
# FUNGSI: CEK DEPENDENCIES
###############################################################################
check_dependencies() {
    local deps=("ffmpeg" "python3" "nginx")

    for dep in "${deps[@]}"; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            log_error "Dependency '$dep' tidak ditemukan di PATH!"
            log_error "Pastikan image Docker Anda meng-install '$dep'."
            exit 1
        fi
    done

    log_info "Semua dependencies utama (ffmpeg, python3, nginx) terdeteksi."
}

###############################################################################
# FUNGSI: DECODE RTSP CREDENTIALS
###############################################################################
decode_credentials() {
    log_info "AUTH: Mendekode kredensial RTSP..."

    if [ -n "${RTSP_USER_BASE64:-}" ] && [ -n "${RTSP_PASSWORD_BASE64:-}" ]; then
        export RTSP_USER
        export RTSP_PASSWORD

        RTSP_USER="$(echo "$RTSP_USER_BASE64" | base64 -d 2>/dev/null || true)"
        RTSP_PASSWORD="$(echo "$RTSP_PASSWORD_BASE64" | base64 -d 2>/dev/null || true)"

        if [ -z "$RTSP_USER" ] || [ -z "$RTSP_PASSWORD" ]; then
            log_error "AUTH: Kredensial RTSP gagal didekode (hasil kosong)."
            exit 1
        fi
        log_info "AUTH: Kredensial RTSP berhasil didekode."
    else
        log_error "AUTH: Variabel RTSP_USER_BASE64 atau RTSP_PASSWORD_BASE64 tidak diset!"
        exit 1
    fi
}

###############################################################################
# FUNGSI: URL-ENCODE (menggunakan Python)
###############################################################################
urlencode() {
    python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$1"
}

###############################################################################
# FUNGSI: VALIDASI VARIABEL LINGKUNGAN
###############################################################################
validate_environment() {
    log_info "Memvalidasi variabel lingkungan..."

    # Pastikan RTSP_IP terisi
    if [ -z "${RTSP_IP:-}" ]; then
        log_error "NETWORK: RTSP_IP tidak diset!"
        exit 1
    fi

    # Pastikan RTSP_USER dan RTSP_PASSWORD sudah ada
    if [ -z "${RTSP_USER:-}" ] || [ -z "${RTSP_PASSWORD:-}" ]; then
        log_error "AUTH: RTSP_USER / RTSP_PASSWORD tidak diset!"
        exit 1
    fi

    # RTSP_SUBTYPE
    if [ -z "${RTSP_SUBTYPE:-}" ]; then
        log_info "RTSP_SUBTYPE tidak diset. default=1"
        export RTSP_SUBTYPE=1
    fi

    # TEST_CHANNEL vs CHANNELS
    if [ "${TEST_CHANNEL:-off}" != "off" ]; then
        log_info "TEST_CHANNEL diisi => Channel list diambil dari situ."
    else
        if [[ "${CHANNELS:-1}" =~ ^[0-9]+$ ]]; then
            log_info "CHANNELS = ${CHANNELS:-1}"
        else
            log_error "CHANNELS harus berupa angka. (8,16,32 dsb)"
            exit 1
        fi
    fi

    # Cek user abdullah
    if [ "$SKIP_ABDULLAH_CHECK" = "false" ]; then
        log_info "Memverifikasi user abdullah..."
        if ! id abdullah &>/dev/null; then
            log_error "User abdullah tidak ditemukan!"
            exit 1
        fi
        log_info "User abdullah tersedia."
    else
        log_info "SKIP_ABDULLAH_CHECK=true => lewati cek user abdullah."
    fi

    log_info "Environment valid."
}

###############################################################################
# FUNGSI: MEMBUAT DIREKTORI LOG
###############################################################################
create_log_dirs() {
    log_info "Membuat folder log (Nginx, CCTV)..."

    # Nginx
    mkdir -p "$NGINX_LOG_PATH" || {
        log_error "Gagal buat folder $NGINX_LOG_PATH!"
        exit 1
    }
    touch "$NGINX_LOG_PATH/error.log" "$NGINX_LOG_PATH/access.log"
    chmod -R 750 "$NGINX_LOG_PATH"

    # CCTV
    mkdir -p "$CCTV_LOG_PATH" || {
        log_error "Gagal buat folder $CCTV_LOG_PATH!"
        exit 1
    }
    touch "$CCTV_LOG_PATH/validation.log" "$CCTV_LOG_PATH/cctv_status.log"
    chmod -R 750 "$CCTV_LOG_PATH"
}

###############################################################################
# OPSIONAL: PERBAIKI PERMISSION FOLDER HLS
###############################################################################
fix_hls_permissions() {
    # as needed, misalnya chown -R root:root
    chown -R abdullah:abdullah "$HLS_PATH"
    chmod -R 775 "$HLS_PATH"
    log_info "Permissions di $HLS_PATH => abdullah:abdullah & 775"
}

###############################################################################
# FUNGSI: MEMBERSIHKAN DIREKTORI HLS
###############################################################################
cleanup_hls() {
    log_info "Membersihkan direktori HLS..."
    if [ -d "$HLS_PATH" ]; then
        rm -rf "${HLS_PATH:?}/"*
        log_info "HLS dikosongkan."
    else
        log_info "Direktori HLS blm ada => buat baru"
        mkdir -p "$HLS_PATH"
    fi

    fix_hls_permissions
}

###############################################################################
# FUNGSI: MEMULAI STREAMING HLS (FFmpeg)
###############################################################################
start_hls_stream() {
    local ch="$1"
    local folder_name="ch${ch}"

    # encode pass
    local encoded_pass
    encoded_pass="$(urlencode "$RTSP_PASSWORD")"

    local masked_cred="${RTSP_USER}:*****"
    local actual_cred="${RTSP_USER}:${encoded_pass}"

    local rtsp_url="rtsp://${actual_cred}@${RTSP_IP}:554/cam/realmonitor?channel=${ch}&subtype=${RTSP_SUBTYPE}"
    local hls_dir="$HLS_PATH/$folder_name"
    local hls_output="$hls_dir/live.m3u8"

    # metadata
    local title="${STREAM_TITLE:-Default Stream} - Channel ${ch}"
    log_info "STREAM: $title => folder: $folder_name"
    log_info "RTSP (masked): rtsp://${masked_cred}@${RTSP_IP}:554/...ch=${ch}..."

    mkdir -p "$hls_dir"

    ffmpeg \
        -hide_banner \
        -loglevel error \
        -rtsp_transport tcp \
        -i "$rtsp_url" \
        -c copy \
        -f hls \
        -hls_time 10 \
        -hls_list_size 30 \
        -hls_flags delete_segments+append_list \
        -metadata title="${title}" \
        "$hls_output" &>/dev/null &

#    ffmpeg \
#        -hide_banner \
#        -loglevel error \
#        -rtsp_transport tcp \
#        -i "$rtsp_url" \
#        -c:v libx264 -preset ultrafast -r 15 -g 30 -crf 28 -threads 4 \
#        -an \
#        -f hls \
#        -hls_time 10 \
#        -hls_list_size 30 \
#        -hls_flags delete_segments+append_list \
#        -metadata title="${title}" \
#        "$hls_output" &>/dev/null &

    log_info "FFmpeg channel $ch => background (PID=$!)."
}

start_hls_streams() {
    log_info "Mulai seluruh HLS stream..."

    local channels
    if [ "${TEST_CHANNEL:-off}" != "off" ]; then
        IFS=',' read -ra channels <<< "${TEST_CHANNEL}"
    else
        channels=($(seq 1 "${CHANNELS:-1}"))
    fi

    for c in "${channels[@]}"; do
        start_hls_stream "$c"
    done
}

###############################################################################
# FUNGSI UTAMA
###############################################################################
main() {
    # cek dependencies
    check_dependencies

    # decode credentials
    decode_credentials

    # validate environment
    validate_environment

    # buat folder log
    create_log_dirs

    # bersihkan folder hls
    cleanup_hls

    # opsional => jalankan validate_cctv
    if [ "$ENABLE_RTSP_VALIDATION" = "true" ]; then
        local script="/app/streamserver/scripts/validate_cctv.py"
        if [ -f "$script" ]; then
            log_info "Menjalankan $script..."

            if [ "$LOOP_ENABLE" = "true" ]; then
                # loop => background
                python3 "$script" &
                log_info "validate_cctv => loop di background"
            else
                # single-run
                if ! python3 "$script"; then
                    log_error "validate_cctv exit !=0"
                    # opsional: exit 1
                fi
            fi
        else
            log_error "script $script tidak ada => skip validation"
        fi
    else
        log_info "RTSP validation dimatikan"
    fi

    # mulai streaming
    start_hls_streams

    # cek arg
    if [ $# -eq 0 ]; then
        log_info "No arg => jalankan nginx -g 'daemon off;'"
        exec nginx -g 'daemon off;'
    else
        log_info "Menjalankan perintah akhir: $*"
        exec "$@"
    fi
}

main