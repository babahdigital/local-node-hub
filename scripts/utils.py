import json
import logging
from logging.handlers import SysLogHandler, RotatingFileHandler
import os
from datetime import datetime
import pytz
from dotenv import load_dotenv

load_dotenv()  # Memuat environment variables dari .env

# === Konstanta & Default ===
DEFAULT_SYSLOG_SERVER = "syslog-ng"
DEFAULT_SYSLOG_PORT = 1514
DEFAULT_LOG_DIR = "/mnt/Data/Syslog"
DEFAULT_BACKUP_LOG_DIR = f"{DEFAULT_LOG_DIR}/backup"
DEFAULT_LOG_PATH = "/mnt/Data/Syslog/rtsp/stream/stream_service.log"
DEFAULT_MESSAGES_FILE = "/app/config/log_messages.json"
TIMEZONE = os.getenv("TIMEZONE", "Asia/Makassar")

# === Environment Variables ===
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", DEFAULT_MESSAGES_FILE)
ENABLE_SYSLOG = os.getenv("ENABLE_SYSLOG", "true").lower() == "true"
SYSLOG_SERVER = os.getenv("SYSLOG_SERVER", DEFAULT_SYSLOG_SERVER)
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", DEFAULT_SYSLOG_PORT))
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

# === Load Log Messages Sekali Saja ===
def load_log_messages(file_path):
    """
    Memuat pesan log dari file JSON.
    """
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARNING] Gagal memuat pesan log dari {file_path}: {e}")
        return {}

LOG_MESSAGES = load_log_messages(LOG_MESSAGES_FILE)

# === Setup Logger ===
def setup_logger(name, log_path=DEFAULT_LOG_PATH):
    """
    Mengatur logger dengan File Handler dan optional Syslog Handler.
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
        print(f"[ERROR] Gagal mengatur file handler: {e}")

    # === Syslog Handler (Opsional) ===
    if ENABLE_SYSLOG:
        try:
            syslog_handler = SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))
            syslog_formatter = logging.Formatter(f"[{name}] %(message)s")
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            print(f"[WARNING] Gagal mengatur syslog handler: {e}")

    return logger

# === Utility untuk Log Messages ===
def get_log_message(key):
    """
    Mengambil pesan log berdasarkan kunci (key) dari LOG_MESSAGES global.
    """
    try:
        parts = key.split('.')
        data = LOG_MESSAGES
        for part in parts:
            data = data[part]
        return data
    except KeyError:
        raise RuntimeError(f"Pesan log untuk kunci '{key}' tidak ditemukan.")

# === Utility untuk Waktu Lokal ===
def get_local_time():
    """
    Mengembalikan waktu lokal (string) berdasarkan zona waktu.
    """
    try:
        local_tz = pytz.timezone(TIMEZONE)
        local_time = datetime.now(local_tz)
        return local_time.strftime('%d-%m-%Y %H:%M:%S %Z%z')
    except Exception as e:
        raise RuntimeError(f"Gagal mendapatkan waktu lokal: {e}")
