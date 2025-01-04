import os
import subprocess
from datetime import datetime
import sys

# Pastikan folder scripts ada di PATH
sys.path.append("/app/scripts")

from utils import load_log_messages, setup_logger

# File JSON untuk pesan log
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", "/app/config/log_messages.json")
# File log utama
LOG_PATH = "/mnt/Data/Syslog/rtsp/stream/stream_service.log"

# Siapkan logger
logger = setup_logger("RTSP-Validation", LOG_PATH)

# Muat pesan log (jika Anda menggunakan load_log_messages)
log_messages = load_log_messages(LOG_MESSAGES_FILE)

def write_status_log(channel, status):
    """
    Menulis status kamera (Online/Offline) ke file log CCTV.
    """
    log_file = "/mnt/Data/Syslog/cctv/cctv_status.log"
    timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    with open(log_file, "a") as f:
        f.write(f"{timestamp} - Channel {channel}: {status}\n")

def check_black_frames(rtsp_url):
    """
    Periksa apakah frame hitam terdeteksi pada RTSP URL dengan ffmpeg filter blackdetect.
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
        # Jika string "black_start" muncul di stderr => terdeteksi frame hitam
        if b"black_start" in result.stderr:
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error(log_messages["validation"]["stream_invalid"].format(channel=rtsp_url))
        return False
    except Exception as e:
        logger.error(log_messages["general"]["unexpected_error"].format(error=str(e)))
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
            # Stream valid, selanjutnya cek frame hitam
            if not check_black_frames(rtsp_url):
                logger.error(log_messages["validation"]["camera_down"].format(channel=rtsp_url))
                write_status_log(channel, "Offline (Black Frames Detected)")
                return False
            # Jika lolos blackframe check
            write_status_log(channel, "Online")
            return True
        else:
            logger.error(log_messages["validation"]["stream_invalid"].format(channel=rtsp_url))
            write_status_log(channel, "Offline")
            return False
    except subprocess.TimeoutExpired:
        logger.error(log_messages["validation"]["stream_invalid"].format(channel=rtsp_url))
        write_status_log(channel, "Offline (Timeout)")
        return False
    except Exception as e:
        logger.error(log_messages["general"]["unexpected_error"].format(error=str(e)))
        write_status_log(channel, f"Offline (Error: {str(e)})")
        return False

def main():
    """
    Fungsi utama untuk memvalidasi semua channel berdasarkan variabel lingkungan CHANNELS.
    """
    total_channels = int(os.getenv("CHANNELS", 1))

    for channel in range(1, total_channels + 1):
        rtsp_url = f"rtsp://{os.getenv('RTSP_USER')}:{os.getenv('RTSP_PASSWORD')}@{os.getenv('RTSP_IP')}:554/cam/realmonitor?channel={channel}&subtype={os.getenv('RTSP_SUBTYPE', 1)}"
        result = validate_rtsp_stream(rtsp_url, channel)
        if not result:
            sys.exit(1)

if __name__ == "__main__":
    main()