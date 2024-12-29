#!/usr/bin/env bash
set -eu  # Stop on error or undefined var

###############################################################################
#                              VARIABEL DASAR
###############################################################################
CREDENTIALS_FILE="/app/config/credentials.sh"
TEMPLATE_FILE="/app/config/nginx.conf.template"
RTSP_TEMPLATE="/app/config/rtsp.conf.template"
OUTPUT_FILE="/etc/nginx/nginx.conf"
RTSP_OUTPUT_FILE="/etc/nginx/conf.d/rtsp.conf"
LOG_DIR="/mnt/Data/Syslog/nginx"
ERROR_LOG="$LOG_DIR/error.log"
ACCESS_LOG="$LOG_DIR/access.log"
LOG_MESSAGES="/app/config/log_messages.json"

###############################################################################
#                             FUNGSI UTILITAS
###############################################################################

# Fungsi membaca pesan dari file JSON (log_messages.json)
get_log_message() {
  local key="$1"
  if [[ ! -f "$LOG_MESSAGES" ]]; then
    echo "Log file $LOG_MESSAGES tidak ditemukan."
    return
  fi
  jq -r ".${key}" "$LOG_MESSAGES" || echo "Key ${key} tidak ditemukan di $LOG_MESSAGES."
}

# Fungsi sederhana untuk mencatat log
log() {
  local level="$1"
  local message="$2"
  local timestamp
  timestamp=$(date '+%d-%m-%Y %H:%M:%S')
  echo "$timestamp - $level: $message" | tee -a "$ERROR_LOG"
}

# Fungsi untuk URL-encode nilai menggunakan 'perl'
encode_url() {
  echo -n "$1" | perl -pe 's/([^A-Za-z0-9])/sprintf("%%%02X", ord($1))/seg'
}

###############################################################################
#                           FUNGSI VALIDASI & SETUP
###############################################################################

# Membuat folder log, mengatur kepemilikan dan izin
setup_permissions() {
  log "INFO" "Mengatur izin direktori dan file log..."
  mkdir -p "$LOG_DIR" /etc/nginx/conf.d
  chown -R abdullah:abdullah "$LOG_DIR" /etc/nginx
  chmod -R 775 "$LOG_DIR" /etc/nginx
  
  touch "$ACCESS_LOG" "$ERROR_LOG"
  chown abdullah:abdullah "$ACCESS_LOG" "$ERROR_LOG"
  chmod 664 "$ACCESS_LOG" "$ERROR_LOG"
  
  log "INFO" "$(get_log_message 'proxy.permissions.permissions_set')"
}

# Memastikan file konfigurasi yang diperlukan tersedia
validate_files() {
  log "INFO" "Memvalidasi ketersediaan file konfigurasi..."
  local files=("$CREDENTIALS_FILE" "$TEMPLATE_FILE" "$RTSP_TEMPLATE")
  for file in "${files[@]}"; do
    if [[ ! -f "$file" ]]; then
      log "ERROR" "$(get_log_message 'proxy.validation.files_valid') - File tidak ditemukan: $file"
      exit 1
    fi
  done
  log "INFO" "$(get_log_message 'proxy.validation.files_valid')"
}

# Memastikan environment variable yang dibutuhkan telah di-set
validate_env() {
  log "INFO" "Memvalidasi variabel lingkungan..."
  # Muat file credentials
  if [[ ! -f "$CREDENTIALS_FILE" ]]; then
    log "ERROR" "File credentials.sh tidak ditemukan: $CREDENTIALS_FILE"
    exit 1
  fi
  source "$CREDENTIALS_FILE"
  local required_vars=("RTSP_USERNAME" "RTSP_PASSWORD" "RTSP_IP")

  for var in "${required_vars[@]}"; do
    if [[ -z "${!var:-}" ]]; then
      log "ERROR" "$(get_log_message 'proxy.validation.env_valid') - Variabel lingkungan tidak ditemukan: $var"
      exit 1
    fi
  done

  # Bersihkan password (jika ada \r\n) dan lakukan URL-encode
  RTSP_PASSWORD=$(echo -n "$RTSP_PASSWORD" | tr -d '\r\n')
  RTSP_PASSWORD_ENCODED=$(encode_url "$RTSP_PASSWORD")
  export RTSP_PASSWORD="$RTSP_PASSWORD_ENCODED"

  log "INFO" "$(get_log_message 'proxy.validation.env_valid')"
}

# Validasi URL RTSP
validate_rtsp() {
  local url="rtsp://${RTSP_USERNAME}:${RTSP_PASSWORD}@${RTSP_IP}:554/"
  log "INFO" "Memeriksa koneksi ke RTSP URL: $url"
  if ! curl --head --silent "$url" > /dev/null; then
    log "ERROR" "RTSP URL tidak dapat dijangkau: $url"
    exit 1
  fi
  log "INFO" "RTSP URL berhasil dijangkau."
}

###############################################################################
#                          FUNGSI GENERATE KONFIG
###############################################################################

generate_nginx_config() {
  log "INFO" "$(get_log_message 'proxy.config.generate_main')"
  
  if [[ ! -f "$TEMPLATE_FILE" ]]; then
    log "ERROR" "File template tidak ditemukan: $TEMPLATE_FILE"
    exit 1
  fi
  cp "$TEMPLATE_FILE" "$OUTPUT_FILE"
  log "INFO" "File template utama Nginx telah disalin ke $OUTPUT_FILE."

  log "INFO" "$(get_log_message 'proxy.config.generate_rtsp')"
  if [[ ! -f "$RTSP_TEMPLATE" ]]; then
    log "ERROR" "File RTSP template tidak ditemukan: $RTSP_TEMPLATE"
    exit 1
  fi
  envsubst '${RTSP_USERNAME} ${RTSP_PASSWORD} ${RTSP_IP}' \
    < "$RTSP_TEMPLATE" \
    > "$RTSP_OUTPUT_FILE"

  # Log isi file yang dihasilkan
  log "DEBUG" "Isi file $RTSP_OUTPUT_FILE:"
  cat "$RTSP_OUTPUT_FILE" | tee -a "$ERROR_LOG"

  # Agar mudah di-copy dengan `docker cp`, kita buat symlink:
  ln -sf "$RTSP_OUTPUT_FILE" /etc/nginx/rtsp.conf

  # Validasi sintaks Nginx
  if ! nginx -t > /dev/null 2>&1; then
    log "ERROR" "Validasi sintaks gagal: $(nginx -t 2>&1)"
    # Lampirkan isi rtsp.conf ke error.log untuk debugging
    cat "$RTSP_OUTPUT_FILE" >> "$ERROR_LOG"
    exit 1
  fi

  log "INFO" "$(get_log_message 'proxy.config.config_validated')"
}

###############################################################################
#                           FUNGSI UTAMA (MAIN)
###############################################################################
main() {
  log "INFO" "$(get_log_message 'proxy.runtime.starting')"
  
  setup_permissions
  validate_files
  validate_env
  validate_rtsp
  generate_nginx_config

  log "INFO" "$(get_log_message 'proxy.runtime.started')"
  exec nginx -g 'daemon off;'
}

# Eksekusi main
main
