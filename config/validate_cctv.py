import subprocess
from utils import load_log_messages, setup_logger

# Load log messages for logging
log_messages = load_log_messages("/app/config/log_messages.json")
logger = setup_logger("RTSP-Backup")

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
            # Frame hitam terdeteksi
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error(log_messages["backup_manager"]["validation"]["stream_invalid"].format(channel=rtsp_url))
        return False
    except Exception as e:
        logger.error(log_messages["general"]["unexpected_error"].format(error=str(e)))
        return False

def validate_rtsp_stream(rtsp_url):
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
            logger.info(log_messages["backup_manager"]["validation"]["success"].format(channel=rtsp_url))
            # Cek frame hitam
            if not check_black_frames(rtsp_url):
                logger.error(log_messages["backup_manager"]["validation"]["camera_down"].format(channel=rtsp_url))
                return False
            return True
        else:
            logger.error(log_messages["backup_manager"]["validation"]["stream_invalid"].format(channel=rtsp_url))
            return False
    except subprocess.TimeoutExpired:
        logger.error(log_messages["backup_manager"]["validation"]["stream_invalid"].format(channel=rtsp_url))
        return False
    except Exception as e:
        logger.error(log_messages["general"]["unexpected_error"].format(error=str(e)))
        return False