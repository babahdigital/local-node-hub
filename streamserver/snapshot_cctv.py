#!/usr/bin/env python3
"""
snapshot_cctv.py

Mengambil snapshot (frame tunggal) dari beberapa channel RTSP
(baca dari /mnt/Data/Syslog/rtsp/channel_validation.json).
Hanya channel "is_active": true yang di-snapshot.

- Reload otomatis jika file JSON berubah (dengan cek hash/mtime).
- ENV:
  * RTSP_USER_BASE64, RTSP_PASSWORD_BASE64 (user/pass)
  * DEBUG_CREDENTIALS="true"/"false"

Author: Anda
"""

import os
import sys
import time
import subprocess
import re
import hashlib

sys.path.append("/app/scripts")
from utils import decode_credentials, setup_category_logger, load_json_file

###############################################################################
# KONFIGURASI
###############################################################################
CHANNEL_VALIDATION_JSON = "/mnt/Data/Syslog/rtsp/channel_validation.json"
SNAPSHOT_DIR            = "/app/streamserver/html/snapshots"
INTERVAL_SEC            = 30

logger = setup_category_logger("RTSP")
DEBUG_CREDENTIALS = (os.getenv("DEBUG_CREDENTIALS", "false").lower() == "true")

###############################################################################
# FUNGSI BANTU
###############################################################################
def get_file_hash(filepath):
    """Menghasilkan hash MD5 file, atau None jika tidak ada."""
    if not os.path.isfile(filepath):
        return None
    try:
        md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                md5.update(chunk)
        return md5.hexdigest()
    except Exception as e:
        logger.error(f"get_file_hash({filepath}) => {e}")
        return None

def mask_rtsp_link(rtsp_link: str) -> str:
    """Mask user:pass => ****:**** dalam link RTSP."""
    pattern = re.compile(r"(rtsp://)([^:]+):([^@]+)@(.*)")
    return pattern.sub(r"\1****:****@\4", rtsp_link)

def unify_placeholder_at_signs(link: str) -> str:
    """
    Menyatukan placeholder '****:****@@...' => '****:****@...'
    agar tidak triple '@'.
    """
    pattern = re.compile(r"(\*\*\*\*:\*\*\*\*)@+")
    return pattern.sub(r"\1@", link)

def unify_consecutive_ats(link: str) -> str:
    """
    Menyatukan '@@' jadi '@' jika password tidak berakhir '@'.
    """
    return re.sub(r"@{2,}", "@", link)

def replace_credentials_in_link(link: str, user: str, pwd: str) -> str:
    """
    1) Samakan placeholder => satu '@'.
    2) Ganti '****:****@' => 'user:pwd@'.
    3) Jika pwd diakhiri '@', skip unify '@@' => '@'.
       Else unify => '@'.
    """
    link_fixed = unify_placeholder_at_signs(link)

    if "****:****@" in link_fixed:
        parts = link_fixed.split("@", 1)
        link_fixed = parts[0].replace('****:****', f'{user}:{pwd}') + "@" + parts[1]

    if pwd.endswith('@'):
        # Device butuh double '@'
        link_final = link_fixed
    else:
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
    # Minimalkan log => stdout/stderr ke DEVNULL
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return (result.returncode == 0)

def log_credentials(user: str, pwd: str):
    if DEBUG_CREDENTIALS:
        logger.info(f"[snapshot_cctv] RTSP Credentials => user={user} pass={pwd}")
    else:
        logger.info("[snapshot_cctv] RTSP Credentials => user=**** pass=****")

def log_rtsp(ch: str, rtsp_link: str, success: bool):
    """Log link RTSP, mask or plaintext depending on DEBUG_CREDENTIALS."""
    if DEBUG_CREDENTIALS:
        if success:
            logger.debug(f"[snapshot_cctv] Channel {ch} => {rtsp_link} (OK)")
        else:
            logger.warning(f"[snapshot_cctv] Gagal snapshot ch {ch} => {rtsp_link}")
    else:
        masked = mask_rtsp_link(rtsp_link)
        if success:
            logger.debug(f"[snapshot_cctv] Channel {ch} => {masked} (OK)")
        else:
            logger.warning(f"[snapshot_cctv] Gagal snapshot ch {ch} => {masked}")

###############################################################################
# MAIN
###############################################################################
def main():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    try:
        user, pwd = decode_credentials("RTSP_USER_BASE64","RTSP_PASSWORD_BASE64")
        log_credentials(user, pwd)
    except Exception as e:
        logger.error(f"[snapshot_cctv] Gagal decode kredensial => {e}")
        return

    old_hash = get_file_hash(CHANNEL_VALIDATION_JSON)
    logger.info(f"[snapshot_cctv] Mulai loop setiap {INTERVAL_SEC} detik...")

    while True:
        start = time.time()
        new_hash = get_file_hash(CHANNEL_VALIDATION_JSON)
        if new_hash != old_hash:
            # Hanya log sekali
            logger.info(f"[snapshot_cctv] Deteksi perubahan pada {CHANNEL_VALIDATION_JSON}, reload...")
            old_hash = new_hash

        # Load JSON
        data = load_json_file(CHANNEL_VALIDATION_JSON)
        if not data:
            logger.warning(f"[snapshot_cctv] {CHANNEL_VALIDATION_JSON} kosong/invalid, skip.")
            time.sleep(INTERVAL_SEC)
            continue

        # Ambil snapshot utk channel is_active
        for ch_str, info in data.items():
            if not isinstance(info, dict):
                continue
            if not info.get("is_active", False):
                continue

            raw_link = info.get("livestream_link","")
            if not raw_link:
                # skip channel tanpa link
                continue

            rtsp_final = replace_credentials_in_link(raw_link, user, pwd)
            snapshot_path = os.path.join(SNAPSHOT_DIR, f"ch_{ch_str}.jpg")

            ok = take_snapshot(rtsp_final, snapshot_path)
            log_rtsp(ch_str, rtsp_final, ok)

        elapsed = time.time() - start
        delay = INTERVAL_SEC - elapsed
        if delay < 0:
            delay = 0
        time.sleep(delay)

if __name__ == "__main__":
    main()