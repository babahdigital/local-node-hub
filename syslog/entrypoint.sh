#!/usr/bin/env bash
set -e

###############################################################################
# Fungsi log singkat (dengan zona waktu)
###############################################################################
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

  echo "$(date +"$time_format") $zone - $*"
}

###############################################################################
# Variabel dan Konfigurasi
###############################################################################
LOG_MESSAGES_FILE_PATH="${LOG_MESSAGES_FILE_PATH:-"/app/syslog/config/log_messages.json"}"
CONFIG_SOURCE="/app/syslog/config/logrotate/syslog-ng"
CONFIG_TARGET="/etc/logrotate.d/syslog-ng"
LOGROTATE_STATE_FILE="/mnt/Data/Syslog/default/logrotate/logrotate.status"
LOGROTATE_LOG="/mnt/Data/Syslog/default/logrotate/logrotate.log"
CRON_JOB="0 * * * * /usr/bin/docker compose up logrotate >> /var/log/cron-custom.log 2>&1"
CRON_FILE="/app/syslog/crontabs/root"

###############################################################################
# Load pesan dari log_messages.json
###############################################################################
load_messages() {
  local filepath="$LOG_MESSAGES_FILE_PATH"
  if [[ -f "$filepath" ]]; then
    MESSAGES="$(cat "$filepath")"
    log "$(get_message "entrypoint.load_messages_ok") $filepath"
  else
    log "$(get_message "entrypoint.load_messages_not_found") $filepath"
    exit 1
  fi
}

get_message() {
  local key="$1"
  # Gunakan jq untuk membaca kunci di JSON (jika tidak ditemukan, default kosong)
  echo "$MESSAGES" | jq -r "$key // \"\""
}

###############################################################################
# Eksekusi utama
###############################################################################
load_messages

# 1. Bersihkan folder log utama
log "$(get_message "entrypoint.cleaning_logs")"
sudo -u root bash -c '
  set -x
  rm -rf /mnt/Data/Syslog/*
  mkdir -p /mnt/Data/Syslog/{test,debug}
  mkdir -p /mnt/Data/Syslog/default/logrotate
  touch /mnt/Data/Syslog/default/default.log
  touch /mnt/Data/Syslog/test/test.log
  touch /mnt/Data/Syslog/debug/debug.log
  touch /mnt/Data/Syslog/default/logrotate/logrotate.status
  touch /mnt/Data/Syslog/default/logrotate/logrotate.log
'

# 2. Verifikasi file cron
log "$(get_message "entrypoint.verifying_cron_file")"
[ -f "$CRON_FILE" ] || touch "$CRON_FILE"
chown abdullah:abdullah "$CRON_FILE"
chmod 600 "$CRON_FILE"

# 3. Pastikan direktori state logrotate ada
log "$(get_message "entrypoint.ensure_state_dir")"
mkdir -p "$(dirname "$LOGROTATE_STATE_FILE")"
log "$(get_message "entrypoint.state_dir_created")"

# 4. Cek file konfigurasi logrotate
log "$(get_message "entrypoint.check_logrotate_config")"
if [[ ! -f "$CONFIG_SOURCE" ]]; then
  log "$(get_message "entrypoint.config_not_found")"
  log "$(get_message "entrypoint.running_generate_rotate")"
  /app/syslog/config/generate_rotate.sh
  log "$(get_message "entrypoint.generate_rotate_done")"
else
  log "$(get_message "entrypoint.config_found")"
fi

# 5. Jika ada symlink lama, hapus
if [[ -L "$CONFIG_TARGET" ]]; then
  log "$(get_message "entrypoint.removing_existing_symlink")"
  rm "$CONFIG_TARGET"
  log "$(get_message "entrypoint.symlink_removed")"
fi

# 6. Bersihkan file backup logrotate yg lebih dari 7 hari
log "$(get_message "entrypoint.clean_old_backup_files")"
find /etc/logrotate.d/backup -type f -mtime +7 -exec rm -f {} \; 2>/dev/null || true
log "$(get_message "entrypoint.old_backup_files_cleaned")"

# 7. Pastikan cron job ada
log "$(get_message "entrypoint.checking_cron_job")"
if ! grep -Fxq "$CRON_JOB" "$CRON_FILE"; then
  log "$(get_message "entrypoint.cron_job_added")"
  echo "$CRON_JOB" >> "$CRON_FILE"
fi

# 8. Mulai layanan cron
log "$(get_message "entrypoint.starting_cron")"
crond -c "$(dirname "$CRON_FILE")" -b -l 2 -p /app/syslog/var-run/crond.pid || {
  log "$(get_message "entrypoint.crond_not_found")"
  exit 1
}

# 9. Jalankan logrotate manual (force)
log "$(get_message "entrypoint.run_logrotate")"
# Redirect output logrotate ke $LOGROTATE_LOG
if logrotate -v -f -s "$LOGROTATE_STATE_FILE" "$CONFIG_TARGET" >> "$LOGROTATE_LOG" 2>&1; then
  log "$(get_message "entrypoint.logrotate_no_rotation")"
else
  log "$(get_message "entrypoint.logrotate_rotated")"
fi

# 10. Terakhir, jalankan syslog-ng
log "$(get_message "entrypoint.start_syslog_ng")"
exec syslog-ng --foreground -f "/app/syslog/config/syslog-ng.conf"