"""
utils.py

Modul utilitas yang menyediakan:
1) Fungsi logger (opsional RotatingFileHandler, SysLogHandler, opsional StreamHandler).
2) Fungsi-fungsi umum (get_local_time, decode_credentials, dsb.).
3) Kemudahan penggunaan log kategori (LOG_CATEGORIES).

Untuk produksi (bukan dummy), disesuaikan dengan syslog-ng config dan environment .env.

Author: YourName
"""

import os
import json
import logging
import base64
import threading
from logging.handlers import SysLogHandler, RotatingFileHandler
from datetime import datetime
import pytz

# Hanya diperlukan jika kita menggunakan file .env:
from dotenv import load_dotenv


###############################################################################
# 1) MUAT ENVIRONMENT VARIABLES
###############################################################################
load_dotenv()  # Opsional: memuat variabel .env jika ada


###############################################################################
# 2) KONSTANTA & DEFAULT
###############################################################################
DEFAULT_SYSLOG_SERVER = "syslog-ng"
DEFAULT_SYSLOG_PORT = 1514

DEFAULT_LOG_DIR = "/mnt/Data/Syslog/rtsp"
DEFAULT_BACKUP_LOG_DIR = f"{DEFAULT_LOG_DIR}/backup"

# Fallback path jika kategori tidak ditemukan
DEFAULT_LOG_PATH = f"{DEFAULT_LOG_DIR}/stream/stream_service.log"
DEFAULT_MESSAGES_FILE = "/app/config/log_messages.json"

# Konfigurasi Rotating File
DEFAULT_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUP_COUNT = 5

# Timezone default jika tidak ada di environment
TIMEZONE = os.getenv("TIMEZONE", "Asia/Makassar")

# Environment fallback (untuk file pesan log, syslog, dll.)
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", DEFAULT_MESSAGES_FILE)
ENABLE_SYSLOG = os.getenv("ENABLE_SYSLOG", "false").lower() == "true"
SYSLOG_SERVER = os.getenv("SYSLOG_SERVER", DEFAULT_SYSLOG_SERVER)
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", f"{DEFAULT_SYSLOG_PORT}"))

DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

# Opsi untuk mengaktifkan File Handler & Stream Handler:
ENABLE_FILE_LOG = os.getenv("ENABLE_FILE_LOG", "false").lower() == "true"
ENABLE_STREAM_LOG = os.getenv("ENABLE_STREAM_LOG", "true").lower() == "true"


###############################################################################
# 3) KATEGORI LOG (DICTIONARY)
#    Sesuaikan path berdasarkan preferensi Anda.
###############################################################################
LOG_CATEGORIES = {
    "PERFORMANCE": {
        "description": "Mencatat metrik kinerja (CPU/RAM, dsb.).",
        "path": f"{DEFAULT_LOG_DIR}/performance/performance.log"
    },
    "BACKUP": {
        "description": "Mencatat status proses backup.",
        "path": f"{DEFAULT_LOG_DIR}/backup/backup.log"
    },
    "SECURITY": {
        "description": "Aktivitas keamanan (percobaan login, dsb.).",
        "path": f"{DEFAULT_LOG_DIR}/security/security.log"
    },
    "ALERTS": {
        "description": "Peringatan penting yang butuh perhatian segera.",
        "path": f"{DEFAULT_LOG_DIR}/alerts/alerts.log"
    },
    "AUDIT": {
        "description": "Aktivitas audit, perubahan konfigurasi/pengguna.",
        "path": f"{DEFAULT_LOG_DIR}/audit/audit.log"
    },
    "SCHEDULER": {
        "description": "Log tugas terjadwal (cron, dsb.).",
        "path": f"{DEFAULT_LOG_DIR}/scheduler/scheduler.log"
    },
    "RTSP": {
        "description": "Log aktivitas RTSP (validasi, streaming, dsb.).",
        "path": f"{DEFAULT_LOG_DIR}/rtsp/rtsp.log"
    },
    "STREAMING-HLS": {
        "description": "Log streaming HLS (FFmpeg, segmen, dsb.).",
        "path": f"{DEFAULT_LOG_DIR}/streaming/hls.log"
    },
    "NETWORK": {
        "description": "Log status jaringan (koneksi gagal, timeout, dsb.).",
        "path": f"{DEFAULT_LOG_DIR}/network/network.log"
    },
    "HDD Monitoring": {
        "description": "Log kapasitas/health disk.",
        "path": f"{DEFAULT_LOG_DIR}/hdd/hdd_monitor.log"
    },
    "Test": {
        "description": "Log pengujian (validasi fungsi, dsb.).",
        "path": f"{DEFAULT_LOG_DIR}/test/test.log"
    },
    "Debug": {
        "description": "Log level debug (untuk development).",
        "path": f"{DEFAULT_LOG_DIR}/debug/debug.log"
    },
    "Resource-Monitor": {
        "description": "Log pemantauan CPU/RAM dsb. (resource_monitor.py).",
        "path": "/mnt/Data/Syslog/resource/resource_monitor.log"
    },
    "default": {
        "description": "Fallback untuk log umum.",
        "path": DEFAULT_LOG_PATH
    },
}


