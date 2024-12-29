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
from logging.handlers import SysLogHandler, RotatingFileHandler
from report_manager import send_report_to_backend

# Load environment variables
load_dotenv()

# Path ke log_messages.json
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", "/app/config/log_messages.json")

# Fungsi untuk memuat pesan log dari file JSON
def load_log_messages(file_path):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Gagal memuat pesan log dari {file_path}: {e}")

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

file_handler = RotatingFileHandler("/mnt/Data/Syslog/rtsp/backup_manager.log", maxBytes=10 * 1024 * 1024, backupCount=5)
file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%d-%m-%Y %H:%M:%S')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Fungsi untuk menghitung delay retry berdasarkan beban CPU atau I/O
def get_dynamic_retry_delay():
    cpu_percent = psutil.cpu_percent(interval=1)
    if cpu_percent < 50:
        return 5   # Tunggu 5 detik jika CPU rendah
    elif cpu_percent < 80:
        return 10  # 10 detik jika CPU sedang
    return 15      # 15 detik jika CPU tinggi

# Fungsi untuk menghitung batas concurrency berdasarkan jumlah core CPU
def get_dynamic_concurrency_limit():
    cpu_percent = psutil.cpu_percent(interval=1)
    if cpu_percent < 50:
        return 8  # Lebih banyak channel paralel jika CPU rendah
    elif cpu_percent < 80:
        return 4  # Sedang
    return 2      # Lebih sedikit jika CPU tinggi

# Dynamic scaling untuk jumlah pekerja
def get_dynamic_max_workers():
    """
    Menentukan jumlah pekerja untuk ProcessPoolExecutor 
    berdasarkan beban CPU.
    """
    cpu_percent = psutil.cpu_percent(interval=1)
    if cpu_percent < 50:
        return 8  # Maksimum 8 pekerja jika CPU rendah
    elif cpu_percent < 80:
        return 4  # Sedang
    return 2      # Minimum 2 pekerja jika CPU tinggi

# Fungsi untuk menghitung jumlah maksimal retry berdasarkan stabilitas jaringan atau jumlah kegagalan sebelumnya
def get_dynamic_max_retries():
    # Misalnya, kita bisa menggunakan jumlah kegagalan sebelumnya untuk menentukan ini
    # Untuk contoh ini, kita set nilai statis
    return 3

# Konfigurasi dari .env dengan fallback ke nilai otomatis
RTSP_USERNAME = os.getenv("RTSP_USERNAME")
RTSP_PASSWORD = os.getenv("RTSP_PASSWORD")
RTSP_IP = os.getenv("RTSP_IP")
RTSP_SUBTYPE = os.getenv("RTSP_SUBTYPE", "1")
VIDEO_DURATION = int(os.getenv("VIDEO_DURATION", "10"))
CHANNELS = int(os.getenv("CHANNELS", "1"))
BACKUP_DIR = os.getenv("BACKUP_DIR", "/mnt/Data/Backup")
MAX_RETRIES = get_dynamic_max_retries()
APP_VERSION = "1.4.0"

HEALTH_CHECK_URL = os.getenv("HEALTH_CHECK_URL", "http://127.0.0.1:8080/health")
HEALTH_CHECK_TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "50"))

SYSLOG_SERVER = os.getenv("SYSLOG_SERVER", "syslog-ng")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", "1514"))
ENABLE_SYSLOG = os.getenv("ENABLE_SYSLOG", "true").lower() == "true"

BACKEND_ENDPOINT = os.getenv("BACKEND_ENDPOINT", "http://127.0.0.1:5001/api/report")

# Fungsi untuk menghasilkan URL RTSP
def get_rtsp_url(channel):
    return f"rtsp://{RTSP_USERNAME}:{RTSP_PASSWORD}@{RTSP_IP}:554/cam/realmonitor?channel={channel}&subtype={RTSP_SUBTYPE}"

# Fungsi untuk memvalidasi stream RTSP menggunakan FFprobe
def validate_rtsp_stream(rtsp_url):
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

    # Validasi sebelum backup
    if validate_rtsp_stream(rtsp_url):
        try:
            subprocess.run(
                ["openRTSP", "-t", str(VIDEO_DURATION), "-V", rtsp_url, "-o", output_file],
                check=True
            )
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                logger.info(
                    log_messages["backup_manager"]["backup"]["success"].format(
                        channel=channel, file=output_file
                    )
                )
                payload = {
                    "type": "backup_status",
                    "status": "success",
                    "channel": channel,
                    "file": output_file,
                }
                send_report_to_backend(BACKEND_ENDPOINT, payload)
            else:
                logger.error(
                    log_messages["backup_manager"]["backup"]["invalid_file"].format(file=output_file)
                )
        except subprocess.CalledProcessError as e:
            logger.error(
                log_messages["backup_manager"]["backup"]["failed"].format(channel=channel, error=e)
            )
    else:
        logger.error(
            log_messages["backup_manager"]["validation"]["stream_invalid"].format(channel=channel)
        )

# Fungsi utama
def main():
    logger.info(log_messages["backup_manager"]["init_start"])
    try:
        # Health check awal (opsional, bisa diganti atau dimatikan jika tidak dibutuhkan)
        logger.info(log_messages["backup_manager"]["health_check"]["start"].format(url=HEALTH_CHECK_URL))
        if not validate_rtsp_stream(HEALTH_CHECK_URL):
            logger.error(log_messages["backup_manager"]["health_check"]["failed"].format(timeout=HEALTH_CHECK_TIMEOUT))
            return
        logger.info(log_messages["backup_manager"]["health_check"]["success"].format(elapsed_time=HEALTH_CHECK_TIMEOUT))

        # Ambil nilai-nilai dinamis
        max_workers = get_dynamic_max_workers()
        concurrency_limit = get_dynamic_concurrency_limit()
        retry_delay = get_dynamic_retry_delay()

        logger.info(f"Proses backup dimulai dengan MAX_WORKERS: {max_workers}")
        logger.info(f"Concurrency limit (chunk size): {concurrency_limit}")
        logger.info(f"Retry delay antar batch: {retry_delay} detik")

        channels_to_backup = range(1, CHANNELS + 1)

        # Jalankan proses backup secara paralel dengan ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            for i in range(0, len(channels_to_backup), concurrency_limit):
                subset = channels_to_backup[i : i + concurrency_limit]
                logger.info(
                    log_messages["backup_manager"]["batch"]["start"].format(channels=list(subset))
                )
                executor.map(backup_channel, subset)

                # Beri jeda antar batch untuk menekan lonjakan resource
                time.sleep(retry_delay)

    except KeyboardInterrupt:
        logger.info(log_messages["general"]["process_terminated"])
    except Exception as e:
        logger.error(log_messages["general"]["unexpected_error"].format(error=str(e)))
    finally:
        logger.info(log_messages["general"]["process_finished"])

if __name__ == "__main__":
    main()