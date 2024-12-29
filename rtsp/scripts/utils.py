import json
import logging
from logging.handlers import SysLogHandler, RotatingFileHandler
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", "/app/config/log_messages.json")
ENABLE_SYSLOG = os.getenv("ENABLE_SYSLOG", "true").lower() == "true"
SYSLOG_SERVER = os.getenv("SYSLOG_SERVER", "syslog-ng")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", "1514"))

def load_log_messages(file_path):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Gagal memuat pesan log dari {file_path}: {e}")

def setup_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if os.getenv("DEBUG", "false").lower() == "true" else logging.INFO)

    if ENABLE_SYSLOG:
        syslog_handler = SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))
        formatter = logging.Formatter('[{}] %(message)s'.format(name))
        syslog_handler.setFormatter(formatter)
        logger.addHandler(syslog_handler)

    file_handler = RotatingFileHandler("/mnt/Data/Syslog/rtsp/{}.log".format(name), maxBytes=10 * 1024 * 1024, backupCount=5)
    file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%d-%m-%Y %H:%M:%S')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger

def validate_backend_url(endpoint):
    if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
        logger.error("URL backend tidak valid: {}".format(endpoint))
        return False
    return True

def get_log_message(key):
    try:
        with open(LOG_MESSAGES_FILE, "r") as f:
            log_messages = json.load(f)
        message = log_messages["bash_entrypoint"].get(key)
        if message is None:
            raise KeyError(f"Pesan untuk kunci '{key}' tidak ditemukan di {LOG_MESSAGES_FILE}")
        return message
    except Exception as e:
        raise RuntimeError(f"Gagal memuat pesan log dari {LOG_MESSAGES_FILE}: {e}")

def get_local_time(timezone):
    tz_suffix = "WIB" if timezone == "Asia/Jakarta" else "WITA"
    return os.popen(f'TZ="{timezone}" date "+%d-%m-%Y %H:%M:%S {tz_suffix}"').read().strip()