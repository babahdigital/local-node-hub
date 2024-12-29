#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import time
import logging
from logging.handlers import SysLogHandler, RotatingFileHandler
import pytz
import datetime
import requests
import json

from report_manager import send_report_to_backend  # Pastikan module ini ada atau sesuaikan import-nya

# Zona waktu lokal
local_tz = pytz.timezone("Asia/Makassar")

def get_local_time():
    """Fungsi untuk mendapatkan waktu lokal."""
    return datetime.datetime.now(local_tz).strftime("%d-%m-%Y %H:%M:%S") + \
           (" WITA" if local_tz.zone == "Asia/Makassar" else " WIB")

def calculate_max_capacity():
    """
    Menghitung kapasitas maksimum disk yang diperbolehkan secara dinamis.
    Mengadaptasi untuk HDD fisik dan quota di TrueNAS.
    """
    min_limit = 90  # Minimum kapasitas yang dapat diterima
    max_limit = 95  # Maksimum kapasitas yang dapat diterima

    # Pastikan BACKUP_DIR ada sebelum penghitungan
    if not os.path.exists(BACKUP_DIR):
        logger.warning(
            "Direktori backup {} tidak ditemukan. Menggunakan nilai default "
            "MAX_CAPACITY_PERCENT.".format(BACKUP_DIR)
        )
        return min_limit  # Gunakan nilai default jika direktori tidak ditemukan

    total, _, _ = shutil.disk_usage(BACKUP_DIR)
    total_gb = total // (1024 ** 3)

    # Tentukan batas berdasarkan ukuran disk atau quota
    if total_gb > 500:  # Jika kapasitas > 500GB, tetapkan batas 95%
        return max_limit
    elif total_gb > 100:  # Jika kapasitas > 100GB, tetapkan batas 92%
        return min_limit + 2
    else:  # Untuk disk kecil, gunakan nilai minimum 90%
        return min_limit

# Variabel lingkungan
BACKUP_DIR = os.getenv("BACKUP_DIR", "/mnt/Data/Backup")
MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", "60"))
MAX_CAPACITY_PERCENT = (
    calculate_max_capacity() if not os.getenv("MAX_CAPACITY_PERCENT")
    else int(os.getenv("MAX_CAPACITY_PERCENT"))
)
ROTATE_THRESHOLD = int(os.getenv("ROTATE_THRESHOLD", "5"))
SYSLOG_SERVER = os.getenv("SYSLOG_SERVER", "syslog-ng")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", "1514"))
ENABLE_SYSLOG = os.getenv("ENABLE_SYSLOG", "true").lower() == "true"
BACKEND_ENDPOINT = os.getenv("BACKEND_ENDPOINT", "http://127.0.0.1:5001/api/disk_status")
HEALTH_CHECK_URL = os.getenv("HEALTH_CHECK_URL", "http://127.0.0.1:8080/health")
HEALTH_CHECK_TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "50"))
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", "/app/config/log_messages.json")

# Batas jumlah file yang dihapus per siklus rotasi
MAX_DELETE_PER_CYCLE = 500

# Umur file untuk retensi (HAPUS KOMENTAR jika ingin retensi by age, opsional)
FILE_RETENTION_DAYS = 7

# Pastikan file log_messages.json ada
if not os.path.exists(LOG_MESSAGES_FILE):
    raise FileNotFoundError(
        f"File log_messages.json tidak ditemukan di {LOG_MESSAGES_FILE}"
    )

def load_log_messages(file_path):
    """Muat pesan log dari file JSON."""
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Gagal memuat pesan log dari {file_path}: {e}")

# Konfigurasi Logging
LOG_FILE = "/mnt/Data/Syslog/rtsp/hdd_monitor.log"
logger = logging.getLogger("HDD-Monitor")
logger.setLevel(logging.INFO)

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5)
file_formatter = logging.Formatter('%(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

if ENABLE_SYSLOG:
    syslog_handler = SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))
    syslog_formatter = logging.Formatter('[HDD-MONITOR] %(message)s')
    syslog_handler.setFormatter(syslog_formatter)
    logger.addHandler(syslog_handler)

# Muat file JSON yang berisi pesan log
log_messages = load_log_messages(LOG_MESSAGES_FILE)

def wait_for_health_check(url, timeout):
    """Periksa apakah layanan health check aktif."""
    logger.info(log_messages["hdd_monitor"]["health_check"]["start"].format(url=url))
    start_time = time.time()
    retries = 0
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=5)
            if (
                response.status_code == 200
                and response.json().get("status")
                == log_messages["health_check"]["healthy"]
            ):
                logger.info(log_messages["hdd_monitor"]["health_check"]["ready"])
                return True
        except requests.exceptions.RequestException as e:
            retries += 1
            logger.warning(
                log_messages["hdd_monitor"]["health_check"]["warning"].format(
                    error=e, retries=retries
                )
            )
        time.sleep(5)

    logger.error(log_messages["hdd_monitor"]["health_check"]["failed"].format(timeout=timeout))
    payload = {
        "type": "system_status",
        "status": "unhealthy",
        "message": log_messages["hdd_monitor"]["health_check"]["unhealthy"],
        "timestamp": get_local_time(),
    }
    send_report_to_backend(BACKEND_ENDPOINT, payload)
    return False

