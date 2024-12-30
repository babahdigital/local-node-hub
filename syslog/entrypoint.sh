#!/usr/bin/env bash
set -e

#####################################
# Fungsi-fungsi bantu
#####################################

# Fungsi untuk mencatat log dengan format waktu dan label zona waktu
log() {
  local offset_hours
  local zone
  local time_format="%d-%m-%Y %H:%M:%S"

  # Mendapatkan offset UTC dalam jam (bulat)
  offset_hours=$(date +%z | awk '{
    sign = substr($0,1,1)
    hours = substr($0,2,2)
    minutes = substr($0,4,2)
    total = hours + (minutes / 60)
    if (sign == "-") {
      total = -total
    }
    # Membulatkan ke angka bulat terdekat
    printf "%.0f", total
  }')

  # Menentukan label zona waktu berdasarkan offset
  if [[ "$offset_hours" -eq 8 ]]; then
    zone="WITA"
  elif [[ "$offset_hours" -eq 7 ]]; then
    zone="WIB"
  else
    zone="UTC"
  fi

  echo "$(date +"$time_format") $zone - $1"
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

# Pastikan direktori backup ada
log "$(get_message "entrypoint.ensure_backup_dir")"
mkdir -p "$BACKUP_DIR"
log "$(get_message "entrypoint.backup_dir_created")"

# Pastikan direktori untuk state file logrotate ada
log "$(get_message "entrypoint.ensure_state_dir")"
mkdir -p "$(dirname "$LOGROTATE_STATE_FILE")"
log "$(get_message "entrypoint.state_dir_created")"

# **Tambahkan Logika untuk Membuat Konfigurasi Logrotate Jika Tidak Ada**
log "$(get_message "entrypoint.check_logrotate_config")"
if [[ ! -f "$CONFIG_SOURCE" ]]; then
  log "$(get_message "entrypoint.config_not_found")"
  log "Menjalankan generate_rotate.sh untuk membuat konfigurasi logrotate..."
  /app/generate_rotate.sh
  log "generate_rotate.sh selesai dijalankan."
else
  log "File konfigurasi logrotate $CONFIG_SOURCE sudah ada. Melanjutkan proses."
fi

# Menghapus symlink logrotate jika sudah ada
if [[ -L "$CONFIG_TARGET" ]]; then
  log "$(get_message "entrypoint.removing_existing_symlink")"
  rm "$CONFIG_TARGET"
  log "$(get_message "entrypoint.symlink_removed")"
fi

# Bersihkan file backup lama (lebih dari 7 hari)
log "$(get_message "entrypoint.clean_old_backup_files")"
find "$BACKUP_DIR" -type f -mtime +7 -exec rm -f {} \;
log "$(get_message "entrypoint.old_backup_files_cleaned")"

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