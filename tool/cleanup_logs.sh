#!/bin/bash
set -e

# Direktori log root
LOG_ROOT="/mnt/Data/Syslog"

# Fungsi mencatat aktivitas
log_activity() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_activity "Memulai pembersihan log sisa di direktori: $LOG_ROOT"

# Daftar direktori yang akan dibersihkan
DIRECTORIES=("debug" "default" "rtsp" "test")

# Pola file log yang akan dihapus
PATTERNS=(
  "*.log"  # Semua file log
  "*.log.1"  # File log rotasi level 1
  "*.gz"  # File log terkompresi
)

# Membersihkan log berdasarkan direktori dan pola
for DIR in "${DIRECTORIES[@]}"; do
  TARGET_DIR="$LOG_ROOT/$DIR"
  
  if [[ -d "$TARGET_DIR" ]]; then
    log_activity "Membersihkan log di $TARGET_DIR"
    
    for PATTERN in "${PATTERNS[@]}"; do
      find "$TARGET_DIR" -type f -name "$PATTERN" -exec rm -f {} \;
    done
    
    log_activity "Pembersihan log di $TARGET_DIR selesai."
  else
    log_activity "Direktori $TARGET_DIR tidak ditemukan, melewatkan."
  fi
done

# Verifikasi hasil pembersihan
log_activity "Pembersihan selesai. Menampilkan isi direktori log:"
find "$LOG_ROOT" -type f

log_activity "Pembersihan log sisa selesai!"