###############################################################################
# 4) LOAD PESAN LOG DARI JSON (OPSIONAL)
###############################################################################
def load_log_messages(file_path: str) -> dict:
    """
    Memuat pesan log dari file JSON (opsional).
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


###############################################################################
# 5) FUNGSI UTILITY LOGGER
#    - Menggabungkan RotatingFileHandler, SysLogHandler, StreamHandler
###############################################################################
def setup_logger(logger_name: str, log_path: str) -> logging.Logger:
    """
    Membuat logger dengan opsional RotatingFileHandler, SyslogHandler, dan StreamHandler.
    Berdasarkan environment variable:
      ENABLE_SYSLOG, ENABLE_FILE_LOG, ENABLE_STREAM_LOG.

    :param logger_name: Nama logger.
    :param log_path: Path file log (jika file logging diaktifkan).
    :return: instance logging.Logger
    """
    logger = logging.getLogger(logger_name)

    # Cegah duplikasi handler jika logger sudah diset
    if logger.hasHandlers():
        return logger

    # Level log: DEBUG jika DEBUG_MODE=true, else INFO
    level = logging.DEBUG if DEBUG_MODE else logging.INFO
    logger.setLevel(level)

    formatter_file = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%d-%m-%Y %H:%M:%S'
    )

    # 1) RotatingFileHandler
    if ENABLE_FILE_LOG:
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            file_handler = RotatingFileHandler(
                filename=log_path,
                maxBytes=DEFAULT_LOG_SIZE,
                backupCount=DEFAULT_BACKUP_COUNT
            )
            file_handler.setFormatter(formatter_file)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"[ERROR] Gagal mengatur file handler untuk {log_path}: {e}")

    # 2) SyslogHandler
    if ENABLE_SYSLOG:
        try:
            syslog_handler = SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))
            syslog_formatter = logging.Formatter(f"[{logger_name}] %(message)s")
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            print(f"[WARNING] Gagal mengatur syslog handler: {SYSLOG_SERVER}:{SYSLOG_PORT} => {e}")

    # 3) StreamHandler => ke console (docker logs)
    if ENABLE_STREAM_LOG:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter_file)
        logger.addHandler(stream_handler)

    return logger


def setup_category_logger(category: str) -> logging.Logger:
    """
    Membuat logger berdasarkan kategori di LOG_CATEGORIES.
    Memudahkan mapping ke path log spesifik.
    """
    if category not in LOG_CATEGORIES:
        category = "default"
    log_path = LOG_CATEGORIES[category]["path"]
    return setup_logger(category, log_path)


def get_log_message(key: str) -> str:
    """
    Mengambil pesan log berdasarkan kunci dari LOG_MESSAGES (opsional).
    Contoh key: "error.invalid_credentials"
    """
    try:
        parts = key.split('.')
        data = LOG_MESSAGES
        for part in parts:
            data = data[part]
        return data
    except KeyError:
        raise RuntimeError(
            f"Pesan log untuk kunci '{key}' tidak ditemukan di {LOG_MESSAGES_FILE}."
        )


###############################################################################
# 6) FUNGSI UTILITY UMUM & LOCK
###############################################################################
file_write_lock = threading.Lock()  # Lock global untuk penulisan file

def get_local_time() -> str:
    """
    Mengembalikan waktu lokal dengan format:
      'dd-MM-YYYY HH:mm:ss TZZZ+Offset'
    Sesuai TIMEZONE (default "Asia/Makassar").
    """
    try:
        tz_name = TIMEZONE.strip() if TIMEZONE else ""
        if tz_name:
            local_tz = pytz.timezone(tz_name)
            local_time = datetime.now(local_tz)
        else:
            local_time = datetime.now().astimezone()
        return local_time.strftime('%d-%m-%Y %H:%M:%S %Z%z')
    except Exception:
        fallback_time = datetime.now().astimezone()
        return fallback_time.strftime('%d-%m-%Y %H:%M:%S %Z%z')


def decode_credentials(
    user_var="RTSP_USER_BASE64",
    pass_var="RTSP_PASSWORD_BASE64"
) -> tuple:
    """
    Default: Membaca RTSP_USER_BASE64 & RTSP_PASSWORD_BASE64 dari environment.
    Jika ingin user RTSP kedua:
      decode_credentials("RTSP_USER1_BASE64", "RTSP_PASSWORD1_BASE64").

    Kembalikan (user, pwd) plaintext setelah base64 decode.
    Raise error jika env tidak diset atau decode gagal.
    """
    import os, base64

    u_b64 = os.getenv(user_var, "")
    p_b64 = os.getenv(pass_var, "")
    if not u_b64 or not p_b64:
        raise RuntimeError(f"{user_var} atau {pass_var} belum diset di environment.")

    try:
        user = base64.b64decode(u_b64).decode().strip()
        pwd  = base64.b64decode(p_b64).decode().strip()
        if not user or not pwd:
            raise ValueError("Kredensial kosong setelah decode.")
        return (user, pwd)
    except Exception as e:
        raise RuntimeError(f"Gagal decode base64 => {e}")


def generate_channels() -> list:
    """
    Membuat list channel berdasarkan ENV TEST_CHANNEL atau CHANNELS.
    TEST_CHANNEL="1,3,4" => [1,3,4]
    TEST_CHANNEL="off" => range(1..CHANNELS).
    """
    tc = os.getenv("TEST_CHANNEL", "off").lower()
    if tc != "off":
        try:
            return [int(x.strip()) for x in tc.split(",")]
        except ValueError:
            raise RuntimeError("TEST_CHANNEL tidak valid (gunakan format '1,3,4').")
    else:
        ch = int(os.getenv("CHANNELS", "1"))
        return list(range(1, ch + 1))


def load_json_file(file_path: str) -> dict:
    """
    Membaca file JSON dan mengembalikan dict.
    Berguna jika kita punya config tambahan (validation, resource, dsb.).
    """
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[WARNING] File {file_path} tidak ditemukan.")
        return {}
    except json.JSONDecodeError as e:
        print(f"[WARNING] File {file_path} tidak dapat didecode JSON: {e}")
        return {}
    except Exception as e:
        print(f"[WARNING] Gagal membaca file {file_path}: {e}")
        return {}


def save_json_file(file_path: str, data: dict):
    """
    Menyimpan data dict ke file JSON secara 'atomic' (memakai .tmp -> replace).
    """
    try:
        tmp_file = file_path + ".tmp"
        with open(tmp_file, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_file, file_path)
    except Exception as e:
        print(f"[ERROR] Gagal menulis file {file_path}: {e}")


###############################################################################
# 7) DOKUMENTASI PENGGUNAAN
###############################################################################
"""
Dokumentasi Penggunaan (Production-Ready):
------------------------------------------
1) Environment Variables yang dibaca:
   - DEBUG => "true" / "false" (untuk level log)
   - ENABLE_SYSLOG => "true" / "false" (aktifkan SysLogHandler)
   - ENABLE_FILE_LOG => "true" / "false" (aktifkan RotatingFileHandler)
   - ENABLE_STREAM_LOG => "true" / "false" (aktifkan output ke console)
   - SYSLOG_SERVER, SYSLOG_PORT => alamat Syslog
   - TIMEZONE => default "Asia/Makassar"

