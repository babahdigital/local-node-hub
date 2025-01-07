#!/usr/bin/env python3
"""
resource_monitor.py

Script ini memantau pemakaian CPU, RAM, Disk, Swap, dan Jaringan.
Hasil pemantauan disimpan dalam file JSON untuk digunakan oleh sistem lain.

- Menghapus "per_core_usage_percent" dari output JSON.
- Tetap menampilkan timestamp_local, timestamp_wib, dan timestamp_wita.
"""

import os
import sys
import time
import json
import psutil
from datetime import datetime
import pytz

# Pastikan folder scripts ada di PATH (jika utils.py ada di /app/scripts)
sys.path.append("/app/scripts")

from utils import setup_logger

###############################################################################
# KONFIGURASI & SETUP LOGGER
###############################################################################
LOG_PATH = os.getenv("LOG_PATH", "/mnt/Data/Syslog/resource/resource_monitor.log")
logger = setup_logger("Resource-Monitor", LOG_PATH)

###############################################################################
# KONFIGURASI RESOURCE MONITOR
###############################################################################
MONITOR_STATE_FILE = os.getenv("MONITOR_STATE_FILE",
                               "/mnt/Data/Syslog/resource/resource_monitor_state.json")
RESOURCE_MONITOR_INTERVAL = int(os.getenv("RESOURCE_MONITOR_INTERVAL", "5"))

###############################################################################
# FUNGSI TIMEZONE
###############################################################################
def get_time_in_timezone(tz_name: str) -> str:
    """
    Mengembalikan waktu saat ini dalam timezone tertentu (misal 'Asia/Makassar')
    dengan format 'dd-MM-YYYY HH:mm:ss ZZZZ'.
    Jika tz_name tidak valid, kembalikan 'unknown'.
    """
    try:
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        return now.strftime('%d-%m-%Y %H:%M:%S %Z%z')
    except Exception:
        return "unknown"

def get_local_time() -> str:
    """
    Mengembalikan waktu 'lokal' (sesuai local timezone container/host)
    dengan format 'dd-MM-YYYY HH:mm:ss ZZZZ'.
    """
    try:
        now = datetime.now().astimezone()
        return now.strftime('%d-%m-%Y %H:%M:%S %Z%z')
    except Exception as e:
        logger.error(f"[Resource-Monitor] Gagal mendapatkan waktu lokal: {e}")
        return "unknown"

###############################################################################
# FUNGSI PENGUMPULAN RESOURCE
###############################################################################
def collect_resource_data():
    """
    Mengumpulkan data resource (CPU, RAM, Disk, Swap, Load Avg, Network).
    *Tanpa* 'per_core_usage_percent'.
    Menyertakan tiga timestamp (local, WIB, WITA).
    """

    # CPU usage
    cpu_usage_percent = psutil.cpu_percent(interval=None)
    cpu_count_logical = psutil.cpu_count(logical=True)
    # (Dihilangkan) cpu_per_core_usage = psutil.cpu_percent(interval=None, percpu=True)

    # RAM usage
    mem_info = psutil.virtual_memory()
    ram_total = mem_info.total
    ram_used = mem_info.used
    ram_free = mem_info.available
    ram_usage_percent = mem_info.percent

    # Disk usage (root '/')
    disk_info = psutil.disk_usage('/')
    disk_total = disk_info.total
    disk_used = disk_info.used
    disk_free = disk_info.free
    disk_usage_percent = disk_info.percent

    # Swap usage
    swap_info = psutil.swap_memory()
    swap_total = swap_info.total
    swap_used = swap_info.used
    swap_free = swap_info.free
    swap_usage_percent = swap_info.percent

    # Load average (Unix-based only)
    try:
        load_1, load_5, load_15 = os.getloadavg()
    except OSError:
        load_1, load_5, load_15 = (0, 0, 0)

    # Network I/O
    net_io = psutil.net_io_counters()
    bytes_sent = net_io.bytes_sent
    bytes_recv = net_io.bytes_recv

    # Buat struktur data (tanpa per_core_usage_percent)
    data = {
        "cpu": {
            "usage_percent": cpu_usage_percent,
            "core_count_logical": cpu_count_logical
        },
        "ram": {
            "total": ram_total,
            "used": ram_used,
            "free": ram_free,
            "usage_percent": ram_usage_percent
        },
        "disk": {
            "total": disk_total,
            "used": disk_used,
            "free": disk_free,
            "usage_percent": disk_usage_percent
        },
        "swap": {
            "total": swap_total,
            "used": swap_used,
            "free": swap_free,
            "usage_percent": swap_usage_percent
        },
        "load_average": {
            "1min": load_1,
            "5min": load_5,
            "15min": load_15
        },
        "network": {
            "bytes_sent": bytes_sent,
            "bytes_received": bytes_recv
        },
        # Timestamp lokal, WIB, WITA
        "timestamp_local": get_local_time(),
        #"timestamp_wib": get_time_in_timezone("Asia/Jakarta"),
        #"timestamp_wita": get_time_in_timezone("Asia/Makassar")
    }

    return data

###############################################################################
# MAIN LOOP
###############################################################################
def main():
    logger.info("[Resource-Monitor] Memulai pemantauan resource.")
    logger.info(f"[Resource-Monitor] Hasil akan ditulis di: {MONITOR_STATE_FILE}")
    logger.info(f"[Resource-Monitor] Interval pemantauan: {RESOURCE_MONITOR_INTERVAL} detik")

    while True:
        try:
            # 1. Kumpulkan data resource lengkap
            data = collect_resource_data()

            # 2. Tulis ke file JSON
            with open(MONITOR_STATE_FILE, "w") as f:
                json.dump(data, f, indent=2)

            # 3. Tampilkan ringkasan CPU & RAM di log
            cpu_short = data["cpu"]["usage_percent"]
            ram_short = data["ram"]["usage_percent"]
            logger.info(
                f"[Resource-Monitor] CPU={cpu_short:.1f}% RAM={ram_short:.1f}% => "
                f"Data diperbarui. (LocalTime={data['timestamp_local']})"
            )

        except Exception as e:
            logger.error(f"[Resource-Monitor] Gagal memproses data resource: {e}")

        # 4. Tunggu sebelum loop berikutnya
        time.sleep(RESOURCE_MONITOR_INTERVAL)

if __name__ == "__main__":
    main()