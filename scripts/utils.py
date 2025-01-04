import json
import logging
from logging.handlers import SysLogHandler, RotatingFileHandler
import os
import subprocess
from datetime import datetime
import pytz
from dotenv import load_dotenv

load_dotenv()  # Memuat environment variables dari .env (jika ada)

# === Konstanta & Default ===
DEFAULT_SYSLOG_SERVER = "syslog-ng"
DEFAULT_SYSLOG_PORT = 1514
DEFAULT_LOG_DIR = "/mnt/Data/Syslog"
DEFAULT_BACKUP_LOG_DIR = f"{DEFAULT_LOG_DIR}/backup"
DEFAULT_LOG_PATH = "/mnt/Data/Syslog/rtsp/stream/stream_service.log"
DEFAULT_MESSAGES_FILE = "/app/config/log_messages.json"

# === Environment Variables ===
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", DEFAULT_MESSAGES_FILE)
ENABLE_SYSLOG = os.getenv("ENABLE_SYSLOG", "true").lower() == "true"
SYSLOG_SERVER = os.getenv("SYSLOG_SERVER", DEFAULT_SYSLOG_SERVER)
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", DEFAULT_SYSLOG_PORT))
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"
TIMEZONE = os.getenv("TIMEZONE", "Asia/Makassar")

# === Load Log Messages Sekali Saja ===
def load_log_messages(file_path):
    """
    Memuat pesan log dari file JSON.
    """
    with open(file_path, "r") as f:
        return json.load(f)

try:
    LOG_MESSAGES = load_log_messages(LOG_MESSAGES_FILE)
except Exception as e:
    # Jika gagal memuat log messages, kita isi dengan dict kosong agar tidak error
    print(f"[WARNING] Gagal memuat pesan log dari {LOG_MESSAGES_FILE}: {e}")
    LOG_MESSAGES = {}

def setup_logger(name, log_path=DEFAULT_LOG_PATH):
    """
    Mengatur logger dengan File Handler dan optional Syslog Handler.
    Menggunakan RotatingFileHandler untuk membatasi ukuran file log.
    """
    logger = logging.getLogger(name)

    # Hindari duplikasi handler jika logger sudah dikonfigurasi
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)

    # === File Handler ===
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        file_formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    except Exception as e:
        # Jika gagal set file handler, fallback ke console
        print(f"[ERROR] Gagal mengatur file handler: {e}")
        print("[INFO] Logging akan diarahkan ke console.")
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # === Syslog Handler (Opsional) ===
    if ENABLE_SYSLOG:
        try:
            syslog_handler = SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))
            # Format syslog bisa dibuat ringkas agar memudahkan identifikasi
            syslog_formatter = logging.Formatter(f"[{name}] %(message)s")
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            print(f"[WARNING] Gagal mengatur syslog handler: {e}")
            print("[INFO] Melewati syslog handler.")

    return logger

def validate_backend_url(endpoint, logger=None):
    """
    Validasi apakah URL backend valid (harus mulai dengan http:// atau https://).
    """
    if not (endpoint.startswith("http://") or endpoint.startswith("https://")):
        # Ambil pesan log dari LOG_MESSAGES
        if "general" in LOG_MESSAGES and "invalid_backend_url" in LOG_MESSAGES["general"]:
            msg = LOG_MESSAGES["general"]["invalid_backend_url"].format(url=endpoint)
        else:
            msg = f"URL '{endpoint}' tidak valid, harus http:// atau https://"
        if logger:
            logger.error(msg)
        return False
    return True

def get_log_message(key, logger=None):
    """
    Mengambil pesan log berdasarkan kunci (key) dari LOG_MESSAGES global.
    Jika tidak ditemukan, lempar RuntimeError atau tulis error ke logger.
    """
    try:
        parts = key.split('.')  # Misal "validation.stream_invalid"
        data = LOG_MESSAGES
        for part in parts:
            data = data[part]  # Telusuri hingga level paling dalam
        return data
    except KeyError:
        error_message = f"Pesan log untuk kunci '{key}' tidak ditemukan di {LOG_MESSAGES_FILE}"
        if logger:
            logger.error(error_message)
        raise RuntimeError(error_message)

def get_local_time(timezone=TIMEZONE):
    """
    Mengembalikan waktu lokal (string) berdasarkan zona waktu yang diinginkan.
    Format: DD-MM-YYYY HH:MM:SS TZ±Offset
    """
    try:
        local_tz = pytz.timezone(timezone)
        local_time = datetime.now(local_tz)
        return local_time.strftime('%d-%m-%Y %H:%M:%S %Z%z')
    except Exception as e:
        # Jika ada entry 'local_time_failed' di log_messages, gunakan itu
        if "general" in LOG_MESSAGES and "local_time_failed" in LOG_MESSAGES["general"]:
            error_message = LOG_MESSAGES["general"]["local_time_failed"].format(timezone=timezone, error=e)
        else:
            error_message = f"Gagal mendapatkan waktu lokal untuk timezone '{timezone}': {e}"
        raise RuntimeError(error_message)