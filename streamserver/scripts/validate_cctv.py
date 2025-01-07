import os
import sys
import subprocess
import ipaddress
import time
import json
from datetime import datetime

# Pastikan folder scripts ada di PATH (jika utils.py ada di /app/scripts)
sys.path.append("/app/scripts")

from utils import (
    setup_logger,
    get_local_time,
    decode_credentials,
    generate_channels
)

###############################################################################
# KONFIGURASI & SETUP LOGGER
###############################################################################
LOG_PATH = os.getenv("LOG_PATH", "/mnt/Data/Syslog/rtsp/cctv/validation.log")
CCTV_LOG_PATH = os.getenv("CCTV_LOG_PATH", "/mnt/Data/Syslog/rtsp/cctv/cctv_status.log")

# Gunakan "RTSP-Validation" sebagai nama logger
logger = setup_logger("RTSP-Validation", LOG_PATH)

###############################################################################
# Opsi Loop & Interval
###############################################################################
LOOP_ENABLE = os.getenv("LOOP_ENABLE", "false").lower() == "true"
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # default 300 detik (5 menit)

###############################################################################
# FREEZE SENSITIVITY (Bisa diubah Dinamis)
###############################################################################
# Nilai default dari environment (misal 0.5)
DEFAULT_FREEZE_SENSITIVITY = float(os.getenv("FREEZE_SENSITIVITY", "0.5"))

# File JSON berisi resource server (contoh: /mnt/Data/Syslog/resource/resource_monitor_state.json)
RESOURCE_STATE_PATH = os.getenv("RESOURCE_STATE_PATH", "/mnt/Data/Syslog/resource/resource_monitor_state.json")

###############################################################################
# FUNGSI MEMBACA RESOURCE STATE JSON
###############################################################################
def read_resource_state(json_path: str) -> dict:
    """
    Membaca file JSON resource monitor (CPU, RAM, dll.).
    Return dictionary, atau {} jika gagal.
    {
      "cpu": {"usage_percent": 0.0, ...},
      "ram": {...}, "disk": {...}, ...
    }
    """
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        logger.warning(f"Resource JSON {json_path} tidak ditemukan.")
    except Exception as e:
        logger.error(f"Gagal membaca resource JSON {json_path}: {e}")
    return {}

###############################################################################
# FUNGSI MENENTUKAN FREEZE SENSITIVITY (OTOMATIS)
###############################################################################
def get_dynamic_freeze_sensitivity(default_sensitivity: float) -> float:
    """
    Membaca resource_usage (misal CPU usage) dari file JSON.
    Jika CPU usage tinggi => naikkan sensitivitas (agar freeze detect kurang sensitif).
    Jika CPU usage rendah => turunkan sensitivitas (lebih sensitif).
    
    Bebas Anda kustom logikanya. Contoh sederhana:
      - CPU usage > 80% => freeze_sens = default_sensitivity * 2  (kurang sensitif)
      - CPU usage < 30% => freeze_sens = default_sensitivity * 0.5
      - lainnya => default_sens
    """
    state = read_resource_state(RESOURCE_STATE_PATH)
    cpu_usage = 0.0
    if "cpu" in state and "usage_percent" in state["cpu"]:
        cpu_usage = float(state["cpu"]["usage_percent"])

    # Log resource
    logger.info(f"Resource Monitor => CPU usage: {cpu_usage}%")

    # Contoh logika penyesuaian
    if cpu_usage > 80:
        new_sens = default_sensitivity * 2.0
        logger.info(f"CPU tinggi => FREEZE_SENSITIVITY diset {new_sens:.2f}")
        return new_sens
    elif cpu_usage < 30:
        new_sens = default_sensitivity * 0.5
        logger.info(f"CPU rendah => FREEZE_SENSITIVITY diset {new_sens:.2f}")
        return new_sens
    else:
        return default_sensitivity

###############################################################################
# FUNGSI MEMBANTU (LOG STATUS)
###############################################################################
def write_status_log(channel: int, status: str) -> None:
    """
    Menulis status kamera (Online/Offline/dsb.) ke file log CCTV.
    """
    timestamp = get_local_time()
    try:
        with open(CCTV_LOG_PATH, "a") as f:
            f.write(f"{timestamp} - Channel {channel}: {status}\n")
    except IOError as e:
        logger.error(
            f"Gagal menulis ke {CCTV_LOG_PATH}: {e} "
            f"(Channel {channel}, Status: {status})"
        )

