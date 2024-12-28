#!/usr/bin/env bash

# Aktifkan mode penanganan kesalahan
set -e

# Path ke file konfigurasi dan log
CREDENTIALS_FILE="/app/config/credentials.sh"
NGINX_TEMPLATE="/app/config/nginx.conf.template"
NGINX_CONF="/etc/nginx/nginx.conf"
LOG_MESSAGES_FILE="/app/config/log_messages.json"
ACCESS_LOG="/app/logs/access.log"
ERROR_LOG="/app/logs/error.log"

# Fungsi logging
log() {
    local level="$1"
    local message="$2"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $level: $message"
}

# Fungsi untuk memuat pesan dari log_messages.json
get_log_message() {
    local key="$1"
    local default_message="$2"

    if [ -f "$LOG_MESSAGES_FILE" ]; then
        local message
        message=$(jq -r ".$key" "$LOG_MESSAGES_FILE" 2>/dev/null)
        if [ "$message" != "null" ]; then
            echo "$message"
            return
        fi
    fi
    echo "$default_message"
}

# Periksa apakah file credentials.sh ada
if [ ! -f "$CREDENTIALS_FILE" ]; then
    log "ERROR" "$(get_log_message "proxy.credentials.file_missing" "File credentials.sh tidak ditemukan.")"
    exit 1
fi

# Muat variabel dari credentials.sh
log "INFO" "$(get_log_message "proxy.credentials.env_loaded" "Memuat variabel dari credentials.sh...")"
source "$CREDENTIALS_FILE"

# Periksa apakah template nginx.conf tersedia
if [ ! -f "$NGINX_TEMPLATE" ]; then
    log "ERROR" "$(get_log_message "proxy.config.template_failed" "Template nginx.conf tidak ditemukan.")"
    exit 1
fi

# Generate konfigurasi nginx.conf dari template
log "INFO" "$(get_log_message "proxy.config.env_substitution_start" "Menghasilkan konfigurasi Nginx dari template...")"
envsubst < "$NGINX_TEMPLATE" > "$NGINX_CONF"
log "INFO" "$(get_log_message "proxy.config.env_substitution_success" "Konfigurasi Nginx berhasil dibuat.")"

# Pastikan direktori log tersedia
mkdir -p "$(dirname "$ACCESS_LOG")"
mkdir -p "$(dirname "$ERROR_LOG")"

# Jalankan Nginx
log "INFO" "$(get_log_message "proxy.runtime.start_success" "Memulai Nginx Proxy...")"
nginx -g "daemon off;"