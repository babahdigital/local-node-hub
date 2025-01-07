#!/usr/bin/env python3
"""
validate_cctv.py

Memeriksa RTSP stream (ffprobe), blackdetect, freezedetect (opsional),
dan menulis status (Online/Offline) ke cctv_status.log.

Fitur:
1) Baca data IP/Channel dari JSON (resource_monitor_state.json).
2) ffprobe => cek valid/tidak.
3) blackdetect/freezedetect => offline jika black/freeze.
4) Tulis ringkasan ke validation.log & cctv_status.log.

Menggunakan 'utils.py' untuk logging (setup_logger).
"""

import os
import sys
import subprocess
import time
import json
from datetime import datetime

# Pastikan folder scripts ada di PATH (untuk utils.py).
sys.path.append("/app/scripts")

from utils import (
    setup_logger,
    get_local_time,
    decode_credentials
)

###############################################################################
# KONFIGURASI & SETUP LOGGER
###############################################################################
LOG_PATH = os.getenv("LOG_PATH", "/mnt/Data/Syslog/rtsp/cctv/validation.log")
CCTV_LOG_PATH = os.getenv("CCTV_LOG_PATH", "/mnt/Data/Syslog/rtsp/cctv/cctv_status.log")

# Di sini kita buat logger "RTSP-Validation"
# => agar syslog-ng dapat memfilter "[RTSP-Validation]"
logger = setup_logger("RTSP-Validation", LOG_PATH)

###############################################################################
# MODE LOOP
###############################################################################
LOOP_ENABLE = os.getenv("LOOP_ENABLE", "false").lower() == "true"
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # Default 5 menit

###############################################################################
# FREEZE & BLACKDETECT CONFIG
###############################################################################
DEFAULT_FREEZE_SENSITIVITY = float(os.getenv("FREEZE_SENSITIVITY", "3.0"))
FREEZE_RECHECK_TIMES = int(os.getenv("FREEZE_RECHECK_TIMES", "3"))
FREEZE_RECHECK_DELAY = float(os.getenv("FREEZE_RECHECK_DELAY", "2.0"))
ENABLE_FREEZE_CHECK = os.getenv("ENABLE_FREEZE_CHECK", "true").lower() == "true"
FREEZE_COOLDOWN = int(os.getenv("FREEZE_COOLDOWN", "10"))

###############################################################################
# RESOURCE STATE PATH (JSON) => Ambil IP/CHANNEL dari resource_monitor
###############################################################################
RESOURCE_STATE_PATH = os.getenv("RESOURCE_STATE_PATH", "/mnt/Data/Syslog/resource/resource_monitor_state.json")

###############################################################################
# LAST ONLINE TIMESTAMP (untuk cooldown freeze)
###############################################################################
last_online_timestamp = {}

###############################################################################
# FUNGSI: LOAD JSON MONITOR
###############################################################################
def load_monitor_json(path: str) -> dict:
    """
    Membaca file JSON yang dihasilkan oleh resource_monitor.py.
    Return dict, atau {} jika gagal.
    """
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        logger.warning(f"[validate_cctv] File JSON {path} tidak ditemukan.")
        return {}
    except Exception as e:
        logger.error(f"[validate_cctv] Gagal membaca JSON {path}: {e}")
        return {}

###############################################################################
# FUNGSI BACA CPU USAGE & ATUR FREEZE SENSITIVITY
###############################################################################
def get_cpu_usage_and_sensitivity(default_sensitivity: float):
    """
    Membaca CPU usage dari resource_usage.cpu.usage_percent (file JSON),
    menyesuaikan freeze_sensitivity jika CPU usage tinggi/rendah.
    Jika CPU usage >90, skip freeze-check => return None (disable).
    """
    monitor_data = load_monitor_json(RESOURCE_STATE_PATH)
    if not monitor_data:
        logger.warning("[validate_cctv] Tidak ada data resource_usage => pakai default freeze_sens.")
        return 0.0, default_sensitivity

    resource_usage = monitor_data.get("resource_usage", {})
    cpu_dict = resource_usage.get("cpu", {})
    cpu_usage = float(cpu_dict.get("usage_percent", 0.0))

    logger.info(f"[validate_cctv] CPU usage: {cpu_usage:.1f}% => menyesuaikan freeze_sensitivity.")

    if cpu_usage > 90:
        logger.warning("[validate_cctv] CPU >90% => skip freeze-check.")
        return cpu_usage, None
    elif 80 < cpu_usage <= 90:
        new_sens = default_sensitivity * 2.0
        logger.info(f"[validate_cctv] CPU tinggi => freeze_sens={new_sens:.2f}")
        return cpu_usage, new_sens
    elif cpu_usage < 30:
        new_sens = default_sensitivity * 0.5
        logger.info(f"[validate_cctv] CPU rendah => freeze_sens={new_sens:.2f}")
        return cpu_usage, new_sens

    return cpu_usage, default_sensitivity

