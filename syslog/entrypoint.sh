```bash
// filepath: /app/syslog/entrypoint.sh
#!/usr/bin/env bash
set -e

# Fungsi log singkat
log() {
  local offset_hours zone time_format="%d-%m-%Y %H:%M:%S"
  offset_hours=$(date +%z | awk '{
    sign=substr($0,1,1); hours=substr($0,2,2); minutes=substr($0,4,2);
    total=hours+(minutes/60); if(sign=="-"){total=-total}; printf "%.0f", total
  }')
  if [[ "$offset_hours" -eq 8 ]]; then
    zone="WITA"
  elif [[ "$offset_hours" -eq 7 ]]; then
    zone="WIB"
  else
    zone="UTC"
  fi
  echo "$(date +"$time_format") $zone - $1"
}

LOG_MESSAGES_FILE_PATH="${LOG_MESSAGES_FILE_PATH:-"/app/syslog/config/log_messages.json"}"
CONFIG_SOURCE="/app/syslog/config/logrotate/syslog-ng"
CONFIG_TARGET="/etc/logrotate.d/syslog-ng"
LOGROTATE_STATE_FILE="/app/syslog/logrotate/logrotate.status"
LOGROTATE_LOG="/app/syslog/logrotate/logrotate.log"
CRON_FILE="/app/syslog/crontabs/root"
CRON_JOB="0 * * * * /usr/sbin/logrotate /app/syslog/logrotate/syslog-ng >> /var/log/cron-custom.log 2>&1"

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

load_messages

log "Membersihkan /mnt/Data/Syslog..."
sudo -u root bash -c '
set -x
rm -rf /mnt/Data/Syslog/*
mkdir -p /mnt/Data/Syslog/{default,test,debug}
touch /mnt/Data/Syslog/default/default.log
touch /mnt/Data/Syslog/test/test.log
touch /mnt/Data/Syslog/debug/debug.log
'

log "$(get_message "entrypoint.ensure_state_dir")"
mkdir -p "$(dirname "$LOGROTATE_STATE_FILE")"

log "$(get_message "entrypoint.check_logrotate_config")"
if [[ ! -f "$CONFIG_SOURCE" ]]; then
  log "$(get_message "entrypoint.config_not_found")"
  /app/syslog/config/generate_rotate.sh
  log "generate_rotate.sh selesai."
else
  log "File konfigurasi logrotate $CONFIG_SOURCE sudah ada."
fi

if [[ -L "$CONFIG_TARGET" ]]; then
  log "$(get_message "entrypoint.removing_existing_symlink")"
  rm "$CONFIG_TARGET"
  log "$(get_message "entrypoint.symlink_removed")"
fi

log "$(get_message "entrypoint.clean_old_backup_files")"
find /etc/logrotate.d/backup -type f -mtime +7 -exec rm -f {} \; 2>/dev/null || true

log "Memeriksa keberadaan cron job..."
[ -f "$CRON_FILE" ] || touch "$CRON_FILE"
if ! grep -Fxq "$CRON_JOB" "$CRON_FILE"; then
  echo "$CRON_JOB" >> "$CRON_FILE"
  log "Cron job baru ditambahkan."
fi

chown root:root "$CRON_FILE"
chmod 600 "$CRON_FILE"

log "Memulai layanan cron..."
mkdir -p /var/log
touch /var/log/cron-custom.log
crond -c "$(dirname "$CRON_FILE")" -b -l 8 -L /var/log/cron.log -p /app/syslog/var-run/crond.pid || {
  log "Error: crond tidak dapat dijalankan."
  exit 1
}

log "Uji awal logrotate..."
logrotate -v -f -s "$LOGROTATE_STATE_FILE" "$CONFIG_SOURCE" >> "$LOGROTATE_LOG" 2>&1

log "$(get_message "entrypoint.start_syslog_ng")"
exec syslog-ng --foreground -f "/app/syslog/config/syslog-ng.conf"