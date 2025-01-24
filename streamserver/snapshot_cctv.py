#!/usr/bin/env python3
"""
snapshot_cctv.py

Mengambil snapshot (frame tunggal) dari beberapa channel RTSP
berdasarkan file /mnt/Data/Syslog/rtsp/channel_validation.json.
Hanya channel "is_active": true yang akan di-snapshot.

Reload otomatis jika file JSON berubah (mtime berubah).

ENV Variables:
- RTSP_USER_BASE64
- RTSP_PASSWORD_BASE64
- DEBUG_CREDENTIALS (opsional): "true"/"false"

Dependensi:
- ffmpeg (harus terinstall)
- utils.py (berisi decode_credentials, dsb.)
"""

import os
import sys
import time
import subprocess
import re

# Pastikan utils.py ada di /app/scripts
sys.path.append("/app/scripts")
from utils import decode_credentials, setup_category_logger, load_json_file

###############################################################################
# 1) KONFIGURASI
###############################################################################
CHANNEL_VALIDATION_JSON = "/mnt/Data/Syslog/rtsp/channel_validation.json"
SNAPSHOT_DIR            = "/app/streamserver/html/snapshots"
INTERVAL_SEC            = 30

# Siapkan logger kategori "RTSP"
logger = setup_category_logger("RTSP")

# Apakah kita menampilkan credential & link secara plaintext?
DEBUG_CREDENTIALS = (os.getenv("DEBUG_CREDENTIALS", "false").lower() == "true")

###############################################################################
# 2) FUNGSI BANTU
###############################################################################
def get_file_mtime(path: str) -> float:
    """Mengembalikan mtime file, atau 0 jika tidak ada."""
    try:
        return os.path.getmtime(path)
    except FileNotFoundError:
        return 0

def mask_rtsp_link(rtsp_link: str) -> str:
    """
    Mendeteksi pola rtsp://user:pwd@host lalu mengganti user:pwd => ****:****,
    agar password tidak tampil di log.
    """
    pattern = re.compile(r"(rtsp://)([^:]+):([^@]+)@(.*)")
    return pattern.sub(r"\1****:****@\4", rtsp_link)

def unify_placeholder_at_signs(link: str) -> str:
    """
    Mencari segmen '****:****@' di link, di mana '@' bisa berulang (@@, @@@).
    Contoh:
      "rtsp://****:****@@172.16.10.252..."
      => "rtsp://****:****@172.16.10.252..."
    """
    pattern = re.compile(r"(\*\*\*\*:\*\*\*\*)@+")
    return pattern.sub(r"\1@", link)

def unify_consecutive_ats(link: str) -> str:
    """
    Menyatukan consecutive '@' => '@'.
    'user:pass@@host' => 'user:pass@host'.

    Akan dipakai HANYA jika password TIDAK berakhir '@'.
    Jika password diakhiri '@', berarti device butuh double '@'.
    """
    return re.sub(r"@{2,}", "@", link)

def replace_credentials_in_link(link: str, user: str, pwd: str) -> str:
    """
    1) Samakan placeholder => satu '@' (****:****@@ => ****:****@).
    2) Ganti "****:****@" => "user:pwd@".
    3) Jika password TIDAK diakhiri '@', satukan consecutive '@' => '@'.
       Jika password diakhiri '@', berarti device mau double '@'.
    """
    # 1) Samakan placeholder => satu '@'
    link_fixed = unify_placeholder_at_signs(link)

    # 2) Ganti => user:pwd@
    if "****:****@" in link_fixed:
        parts = link_fixed.split("@", 1)
        link_fixed = f"{parts[0].replace('****:****', f'{user}:{pwd}')}@{parts[1]}"

    # 3) Cek apakah password berakhir '@'
    if pwd.endswith('@'):
        # SKIP unify => device butuh double '@' 
        link_final = link_fixed
    else:
        # Satukan '@@' => '@'
        link_final = unify_consecutive_ats(link_fixed)

    return link_final

def take_snapshot(rtsp_link: str, output_path: str) -> bool:
    cmd = [
        "ffmpeg", "-y",
        "-rtsp_transport", "tcp",
        "-i", rtsp_link,
        "-frames:v", "1",
        output_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return (result.returncode == 0)

def log_credentials(user: str, pwd: str):
    """
    Menampilkan credential secara plaintext jika DEBUG_CREDENTIALS=true,
    atau masked jika false.
    """
    if DEBUG_CREDENTIALS:
        logger.info("Kredensial RTSP => user=%s pass=%s", user, pwd)
    else:
        logger.info("Kredensial RTSP => user=**** pass=****")

def log_rtsp_link(ch_str: str, rtsp_link: str, success: bool):
    """
    Log link RTSP plaintext jika DEBUG_CREDENTIALS=true, 
    else masked. Log success/warning.
    """
    if DEBUG_CREDENTIALS:
        if success:
            logger.debug("Snapshot channel %s => %s (OK)", ch_str, rtsp_link)
        else:
            logger.warning("Gagal mengambil snapshot channel %s => link=%s",
                           ch_str, rtsp_link)
    else:
        masked = mask_rtsp_link(rtsp_link)
        if success:
            logger.debug("Snapshot channel %s => %s (OK)", ch_str, masked)
        else:
            logger.warning("Gagal mengambil snapshot channel %s => link=%s",
                           ch_str, masked)

###############################################################################
# 3) FUNGSI MAIN
###############################################################################
def main():
    # Pastikan folder snapshot ada
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    # 1) Load kredensial RTSP
    try:
        user, pwd = decode_credentials("RTSP_USER_BASE64", "RTSP_PASSWORD_BASE64")
        log_credentials(user, pwd)
    except Exception as e:
        logger.error("Gagal decode RTSP_USER_BASE64/RTSP_PASSWORD_BASE64: %s", e)
        return

    old_mtime = get_file_mtime(CHANNEL_VALIDATION_JSON)
    logger.info("Mulai mengambil snapshot setiap %d detik...", INTERVAL_SEC)

    while True:
        start_time = time.time()

        # Cek perubahan file JSON
        new_mtime = get_file_mtime(CHANNEL_VALIDATION_JSON)
        if new_mtime != old_mtime:
            logger.info("Terdeteksi perubahan pada %s => reload file JSON...",
                        CHANNEL_VALIDATION_JSON)
            old_mtime = new_mtime

        data = load_json_file(CHANNEL_VALIDATION_JSON)
        if not data:
            logger.warning("File %s kosong/tidak valid, skip loop.",
                           CHANNEL_VALIDATION_JSON)
            time.sleep(INTERVAL_SEC)
            continue

        # Loop channel
        for ch_str, info in data.items():
            if not isinstance(info, dict):
                continue

            if not info.get("is_active", False):
                continue

            rtsp_raw = info.get("livestream_link", "")
            if not rtsp_raw:
                continue

            # Ganti placeholder + tangani '@' 
            rtsp_final = replace_credentials_in_link(rtsp_raw, user, pwd)

            snapshot_file = os.path.join(SNAPSHOT_DIR, f"ch_{ch_str}.jpg")

            success = take_snapshot(rtsp_final, snapshot_file)
            log_rtsp_link(ch_str, rtsp_final, success)

        # Perhitungan jeda agar total loop ~INTERVAL_SEC
        elapsed = time.time() - start_time
        delay = INTERVAL_SEC - elapsed
        if delay < 0:
            delay = 0
        time.sleep(delay)

if __name__ == "__main__":
    main()