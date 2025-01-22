#!/usr/bin/env bash
set -e

###############################################################################
# 1. Fungsi logging dengan zona waktu
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
# 2. Variabel dan Konfigurasi Dasar
###############################################################################
LOG_MESSAGES_FILE_PATH="${LOG_MESSAGES_FILE_PATH:-"/app/config/log_messages.json"}"
SYSLOG_CONFIG="/app/syslog/config/syslog-ng.conf"

# Logrotate
CONFIG_SOURCE="/app/syslog/logrotate/syslog-ng"
CONFIG_TARGET="/etc/logrotate.d/syslog-ng"
LOGROTATE_STATE_FILE="/mnt/Data/Syslog/default/logrotate/logrotate.status"
LOGROTATE_LOG="/mnt/Data/Syslog/default/logrotate/logrotate.log"
CRON_FILE="/app/syslog/logrotate/crontabs/root"
CRON_JOB="0 * * * * logrotate -v -f -s /mnt/Data/Syslog/default/logrotate/logrotate.status /etc/logrotate.d/syslog-ng >> /mnt/Data/Syslog/default/logrotate/cron.log 2>&1"

# User/Group (override if needed)
USER_OWNER="${USER_OWNER:-abdullah}"
GROUP_OWNER="${GROUP_OWNER:-abdullah}"
CHMOD_DIR=755
CHMOD_FILE=644

# Folder log base
LOG_BASE_DIR="/mnt/Data/Syslog"

# Bersihkan logs saat startup?
CLEAN_ON_STARTUP="${CLEAN_ON_STARTUP:-true}"

###############################################################################
# 3. Load pesan dari log_messages.json
###############################################################################
load_messages() {
  local filepath="$LOG_MESSAGES_FILE_PATH"
  if [[ -f "$filepath" ]]; then
    MESSAGES="$(cat "$filepath")"
    log "Memuat file log_messages.json: $filepath"
  else
    log "WARNING: File log_messages.json tidak ditemukan di $filepath"
    MESSAGES="{}"
  fi
}

get_message() {
  local key="$1"
  echo "$MESSAGES" | jq -r ".${key} // \"\""
}

###############################################################################
# 4. Bersihkan & buat folder-file log
###############################################################################
clean_logs() {
  if [[ "$CLEAN_ON_STARTUP" == "true" ]]; then
    log "Membersihkan isi $LOG_BASE_DIR (CLEAN_ON_STARTUP=true)"
    find "$LOG_BASE_DIR" -mindepth 1 -delete 2>/dev/null || true
  else
    log "CLEAN_ON_STARTUP=false, tidak menghapus log lama."
  fi

  mkdir -p "$LOG_BASE_DIR"

  local directories=(
    "default/logrotate"
    "debug"
    "test"
    "auth"
    "streaming"
    "network"
    "resource"
    "rtsp/cctv"
    "rtsp/backup"
  )

  local files=(
    "default/default.log"
    "default/logrotate/logrotate.status"
    "default/logrotate/logrotate.log"
    "default/logrotate/cron.log"
    "debug/debug.log"
    "test/test.log"
    "auth/auth.log"
    "streaming/hls.log"
    "network/network.log"
    "resource/resource_monitor.log"
    "resource/resource_monitor_error.log"
    "rtsp/channel_validation.json"
    "rtsp/cctv/cctv.log"
  )

  for dir in "${directories[@]}"; do
    mkdir -p "$LOG_BASE_DIR/$dir"
    chown "$USER_OWNER:$GROUP_OWNER" "$LOG_BASE_DIR/$dir"
    chmod "$CHMOD_DIR" "$LOG_BASE_DIR/$dir"
  done

  for file in "${files[@]}"; do
    local filepath="$LOG_BASE_DIR/$file"
    mkdir -p "$(dirname "$filepath")"
    # Jangan dihapus jika CLEAN_ON_STARTUP=false?
    # Boleh disesuaikan. Sekarang kita 'touch' agar exist
    touch "$filepath"
    chown "$USER_OWNER:$GROUP_OWNER" "$filepath"
    chmod "$CHMOD_FILE" "$filepath"
  done

  log "INFO: Proses pembuatan folder/file log selesai."
}

