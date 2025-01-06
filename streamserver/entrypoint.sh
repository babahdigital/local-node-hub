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

# Jika Anda ingin mem‐skip cek user abdullah, set SKIP_ABDULLAH_CHECK=true
SKIP_ABDULLAH_CHECK="${SKIP_ABDULLAH_CHECK:-false}"

###############################################################################
# FUNGSI LOGGING SEDERHANA
###############################################################################
log_info() {
    echo "$(date '+%d-%m-%Y %H:%M:%S %Z') [INFO] $*"
}

log_error() {
    echo "$(date '+%d-%m-%Y %H:%M:%S %Z') [ERROR] $*" >&2
}

###############################################################################
# LOAD CREDENTIALS (OPTIONAL)
###############################################################################
# Jika Anda menempatkan RTSP_USER_BASE64, RTSP_PASSWORD_BASE64 di /app/config/credentials.sh,
# Anda bisa "source" di sini. Jika environment sudah diset di .env, ini bisa di-skip.
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
            log_error "Pastikan image Docker Anda meng‐install '$dep'."
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
    # Fungsi ini akan meng-encode semua karakter spesial, termasuk '@'
    # Contoh: "Admin123@" => "Admin123%40"
    python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$1"
}

###############################################################################
# FUNGSI: VALIDASI VARIABEL LINGKUNGAN
###############################################################################
validate_environment() {
    log_info "Memvalidasi variabel lingkungan..."

    # Pastikan RTSP_IP terisi (untuk DVR/NVR).
    if [ -z "${RTSP_IP:-}" ]; then
        log_error "NETWORK: RTSP_IP tidak diset!"
        exit 1
    fi

    # Pastikan RTSP_USER dan RTSP_PASSWORD sudah diset
    if [ -z "${RTSP_USER:-}" ] || [ -z "${RTSP_PASSWORD:-}" ]; then
        log_error "AUTH: RTSP_USER atau RTSP_PASSWORD tidak diset!"
        exit 1
    fi

    # RTSP_SUBTYPE default
    if [ -z "${RTSP_SUBTYPE:-}" ]; then
        log_info "RTSP_SUBTYPE tidak diset. Menggunakan default = 1."
        export RTSP_SUBTYPE=1
    fi

    # TEST_CHANNEL vs CHANNELS
    # - TEST_CHANNEL bisa berupa "1,2,3" (dipisahkan koma).
    # - CHANNELS default-nya 1 (jika tidak di-set).
    if [ "${TEST_CHANNEL:-off}" != "off" ]; then
        log_info "Mode Testing Hidup, Variabel CHANNELS diabaikan."
    else
        if [[ "${CHANNELS:-1}" =~ ^[0-9]+$ ]]; then
            log_info "CHANNELS diatur sebagai angka: ${CHANNELS:-1}."
        else
            log_error "CHANNELS harus berupa angka (contoh: 8, 16, 32)."
            exit 1
        fi
    fi

    # Cek user abdullah, kalau tidak di-skip
    if [ "$SKIP_ABDULLAH_CHECK" = "false" ]; then
        log_info "Memverifikasi user abdullah..."
        if ! id abdullah &>/dev/null; then
            log_error "User abdullah tidak ditemukan!"
            exit 1
        fi
        log_info "User abdullah tersedia."
    else
        log_info "SKIP_ABDULLAH_CHECK=true => Melewati pengecekan user abdullah."
    fi

    log_info "Semua variabel lingkungan valid."
}

###############################################################################
# FUNGSI: MEMBUAT DIREKTORI LOG
###############################################################################
create_log_dirs() {
    log_info "Memeriksa dan membuat folder log yang dibutuhkan..."

    # 1. Folder log Nginx
    mkdir -p "$NGINX_LOG_PATH" || {
        log_error "Gagal membuat folder $NGINX_LOG_PATH!"
        exit 1
    }
    touch "$NGINX_LOG_PATH/error.log" "$NGINX_LOG_PATH/access.log"
    chmod -R 750 "$NGINX_LOG_PATH"
    log_info "Folder $NGINX_LOG_PATH siap digunakan."

    # 2. Folder log CCTV (untuk Python validation)
    mkdir -p "$CCTV_LOG_PATH" || {
        log_error "Gagal membuat folder $CCTV_LOG_PATH!"
        exit 1
    }
    # Bisa juga siapkan file cctv_status.log dsb. sesuai kebutuhan
    touch "$CCTV_LOG_PATH/validation.log" "$CCTV_LOG_PATH/cctv_status.log"
    chmod -R 750 "$CCTV_LOG_PATH"
    log_info "Folder $CCTV_LOG_PATH siap digunakan."
}

###############################################################################
# FUNGSI: MEMBERSIHKAN DIREKTORI HLS
###############################################################################
cleanup_hls() {
    log_info "Membersihkan direktori HLS..."
    if [ -d "$HLS_PATH" ]; then
        rm -rf "${HLS_PATH:?}/"*
        log_info "Direktori HLS berhasil dibersihkan."
    else
        log_info "Direktori HLS tidak ditemukan. Membuat baru..."
        mkdir -p "$HLS_PATH"
    fi
}

