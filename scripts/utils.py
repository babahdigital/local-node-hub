import os
import json
import logging
import base64
from logging.handlers import SysLogHandler, RotatingFileHandler
from datetime import datetime
import pytz
from dotenv import load_dotenv

###############################################################################
# MUAT ENVIRONMENT VARIABLES
###############################################################################
load_dotenv()  # Memuat environment variables dari .env (jika ada)

###############################################################################
# KONSTANTA & DEFAULT
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

# Ambil dari .env, dengan fallback
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", DEFAULT_MESSAGES_FILE)
ENABLE_SYSLOG = os.getenv("ENABLE_SYSLOG", "false").lower() == "true"
SYSLOG_SERVER = os.getenv("SYSLOG_SERVER", DEFAULT_SYSLOG_SERVER)
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", DEFAULT_SYSLOG_PORT))
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

###############################################################################
# KATEGORI LOG (DICTIONARY)
###############################################################################
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
    "default": {
        "description": "Fallback untuk log umum.",
        "path": DEFAULT_LOG_PATH
    },
}

###############################################################################
# LOAD PESAN LOG DARI JSON (OPSIONAL)
###############################################################################
def load_log_messages(file_path: str) -> dict:
    """
    Memuat pesan log dari file JSON.
    Berguna jika ada penanganan log berbasis template message.
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
# FUNGSI UTILITY LOGGER
###############################################################################
def setup_logger(logger_name: str, log_path: str) -> logging.Logger:
    """
    Membuat logger dengan RotatingFileHandler dan opsional SyslogHandler.
    - logger_name: nama logger (bebas).
    - log_path   : path file log.
    """
    logger = logging.getLogger(logger_name)
    if logger.hasHandlers():
        # Sudah pernah dibuat, langsung kembalikan
        return logger

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

    # Setup Syslog Handler (opsional)
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
    Membuat logger berdasarkan kategori LOG_CATEGORIES.
    Jika tidak ditemukan, fallback ke 'default'.
    """
    if category not in LOG_CATEGORIES:
        category = "default"
    log_path = LOG_CATEGORIES[category]["path"]
    return setup_logger(category, log_path)

def get_log_message(key: str) -> str:
    """
    Mengambil pesan log berdasarkan kunci (key) dari LOG_MESSAGES global.
    Format key: "some.key.path" => messages[some][key][path]
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
# FUNGSI UTILITY UMUM
###############################################################################
def get_local_time() -> str:
    """
    Mengembalikan waktu lokal dengan format 'dd-MM-yyyy HH:mm:ss TZZZ+Offset'.
    - Jika ENV TIMEZONE valid, gunakan pytz.timezone() => Contoh: Asia/Makassar (WITA).
    - Jika TIMEZONE tidak valid / tidak ada, fallback ke system local time.
    """
    try:
        tz_name = TIMEZONE.strip() if TIMEZONE else ""
        if tz_name:
            # Mencoba timezone yang di-set
            local_tz = pytz.timezone(tz_name)
            local_time = datetime.now(local_tz)
        else:
            # TIMEZONE kosong => fallback ke system local time
            local_time = datetime.now().astimezone()

        return local_time.strftime('%d-%m-%Y %H:%M:%S %Z%z')
    except Exception:
        # Jika TIMEZONE tidak valid => fallback system local time
        fallback_time = datetime.now().astimezone()
        return fallback_time.strftime('%d-%m-%Y %H:%M:%S %Z%z')

def decode_credentials() -> tuple:
    """
    Dekode RTSP_USER_BASE64 dan RTSP_PASSWORD_BASE64 dari ENV.
    Return (rtsp_user, rtsp_password).

    Pastikan env:
      RTSP_USER_BASE64=<base64 dr user>
      RTSP_PASSWORD_BASE64=<base64 dr password>
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
# DOKUMENTASI PENGGUNAAN
###############################################################################
"""
Dokumentasi Penggunaan

1. Konfigurasi ENV:
   - TIMEZONE (default: "Asia/Makassar" => WITA).
     Jika kosong atau tidak valid, akan fallback ke system local time.
     Contoh: TIMEZONE="Asia/Jakarta" => WIB, TIMEZONE="Asia/Jayapura" => WIT, dsb.

2. Contoh Penggunaan di Script Lain (validate_cctv / resource_monitor):
   from utils import (
       setup_logger, get_local_time, decode_credentials, load_json_file, ...
   )

   # Membuat logger
   logger = setup_logger("NamaLoggerBebas", "/path/to/log/file.log")
   logger.info("Halo, saya log info")

   # Mendapatkan waktu lokal (WITA/WIB fallback)
   now_str = get_local_time()

   # Decode user pass
   user, pwd = decode_credentials()

   # Membaca file JSON
   data = load_json_file("/mnt/Data/Syslog/resource/resource_monitor_state.json")

3. Logging Kategori
   - Jika Anda ingin log dengan kategori, gunakan:
       logger_rtsp = setup_category_logger("RTSP")
       logger_rtsp.info("Log dari kategori RTSP")

4. Pesan Log via get_log_message(key)
   - Jika Anda menyimpan template log di LOG_MESSAGES_FILE,
     panggil get_log_message("some.path") untuk mengambil string template.

5. Rotasi Log & Syslog
   - Log dirotasi ketika ukuran > DEFAULT_LOG_SIZE (10MB), disimpan 5 backup.
   - Jika ENABLE_SYSLOG=true, maka log juga dikirim ke server Syslog.
   - Pastikan SYSLOG_SERVER, SYSLOG_PORT di-set.

Dengan struktur ini, Anda dapat menggunakan `utils.py` untuk
- Mendapatkan logger (file rotating / syslog).
- Membaca credensial RTSP (Base64).
- Membaca file JSON.
- Mengambil waktu lokal dengan format dd-MM-yyyy HH:mm:ss [TimeZone][Offset],
  default "Asia/Makassar" (WITA), fallback ke system local time jika TIMEZONE tidak valid.
  
"""