import os
import subprocess
import datetime
import time
import json
import requests
import psutil  # Digunakan untuk dynamic scaling
from concurrent.futures import ProcessPoolExecutor
from dotenv import load_dotenv
import logging
from logging.handlers import SysLogHandler
from report_manager import send_report_to_backend

# Load environment variables
load_dotenv()

# Konfigurasi dari .env
RTSP_USERNAME = os.getenv("RTSP_USERNAME")
RTSP_PASSWORD = os.getenv("RTSP_PASSWORD")
RTSP_IP = os.getenv("RTSP_IP")
RTSP_SUBTYPE = os.getenv("RTSP_SUBTYPE", "1")
VIDEO_DURATION = int(os.getenv("VIDEO_DURATION", "10"))
CHANNELS = int(os.getenv("CHANNELS", "1"))
CONCURRENCY_LIMIT = int(os.getenv("CONCURRENCY_LIMIT", "1"))
BACKUP_DIR = os.getenv("BACKUP_DIR", "/mnt/Data/Backup")
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "30"))
MAX_RETRIES = int(os.getenv("BACKEND_RETRIES", "3"))
APP_VERSION = "1.4.0"

HEALTH_CHECK_URL = os.getenv("HEALTH_CHECK_URL", "http://127.0.0.1:8080/health")
HEALTH_CHECK_TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "50"))

SYSLOG_SERVER = os.getenv("SYSLOG_SERVER", "syslog-ng")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", "1514"))
ENABLE_SYSLOG = os.getenv("ENABLE_SYSLOG", "true").lower() == "true"

BACKEND_ENDPOINT = os.getenv("BACKEND_ENDPOINT", "http://127.0.0.1:5001/api/report")

# Path ke log_messages.json
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", "/app/config/log_messages.json")

# Fungsi untuk memuat log pesan
def load_log_messages(file_path):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Gagal memuat pesan log dari {file_path}: {e}")

# Validasi log messages
try:
    log_messages = load_log_messages(LOG_MESSAGES_FILE)
except RuntimeError as e:
    print(e)
    exit(1)

# Setup logger
logger = logging.getLogger("RTSP-Backup")
logger.setLevel(logging.DEBUG if os.getenv("DEBUG", "false").lower() == "true" else logging.INFO)

if ENABLE_SYSLOG:
    syslog_handler = SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))
    formatter = logging.Formatter('[RTSP-BACKUP] %(message)s')
    syslog_handler.setFormatter(formatter)
    logger.addHandler(syslog_handler)

# Dynamic scaling untuk jumlah pekerja
def get_dynamic_max_workers():
    """Menentukan jumlah pekerja berdasarkan beban CPU."""
    cpu_percent = psutil.cpu_percent(interval=1)
    if cpu_percent < 50:
        return 8  # Maksimum 8 pekerja jika CPU rendah
    elif cpu_percent < 80:
        return 4  # Kurangi pekerja jika CPU sedang
    return 2  # Minimum 2 pekerja jika CPU tinggi

MAX_WORKERS = get_dynamic_max_workers()

# Fungsi untuk menghasilkan URL RTSP
def get_rtsp_url(channel):
    return f"rtsp://{RTSP_USERNAME}:{RTSP_PASSWORD}@{RTSP_IP}:554/cam/realmonitor?channel={channel}&subtype={RTSP_SUBTYPE}"

# Fungsi untuk memvalidasi stream RTSP menggunakan FFprobe
def validate_rtsp_stream(rtsp_url):
    """
    Memeriksa apakah stream RTSP tersedia menggunakan FFprobe.
    """
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1", rtsp_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )
        if result.returncode == 0 and result.stdout:
            logger.info(log_messages["backup_manager"]["validation"]["success"].format(channel=rtsp_url))
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

# Fungsi untuk melakukan backup channel menggunakan OpenRTSP
def backup_channel(channel):
    rtsp_url = get_rtsp_url(channel)
    today = datetime.date.today().strftime("%d-%m-%Y")
    channel_dir = os.path.join(BACKUP_DIR, today, f"Channel-{channel}")
    try:
        os.makedirs(channel_dir, exist_ok=True)
    except Exception as e:
        logger.error(log_messages["backup_manager"]["backup"]["dir_creation_failed"].format(channel=channel, error=e))
        return

    timestamp = datetime.datetime.now().strftime("%H-%M-%S")
    output_file = os.path.join(channel_dir, f"{timestamp}.ts")

    if validate_rtsp_stream(rtsp_url):
        try:
            subprocess.run(
                ["openRTSP", "-t", str(VIDEO_DURATION), "-V", rtsp_url, "-o", output_file],
                check=True
            )
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                logger.info(log_messages["backup_manager"]["backup"]["success"].format(channel=channel, file=output_file))
                payload = {
                    "type": "backup_status",
                    "status": "success",
                    "channel": channel,
                    "file": output_file,
                }
                send_report_to_backend(BACKEND_ENDPOINT, payload)
            else:
                logger.error(log_messages["backup_manager"]["backup"]["invalid_file"].format(file=output_file))
        except subprocess.CalledProcessError as e:
            logger.error(log_messages["backup_manager"]["backup"]["failed"].format(channel=channel, error=e))
    else:
        logger.error(log_messages["backup_manager"]["validation"]["stream_invalid"].format(channel=channel))

# Fungsi utama
def main():
    logger.info(log_messages["backup_manager"]["init_start"])
    try:
        logger.info(log_messages["backup_manager"]["health_check"]["start"].format(url=HEALTH_CHECK_URL))
        if not validate_rtsp_stream(HEALTH_CHECK_URL):
            logger.error(log_messages["backup_manager"]["health_check"]["failed"].format(timeout=HEALTH_CHECK_TIMEOUT))
            return
        logger.info(log_messages["backup_manager"]["health_check"]["success"].format(elapsed_time=HEALTH_CHECK_TIMEOUT))

        channels_to_backup = range(1, CHANNELS + 1)
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            logger.info(f"Proses backup dimulai dengan MAX_WORKERS: {MAX_WORKERS}")
            for i in range(0, len(channels_to_backup), CONCURRENCY_LIMIT):
                subset = channels_to_backup[i:i + CONCURRENCY_LIMIT]
                logger.info(log_messages["backup_manager"]["batch"]["start"].format(channels=list(subset)))
                executor.map(backup_channel, subset)
                time.sleep(RETRY_DELAY)
    except KeyboardInterrupt:
        logger.info(log_messages["general"]["process_terminated"])
    except Exception as e:
        logger.error(log_messages["general"]["unexpected_error"].format(error=str(e)))
    finally:
        logger.info(log_messages["general"]["process_finished"])

if __name__ == "__main__":
    main()