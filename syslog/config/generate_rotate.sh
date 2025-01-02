#!/usr/bin/env bash
set -e

log() {
  local offset_hours zone time_format="%d-%m-%Y %H:%M:%S"
  offset_hours=$(date +%z | awk '{
    sign=substr($0,1,1);hours=substr($0,2,2);minutes=substr($0,4,2);
    total=hours+(minutes/60); if(sign=="-"){total=-total}; printf "%.0f", total
  }')
  if [[ "$offset_hours" -eq 8 ]]; then zone="WITA"
  elif [[ "$offset_hours" -eq 7 ]]; then zone="WIB"
  else zone="UTC"; fi
  echo "$(date +"$time_format") $zone - $1"
}

# Di sini kita ambil path dari ENV; kalau tidak ada, default ke /app/syslog/config/log_messages.json
LOG_MESSAGES_FILE_PATH="${LOG_MESSAGES_FILE_PATH:-"/app/config/log_messages.json"}"

load_messages() {
  local filepath="$LOG_MESSAGES_FILE_PATH"
  if [[ -f "$filepath" ]]; then
    MESSAGES="$(cat "$filepath")"
    log "Pesan log_messages.json berhasil diload dari $filepath"
  else
    log "Error: File log_messages.json tidak ditemukan di $filepath"
    exit 1
  fi
}

get_message() {
  local key="$1"
  echo "$MESSAGES" | jq -r ".$key // \"\""
}

LOG_ROOT="/mnt/Data/Syslog"
CONFIG_FILE="/app/syslog/logrotate/syslog-ng"
OWNER="abdullah"
GROUP="abdullah"

load_messages
log "Memastikan direktori konfigurasi logrotate ada..."
mkdir -p "$(dirname "$CONFIG_FILE")"

if [[ ! -d "$LOG_ROOT" ]]; then
  log "Direktori log root $LOG_ROOT tidak ditemukan!"
  exit 1
fi

if [[ -f "$CONFIG_FILE" ]]; then
  log "File konfigurasi logrotate $CONFIG_FILE sudah ada. Mengabaikan pembuatan ulang."
else
  log "Membuat file konfigurasi logrotate di $CONFIG_FILE..."
  cat <<EOF > "$CONFIG_FILE"
# Generated by generate_rotate.sh
# Date: $(date '+%d-%m-%Y %H:%M:%S %Z')

EOF

  log "Memindai semua file log di $LOG_ROOT..."
  while IFS= read -r LOG_FILE; do
    cat <<EOF >> "$CONFIG_FILE"
"$LOG_FILE" {
    size 5M
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    su $OWNER $GROUP
    create 0644 $OWNER $GROUP
    postrotate
        docker exec syslog-ng kill -HUP 1 || true
    endscript
}

EOF
    log "Menambahkan konfigurasi untuk $LOG_FILE"
  done < <(find "$LOG_ROOT" -type f -name "*.log")

  log "Konfigurasi logrotate selesai. File disimpan di $CONFIG_FILE."
fi