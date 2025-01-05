import os
import subprocess
import ipaddress
from datetime import datetime
import sys

# Pastikan folder scripts ada di PATH (jika utils.py ada di /app/scripts)
sys.path.append("/app/scripts")

from utils import setup_logger, get_local_time

# Konfigurasi file log utama (disesuaikan via ENV atau gunakan default)
LOG_PATH = os.getenv("LOG_PATH", "/mnt/Data/Syslog/rtsp/cctv/validation.log")
CCTV_LOG_PATH = os.getenv("CCTV_LOG_PATH", "/mnt/Data/Syslog/rtsp/cctv/cctv_status.log")

# Siapkan logger
logger = setup_logger("RTSP-Validation", LOG_PATH)

def write_status_log(channel, status):
    """
    Menulis status kamera (Online/Offline) ke file log CCTV.
    """
    timestamp = get_local_time()
    try:
        with open(CCTV_LOG_PATH, "a") as f:
            f.write(f"{timestamp} - Channel {channel}: {status}\n")
    except IOError as e:
        logger.error(f"Gagal menulis ke {CCTV_LOG_PATH}: {e}. Status: {timestamp} - Channel {channel}: {status}")

def check_black_frames(rtsp_url):
    """
    Periksa apakah frame hitam terdeteksi pada RTSP URL.
    """
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", rtsp_url,
                "-vf", "blackdetect=d=0.1:pic_th=0.98",
                "-an",
                "-t", "5",
                "-f", "null",
                "-"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10
        )
        # Jika b"black_start" terdeteksi => frame hitam
        return b"black_start" not in result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout saat memeriksa frame hitam pada URL: {rtsp_url}")
        return False
    except Exception as e:
        logger.error(f"Kesalahan tidak terduga saat memeriksa frame hitam: {e}")
        return False

def parse_subnet(nvr_subnet):
    """
    Parsing IP dari subnet NVR.
    """
    logger.info(f"Parsing subnet NVR: {nvr_subnet}")
    return list(ipaddress.ip_network(nvr_subnet, strict=False).hosts())

def validate_rtsp_stream(rtsp_url, channel):
    """
    Validasi RTSP stream menggunakan ffprobe dan memeriksa frame hitam.
    """
    try:
        logger.info(f"Validasi channel {channel} dimulai...")
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1",
                rtsp_url
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20
        )
        if result.returncode == 0 and result.stdout:
            # Jika valid, cek frame hitam
            if not check_black_frames(rtsp_url):
                logger.warning(f"Channel {channel}: Frame hitam terdeteksi.")
                write_status_log(channel, "Offline (Black Frames Detected)")
                return False
            write_status_log(channel, "Online")
            return True
        else:
            logger.error(f"Channel {channel}: Stream tidak valid.")
            write_status_log(channel, "Offline")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"Channel {channel}: Timeout saat validasi.")
        write_status_log(channel, "Offline (Timeout)")
        return False
    except Exception as e:
        logger.error(f"Channel {channel}: Kesalahan tidak terduga: {e}")
        write_status_log(channel, f"Offline (Error: {e})")
        return False

def main():
    """
    Fungsi utama untuk memvalidasi RTSP stream dengan dukungan TEST_CHANNEL dan multi-channel.
    """
    enable_rtsp_validation = os.getenv("ENABLE_RTSP_VALIDATION", "true").lower() == "true"
    nvr_enable = os.getenv("NVR_ENABLE", "false").lower() == "true"
    rtsp_ip = os.getenv("RTSP_IP")
    rtsp_user = os.getenv("RTSP_USER")
    rtsp_password = os.getenv("RTSP_PASSWORD")
    rtsp_subtype = os.getenv("RTSP_SUBTYPE", "1")
    channels = int(os.getenv("CHANNELS", 1))
    test_channel = os.getenv("TEST_CHANNEL", "off").lower()
    nvr_subnet = os.getenv("NVR_SUBNET", "")

    if not enable_rtsp_validation:
        logger.info("ENABLE_RTSP_VALIDATION=false, semua validasi RTSP dilewati.")
        return

    if nvr_enable:
        # Jika NVR_ENABLE=true, gunakan subnet untuk mencari IP
        ips = parse_subnet(nvr_subnet)
        logger.info(f"Mode NVR diaktifkan, subnet: {nvr_subnet}, total IP: {len(ips)}")
    else:
        # Jika NVR_ENABLE=false, hanya gunakan IP tunggal
        ips = [rtsp_ip]
        logger.info(f"Mode DVR diaktifkan, menggunakan IP: {rtsp_ip}")

    # Tentukan channel yang divalidasi
    if test_channel != "off":
        # Parse TEST_CHANNEL sebagai daftar integer
        try:
            channels_to_validate = [int(ch.strip()) for ch in test_channel.split(",")]
            logger.info(f"TEST_CHANNEL={test_channel} diatur. Memvalidasi channel: {channels_to_validate}")
        except ValueError:
            logger.error(f"TEST_CHANNEL={test_channel} tidak valid. Gunakan format seperti '1' atau '1,2,3'.")
            return
    else:
        logger.info(f"TEST_CHANNEL=off. Memvalidasi semua channel (1 hingga {channels}).")
        channels_to_validate = range(1, channels + 1)

    # Validasi setiap IP dan channel
    for ip in ips:
        for channel in channels_to_validate:
            rtsp_url = f"rtsp://{rtsp_user}:{rtsp_password}@{ip}:554/cam/realmonitor?channel={channel}&subtype={rtsp_subtype}"
            logger.info(f"Memvalidasi URL: {rtsp_url}")
            validate_rtsp_stream(rtsp_url, channel)

    logger.info("Validasi selesai untuk semua channel.")

if __name__ == "__main__":
    main()