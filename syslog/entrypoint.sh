#!/usr/bin/env bash
set -e

###############################################################################
# Fungsi log dengan zona waktu
###############################################################################
log() {
  local offset_hours zone time_format="%d-%m-%Y %H:%M:%S"
  offset_hours=$(date +%z | awk '{
    sign=substr($0,1,1);
    hours=substr($0,2,2);
    minutes=substr($0,4,2);
    total=hours+(minutes/60);
    if(sign=="-"){total=-total};
    printf "%.0f", total
  }')

  if [[ "$offset_hours" -eq 8 ]]; then
    zone="WITA"
  elif [[ "$offset_hours" -eq 7 ]]; then
    zone="WIB"
  else
    zone="UTC"
  fi

  echo "$(date +"$time_format") $zone - $*"
}

###############################################################################
# Variabel dan Konfigurasi
###############################################################################
LOG_MESSAGES_FILE_PATH="${LOG_MESSAGES_FILE_PATH:-"/app/syslog/config/log_messages.json"}"
SYSLOG_CONFIG="/app/syslog/config/syslog-ng.conf"

###############################################################################
# Load pesan dari log_messages.json
###############################################################################
load_messages() {
  local filepath="$LOG_MESSAGES_FILE_PATH"
  if [[ -f "$filepath" ]]; then
    MESSAGES="$(cat "$filepath")"
    log "$(get_message "syslog.load_messages_ok") $filepath"
  else
    log "$(get_message "syslog.load_messages_not_found")"
    exit 1
  fi
}

get_message() {
  local key="$1"
  echo "$MESSAGES" | jq -r ".${key} // \"\""
}

###############################################################################
# Eksekusi Utama (Hanya untuk syslog-ng)
###############################################################################
load_messages

log "$(get_message "syslog.init_start")"

# 1. Cek file config syslog-ng
log "$(get_message "syslog.check_config")"
if [[ -f "$SYSLOG_CONFIG" ]]; then
  log "$(get_message "syslog.config_found")"
else
  log "$(get_message "syslog.config_not_found")"
  # Di sini Anda bisa copy file default, dll.
fi

# 2. Jalankan syslog-ng
log "$(get_message "syslog.start_syslog_ng")"
exec syslog-ng --foreground -f "$SYSLOG_CONFIG"

# (Jika ada step tambahan, masukkan di atas eksekusi syslog-ng)

log "$(get_message "syslog.done")"