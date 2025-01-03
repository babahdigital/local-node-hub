import os
import subprocess
from datetime import datetime
import sys
sys.path.append("/app/")   # Pastikan /app/ ada di PYTHONPATH
from scripts.utils import load_log_messages, setup_logger

# Load log messages for logging
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", "/app/config/log_messages.json")
logger = setup_logger("RTSP-Validation", "/mnt/Data/Syslog/cctv/cctv_status.log")

def write_status_log(channel, status):
    """
    Menulis status kamera (Online/Offline) ke file log.
    """
    log_file = "/mnt/Data/Syslog/cctv/cctv_status.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as f:
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
        if b"black_start" in result.stderr:
            return False  # Frame hitam terdeteksi
        return True
    except subprocess.TimeoutExpired:
        logger.error(log_messages["validation"]["stream_invalid"].format(channel=rtsp_url))
        return False
    except Exception as e:
        logger.error(log_messages["general"]["unexpected_error"].format(error=str(e)))
        return False

def validate_rtsp_stream(rtsp_url, channel):
    """
    Validasi RTSP stream menggunakan ffprobe lalu memeriksa frame hitam.
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
            # Stream valid, cek frame hitam
            if not check_black_frames(rtsp_url):
                logger.error(log_messages["validation"]["camera_down"].format(channel=rtsp_url))
                write_status_log(channel, "Offline (Black Frames Detected)")
                return False
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