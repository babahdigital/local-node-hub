"""
utils.py

Modul utilitas yang menyediakan:
1) Fungsi logger (RotatingFileHandler, opsional SysLogHandler).
2) Fungsi-fungsi umum: get_local_time, decode_credentials, dsb.
3) Kemudahan penggunaan log kategori (LOG_CATEGORIES).

Bisa digunakan di script lain seperti resource_monitor.py, validate_cctv.py, dsb.
"""

import os
import json
import logging
import base64
from logging.handlers import SysLogHandler, RotatingFileHandler
from datetime import datetime
import pytz
from dotenv import load_dotenv

###############################################################################
# 1. MUAT ENVIRONMENT VARIABLES (opsional dari .env)
###############################################################################
load_dotenv()  # Memuat environment variables dari .env (jika ada)

###############################################################################
# 2. KONSTANTA & DEFAULT
###############################################################################
DEFAULT_SYSLOG_SERVER = "syslog-ng"
DEFAULT_SYSLOG_PORT = 1514

DEFAULT_LOG_DIR = "/mnt/Data/Syslog/rtsp"
DEFAULT_BACKUP_LOG_DIR = f"{DEFAULT_LOG_DIR}/backup"

# Fallback path jika kategori tidak ditentukan
DEFAULT_LOG_PATH = f"{DEFAULT_LOG_DIR}/stream/stream_service.log"
DEFAULT_MESSAGES_FILE = "/app/config/log_messages.json"

# Rotating File Config
DEFAULT_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUP_COUNT = 5

# Timezone default: Asia/Makassar (WITA).
# Jika tidak valid atau tidak di-set, akan fallback ke system local time.
TIMEZONE = os.getenv("TIMEZONE", "Asia/Makassar")

# Environment fallback
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", DEFAULT_MESSAGES_FILE)
ENABLE_SYSLOG = os.getenv("ENABLE_SYSLOG", "false").lower() == "true"
SYSLOG_SERVER = os.getenv("SYSLOG_SERVER", DEFAULT_SYSLOG_SERVER)
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", DEFAULT_SYSLOG_PORT))

# DEBUG_MODE => menentukan level logging (DEBUG vs INFO)
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

