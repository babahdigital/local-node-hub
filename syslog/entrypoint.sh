#!/usr/bin/env bash
set -e

log() {
  echo "$(date '+%d-%m-%Y %H:%M:%S') - $1"
}

# Load pesan dari file JSON
load_messages() {
  if [[ -f "/app/config/log_messages.json" ]]; then
    MESSAGES=$(cat /app/config/log_messages.json)
    log "Pesan log_messages.json berhasil diload."
  else
    log "Error: File log_messages.json tidak ditemukan. Pastikan file tersedia di /app/config."
    exit 1
  fi
}

# Ambil pesan dari JSON
get_message() {
  echo "$MESSAGES" | jq -r ".$1"
}

# Atur zona waktu
configure_timezone() {
  if [[ -n "$TIMEZONE" ]]; then
    log "$(get_message "configure_timezone") $TIMEZONE"
    if [[ -f "/usr/share/zoneinfo/$TIMEZONE" ]]; then
      export TZ="$TIMEZONE"
      ln -sf "/usr/share/zoneinfo/$TIMEZONE" /mnt/Data/Syslog/localtime
      echo "$TIMEZONE" > /mnt/Data/Syslog/timezone
      log "$(get_message "timezone_set_custom") $TIMEZONE"
    else
      log "$(get_message "timezone_invalid") $TIMEZONE"
      export TZ="UTC"
      ln -sf "/usr/share/zoneinfo/UTC" /mnt/Data/Syslog/localtime
      echo "UTC" > /mnt/Data/Syslog/timezone
    fi
  else
    log "$(get_message "timezone_missing")"
    export TZ="UTC"
    ln -sf "/usr/share/zoneinfo/UTC" /mnt/Data/Syslog/localtime
    echo "UTC" > /mnt/Data/Syslog/timezone
  fi
}

# Variabel logrotate
CONFIG_SOURCE="/app/logrotate/syslog-ng"
CONFIG_TARGET="/etc/logrotate.d/syslog-ng"
BACKUP_DIR="/etc/logrotate.d/backup"
SYSLOG_CONF="/app/config/syslog-ng.conf"
LOGROTATE_STATE_FILE="/mnt/Data/Syslog/default/logrotate.status"
LOGROTATE_LOG="/mnt/Data/Syslog/logrotate.log"

load_messages
configure_timezone

# Pastikan direktori backup ada
log "$(get_message "ensure_backup_dir")"
if [[ ! -d "$BACKUP_DIR" ]]; then
  mkdir -p "$BACKUP_DIR"
  log "$(get_message "backup_dir_created")"
fi

# Pastikan direktori untuk state file logrotate ada
log "$(get_message "ensure_state_dir")"
if [[ ! -d "$(dirname "$LOGROTATE_STATE_FILE")" ]]; then
  mkdir -p "$(dirname "$LOGROTATE_STATE_FILE")"
  log "$(get_message "state_dir_created")"
fi

# Validasi file konfigurasi logrotate
log "$(get_message "validate_logrotate_config")"
if [[ ! -f "$CONFIG_SOURCE" ]]; then
  log "$(get_message "config_not_found")"
  exit 1
fi

# Bersihkan file backup lama (lebih dari 7 hari)
log "$(get_message "clean_old_backup_files")"
find "$BACKUP_DIR" -type f -mtime +7 -exec rm -f {} \;
log "$(get_message "old_backup_files_cleaned")"

# Validasi symlink logrotate
log "$(get_message "check_symlink")"
if [[ -L "$CONFIG_TARGET" && "$(readlink -f "$CONFIG_TARGET")" == "$CONFIG_SOURCE" ]]; then
  log "$(get_message "symlink_valid")"
else
  log "$(get_message "create_symlink")"
  ln -sf "$CONFIG_SOURCE" "$CONFIG_TARGET"
  log "$(get_message "symlink_created")"
fi

# Jalankan logrotate manual (force)
log "$(get_message "run_logrotate")"
if logrotate -v -f -s "$LOGROTATE_STATE_FILE" "$CONFIG_TARGET" >> "$LOGROTATE_LOG" 2>&1; then
  log "$(get_message "logrotate_no_rotation")"
else
  log "$(get_message "logrotate_rotated")"
fi

# Terakhir, jalankan syslog-ng di foreground
log "$(get_message "start_syslog_ng")"
exec syslog-ng --foreground -f "$SYSLOG_CONF"