###############################################################################
# FUNGSI: MEMULAI STREAMING HLS (FFmpeg)
###############################################################################
start_hls_stream() {
    local channel_name=$1
    local folder_name="ch${channel_name}"  # Format folder ch<n>

    # Lakukan URL-encode untuk password agar tidak terjadi '@@' dsb.
    local encoded_password
    encoded_password="$(urlencode "$RTSP_PASSWORD")"

    # Bagi logging, kita mask password agar tidak terlihat
    local masked_cred="${RTSP_USER}:*****"
    # Untuk URL asli, pakai password yang sudah di-encode
    local actual_cred="${RTSP_USER}:${encoded_password}"

    # Pakai -rtsp_transport tcp agar FFmpeg memaksa RTSP via TCP (beberapa DVR butuh ini)
    local rtsp_url="rtsp://${actual_cred}@${RTSP_IP}:554/cam/realmonitor?channel=${channel_name}&subtype=${RTSP_SUBTYPE}"
    local hls_output="$HLS_PATH/${folder_name}/live.m3u8"

    # Metadata Title: Gabungkan STREAM_TITLE (dari ENV) dengan informasi channel
    local metadata_title="${STREAM_TITLE:-Default Stream} - Channel ${channel_name}"

    #log_info "STREAMING-HLS: Memulai proses conversi untuk channel: $channel_name (folder: $folder_name)..."
    #log_info "STREAMING-HLS: RTSP URL: rtsp://${masked_cred}@${RTSP_IP}...[REDACTED PATH]"
    log_info "STREAMING-HLS: Menjalankan CCTV ${metadata_title}"
    log_info "STREAMING-HLS: Akses lokal melalui URL: http://bankkalsel/$folder_name/"

    mkdir -p "$HLS_PATH/$folder_name"

    ffmpeg \
        -hide_banner \
        -loglevel error \
        -rtsp_transport tcp \
        -i "$rtsp_url" \
        -c:v copy -c:a aac \
        -metadata title="${metadata_title}" \
        -f hls -hls_time 4 -hls_list_size 10 -hls_flags delete_segments \
        "$hls_output" &>/dev/null &

    #log_info "STREAMING-HLS: FFmpeg untuk channel $channel_name berjalan di background (PID=$!)."
}

start_hls_streams() {
    log_info "Memulai seluruh HLS stream..."

    # Jika TEST_CHANNEL di-set, maka pakai daftar channel dari situ.
    # Kalau tidak, pakai range 1..CHANNELS.
    local channels
    if [ "${TEST_CHANNEL:-off}" != "off" ]; then
        IFS=',' read -ra channels <<< "$TEST_CHANNEL"
    else
        channels=($(seq 1 "${CHANNELS:-1}"))
    fi

    for channel in "${channels[@]}"; do
        start_hls_stream "$channel"
    done
}

###############################################################################
# FUNGSI UTAMA
###############################################################################
main() {
    # 0. Pastikan dependencies ada
    check_dependencies

    # 1. Decode credentials
    decode_credentials

    # 2. Validasi environment
    validate_environment

    # 3. Buat folder log (Nginx, CCTV, dsb.)
    create_log_dirs

    # 4. Bersihkan (atau buat) direktori HLS
    cleanup_hls

    # 5. Validasi RTSP dengan Python (opsional)
    if [ "$ENABLE_RTSP_VALIDATION" = "true" ]; then
        local validation_script="/app/streamserver/scripts/validate_cctv.py"
        if [ -f "$validation_script" ]; then
            log_info "Menjalankan script Python untuk validasi RTSP..."

            # Jika Anda ingin script Python loop berjalan di background:
            python3 "$validation_script" &

            # === Kalau cuma mau jalankan sekali (blocking), pakai tanpa ampersand ===
            # if ! python3 "$validation_script"; then
            #     log_error "Terjadi error saat menjalankan validate_cctv.py (exit code != 0)."
            #     # Jika mau kontainer tetap jalan meski validasi gagal, JANGAN exit 1 di sini.
            #     # exit 1
            # fi

        else
            log_error "File $validation_script tidak ditemukan! Skipping validation..."
        fi
    else
        log_info "RTSP validation dimatikan (ENABLE_RTSP_VALIDATION=false)."
    fi

    # 6. Mulai streaming HLS
    start_hls_streams

    # 7. Jalankan perintah akhir (misal: Nginx, jika tidak ada argumen).
    if [ $# -eq 0 ]; then
        log_info "Tidak ada argumen. Menjalankan default: nginx -g 'daemon off;'."
        exec nginx -g 'daemon off;'
    else
        log_info "Menjalankan perintah akhir: $*"
        exec "$@"
    fi
}

# Panggil fungsi main
main