#!/usr/bin/env bash

set -e

# Path ke file konfigurasi dan log
CREDENTIALS_FILE="/app/config/credentials.sh"
NGINX_TEMPLATE="/app/config/nginx.conf.template"
NGINX_CONF="/etc/nginx/nginx.conf"
LOG_DIR="/mnt/Data/Syslog/nginx"
ACCESS_LOG="$LOG_DIR/access.log"
ERROR_LOG="$LOG_DIR/error.log"
CONFIG_CHECKSUM_FILE="$LOG_DIR/nginx_config_checksum"

# Fungsi logging
log() {
    local level="$1"
    local message="$2"
    echo "$(date '+%d-%m-%Y %H:%M:%S') - $level: $message" | tee -a "$ERROR_LOG"
}

# Fungsi validasi file
validate_files() {
    [ -f "$CREDENTIALS_FILE" ] || { log "ERROR" "Credentials file not found: $CREDENTIALS_FILE"; exit 1; }
    [ -f "$NGINX_TEMPLATE" ] || { log "ERROR" "Nginx template not found: $NGINX_TEMPLATE"; exit 1; }
}

# Fungsi validasi environment variables
validate_env() {
    source "$CREDENTIALS_FILE"
    local required_vars=("RTSP_USERNAME" "RTSP_PASSWORD" "RTSP_IP")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            log "ERROR" "Required environment variable $var is not set"
            exit 1
        fi
    done
    log "INFO" "Environment variables are valid."
    log "DEBUG" "RTSP_USERNAME=${RTSP_USERNAME}, RTSP_IP=${RTSP_IP}"  # Menyembunyikan RTSP_PASSWORD
}

# Fungsi untuk membuat konfigurasi Nginx
generate_nginx_config() {
    local new_checksum
    new_checksum=$(sha256sum "$CREDENTIALS_FILE" "$NGINX_TEMPLATE" | awk '{ print $1 }')
    if [ -f "$CONFIG_CHECKSUM_FILE" ] && grep -q "$new_checksum" "$CONFIG_CHECKSUM_FILE"; then
        log "INFO" "Nginx configuration is up-to-date."
    else
        log "INFO" "Generating new Nginx configuration..."
        if ! envsubst < "$NGINX_TEMPLATE" > "$NGINX_CONF"; then
            log "ERROR" "Failed to generate Nginx configuration."
            exit 1
        fi
        echo "$new_checksum" > "$CONFIG_CHECKSUM_FILE"
        log "DEBUG" "Generated Nginx configuration:"
        cat "$NGINX_CONF" | tee -a "$ERROR_LOG"
    fi
}

# Inisialisasi direktori log
initialize_log_directory() {
    mkdir -p "$LOG_DIR"
    chmod 755 "$LOG_DIR"
    touch "$ACCESS_LOG" "$ERROR_LOG"
    if [ ! -w "$LOG_DIR" ]; then
        log "ERROR" "Log directory is not writable: $LOG_DIR"
        exit 1
    fi
    rm -f "$CONFIG_CHECKSUM_FILE"
    log "INFO" "Log directory initialized: $LOG_DIR"
}

# Validasi dan jalankan Nginx
run_nginx() {
    log "INFO" "Validating Nginx configuration..."
    set +e
    nginx -t
    local nginx_status=$?
    set -e
    if [ $nginx_status -ne 0 ]; then
        log "ERROR" "Nginx configuration validation failed."
        exit 1
    fi
    log "INFO" "Starting Nginx..."
    exec nginx -g "daemon off;"
}

# Eksekusi utama
validate_files
validate_env
initialize_log_directory
generate_nginx_config
run_nginx
