import os
import json
import logging
from logging.handlers import SysLogHandler, RotatingFileHandler
import base64
from datetime import datetime
import pytz
from dotenv import load_dotenv

load_dotenv()  # Memuat environment variables dari .env

# === Konstanta & Default ===
DEFAULT_SYSLOG_SERVER = "syslog-ng"
DEFAULT_SYSLOG_PORT = 1514
DEFAULT_LOG_DIR = "/mnt/Data/Syslog/rtsp"
DEFAULT_BACKUP_LOG_DIR = f"{DEFAULT_LOG_DIR}/backup"
DEFAULT_LOG_PATH = f"{DEFAULT_LOG_DIR}/stream/stream_service.log"
DEFAULT_MESSAGES_FILE = "/app/config/log_messages.json"
TIMEZONE = os.getenv("TIMEZONE", "Asia/Makassar")

# === Environment Variables ===
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", DEFAULT_MESSAGES_FILE)
ENABLE_SYSLOG = os.getenv("ENABLE_SYSLOG", "true").lower() == "true"
SYSLOG_SERVER = os.getenv("SYSLOG_SERVER", DEFAULT_SYSLOG_SERVER)
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", DEFAULT_SYSLOG_PORT))
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

# === Load Pesan Log ===
def load_log_messages(file_path: str) -> dict:
    """
    Memuat pesan log dari file JSON.
    """
    try:
        with open(file_path, "r") as f:
            messages = json.load(f)
            if not isinstance(messages, dict):
                raise ValueError("Format file log messages tidak valid.")
            return messages
    except FileNotFoundError:
        print(f"[WARNING] File log messages {file_path} tidak ditemukan.")
        return {}
    except json.JSONDecodeError as e:
        print(f"[WARNING] File log messages {file_path} tidak dapat di-decode: {e}")
        return {}
    except Exception as e:
        print(f"[WARNING] Gagal memuat pesan log dari {file_path}: {e}")
        return {}

LOG_MESSAGES = load_log_messages(LOG_MESSAGES_FILE)

# === Logger Utility ===
def setup_logger(name: str, log_path: str = DEFAULT_LOG_PATH) -> logging.Logger:
    """
    Mengatur logger dengan File Handler dan optional Syslog Handler.
    """
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)

    # Setup File Handler
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
        print(f"[ERROR] Gagal mengatur file handler untuk {log_path}: {e}")

    # Setup Syslog Handler (opsional)
    if ENABLE_SYSLOG:
        try:
            syslog_handler = SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))
            syslog_formatter = logging.Formatter(f"[{name}] %(message)s")
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            print(f"[WARNING] Gagal mengatur syslog handler ke {SYSLOG_SERVER}:{SYSLOG_PORT}: {e}")

    return logger

# === Fungsi Utility ===
def get_log_message(key: str) -> str:
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

def get_local_time() -> str:
    """
    Mengembalikan waktu lokal (string) berdasarkan zona waktu.
    """
    try:
        local_tz = pytz.timezone(TIMEZONE)
        local_time = datetime.now(local_tz)
        return local_time.strftime('%d-%m-%Y %H:%M:%S %Z%z')
    except Exception as e:
        raise RuntimeError(f"Gagal mendapatkan waktu lokal: {e}")

def decode_credentials() -> tuple:
    """
    Mendekode kredensial RTSP dari variabel lingkungan dengan encoding Base64.
    Mengembalikan tuple (rtsp_user, rtsp_password).
    """
    rtsp_user_base64 = os.getenv("RTSP_USER_BASE64")
    rtsp_password_base64 = os.getenv("RTSP_PASSWORD_BASE64")

    if not rtsp_user_base64 or not rtsp_password_base64:
        raise RuntimeError("Variabel RTSP_USER_BASE64 atau RTSP_PASSWORD_BASE64 tidak diset!")

    try:
        rtsp_user = base64.b64decode(rtsp_user_base64).decode("utf-8").strip()
        rtsp_password = base64.b64decode(rtsp_password_base64).decode("utf-8").strip()

        if not rtsp_user or not rtsp_password:
            raise ValueError("Kredensial RTSP tidak valid setelah decoding.")
        
        return rtsp_user, rtsp_password
    except Exception as e:
        raise RuntimeError(f"Gagal mendekode kredensial RTSP: {e}")

def generate_channels() -> list:
    """
    Menghasilkan daftar channel berdasarkan TEST_CHANNEL atau CHANNELS.
    """
    test_channel = os.getenv("TEST_CHANNEL", "off").lower()
    channels = []

    if test_channel != "off":
        try:
            channels = [int(ch.strip()) for ch in test_channel.split(",")]
        except ValueError:
            raise RuntimeError("TEST_CHANNEL tidak valid. Gunakan format '1' atau '1,2,3'.")
    else:
        try:
            total_channels = int(os.getenv("CHANNELS", 1))
            channels = list(range(1, total_channels + 1))
        except ValueError:
            raise RuntimeError("CHANNELS tidak valid; harus berupa angka.")
    
    return channels