2) Contoh Penggunaan:

   from utils import (
       setup_logger,
       setup_category_logger,
       decode_credentials,
       load_json_file,
       save_json_file
   )

   # 2.1 Buat logger
   logger = setup_logger("MainLogger", "/mnt/Data/Syslog/default/main.log")
   logger.info("Hello, ini log biasa.")

   # 2.2 Buat logger kategori
   cat_logger = setup_category_logger("RTSP")
   cat_logger.info("Mulai streaming RTSP...")

   # 2.3 Baca & tulis JSON
   data = load_json_file("/path/to/config.json")
   data["foo"] = "bar"
   save_json_file("/path/to/config.json", data)

   # 2.4 Decode credentials (default pakai RTSP_USER_BASE64 & RTSP_PASSWORD_BASE64)
   user, pwd = decode_credentials()

3) Syslog-ng:
   - Gunakan filter berdasarkan substring [RTSP], [Resource-Monitor], dsb.
   - Sesuaikan level log dengan DEBUG_MODE di environment.

4) Rotasi Log:
   - RotatingFileHandler bergantung pada maxBytes=10 MB, backupCount=5.
   - Ubah sesuai kebutuhan.

5) Folder log:
   - Pastikan folder log exist jika ENABLE_FILE_LOG=true, 
     misal "/mnt/Data/Syslog/rtsp".

6) Lock Global:
   - file_write_lock bisa digunakan saat menulis file yang sama 
     agar thread-safety.

Script ini siap untuk digunakan di produksi.
"""