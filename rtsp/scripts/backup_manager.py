import os
import subprocess
import datetime
import time
import psutil
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from utils import load_log_messages, setup_logger, validate_backend_url
from report_manager import send_report_to_backend
from validate_cctv import validate_rtsp_stream, check_black_frames

# Load environment variables
load_dotenv()

# Load log messages
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", "/app/config/log_messages.json")
try:
    log_messages = load_log_messages(LOG_MESSAGES_FILE)
except RuntimeError as e:
    print(f"Gagal memuat pesan log: {e}")
    exit(1)

# Initialize logger
logger = setup_logger("RTSP-Backup")

# Dynamic system-based configurations
def get_dynamic_retry_delay():
    cpu_percent = psutil.cpu_percent(interval=1)
    if cpu_percent < 50:
        return 5
    elif cpu_percent < 80:
        return 10
    return 15

def get_dynamic_concurrency_limit():
    cpu_percent = psutil.cpu_percent(interval=1)
    if cpu_percent < 50:
        return 8
    elif cpu_percent < 80:
        return 4
    return 2

def get_dynamic_max_workers():
    cpu_percent = psutil.cpu_percent(interval=1)
    if cpu_percent < 50:
        return 8
    elif cpu_percent < 80:
        return 4
    return 2

# Configuration
RTSP_USERNAME = os.getenv("RTSP_USERNAME")
RTSP_PASSWORD = os.getenv("RTSP_PASSWORD")
RTSP_IP = os.getenv("RTSP_IP")
RTSP_SUBTYPE = os.getenv("RTSP_SUBTYPE", "1")
VIDEO_DURATION = int(os.getenv("VIDEO_DURATION", "10"))
CHANNELS = int(os.getenv("CHANNELS", "1"))
BACKUP_DIR = os.getenv("BACKUP_DIR", "/mnt/Data/Backup")
HEALTH_CHECK_URL = os.getenv("HEALTH_CHECK_URL", "http://127.0.0.1:8080/health")
HEALTH_CHECK_TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "50"))
BACKEND_ENDPOINT = os.getenv("BACKEND_ENDPOINT", "http://127.0.0.1:5001/api/report")

# Helper functions
def get_rtsp_url(channel):
    return f"rtsp://{RTSP_USERNAME}:{RTSP_PASSWORD}@{RTSP_IP}:554/cam/realmonitor?channel={channel}&subtype={RTSP_SUBTYPE}"

def validate_ts_file(file_path):
    try:
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", file_path, "-f", "null", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.error(log_messages["backup_manager"]["backup"]["timeout"].format(file=file_path))
        return False
    except Exception as e:
        logger.error(log_messages["general"]["unexpected_error"].format(error=str(e)))
        return False

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
                if validate_ts_file(output_file):
                    logger.info(log_messages["backup_manager"]["backup"]["success"].format(channel=channel, file=output_file))
                    payload = {"type": "backup_status", "status": "success", "channel": channel, "file": output_file}
                    send_report_to_backend(BACKEND_ENDPOINT, payload)
                else:
                    logger.error(log_messages["backup_manager"]["backup"]["invalid_file"].format(file=output_file))
            else:
                logger.error(log_messages["backup_manager"]["backup"]["invalid_file"].format(file=output_file))
        except subprocess.CalledProcessError as e:
            logger.error(log_messages["backup_manager"]["backup"]["failed"].format(channel=channel, error=e))
    else:
        logger.error(log_messages["backup_manager"]["validation"]["stream_invalid"].format(channel=channel))

def main():
    logger.info(log_messages["backup_manager"]["init_start"])
    try:
        logger.info(log_messages["backup_manager"]["health_check"]["start"].format(url=HEALTH_CHECK_URL))
        if not validate_rtsp_stream(HEALTH_CHECK_URL):
            logger.error(log_messages["backup_manager"]["health_check"]["failed"].format(timeout=HEALTH_CHECK_TIMEOUT))
            return
        logger.info(log_messages["backup_manager"]["health_check"]["success"].format(elapsed_time=HEALTH_CHECK_TIMEOUT))

        max_workers = get_dynamic_max_workers()
        concurrency_limit = get_dynamic_concurrency_limit()
        retry_delay = get_dynamic_retry_delay()

        logger.info(f"Proses backup dimulai dengan MAX_WORKERS: {max_workers}")
        logger.info(f"Concurrency limit (chunk size): {concurrency_limit}")
        logger.info(f"Retry delay antar batch: {retry_delay} detik")

        channels_to_backup = range(1, CHANNELS + 1)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for i in range(0, len(channels_to_backup), concurrency_limit):
                subset = channels_to_backup[i:i + concurrency_limit]
                logger.info(log_messages["backup_manager"]["batch"]["start"].format(channels=list(subset)))
                executor.map(backup_channel, subset)
                time.sleep(retry_delay)
    except KeyboardInterrupt:
        logger.info(log_messages["general"]["process_terminated"])
    except Exception as e:
        logger.error(log_messages["general"]["unexpected_error"].format(error=str(e)))
    finally:
        logger.info(log_messages["general"]["process_finished"])

if __name__ == "__main__":
    main()