def monitor_disk_usage():
    """Monitoring disk dan menjalankan rotasi jika diperlukan."""
    try:
        if not os.path.exists(BACKUP_DIR):
            logger.error(
                log_messages["hdd_monitor"]["disk_usage"]["directory_not_found"].format(
                    BACKUP_DIR=BACKUP_DIR
                )
            )
            raise FileNotFoundError(
                log_messages["hdd_monitor"]["disk_usage"]["directory_not_found"].format(
                    BACKUP_DIR=BACKUP_DIR
                )
            )

        # Ambil kapasitas total sekali saja
        total, _, _ = shutil.disk_usage(BACKUP_DIR)
        logger.info(f"Monitoring disk dimulai dengan interval {MONITOR_INTERVAL} detik.")

        iteration_count = 0
        while True:
            try:
                iteration_count += 1

                # Ambil data 'used' dan 'free' tiap loop
                _, used, free = shutil.disk_usage(BACKUP_DIR)
                usage_percent = (used / total) * 100

                # Tampilkan log ringkas setiap loop, log lebih detail hanya kadang-kadang
                if iteration_count % 5 == 0:  # Misal 1 kali log detail per 5 iterasi
                    logger.info(log_messages["hdd_monitor"]["disk_usage"]["monitor_running"])
                    iteration_count = 0

                if free == 0:
                    logger.error("Quota atau disk penuh! Tidak ada ruang yang tersisa.")
                else:
                    # Log detail tiap 5 iterasi atau sesuai kebijakan
                    if iteration_count == 0:
                        logger.info(
                            log_messages["hdd_monitor"]["disk_usage"]["usage"].format(
                                usage_percent=round(usage_percent, 2),
                                total=f"{total // (1024 ** 3)} GB",
                                used=f"{used // (1024 ** 3)} GB",
                                free=f"{free // (1024 ** 3)} GB",
                            )
                        )

                # Lakukan rotasi jika usage melebihi ambang batas
                if usage_percent >= MAX_CAPACITY_PERCENT:
                    logger.warning(
                        log_messages["hdd_monitor"]["disk_usage"]["rotation_start"].format(
                            usage_percent=round(usage_percent, 2),
                            threshold_percent=MAX_CAPACITY_PERCENT,
                        )
                    )

                    # Kumpulkan semua file di BACKUP_DIR
                    all_files = []
                    for root, _, files in os.walk(BACKUP_DIR):
                        for f in files:
                            full_path = os.path.join(root, f)
                            all_files.append(full_path)

                    # (Opsional) Jika ingin retensi berbasis umur file, aktifkan kode di bawah
                    now_ts = time.time()
                    retention_seconds = FILE_RETENTION_DAYS * 24 * 3600
                    all_files = [
                        f for f in all_files
                        if (now_ts - os.path.getmtime(f)) > retention_seconds
                    ]

                    # Urutkan file berdasarkan waktu modifikasi tertua
                    all_files.sort(key=lambda x: os.path.getmtime(x))

                    deleted_count = 0
                    for file in all_files:
                        # Perbarui usage sebelum menghapus file selanjutnya
                        _, used_new, _ = shutil.disk_usage(BACKUP_DIR)
                        usage_percent = (used_new / total) * 100
                        if usage_percent < MAX_CAPACITY_PERCENT - ROTATE_THRESHOLD:
                            break
                        if deleted_count >= MAX_DELETE_PER_CYCLE:
                            # Batasi jumlah file yang dihapus per iterasi
                            logger.info(
                                "Batas penghapusan file per siklus tercapai: {} file".format(
                                    MAX_DELETE_PER_CYCLE
                                )
                            )
                            break

                        try:
                            os.remove(file)
                            deleted_count += 1
                            logger.info(
                                log_messages["hdd_monitor"]["disk_usage"]["file_deleted"].format(
                                    relative_path=os.path.relpath(file, BACKUP_DIR)
                                )
                            )
                        except Exception as e:
                            logger.error(
                                log_messages["hdd_monitor"]["disk_usage"]["file_deletion_failed"].format(
                                    file_path=file, error=e
                                )
                            )

                    logger.info(
                        log_messages["hdd_monitor"]["disk_usage"]["rotation_complete"].format(
                            usage_percent=round(usage_percent, 2)
                        )
                    )

                    # Jika tetap tidak cukup, beri peringatan
                    if usage_percent >= MAX_CAPACITY_PERCENT:
                        logger.warning(
                            log_messages["hdd_monitor"]["disk_usage"]["rotation_insufficient"].format(
                                usage_percent=round(usage_percent, 2)
                            )
                        )

                    # Menghapus folder kosong setelah rotasi
                    for root, dirs, _ in os.walk(BACKUP_DIR, topdown=False):
                        for d in dirs:
                            path_dir = os.path.join(root, d)
                            try:
                                if not os.listdir(path_dir):
                                    os.rmdir(path_dir)
                                    logger.info(f"Folder kosong dihapus: {path_dir}")
                            except Exception as e:
                                logger.warning(f"Gagal menghapus folder kosong {path_dir}: {e}")

                time.sleep(MONITOR_INTERVAL)

            except Exception as e:
                logger.error(f"Terjadi kesalahan saat monitoring disk: {e}")

    except KeyboardInterrupt:
        logger.info(log_messages["hdd_monitor"]["monitor_stopped"])

if __name__ == "__main__":
    # Pastikan health check service sudah siap
    if not wait_for_health_check(HEALTH_CHECK_URL, HEALTH_CHECK_TIMEOUT):
        logger.error(log_messages["hdd_monitor"]["health_check"]["failed"].format(
            timeout=HEALTH_CHECK_TIMEOUT
        ))
        exit(1)

    # Mulai monitoring disk
    monitor_disk_usage()
