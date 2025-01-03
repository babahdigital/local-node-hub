import json
import logging
from logging.handlers import SysLogHandler, RotatingFileHandler
import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SYSLOG_SERVER = "syslog-ng"
DEFAULT_SYSLOG_PORT = 1514
DEFAULT_LOG_DIR = "/mnt/Data/Syslog"
DEFAULT_BACKUP_LOG_DIR = f"{DEFAULT_LOG_DIR}/backup"

LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", "/app/config/log_messages.json")
ENABLE_SYSLOG = os.getenv("ENABLE_SYSLOG", "true").lower() == "true"
SYSLOG_SERVER = os.getenv("SYSLOG_SERVER", DEFAULT_SYSLOG_SERVER)
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", DEFAULT_SYSLOG_PORT))
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"
TIMEZONE = os.getenv("TIMEZONE", "Asia/Jakarta")

def load_log_messages(file_path):
    """
    Load log messages from a JSON file.
    """
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Gagal memuat pesan log dari {file_path}: {e}")

def setup_logger(name, log_path=DEFAULT_BACKUP_LOG_DIR):
    """
    Konfigurasi logger dengan handler File dan Syslog (dengan fallback).
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)

    # Handler File
    try:
        log_file_path = os.path.join(log_path, f"{name}.log")
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file_path, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%d-%m-%Y %H:%M:%S')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # Fallback: cetak error ke stdout
        print(f"Error setting up file handler: {e}")
        print("=> Fallback ke logging console saja.")
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logger.addHandler(console_handler)

    # Handler Syslog
    if ENABLE_SYSLOG:
        try:
            syslog_handler = SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))
            syslog_formatter = logging.Formatter(f'[{name}] %(message)s')
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            print(f"Error setting up syslog handler: {e}")
            print("=> Melewati syslog handler.")

    return logger

def validate_backend_url(endpoint, logger=None):
    """
    Validasi apakah URL backend valid.
    """
    try:
        log_messages = load_log_messages(LOG_MESSAGES_FILE)
    except RuntimeError as e:
        if logger:
            logger.error(f"Gagal memuat pesan log: {e}")
        return False

    if not (endpoint.startswith("http://") or endpoint.startswith("https://")):
        if logger:
            logger.error(log_messages["general"]["invalid_backend_url"].format(url=endpoint))
        return False
    return True

def get_log_message(key, logger=None):
    """
    Ambil pesan log spesifik berdasarkan kunci dari file JSON.
    """
    try:
        with open(LOG_MESSAGES_FILE, "r") as f:
            log_messages = json.load(f)
        message = log_messages.get(key)
        if message is None:
            raise KeyError(f"Pesan log untuk kunci '{key}' tidak ditemukan di {LOG_MESSAGES_FILE}")
        return message
    except Exception as e:
        error_message = f"Gagal memuat pesan log dari {LOG_MESSAGES_FILE}: {e}"
        if logger:
            logger.error(error_message)
        raise RuntimeError(error_message)

def get_local_time(timezone=TIMEZONE):
    """
    Dapatkan waktu lokal berdasarkan zona waktu.
    """
    tz_suffix = "WIB" if timezone == "Asia/Jakarta" else "WITA"
    try:
        result = subprocess.run(['date', f'TZ={timezone}', "+%d-%m-%Y %H:%M:%S"], stdout=subprocess.PIPE, text=True)
        return f"{result.stdout.strip()} {tz_suffix}"
    except Exception as e:
        try:
            log_messages = load_log_messages(LOG_MESSAGES_FILE)
            error_message = log_messages["general"]["local_time_failed"].format(timezone=timezone, error=e)
        except RuntimeError:
            error_message = f"Gagal mendapatkan waktu lokal: {e}"
        raise RuntimeError(error_message)