#!/usr/bin/env bash

# Aktifkan mode penanganan kesalahan
set -e

# Tetapkan zona waktu lokal dari variabel lingkungan atau default
TIMEZONE="${TIMEZONE:-Asia/Makassar}"
HEALTH_CHECK_URL="http://127.0.0.1:8080/health"
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-50}"  # Default waktu tunggu adalah 50 detik
HEALTH_CHECK_RETRY_DELAY="${HEALTH_CHECK_RETRY_DELAY:-10}"  # Waktu tunggu untuk retry health check

# Path ke file log_messages.json di dalam container
LOG_MESSAGES_FILE="/app/config/log_messages.json"

# Validasi apakah file log_messages.json ada
if [ ! -f "$LOG_MESSAGES_FILE" ]; then
    echo "$(date '+%d-%m-%Y %H:%M:%S') - ERROR: File log messages JSON tidak ditemukan di $LOG_MESSAGES_FILE" >&2
    exit 1
fi

# Fungsi untuk membaca pesan dari file JSON
get_log_message() {
    local key="$1"
    local message
    message=$(jq -r ".bash_entrypoint.${key}" "$LOG_MESSAGES_FILE" 2>/dev/null)
    if [ "$message" == "null" ]; then
        echo "$(date '+%d-%m-%Y %H:%M:%S') - ERROR: Pesan untuk kunci '${key}' tidak ditemukan di $LOG_MESSAGES_FILE" >&2
        exit 1
    fi
    echo "$message"
}

# Fungsi untuk mendapatkan waktu lokal dengan format dd-MM-yyyy HH:mm:ss WITA/WIB
get_local_time() {
    local tz_suffix
    if [ "$TIMEZONE" = "Asia/Jakarta" ]; then
        tz_suffix="WIB"
    else
        tz_suffix="WITA"
    fi
    TZ="$TIMEZONE" date "+%d-%m-%Y %H:%M:%S $tz_suffix"
}

# Fungsi logging
log() {
    local level="$1"
    local message="$2"
    echo "$(get_local_time) - $level: $message" | tee -a /mnt/Data/Syslog/rtsp/entrypoint.log
}

# Pastikan direktori log ada
mkdir -p /mnt/Data/Syslog/rtsp

# Logging saat memuat variabel lingkungan
log "INFO" "$(get_log_message 'loading_env')"

# Validasi file credentials.sh
if [ ! -f "/rtsp/credentials.sh" ]; then
    log "ERROR" "File credentials.sh tidak ditemukan."
    exit 1
fi
source /rtsp/credentials.sh
if [ -n "$RTSP_USERNAME" ] && [ -n "$RTSP_IP" ]; then
    log "INFO" "$(get_log_message 'env_loaded')"
else
    log "ERROR" "$(get_log_message 'env_invalid')"
    exit 1
fi

# Fungsi untuk membersihkan proses saat keluar
cleanup() {
    log "DEBUG" "$(get_log_message 'cleanup_start')."
    if ps -p "$HDD_MONITOR_PID" > /dev/null 2>&1; then
        log "INFO" "$(get_log_message 'stop_hdd_monitor')."
        kill -TERM "$HDD_MONITOR_PID" || log "WARNING" "$(get_log_message 'hdd_monitor_stop_failed')"
    fi
    if ps -p "$HEALTH_CHECK_PID" > /dev/null 2>&1; then
        log "INFO" "$(get_log_message 'stop_health_check')."
        kill -TERM "$HEALTH_CHECK_PID" || log "WARNING" "$(get_log_message 'health_check_stop_failed')"
    fi
    if ps -p "$LIVESTREAM_PID" > /dev/null 2>&1; then
        log "INFO" "Menghentikan Livestream Flask Server."
        kill -TERM "$LIVESTREAM_PID" || log "WARNING" "Gagal menghentikan proses Livestream Flask Server."
    fi
    log "INFO" "$(get_log_message 'cleanup_complete')."
}

# Tangani sinyal EXIT dan INT untuk cleanup
trap cleanup EXIT INT

# Jalankan HDD Monitor di latar belakang
log "INFO" "$(get_log_message 'start_hdd_monitor')"
python3 /app/scripts/hdd_monitor.py >> /mnt/Data/Syslog/rtsp/hdd_monitor.log 2>&1 &
HDD_MONITOR_PID=$!

# Jalankan Flask untuk health check di latar belakang
log "INFO" "$(get_log_message 'start_health_check')"
python3 /app/scripts/health_check.py >> /mnt/Data/Syslog/rtsp/health_check.log 2>&1 &
HEALTH_CHECK_PID=$!

# Jalankan Flask untuk Livestream (jika diaktifkan)
if [[ "$ENABLE_LIVESTREAM" == "true" ]]; then
    log "INFO" "Livestream diaktifkan. Memulai Livestream Flask."
    python3 /app/scripts/livestream_server.py >> /mnt/Data/Syslog/rtsp/livestream_server.log 2>&1 &
    LIVESTREAM_PID=$!
else
    log "INFO" "Livestream tidak diaktifkan. Menunggu permintaan manual."
fi

# Fungsi untuk mengecek status health check dengan retry
check_health_with_retry() {
    local retries=0
    while [[ $retries -lt $((HEALTH_CHECK_TIMEOUT / HEALTH_CHECK_RETRY_DELAY)) ]]; do
        RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_CHECK_URL)
        if [[ $RESPONSE -eq 200 ]]; then
            log "INFO" "$(get_log_message 'health_check_success')."
            return 0
        fi
        retries=$((retries + 1))
        log "WARNING" "$(get_log_message 'health_check_retry'). Percobaan ke-$retries."
        sleep "$HEALTH_CHECK_RETRY_DELAY"
    done
    return 1
}

# Periksa health check dengan auto-retry
if ! check_health_with_retry; then
    log "ERROR" "$(get_log_message 'health_check_failed') URL: $HEALTH_CHECK_URL, Timeout: $HEALTH_CHECK_TIMEOUT detik"
    cleanup
    exit 1
fi

# Jalankan loop backup
log "INFO" "$(get_log_message 'backup_start')"
while true; do
    python3 /app/scripts/backup_manager.py >> /mnt/Data/Syslog/rtsp/backup_manager.log 2>&1
    log "INFO" "$(get_log_message 'backup_wait')"
    sleep "${RETRY_DELAY:-30}"
done