###############################################################################
# 3. KATEGORI LOG (DICTIONARY)
###############################################################################
# Anda bisa menambahkan kategori lain, misalnya "Resource-Monitor" jika diinginkan.
LOG_CATEGORIES = {
    "PERFORMANCE": {
        "description": "Mencatat metrik kinerja sistem (CPU/RAM, eksekusi).",
        "path": f"{DEFAULT_LOG_DIR}/performance/performance.log"
    },
    "BACKUP": {
        "description": "Mencatat status proses backup (berhasil, gagal, dsb.).",
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
        "description": "Log tugas terjadwal (cron, rotasi log, dsb.).",
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
        "description": "Log level debug (untuk dev).",
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
# 4. LOAD PESAN LOG DARI JSON (OPSIONAL)
###############################################################################
def load_log_messages(file_path: str) -> dict:
    """
    Memuat pesan log dari file JSON (opsional).
    Berguna jika ada penanganan log berbasis template message (get_log_message).

    Args:
        file_path (str): Path ke file JSON.

    Returns:
        dict: Isi file JSON sebagai dictionary. {} jika gagal.
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
# 5. FUNGSI UTILITY LOGGER
###############################################################################
def setup_logger(logger_name: str, log_path: str) -> logging.Logger:
    """
    Membuat logger dengan RotatingFileHandler dan opsional SyslogHandler.

    Args:
        logger_name (str): Nama logger (bebas).
        log_path   (str): Path file log (misal /mnt/Data/Syslog/...).

    Returns:
        logging.Logger: Objek logger yang siap digunakan (level INFO/DEBUG).
    """
    logger = logging.getLogger(logger_name)
    if logger.hasHandlers():
        # Sudah pernah dibuat => kembalikan existing
        return logger

    # Set level logging
    logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)

    # Setup Rotating File Handler
    import os
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    try:
        file_handler = RotatingFileHandler(
            filename=log_path,
            maxBytes=DEFAULT_LOG_SIZE,
            backupCount=DEFAULT_BACKUP_COUNT
        )
        formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"[ERROR] Gagal mengatur file handler untuk {log_path}: {e}")

    # Setup Syslog Handler (jika ENABLE_SYSLOG=true di ENV)
    if ENABLE_SYSLOG:
        try:
            syslog_handler = SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))
            syslog_formatter = logging.Formatter(f"[{logger_name}] %(message)s")
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            print(f"[WARNING] Gagal mengatur syslog handler: {SYSLOG_SERVER}:{SYSLOG_PORT} => {e}")

    return logger

def setup_category_logger(category: str) -> logging.Logger:
    """
    Membuat logger berdasarkan kategori di LOG_CATEGORIES.
    Jika kategori tidak ditemukan, fallback ke 'default'.

    Args:
        category (str): Nama kategori (e.g. 'RTSP', 'NETWORK', dsb.)

    Returns:
        logging.Logger: Logger dengan path & handler sesuai kategori.
    """
    if category not in LOG_CATEGORIES:
        category = "default"
    log_path = LOG_CATEGORIES[category]["path"]
    return setup_logger(category, log_path)

def get_log_message(key: str) -> str:
    """
    Mengambil pesan log berdasarkan kunci dari LOG_MESSAGES.

    Format key: "some.key.path" => messages[some][key][path]
    Contoh: get_log_message("resource.start") => "Memulai pemantauan resource..."

    Raises:
        RuntimeError: Jika key tidak ditemukan di file JSON.

    Returns:
        str: Pesan log yang sesuai key.
    """
    try:
        parts = key.split('.')
        data = LOG_MESSAGES
        for part in parts:
            data = data[part]
        return data
    except KeyError:
        raise RuntimeError(f"Pesan log untuk kunci '{key}' tidak ditemukan.")

###############################################################################
# 6. FUNGSI UTILITY UMUM
###############################################################################
def get_local_time() -> str:
    """
    Mengembalikan waktu lokal dengan format 'dd-MM-yyyy HH:mm:ss TZZZ+Offset'.

    - Jika ENV TIMEZONE valid (misal "Asia/Makassar"), gunakan itu.
    - Jika TIMEZONE tidak valid / tidak ada, fallback ke system local time.

    Returns:
        str: Contoh "08-01-2025 10:12:01 WITA+0800"
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
        # Jika TIMEZONE tidak valid => fallback system local time
        fallback_time = datetime.now().astimezone()
        return fallback_time.strftime('%d-%m-%Y %H:%M:%S %Z%z')

def decode_credentials() -> tuple:
    """
    Dekode ENV: RTSP_USER_BASE64, RTSP_PASSWORD_BASE64 => (user, password).

    Pastikan di .env atau environment:
      RTSP_USER_BASE64=<base64 user>
      RTSP_PASSWORD_BASE64=<base64 password>

    Returns:
        tuple: (user, password)

    Raises:
        RuntimeError: Jika env tidak diset atau decode gagal.
    """
    u_b64 = os.getenv("RTSP_USER_BASE64", "")
    p_b64 = os.getenv("RTSP_PASSWORD_BASE64", "")
    if not u_b64 or not p_b64:
        raise RuntimeError("RTSP_USER_BASE64 atau RTSP_PASSWORD_BASE64 tidak diset! (Cek .env)")

    try:
        user = base64.b64decode(u_b64).decode().strip()
        pwd = base64.b64decode(p_b64).decode().strip()
        if not user or not pwd:
            raise ValueError("Kredensial RTSP kosong setelah decode.")
        return user, pwd
    except Exception as e:
        raise RuntimeError(f"Gagal decode kredensial: {e}")

def generate_channels() -> list:
    """
    Membuat list channel berdasarkan TEST_CHANNEL atau CHANNELS.

    - Jika TEST_CHANNEL != 'off', parse string "1,3,4" => [1,3,4].
    - Jika TEST_CHANNEL=='off', gunakan range(1..CHANNELS).

    Returns:
        list: daftar channel (int).
    """
    tc = os.getenv("TEST_CHANNEL", "off").lower()
    if tc != "off":
        try:
            return [int(x.strip()) for x in tc.split(",")]
        except ValueError:
            raise RuntimeError("TEST_CHANNEL tidak valid (Gunakan format '1,3,4').")
    else:
        ch = int(os.getenv("CHANNELS", "1"))
        return list(range(1, ch + 1))

def load_json_file(file_path: str) -> dict:
    """
    Membaca file JSON dan mengembalikan dict.
    Return {} jika gagal atau file tidak ditemukan.

    Args:
        file_path (str): Path ke file JSON

    Returns:
        dict: Isi file, atau {} jika tidak ditemukan/error.
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

###############################################################################
# 7. DOKUMENTASI PENGGUNAAN
###############################################################################
"""
Dokumentasi Penggunaan:

1. Konfigurasi ENV:
   - TIMEZONE (default: "Asia/Makassar").
     Jika kosong/invalid => fallback system local time (misal Asia/Jakarta).
   - ENABLE_SYSLOG, SYSLOG_SERVER, SYSLOG_PORT => untuk mengaktifkan Syslog Handler.
   - DEBUG (default "false") => Menentukan logger.setLevel(DEBUG vs INFO).

2. Contoh Penggunaan di Script Lain:
   from utils import (
       setup_logger, setup_category_logger, get_local_time,
       decode_credentials, load_json_file, ...
   )

   logger = setup_logger("MyLogger", "/path/to/log/file.log")
   logger.info("Hello from MyLogger")

   # atau, kategori
   logger_resource = setup_category_logger("Resource-Monitor")
   logger_resource.info("Memulai pemantauan resource...")

3. Rotasi Log & Syslog:
   - Rotasi otomatis (10MB) dengan 5 backup.
   - Jika ENABLE_SYSLOG=true => log juga ke server syslog-ng (UDP/TCP 1514).
   - Pastikan environment SYSLOG_SERVER, SYSLOG_PORT.

4. Fungsi decode_credentials():
   - Mengambil RTSP_USER_BASE64 & RTSP_PASSWORD_BASE64, decode ke (user, pass).

5. Fungsi generate_channels():
   - Parsing channel dari TEST_CHANNEL (jika tidak 'off'),
     atau range(1..CHANNELS).

6. Fungsi load_json_file():
   - Membaca file JSON, kembalikan dict => berguna untuk config dynamic.

Dengan demikian, modul `utils.py` ini memudahkan:
- Logging (file & syslog).
- Timezone local time.
- Decode credential base64.
- Baca file JSON dsb.
"""