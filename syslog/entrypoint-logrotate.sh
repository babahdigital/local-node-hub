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
LOG_MESSAGES_FILE_PATH="${LOG_MESSAGES_FILE_PATH:-"/app/config/log_messages.json"}"
CONFIG_SOURCE="/app/syslog/logrotate/syslog-ng"
CONFIG_TARGET="/etc/logrotate.d/syslog-ng"
LOGROTATE_STATE_FILE="/mnt/Data/Syslog/default/logrotate/logrotate.status"
LOGROTATE_LOG="/mnt/Data/Syslog/default/logrotate/logrotate.log"
CRON_FILE="/app/syslog/logrotate/crontabs/root"
CRON_JOB="0 * * * * /usr/bin/docker compose up logrotate >> /var/log/cron-custom.log 2>&1"

# Variabel user/group dan permission default
USER_OWNER="abdullah"
GROUP_OWNER="abdullah"
CHMOD_DIR=755
CHMOD_FILE=644

# Direktori induk logs
LOG_BASE_DIR="/mnt/Data/Syslog"

###############################################################################
# Load pesan dari log_messages.json
###############################################################################
load_messages() {
  local filepath="$LOG_MESSAGES_FILE_PATH"
  if [[ -f "$filepath" ]]; then
    MESSAGES="$(cat "$filepath")"
    log "$(get_message "logrotate.load_messages_ok") $filepath"
  else
    log "$(get_message "logrotate.load_messages_not_found")"
    exit 1
  fi
}

get_message() {
  local key="$1"
  # Pastikan 'jq' telah terinstall di image/container Anda
  echo "$MESSAGES" | jq -r ".${key} // \"\""
}

###############################################################################
# Fungsi pembersihan & pembuatan ulang folder/file log
###############################################################################
clean_logs() {
  log "$(get_message "logrotate.cleaning_logs")"

  # 1. Hapus isi subfolder, bukan /mnt/Data/Syslog itu sendiri
  #    -mindepth 1 => agar tidak menghapus /mnt/Data/Syslog
  #    -delete     => menghapus file & folder di dalamnya
  #    2>/dev/null => supresi error
  find "$LOG_BASE_DIR" -mindepth 1 -delete 2>/dev/null || true

  # 2. Pastikan direktori utama tetap ada
  mkdir -p "$LOG_BASE_DIR"

  # 3. Daftar sub-direktori yang akan dibuat
  local directories=(
    "test"
    "debug"
    "auth"
    "streaming"
    "network"
    "default/logrotate"
    "resource"
  )

  # 4. Daftar file yang akan dibuat
  local files=(
    "default/default.log"
    "test/test.log"
    "debug/debug.log"
    "default/logrotate/logrotate.status"
    "default/logrotate/logrotate.log"
    "default/logrotate/cron.log"
    "auth/auth.log"
    "streaming/hls.log"
    "network/network.log"
    "resource/resource_monitor_state.json"
    "resource/resource_monitor.log"
  )

  # 5. Buat folder-folder (beserta permission & kepemilikan)
  for dir in "${directories[@]}"; do
    local dirpath="$LOG_BASE_DIR/$dir"
    mkdir -p "$dirpath"
    chown "$USER_OWNER:$GROUP_OWNER" "$dirpath"
    chmod "$CHMOD_DIR" "$dirpath"
  done

  # 6. Buat file-file (beserta permission & kepemilikan)
  for file in "${files[@]}"; do
    local filepath="$LOG_BASE_DIR/$file"
    mkdir -p "$(dirname "$filepath")"
    rm -f "$filepath"
    touch "$filepath"
    chown "$USER_OWNER:$GROUP_OWNER" "$filepath"
    chmod "$CHMOD_FILE" "$filepath"
  done

  log "INFO: Proses pembersihan dan pembuatan ulang folder/file log selesai."
}

###############################################################################
# Eksekusi Utama (Khusus untuk logrotate)
###############################################################################
load_messages

log "$(get_message "logrotate.init_start")"

# 1. Bersihkan folder log dan buat ulang
clean_logs

# 2. Verifikasi file cron
log "$(get_message "logrotate.verifying_cron_file")"
[ -f "$CRON_FILE" ] || touch "$CRON_FILE"
chown abdullah:abdullah "$CRON_FILE"
chmod 600 "$CRON_FILE"

# 3. Cek keberadaan file konfigurasi logrotate
if [[ ! -f "$CONFIG_SOURCE" ]]; then
  log "$(get_message "logrotate.config_not_found")"
  log "$(get_message "logrotate.running_generate_rotate")"
  /app/syslog/logrotate/generate_rotate.sh
  log "$(get_message "logrotate.generate_rotate_done")"
fi

# (Debug tambahan) Pastikan file logrotate benar-benar ada
if [[ -f "$CONFIG_SOURCE" ]]; then
  log "INFO: File konfigurasi logrotate ditemukan di $CONFIG_SOURCE"
else
  log "ERROR: File konfigurasi logrotate tidak ditemukan di $CONFIG_SOURCE"
  exit 1
fi

# 4. Salin atau symlink config ke /etc/logrotate.d
if [[ ! -f "$CONFIG_TARGET" ]]; then
  cp "$CONFIG_SOURCE" "$CONFIG_TARGET"
fi

# 5. Mulai cron
log "$(get_message "logrotate.start_cron")"
crond \
  -c "$(dirname "$CRON_FILE")" \
  -b \
  -l 8 \
  -L "${LOG_BASE_DIR}/default/logrotate/cron.log" \
  -p /app/syslog/var-run/crond.pid

# 6. Jalankan logrotate manual (force)
log "$(get_message "logrotate.run_force_logrotate")"
if logrotate -v -f -s "$LOGROTATE_STATE_FILE" "$CONFIG_TARGET" >> "$LOGROTATE_LOG" 2>&1; then
  log "$(get_message "logrotate.logrotate_no_rotation")"
else
  log "$(get_message "logrotate.logrotate_rotated")"
fi

# 7. Tambahkan cron job (jika belum ada)
if ! grep -Fxq "$CRON_JOB" "$CRON_FILE"; then
  echo "$CRON_JOB" >> "$CRON_FILE"
fi

log "$(get_message "logrotate.done")"