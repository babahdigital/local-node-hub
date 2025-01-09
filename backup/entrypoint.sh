#!/usr/bin/env bash
set -e

###############################################################################
# 0. Deteksi OS (Alpine / Debian/Ubuntu) & cek tools pembuatan user
###############################################################################
check_useradd_tools() {
  if [[ -f /etc/alpine-release ]]; then
    OS_FLAVOR="alpine"
  else
    OS_FLAVOR="debian"
  fi

  if [[ "$OS_FLAVOR" == "alpine" ]]; then
    if ! command -v addgroup >/dev/null 2>&1; then
      echo "[ERROR] 'addgroup' tidak tersedia. Pastikan apk add shadow atau busybox-shadow."
      exit 1
    fi
    if ! command -v adduser  >/dev/null 2>&1; then
      echo "[ERROR] 'adduser' tidak tersedia. Pastikan apk add shadow atau busybox-shadow."
      exit 1
    fi
  else
    if ! command -v groupadd >/dev/null 2>&1; then
      echo "[ERROR] 'groupadd' tidak tersedia. Pastikan apt-get install shadow/passwd."
      exit 1
    fi
    if ! command -v useradd  >/dev/null 2>&1; then
      echo "[ERROR] 'useradd' tidak tersedia. Pastikan apt-get install shadow/passwd."
      exit 1
    fi
  fi
}

###############################################################################
# 1. Fungsi buat user+group "abdullah" jika belum ada
###############################################################################
create_user_and_group() {
  if id "abdullah" &>/dev/null; then
    echo "[INFO] User 'abdullah' sudah ada, skip creation."
    return
  fi

  echo "[INFO] Membuat user+group 'abdullah' di $OS_FLAVOR"
  if [[ "$OS_FLAVOR" == "alpine" ]]; then
    addgroup -S abdullah
    adduser  -S -G abdullah abdullah
  else
    groupadd -r abdullah
    useradd  -r -g abdullah abdullah
  fi
}

###############################################################################
# 2. Variabel dasar + tempat log, dsb.
###############################################################################
USER_OWNER="abdullah"
GROUP_OWNER="abdullah"
BASE_DIR="/mnt/Data/Syslog"
CHMOD_DIR=755
CHMOD_FILE=644

# Variabel script Python, default "/app/main.py"
APP_PYTHON_SCRIPT="${APP_PYTHON_SCRIPT:-"/app/backup/main.py"}"

###############################################################################
# 3. Fungsi logging sederhana
###############################################################################
log() {
  echo "[$(date '+%d-%m-%Y %H:%M:%S')] $*"
}

###############################################################################
# 4. Membuat folder & file sebagai user abdullah (via sudo -u) 
###############################################################################
init_folders_and_files() {
  # Pastikan 'sudo' tersedia
  if ! command -v sudo >/dev/null 2>&1; then
    echo "[ERROR] 'sudo' tidak tersedia. Skrip tidak bisa membuat folder/file sebagai user abdullah."
    exit 1
  fi

  local directories=(
    "rtsp/backup"
  )

  local files=(
    "rtsp/backup/validation.log"
    "rtsp/backup/event.log"
    "rtsp/backup/error_only.log"
  )

  # Buat folder
  for dir in "${directories[@]}"; do
    # mkdir sebagai user abdullah
    sudo -u "$USER_OWNER" mkdir -p "$BASE_DIR/$dir"
    # Optionally set permission (bisa user abdullah langsung, 
    # atau root + chown, tergantung use case)
    chown "$USER_OWNER:$GROUP_OWNER" "$BASE_DIR/$dir"
    chmod "$CHMOD_DIR" "$BASE_DIR/$dir"
    log "Folder => $BASE_DIR/$dir (owner=$USER_OWNER:$GROUP_OWNER, chmod=$CHMOD_DIR)"
  done

  # Buat file
  for f in "${files[@]}"; do
    local filepath="$BASE_DIR/$f"
    # Pastikan folder induk ada (seharusnya sudah dengan mkdir -p di atas)
    sudo -u "$USER_OWNER" mkdir -p "$(dirname "$filepath")"
    sudo -u "$USER_OWNER" touch "$filepath"
    chown "$USER_OWNER:$GROUP_OWNER" "$filepath"
    chmod "$CHMOD_FILE" "$filepath"
    log "File => $filepath (owner=$USER_OWNER:$GROUP_OWNER, chmod=$CHMOD_FILE)"
  done
}

###############################################################################
# 5. Main
###############################################################################
main() {
  # 5a. cek tool useradd / adduser
  check_useradd_tools

  # 5b. Jika punya credentials.sh => source
  if [[ -f "/app/config/credentials.sh" ]]; then
    source "/app/config/credentials.sh"
    log "[INFO] credentials.sh ditemukan, telah dimuat."
  else
    log "[WARN] /app/config/credentials.sh tidak ditemukan, lanjut tanpa cred..."
  fi

  # 5c. Buat user & group (bersifat opsional, jika root)
  create_user_and_group

  # 5d. Inisialisasi folder & file (sebagai user abdullah)
  log "Mulai inisialisasi folder & file log (via sudo -u $USER_OWNER)"
  init_folders_and_files
  log "Proses selesai. Menjalankan Python => $APP_PYTHON_SCRIPT"

  # 5e. Menjalankan Python (ganti shell)
  exec python "$APP_PYTHON_SCRIPT"
}

main