###############################################################################
# 5. Generate file logrotate (jika belum ada)
###############################################################################
generate_logrotate_config() {
  local CONFIG_FILE="$CONFIG_SOURCE"
  local GENERATE_LOG="$LOG_BASE_DIR/default/logrotate/generate.log"

  log "Memastikan direktori logrotate ada: $(dirname "$CONFIG_FILE")"
  mkdir -p "$(dirname "$CONFIG_FILE")"

  if [[ -f "$CONFIG_FILE" ]]; then
    log "Config logrotate sudah ada di $CONFIG_FILE (skip generate)"
    return
  fi

  log "Membuat config logrotate: $CONFIG_FILE"
  cat <<EOF > "$CONFIG_FILE"
# Babah Digital
# Generated by entrypoint.sh
# Date: $(date '+%d-%m-%Y %H:%M:%S %Z')
EOF

  log "Memindai semua file .log di $LOG_BASE_DIR"
  mapfile -t LOG_FILES < <(find "$LOG_BASE_DIR" -type f -name "*.log")

  if [[ ${#LOG_FILES[@]} -eq 0 ]]; then
    log "Tidak ditemukan file .log di $LOG_BASE_DIR"
  else
    for LOG_FILE in "${LOG_FILES[@]}"; do
      cat <<EOF >> "$CONFIG_FILE"
"$LOG_FILE" {
    size 5M
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    su $USER_OWNER $GROUP_OWNER
    create 0644 $USER_OWNER $GROUP_OWNER
    postrotate
        kill -HUP "\$(pgrep syslog-ng)" 2>/dev/null || true
    endscript
}

EOF
      log "Menambahkan logrotate config untuk: $LOG_FILE"
    done
  fi

  cp "$CONFIG_FILE" "$LOG_BASE_DIR/default/logrotate/syslog-ng.conf.generated"
  log "Salinan config logrotate => $LOG_BASE_DIR/default/logrotate/syslog-ng.conf.generated"
}

###############################################################################
# 6. Setup cron + jalankan logrotate pertama kali
###############################################################################
setup_logrotate_and_cron() {
  log "Memeriksa cron file: $CRON_FILE"
  mkdir -p "$(dirname "$CRON_FILE")"
  if [[ ! -f "$CRON_FILE" ]]; then
    touch "$CRON_FILE"
  fi
  chown "$USER_OWNER:$GROUP_OWNER" "$CRON_FILE"
  chmod 600 "$CRON_FILE"

  # Generate config jika belum ada
  if [[ ! -f "$CONFIG_SOURCE" ]]; then
    log "Config logrotate belum ada, generate..."
    generate_logrotate_config
  fi

  # Pastikan config sudah ada
  if [[ ! -f "$CONFIG_SOURCE" ]]; then
    log "ERROR: File konfigurasi logrotate tidak ditemukan di $CONFIG_SOURCE"
    exit 1
  fi

  # Salin ke /etc/logrotate.d
  if [[ ! -f "$CONFIG_TARGET" ]]; then
    cp "$CONFIG_SOURCE" "$CONFIG_TARGET"
  fi

  log "Memulai cron..."
  crond -c "$(dirname "$CRON_FILE")" -b -l 8 -L "$LOG_BASE_DIR/default/logrotate/cron.log" -p /app/syslog/var-run/crond.pid

  log "Menjalankan logrotate manual (force) sekali..."
  if logrotate -v -f -s "$LOGROTATE_STATE_FILE" "$CONFIG_TARGET" >> "$LOGROTATE_LOG" 2>&1; then
    log "Logrotate tidak memutar log (no rotation)."
  else
    log "Logrotate melakukan rotasi."
  fi

  # Tambah cron job jika belum ada
  if ! grep -Fxq "$CRON_JOB" "$CRON_FILE"; then
    echo "$CRON_JOB" >> "$CRON_FILE"
    log "Menambahkan cron job: $CRON_JOB"
  fi
}

###############################################################################
# 7. Main: Jalankan semuanya
###############################################################################
main() {
  load_messages
  clean_logs
  setup_logrotate_and_cron

  log "Memeriksa config syslog-ng: $SYSLOG_CONFIG"
  if [[ -f "$SYSLOG_CONFIG" ]]; then
    log "Config syslog-ng ditemukan."
  else
    log "WARNING: syslog-ng.conf tidak ditemukan di $SYSLOG_CONFIG"
    # cp /app/syslog/config/default.syslog-ng.conf "$SYSLOG_CONFIG" (jika perlu)
  fi

  log "Menjalankan syslog-ng (foreground) ..."
  exec syslog-ng --foreground -f "$SYSLOG_CONFIG"
}

main