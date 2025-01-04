import os
import subprocess
from datetime import datetime
import sys

# Pastikan folder scripts ada di PATH (jika utils.py ada di /app/scripts)
sys.path.append("/app/scripts")

from utils import setup_logger, get_local_time

# Konfigurasi file log utama (bisa disesuaikan via ENV)
LOG_PATH = os.getenv("LOG_PATH", "/mnt/Data/Syslog/rtsp/cctv/validation.log")
CCTV_LOG_PATH = os.getenv("CCTV_LOG_PATH", "/mnt/Data/Syslog/rtsp/cctv/cctv_status.log")

# Siapkan logger
logger = setup_logger("RTSP-Validation", LOG_PATH)

def write_status_log(channel, status):
    """
    Menulis status kamera (Online/Offline) ke file log CCTV.
    """
    timestamp = get_local_time()
    with open(CCTV_LOG_PATH, "a") as f:
        f.write(f"{timestamp} - Channel {channel}: {status}\n")

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

def validate_rtsp_stream(rtsp_url, channel):
    """
    Validasi RTSP stream menggunakan ffprobe dan memeriksa frame hitam.
    """
    try:
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
            timeout=5
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
    Fungsi utama untuk memvalidasi semua channel berdasarkan variabel lingkungan CHANNELS.
    """
    total_channels = int(os.getenv("CHANNELS", 1))
    for channel in range(1, total_channels + 1):
        rtsp_url = (
            f"rtsp://{os.getenv('RTSP_USER')}:{os.getenv('RTSP_PASSWORD')}@"
            f"{os.getenv('RTSP_IP')}:554/cam/realmonitor?channel={channel}&"
            f"subtype={os.getenv('RTSP_SUBTYPE', '1')}"
        )
        result = validate_rtsp_stream(rtsp_url, channel)
        # Jika RTSP tidak valid, Anda bisa memutuskan exit code
        if not result:
            sys.exit(1)

if __name__ == "__main__":
    main()