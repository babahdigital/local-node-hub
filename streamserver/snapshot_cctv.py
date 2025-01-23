#!/usr/bin/env python3
"""
snapshot_cctv.py

Mengambil snapshot (frame tunggal) dari beberapa channel RTSP
berdasarkan file /mnt/Data/Syslog/rtsp/channel_validation.json.
Hanya channel dengan "is_active": true yang akan di-snapshot.

Jika file JSON berubah (mtime berubah), skrip memuat ulang secara otomatis.

Environment Variables yang diperlukan:
--------------------------------------
- RTSP_USER_BASE64
- RTSP_PASSWORD_BASE64

Dependensi:
-----------
- ffmpeg (harus terinstall di container/host)
- utils.py (berisi fungsi logger dsb.)

Penggunaan:
-----------
Jalankan di supervisor atau sebagai service, misal:
  [program:dynamic_snapshot_cctv]
  command = /usr/bin/python3 /path/to/dynamic_snapshot_cctv.py
"""

import os
import sys
import time
import subprocess
import re
import urllib.parse

sys.path.append("/app/scripts")
from utils import decode_credentials, setup_category_logger, load_json_file

###############################################################################
# KONFIGURASI
###############################################################################
CHANNEL_VALIDATION_JSON = "/mnt/Data/Syslog/rtsp/channel_validation.json"
SNAPSHOT_DIR = "/app/streamserver/html/snapshots"
INTERVAL_SEC = 30  # Interval (detik) untuk loop snapshot

logger = setup_category_logger("RTSP")

###############################################################################
# FUNGSI BANTU
###############################################################################
def get_file_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except FileNotFoundError:
        return 0


def replace_credentials_in_link(link: str, user: str, pwd: str) -> str:
    """
    Menggantikan placeholder '****:****@' (atau ****:****@@, dll.)
    dengan user:pwd (URL-encoded) + satu '@'.

    Contoh:
      link = "rtsp://****:****@@172.16.10.252:554/cam/realmonitor?channel=1&subtype=0"
      => "rtsp://babahdigital:Admin123%40@172.16.10.252:554/cam/realmonitor?channel=1"
    """
    user_enc = urllib.parse.quote(user, safe='')
    pwd_enc  = urllib.parse.quote(pwd,  safe='')

    pattern = r"\*\*\*\*:\*\*\*\*@+"  # ****:****@ diikuti >=1 '@'
    replacement = f"{user_enc}:{pwd_enc}@"
    return re.sub(pattern, replacement, link)


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


###############################################################################
# FUNGSI MAIN
###############################################################################
def main():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    # Dekode kredensial RTSP dari environment
    try:
        user, pwd = decode_credentials("RTSP_USER_BASE64", "RTSP_PASSWORD_BASE64")
        logger.info("Berhasil memuat kredensial RTSP (user/password dimasking).")
    except Exception as e:
        logger.error("Gagal decode RTSP_USER_BASE64/RTSP_PASSWORD_BASE64: %s", e)
        return  # Stop eksekusi, tak bisa jalan tanpa kredensial

    old_mtime = get_file_mtime(CHANNEL_VALIDATION_JSON)
    logger.info("Mulai mengambil snapshot setiap %d detik...", INTERVAL_SEC)

    while True:
        start_time = time.time()

        # Periksa apakah file JSON berubah (mtime berbeda)
        new_mtime = get_file_mtime(CHANNEL_VALIDATION_JSON)
        if new_mtime != old_mtime:
            logger.info("Terdeteksi perubahan pada %s => reload file JSON...", CHANNEL_VALIDATION_JSON)
            old_mtime = new_mtime

        # Load channel_validation.json
        data = load_json_file(CHANNEL_VALIDATION_JSON)
        if not data:
            logger.warning("File %s kosong/tidak valid, skip loop ini.", CHANNEL_VALIDATION_JSON)
            time.sleep(INTERVAL_SEC)
            continue

        logger.debug("Mulai memproses %d channel untuk snapshot...", len(data))

        # Iterasi tiap channel
        for channel_str, info in data.items():
            if not isinstance(info, dict):
                logger.debug("Skip channel %s => data corrupt (not a dict).", channel_str)
                continue

            is_active = info.get("is_active", False)
            rtsp_raw_link = info.get("livestream_link", "")
            if not is_active or not rtsp_raw_link:
                logger.debug("Skip channel %s => is_active=%s, link=%s",
                             channel_str, is_active, rtsp_raw_link)
                continue

            rtsp_final_link = replace_credentials_in_link(rtsp_raw_link, user, pwd)

            snapshot_file = os.path.join(SNAPSHOT_DIR, f"ch_{channel_str}.jpg")

            success = take_snapshot(rtsp_final_link, snapshot_file)
            if success:
                logger.debug("Snapshot channel %s => %s (OK)", channel_str, snapshot_file)
            else:
                logger.warning("Gagal mengambil snapshot channel %s => link=%s",
                               channel_str, rtsp_final_link)

        # Hitung sisa waktu agar total loop ~ INTERVAL_SEC
        elapsed = time.time() - start_time
        delay = INTERVAL_SEC - elapsed
        if delay < 0:
            delay = 0
        time.sleep(delay)


if __name__ == "__main__":
    main()