###############################################################################
# CEK BLACK FRAMES
###############################################################################
def check_black_frames(rtsp_url: str, timeout: int = 5) -> bool:
    """
    Menggunakan filter 'blackdetect' di FFmpeg untuk mendeteksi frame hitam.
    - Return True jika TIDAK ada black frames (aman).
    - Return False jika TERDETEKSI black frames.
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
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 5
        )
        # Jika "black_start" muncul di stderr => black frames => return False
        return b"black_start" not in result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout saat memeriksa frame hitam: {rtsp_url}")
        return False
    except Exception as e:
        logger.error(f"Kesalahan saat memeriksa frame hitam: {e}")
        return False

###############################################################################
# CEK FREEZE FRAMES (DENGAN SENSITIVITAS DINAMIS)
###############################################################################
def check_freeze_frames(rtsp_url: str, freeze_sensitivity: float, timeout: int = 5) -> bool:
    """
    Menggunakan filter 'freezedetect' untuk mendeteksi freeze frames.
    - freeze_sensitivity => parameter d=0.5 (misalnya) => durasi minimal freeze
    - Return True jika TIDAK ada freeze frames.
    - Return False jika freeze frames terdeteksi.
    """
    try:
        # Kita inject freeze_sensitivity ke filter "freezedetect=n=-60dB:d=..."
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
        logger.debug(f"Perintah freeze-check: {' '.join(cmd)}")

        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 5
        )
        # Jika "freeze_start" muncul => freeze frames => return False
        return b"freeze_start" not in result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout saat memeriksa freeze frames: {rtsp_url}")
        return False
    except Exception as e:
        logger.error(f"Kesalahan saat memeriksa freeze frames: {e}")
        return False

###############################################################################
# PARSE SUBNET (NVR MODE)
###############################################################################
def parse_subnet(nvr_subnet: str):
    """
    Membuat daftar IP dari subnet (misal 192.168.1.0/24).
    """
    try:
        net = ipaddress.ip_network(nvr_subnet, strict=False)
        return list(net.hosts())
    except Exception as e:
        logger.error(f"Parse subnet gagal: {nvr_subnet} => {e}")
        return []

###############################################################################
# VALIDASI RTSP STREAM
###############################################################################
def validate_rtsp_stream(rtsp_url: str, rtsp_url_log: str) -> bool:
    """
    Menggunakan ffprobe untuk cek apakah stream valid.
    - Return True jika valid, False jika invalid.
    """
    try:
        logger.info(f"Memvalidasi RTSP stream (ffprobe): {rtsp_url_log}")
        cmd = [
            "ffprobe",
            "-rtsp_transport", "tcp",
            "-v", "error",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1",
            rtsp_url
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
        )
        if result.returncode == 0:
            logger.info("RTSP stream valid.")
            return True
        else:
            stderr_txt = result.stderr.decode(errors="replace").strip()
            logger.error(f"RTSP stream tidak valid: {stderr_txt}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("Timeout saat memvalidasi RTSP stream.")
        return False
    except Exception as e:
        logger.error(f"Kesalahan tidak terduga saat memvalidasi RTSP: {e}")
        return False

###############################################################################
# VALIDASI SATU CHANNEL
###############################################################################
def validate_one_channel(ip, ch, rtsp_user, rtsp_password,
                         rtsp_subtype, do_black_check, do_freeze_check,
                         freeze_sensitivity):
    """
    Memvalidasi satu channel di satu IP:
      1) ffprobe => cek valid stream
      2) blackdetect => offline jika black frames
      3) freezedetect => offline jika freeze frames
    """
    actual_cred = f"{rtsp_user}:{rtsp_password}"
    rtsp_url_full = f"rtsp://{actual_cred}@{ip}:554/cam/realmonitor?channel={ch}&subtype={rtsp_subtype}"
    masked_cred = f"{rtsp_user}:*****"
    rtsp_url_log = f"rtsp://{masked_cred}@{ip}:554/cam/realmonitor?channel={ch}&subtype={rtsp_subtype}"

    if not validate_rtsp_stream(rtsp_url_full, rtsp_url_log):
        logger.error(f"Channel {ch} tidak valid pada IP {ip}")
        write_status_log(ch, "Offline")
        return "Offline"

    logger.info(f"Channel {ch} valid pada IP {ip}")
    write_status_log(ch, "Online")

    if do_black_check:
        ok_black = check_black_frames(rtsp_url_full, timeout=5)
        if not ok_black:
            logger.warning(f"Channel {ch} di IP {ip}: Frame hitam terdeteksi.")
            write_status_log(ch, "Offline (Black Frames)")
            return "Offline (Black Frames)"

    if do_freeze_check:
        freeze_failed_count = 0
        recheck_times = 2
        for i in range(recheck_times):
            ok_freeze = check_freeze_frames(rtsp_url_full, freeze_sensitivity, timeout=3)
            if not ok_freeze:
                freeze_failed_count += 1
            time.sleep(1)

        if freeze_failed_count >= 2:
            logger.warning(f"Channel {ch} di IP {ip}: Freeze frames terdeteksi.")
            write_status_log(ch, "Offline (Freeze Frames)")
            return "Offline (Freeze Frames)"

    return "Online"

###############################################################################
# VALIDASI SEMUA CHANNEL (SATU PUTARAN)
###############################################################################
def run_validation_once():
    """
    Menjalankan validasi satu kali untuk semua IP dan channel.
    Juga menyesuaikan freeze_sensitivity secara dinamis sebelum memulai loop.
    """
    try:
        rtsp_user, rtsp_password = decode_credentials()
    except RuntimeError as e:
        logger.error(f"Kesalahan saat mendekode kredensial: {e}")
        return

    rtsp_ip = os.getenv("RTSP_IP", "")
    rtsp_subtype = os.getenv("RTSP_SUBTYPE", "1")
    nvr_enable = os.getenv("NVR_ENABLE", "false").lower() == "true"
    nvr_subnet = os.getenv("NVR_SUBNET", "")

    if nvr_enable:
        if not nvr_subnet:
            logger.error("NVR_ENABLE=true tetapi NVR_SUBNET kosong.")
            return
        ips = parse_subnet(nvr_subnet)
        logger.info(f"[NVR-Mode] Subnet: {nvr_subnet}, total IP found: {len(ips)}")
        do_black_check = False
        do_freeze_check = False
    else:
        if not rtsp_ip:
            logger.error("Mode DVR: RTSP_IP tidak di-set.")
            return
        ips = [rtsp_ip]
        logger.info(f"[DVR-Mode] IP: {rtsp_ip}")
        do_black_check = True
        do_freeze_check = True

    channels = generate_channels()
    logger.info(f"Channels yang akan divalidasi: {channels}")

    # Dapatkan freeze_sensitivity dinamis
    freeze_sensitivity = get_dynamic_freeze_sensitivity(DEFAULT_FREEZE_SENSITIVITY)

    for ip in ips:
        for ch in channels:
            _final_status = validate_one_channel(
                ip, ch,
                rtsp_user, rtsp_password,
                rtsp_subtype,
                do_black_check, do_freeze_check,
                freeze_sensitivity
            )

    logger.info("Validasi selesai untuk semua channel.")

###############################################################################
# MAIN LOOP / SINGLE RUN
###############################################################################
def main():
    """
    Main entry point:
      - Jika LOOP_ENABLE=true, jalankan run_validation_once() setiap CHECK_INTERVAL detik.
      - Jika LOOP_ENABLE=false, jalankan run_validation_once() sekali saja.
    """
    if LOOP_ENABLE:
        logger.info(f"LOOP_ENABLE=true => Script akan mengulang setiap {CHECK_INTERVAL} detik.")
        while True:
            run_validation_once()
            logger.info(f"Menunggu {CHECK_INTERVAL} detik sebelum pengecekan ulang...")
            time.sleep(CHECK_INTERVAL)
    else:
        run_validation_once()

if __name__ == "__main__":
    main()