###############################################################################
# FUNGSI WRITE STATUS LOG
###############################################################################
def write_status_log(channel: int, status: str):
    """
    Menulis ringkasan status channel ke file cctv_status.log + mencatat timestamp.
    """
    timestamp = get_local_time()
    try:
        with open(CCTV_LOG_PATH, "a") as f:
            f.write(f"{timestamp} - Channel {channel}: {status}\n")
    except IOError as e:
        logger.error(f"[validate_cctv] Gagal menulis ke {CCTV_LOG_PATH}: {e} (Channel={channel}, Status={status})")

###############################################################################
# BLACKDETECT & FREEZEDETECT
###############################################################################
def check_black_frames(rtsp_url: str, timeout=5) -> bool:
    """
    Return True jika stream normal (TIDAK black frames).
    """
    try:
        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-vf", "blackdetect=d=0.1:pic_th=0.98",
            "-an",
            "-t", str(timeout),
            "-f", "null",
            "-"
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout+5)
        return b"black_start" not in result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"[validate_cctv] blackdetect TIMEOUT => {rtsp_url}")
        return False
    except Exception as e:
        logger.error(f"[validate_cctv] blackdetect error: {e}")
        return False

def check_freeze_frames(rtsp_url: str, freeze_sensitivity: float, timeout=5) -> bool:
    """
    Return True jika stream normal (TIDAK freeze).
    freeze_sensitivity=None => skip => True (tidak dicek).
    """
    if freeze_sensitivity is None:
        return True

    try:
        freezedetect_filter = f"freezedetect=n=-60dB:d={freeze_sensitivity}"
        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-vf", freezedetect_filter,
            "-an",
            "-t", str(timeout),
            "-f", "null",
            "-"
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout+5)
        return b"freeze_start" not in result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"[validate_cctv] freezedetect TIMEOUT => {rtsp_url}")
        return False
    except Exception as e:
        logger.error(f"[validate_cctv] freezedetect error: {e}")
        return False

