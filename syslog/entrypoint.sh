#!/usr/bin/env bash
set -e

#####################################
# Fungsi-fungsi bantu
#####################################

# Fungsi untuk mencatat log dengan format waktu
log() {
  local timezone=$(date +%Z)
  local time_format="%d-%m-%Y %H:%M:%S"
  echo "$(date +"$time_format $timezone") - $1"
}

# Memuat isi file JSON ke variabel MESSAGES
load_messages() {
  local filepath="/app/config/log_messages.json"
  if [[ -f "$filepath" ]]; then
    MESSAGES="$(cat "$filepath")"
    log "Pesan log_messages.json berhasil diload."
  else
    log "Error: File log_messages.json tidak ditemukan. Pastikan file tersedia di /app/config."
    exit 1
  fi
}

# Ambil pesan berdasarkan path. Misal "entrypoint.configure_timezone"
get_message() {
  local key="$1"
  # Gunakan 'jq' dengan aman; jika path tidak ada, kembalikan string kosong.
  echo "$MESSAGES" | jq -r ".$key // \"\""
}

# Fungsi untuk mengganti placeholder sederhana seperti {timezone} dengan isi variabel
replace_placeholder() {
  local text="$1"
  local placeholder="$2"
  local replacement="$3"
  # Ganti {placeholder} dengan replacement
  echo "${text//\{$placeholder\}/$replacement}"
}

#####################################
# Konfigurasi Zona Waktu
#####################################
configure_timezone() {
  local default_timezone="UTC"

  # Tampilkan pesan "entrypoint.configure_timezone" + $TIMEZONE
  local msg
  msg=$(get_message "entrypoint.configure_timezone")
  msg=$(replace_placeholder "$msg" "timezone" "$TIMEZONE")
  log "$msg"

  if [[ -n "$TIMEZONE" ]]; then
    # Jika file zoneinfo tersedia, gunakan TIMEZONE
    if [[ -f "/usr/share/zoneinfo/$TIMEZONE" ]]; then
      default_timezone="$TIMEZONE"
    else
      # Tampilkan pesan "entrypoint.timezone_invalid"
      msg=$(get_message "entrypoint.timezone_invalid")
      msg=$(replace_placeholder "$msg" "timezone" "$TIMEZONE")
      log "$msg"
    fi
  else
    # Tampilkan pesan "entrypoint.timezone_missing"
    log "$(get_message "entrypoint.timezone_missing")"
  fi

  export TZ="$default_timezone"
  ln -sf "/usr/share/zoneinfo/$default_timezone" /mnt/Data/Syslog/localtime
  echo "$default_timezone" > /mnt/Data/Syslog/timezone

  # Tampilkan pesan "entrypoint.timezone_set_custom" + $default_timezone
  msg=$(get_message "entrypoint.timezone_set_custom")
  msg=$(replace_placeholder "$msg" "timezone" "$default_timezone")
  log "$msg"
}

#####################################
# Variabel Logrotate & Syslog-ng
#####################################
CONFIG_SOURCE="/app/logrotate/syslog-ng"
CONFIG_TARGET="/etc/logrotate.d/syslog-ng"
BACKUP_DIR="/etc/logrotate.d/backup"
SYSLOG_CONF="/app/config/syslog-ng.conf"
LOGROTATE_STATE_FILE="/mnt/Data/Syslog/default/logrotate/logrotate.status"
LOGROTATE_LOG="/mnt/Data/Syslog/default/logrotate/logrotate.log"

#####################################
# Eksekusi utama
#####################################
load_messages
configure_timezone

# Pastikan direktori backup ada
log "$(get_message "entrypoint.ensure_backup_dir")"
mkdir -p "$BACKUP_DIR"
log "$(get_message "entrypoint.backup_dir_created")"

# Pastikan direktori untuk state file logrotate ada
log "$(get_message "entrypoint.ensure_state_dir")"
mkdir -p "$(dirname "$LOGROTATE_STATE_FILE")"
log "$(get_message "entrypoint.state_dir_created")"

# Validasi file konfigurasi logrotate
log "$(get_message "entrypoint.validate_logrotate_config")"
if [[ ! -f "$CONFIG_SOURCE" ]]; then
  log "$(get_message "entrypoint.config_not_found")"
  exit 1
fi

# Bersihkan file backup lama (lebih dari 7 hari)
log "$(get_message "entrypoint.clean_old_backup_files")"
find "$BACKUP_DIR" -type f -mtime +7 -exec rm -f {} \;
log "$(get_message "entrypoint.old_backup_files_cleaned")"

# Validasi symlink logrotate
log "$(get_message "entrypoint.check_symlink")"
if [[ -L "$CONFIG_TARGET" && "$(readlink -f "$CONFIG_TARGET")" == "$CONFIG_SOURCE" ]]; then
  log "$(get_message "entrypoint.symlink_valid")"
else
  log "$(get_message "entrypoint.create_symlink")"
  ln -sf "$CONFIG_SOURCE" "$CONFIG_TARGET"
  log "$(get_message "entrypoint.symlink_created")"
fi

# Jalankan logrotate manual (force)
log "$(get_message "entrypoint.run_logrotate")"
if logrotate -v -f -s "$LOGROTATE_STATE_FILE" "$CONFIG_TARGET" >> "$LOGROTATE_LOG" 2>&1; then
  log "$(get_message "entrypoint.logrotate_no_rotation")"
else
  log "$(get_message "entrypoint.logrotate_rotated")"
fi

# Terakhir, jalankan syslog-ng di foreground
log "$(get_message "entrypoint.start_syslog_ng")"
exec syslog-ng --foreground -f "$SYSLOG_CONF"