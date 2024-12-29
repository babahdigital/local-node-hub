#!/usr/bin/env bash

set -e

CREDENTIALS_FILE="/app/config/credentials.sh"
NGINX_TEMPLATE="/app/config/nginx.conf.template"
NGINX_CONF="/etc/nginx/nginx.conf"
LOG_MESSAGES_FILE="/app/config/log_messages.json"
ACCESS_LOG="/app/logs/access.log"
ERROR_LOG="/app/logs/error.log"
CONFIG_CHECKSUM_FILE="/tmp/nginx_config_checksum"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1: $2"
}

get_log_message() {
    local key="$1"
    local default_message="$2"
    if [ -f "$LOG_MESSAGES_FILE" ]; then
        jq -r ".$key // \"$default_message\"" "$LOG_MESSAGES_FILE" 2>/dev/null
    else
        echo "$default_message"
    fi
}

validate_files() {
    [ -f "$CREDENTIALS_FILE" ] || { log "ERROR" "$(get_log_message "file_missing" "File kredensial tidak ditemukan.")"; exit 1; }
    [ -f "$NGINX_TEMPLATE" ] || { log "ERROR" "$(get_log_message "template_missing" "Template Nginx tidak ditemukan.")"; exit 1; }
}

generate_nginx_config() {
    local new_checksum
    new_checksum=$(sha256sum "$CREDENTIALS_FILE" "$NGINX_TEMPLATE" | sha256sum)

    if [ -f "$CONFIG_CHECKSUM_FILE" ] && grep -q "$new_checksum" "$CONFIG_CHECKSUM_FILE"; then
        log "INFO" "$(get_log_message "config_no_change" "Konfigurasi tidak berubah.")"
    else
        envsubst < "$NGINX_TEMPLATE" > "$NGINX_CONF"
        echo "$new_checksum" > "$CONFIG_CHECKSUM_FILE"
        log "INFO" "$(get_log_message "config_generated" "Konfigurasi Nginx berhasil dihasilkan.")"
    fi
}

validate_files
generate_nginx_config

log "INFO" "$(get_log_message "nginx_start" "Menjalankan Nginx...")"
exec nginx -g "daemon off;"