###############################################################################
# VALIDASI STREAM (ffprobe)
###############################################################################
def validate_rtsp_stream(rtsp_url: str, rtsp_url_log: str) -> bool:
    """
    Memakai ffprobe => cek apakah stream valid (return True).
    """
    try:
        logger.info(f"[validate_cctv] ffprobe => {rtsp_url_log}")
        cmd = [
            "ffprobe",
            "-rtsp_transport", "tcp",
            "-v", "error",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1",
            rtsp_url
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        if result.returncode == 0:
            logger.info("[validate_cctv] RTSP stream valid.")
            return True
        else:
            stderr_txt = result.stderr.decode(errors="replace").strip()
            logger.error(f"[validate_cctv] Stream invalid => {stderr_txt}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("[validate_cctv] ffprobe TIMEOUT.")
        return False
    except Exception as e:
        logger.error(f"[validate_cctv] validate_rtsp_stream error: {e}")
        return False

###############################################################################
# VALIDASI SATU CHANNEL
###############################################################################
def validate_one_channel(ip_str, channel, rtsp_user, rtsp_pass, rtsp_subtype,
                         freeze_sens, do_black=True, do_freeze=True):
    """
    1) ffprobe => cek valid
    2) blackdetect => offline jika black frames
    3) freezedetect => offline jika freeze frames
    """
    rtsp_url_full = f"rtsp://{rtsp_user}:{rtsp_pass}@{ip_str}:554/cam/realmonitor?channel={channel}&subtype={rtsp_subtype}"
    masked_cred = f"{rtsp_user}:*****"
    rtsp_url_log = f"rtsp://{masked_cred}@{ip_str}:554/cam/realmonitor?channel={channel}&subtype={rtsp_subtype}"

    # Step 1: ffprobe
    if not validate_rtsp_stream(rtsp_url_full, rtsp_url_log):
        logger.error(f"[validate_cctv] Channel {channel} => Offline (stream invalid) IP={ip_str}")
        write_status_log(channel, "Offline")
        return "Offline"

    # Mark as Online
    logger.info(f"[validate_cctv] Channel {channel} valid (IP={ip_str}).")
    write_status_log(channel, "Online")
    last_online_timestamp[channel] = time.time()

    # Step 2: blackdetect
    if do_black:
        no_black = check_black_frames(rtsp_url_full, timeout=5)
        if not no_black:
            logger.warning(f"[validate_cctv] Channel {channel} => black frames.")
            write_status_log(channel, "Offline (Black Frames)")
            return "Offline (Black Frames)"

    # Step 3: freeze detect
    if do_freeze and ENABLE_FREEZE_CHECK and (freeze_sens is not None):
        now = time.time()
        elapsed = now - last_online_timestamp[channel]
        # Cooldown => skip freeze-check jika belum melewati FREEZE_COOLDOWN
        if elapsed < FREEZE_COOLDOWN:
            logger.info(f"[validate_cctv] Channel {channel} => skip freeze-check (cooldown {FREEZE_COOLDOWN}s).")
            return "Online"

        freeze_fail = 0
        for i in range(FREEZE_RECHECK_TIMES):
            ok_freeze = check_freeze_frames(rtsp_url_full, freeze_sens, timeout=3)
            if not ok_freeze:
                freeze_fail += 1
            if i < (FREEZE_RECHECK_TIMES - 1):
                time.sleep(FREEZE_RECHECK_DELAY)

        if freeze_fail >= FREEZE_RECHECK_TIMES:
            logger.warning(f"[validate_cctv] Channel {channel} => Freeze frames terdeteksi.")
            write_status_log(channel, "Offline (Freeze Frames)")
            return "Offline (Freeze Frames)"

    return "Online"

###############################################################################
# MENJALANKAN VALIDASI (SATU PUTARAN)
###############################################################################
def run_validation_once():
    """
    1) Baca JSON monitor => final_ips & channel_list
    2) Baca RTSP_USER/PASS
    3) Validasi tiap IP & channel
    """
    monitor_data = load_monitor_json(RESOURCE_STATE_PATH)
    if not monitor_data:
        logger.error("[validate_cctv] JSON monitor kosong => tidak bisa lanjut validasi.")
        return

    # Ambil data stream_config
    stream_config = monitor_data.get("stream_config", {})
    final_ips = stream_config.get("final_ips", [])
    channel_list = stream_config.get("channel_list", [])

    # Baca credentials
    try:
        rtsp_user, rtsp_pass = decode_credentials()
    except RuntimeError as e:
        logger.error(f"[validate_cctv] decode_credentials error => {e}")
        return

    # RTSP_SUBTYPE + NVR mode
    rtsp_subtype = stream_config.get("rtsp_subtype", "1")
    nvr_enable = bool(stream_config.get("nvr_enable", False))

    # Apakah black/freeze check?
    if nvr_enable:
        logger.info("[validate_cctv] NVR mode => skip black/freeze detection.")
        do_black_check = False
        do_freeze_check = False
    else:
        do_black_check = True
        do_freeze_check = True if ENABLE_FREEZE_CHECK else False

    # CPU usage & freeze_sensitivity
    cpu_usage, freeze_sens = get_cpu_usage_and_sensitivity(DEFAULT_FREEZE_SENSITIVITY)

    # Validasi IP => channel
    for ip_obj in final_ips:
        ip_str = ip_obj.get("ip", "")
        if not ip_str:
            continue
        if not ip_obj.get("reachable", False):
            logger.warning(f"[validate_cctv] IP={ip_str} unreachable => skip.")
            continue

        for ch in channel_list:
            validate_one_channel(
                ip_str, ch,
                rtsp_user, rtsp_pass,
                rtsp_subtype,
                freeze_sens,
                do_black=do_black_check,
                do_freeze=do_freeze_check
            )

    logger.info("[validate_cctv] Validasi selesai untuk semua channel & IP.")

###############################################################################
# MAIN LOOP / SINGLE-RUN
###############################################################################
def main():
    if LOOP_ENABLE:
        logger.info(f"[validate_cctv] LOOP_ENABLE=true => Loop setiap {CHECK_INTERVAL} detik.")
        while True:
            run_validation_once()
            logger.info(f"[validate_cctv] Menunggu {CHECK_INTERVAL} detik sebelum ulang...")
            time.sleep(CHECK_INTERVAL)
    else:
        run_validation_once()

if __name__ == "__main__":
    main()