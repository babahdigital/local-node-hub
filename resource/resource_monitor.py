#!/usr/bin/env python3
"""
resource_monitor.py

Script ini memantau pemakaian CPU, RAM, Disk, Swap, dan Jaringan.
Hasil pemantauan disimpan dalam file JSON untuk digunakan oleh sistem lain.
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
# File tempat menyimpan hasil pemantauan resource:
MONITOR_STATE_FILE = os.getenv("MONITOR_STATE_FILE",
                               "/mnt/Data/Syslog/resource/resource_monitor_state.json")

# Interval pemantauan (detik), default 5:
RESOURCE_MONITOR_INTERVAL = int(os.getenv("RESOURCE_MONITOR_INTERVAL", "5"))

# Opsi timezone (jika diinginkan explicit). Jika tidak di-set, pakai local time.
TIMEZONE = os.getenv("RESOURCE_MONITOR_TIMEZONE", "")

def get_local_time():
    """
    Mengembalikan string waktu lokal dengan format dd-MM-yyyy HH:mm:ss (ZonaWaktu).
    Jika environment RESOURCE_MONITOR_TIMEZONE di-set, pakai TZ tersebut.
    Jika tidak, pakai local timezone sistem host.
    """
    try:
        now = datetime.now()
        if TIMEZONE:
            # Pakai timezone dari env
            tz = pytz.timezone(TIMEZONE)
            now = now.astimezone(tz)
        else:
            # Pakai local timezone sistem
            now = now.astimezone()  # Python 3.6+ => autodetect local timezone
        return now.strftime('%d-%m-%Y %H:%M:%S %Z%z')
    except Exception as e:
        logger.error(f"[Resource-Monitor] Gagal mendapatkan waktu lokal: {e}")
        return "unknown"

def collect_resource_data():
    """
    Mengumpulkan data resource (CPU, RAM, Disk, Swap, dan Jaringan).
    Struktur data dikembalikan sebagai dictionary lengkap.
    """
    # CPU usage (persentase)
    cpu_usage = psutil.cpu_percent(interval=None)
    cpu_count = psutil.cpu_count(logical=True)
    cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)

    # RAM usage
    mem_info = psutil.virtual_memory()
    ram_total = mem_info.total
    ram_used = mem_info.used
    ram_free = mem_info.available
    mem_usage_percent = mem_info.percent

    # Disk usage (root '/')
    disk_info = psutil.disk_usage('/')
    disk_total = disk_info.total
    disk_used = disk_info.used
    disk_free = disk_info.free
    disk_usage_percent = disk_info.percent

    # Swap memory usage
    swap_info = psutil.swap_memory()
    swap_total = swap_info.total
    swap_used = swap_info.used
    swap_free = swap_info.free
    swap_usage_percent = swap_info.percent

    # Load average (hanya tersedia di Unix-based)
    # Return tuple (1min, 5min, 15min)
    try:
        load_avg = os.getloadavg()
    except OSError:
        # Jika di Windows, getloadavg mungkin tidak ada
        load_avg = (0, 0, 0)

    # Network I/O
    net_io = psutil.net_io_counters()
    bytes_sent = net_io.bytes_sent
    bytes_received = net_io.bytes_recv

    # Buat struktur data lengkap
    data = {
        "cpu": {
            "usage_percent": cpu_usage,            # 0..100
            "core_count": cpu_count,
            "per_core_usage_percent": cpu_per_core # list: persentase per core
        },
        "ram": {
            "total": ram_total,
            "used": ram_used,
            "free": ram_free,
            "usage_percent": mem_usage_percent
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
            "1min": load_avg[0],
            "5min": load_avg[1],
            "15min": load_avg[2]
        },
        "network": {
            "bytes_sent": bytes_sent,
            "bytes_received": bytes_received
        },
        "timestamp": get_local_time()
    }
    return data

def main():
    """
    Main loop untuk memantau resource dan menyimpan hasilnya secara berkala.
    """
    logger.info("[Resource-Monitor] Memulai pemantauan resource.")
    logger.info(f"[Resource-Monitor] Hasil akan ditulis di: {MONITOR_STATE_FILE}")
    logger.info(f"[Resource-Monitor] Interval pemantauan: {RESOURCE_MONITOR_INTERVAL} detik")

    while True:
        try:
            # Mengumpulkan data resource
            data = collect_resource_data()

            # Tulis data ke file JSON
            with open(MONITOR_STATE_FILE, "w") as f:
                json.dump(data, f, indent=2)

            # Anda bisa menampilkan ringkasan di log
            cpu_short = data["cpu"]["usage_percent"]
            ram_short = data["ram"]["usage_percent"]
            logger.info(
                f"[Resource-Monitor] CPU={cpu_short:.1f}% RAM={ram_short:.1f}% => Data diperbarui."
            )

        except Exception as e:
            logger.error(f"[Resource-Monitor] Gagal memproses data resource: {e}")

        # Tunggu sesuai RESOURCE_MONITOR_INTERVAL sebelum loop berikutnya
        time.sleep(RESOURCE_MONITOR_INTERVAL)

if __name__ == "__main__":
    main()