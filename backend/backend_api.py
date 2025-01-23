#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import glob
import json
import shutil
import psutil
from datetime import datetime
from flask import Flask, jsonify
from threading import Thread
from dotenv import load_dotenv

# Jika utils.py berada di /app/scripts, kita tambahkan path
sys.path.append("/app/scripts")
from utils import (
    setup_category_logger,
    file_write_lock
)

# -------------------------------------------------------------------------------
# 1) Load environment variables
# -------------------------------------------------------------------------------
load_dotenv()

BACKUP_DIR = os.getenv("BACKUP_DIR", "/mnt/Data/Backup")
SYSLOG_DIR = os.getenv("SYSLOG_DIR", "/mnt/Data/Syslog")

RESOURCE_JSON_PATH = "/mnt/Data/Syslog/resource/resource_monitor_state.json"
VALIDATION_JSON_PATH = "/mnt/Data/Syslog/rtsp/channel_validation.json"

HOST = os.getenv("FLASK_HOST", "0.0.0.0")
PORT = int(os.getenv("FLASK_PORT", "5001"))

# Logger kategori "HDD Monitoring"
logger = setup_category_logger("HDD Monitoring")

app = Flask(__name__)

# -------------------------------------------------------------------------------
# 2) Fungsi Utilitas
# -------------------------------------------------------------------------------
def hitung_uptime_sistem():
    """Mengembalikan uptime sistem (hari, jam, menit)."""
    waktu_boot = datetime.fromtimestamp(psutil.boot_time())
    sekarang = datetime.now()
    uptime = sekarang - waktu_boot
    hari, sisa = divmod(uptime.total_seconds(), 86400)
    jam, sisa = divmod(sisa, 3600)
    menit, _ = divmod(sisa, 60)
    return f"{int(hari)} hari, {int(jam)} jam, {int(menit)} menit"

def get_local_time_with_timezone():
    """
    Mengembalikan waktu lokal + zona (WIB/WITA/WIT) jika offset 7/8/9 jam.
    Contoh output: "23-01-2025 10:12:00 WITA"
    """
    now = datetime.now().astimezone()
    offset = now.utcoffset().total_seconds() if now.utcoffset() else 0
    hours = int(offset // 3600)
    
    if hours == 8:
        timezone = "WITA"
    elif hours == 7:
        timezone = "WIB"
    elif hours == 9:
        timezone = "WIT"
    else:
        timezone = now.tzname() or "UNKNOWN"
    
    return f"{now.strftime('%d-%m-%Y %H:%M:%S')} {timezone}"

def format_size(bytes_):
    """Memformat byte ke B, KiB, MiB, GiB, TiB, dsb."""
    units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
    size = float(bytes_)
    for unit in units:
        if size < 1024:
            return f"{int(size)} {unit}"
        size /= 1024
    return f"{int(size)} PiB"

def monitor_directory_usage(directory: str) -> dict:
    """Mengecek kapasitas disk pada 'directory'."""
    try:
        total, used, free = shutil.disk_usage(directory)
        usage_percent = int((used / total) * 100) if total else 0
        free_percent = 100 - usage_percent

        logger.info(
            f"Monitoring {directory} - Total: {format_size(total)}, "
            f"Used: {format_size(used)}, Free: {format_size(free)} "
            f"({usage_percent}% used)"
        )

        if usage_percent > 90:
            logger.warning(f"Peringatan! Kapasitas di {directory} hampir penuh ({usage_percent}%)")

        return {
            "kapasitas": format_size(total),
            "digunakan": format_size(used),
            "bebas": format_size(free),
            "pemakaian": f"{usage_percent}%",
            "sisa": f"{free_percent}%"
        }
    except Exception as e:
        logger.error(f"Error monitoring {directory}: {e}", exc_info=True)
        return {"error": str(e)}

def parse_resource_json() -> dict:
    """
    Membaca resource_monitor_state.json.
    Misalnya berisi:
    {
      "resource_usage": {
        "cpu": { "usage_percent":..., "core_count_logical":... },
        "ram": { "usage_percent":..., "used":..., "free":... },
        ...
      }
      ...
    }
    """
    try:
        with open(RESOURCE_JSON_PATH, 'r') as f:
            data = json.load(f)
            return data
    except Exception as e:
        logger.error(f"Gagal membaca {RESOURCE_JSON_PATH}: {e}", exc_info=True)
        return {}

def parse_validation_json() -> dict:
    """
    Membaca channel_validation.json.
    Contoh:
    {
      "1": {"is_active": true, "recording": false, ...},
      "2": {...},
      ...
    }
    """
    try:
        with open(VALIDATION_JSON_PATH, 'r') as f:
            data = json.load(f)
            return data
    except Exception as e:
        logger.error(f"Gagal membaca {VALIDATION_JSON_PATH}: {e}", exc_info=True)
        return {}

def get_backup_info(directory: str) -> dict:
    """
    Hitung:
    - Jumlah file di 'directory'
    - Rentang tanggal (start, end) format dd-MM-yyyy berdasar mtime
    """
    try:
        # Dapatkan semua file (rekursif). Ubah pattern jika perlu (misal "*.mp4").
        all_files = glob.glob(f"{directory}/**/*", recursive=True)
        file_paths = [f for f in all_files if os.path.isfile(f)]
        file_count = len(file_paths)

        if file_count == 0:
            return {
                "file_count": 0,
                "date_range": {
                    "start": None,
                    "end": None
                }
            }
        
        mtimes = [os.path.getmtime(p) for p in file_paths]
        mtime_min = min(mtimes)
        mtime_max = max(mtimes)

        # Format dd-MM-yyyy
        start_str = datetime.fromtimestamp(mtime_min).strftime("%d-%m-%Y")
        end_str   = datetime.fromtimestamp(mtime_max).strftime("%d-%m-%Y")

        return {
            "file_count": file_count,
            "date_range": {
                "start": start_str,
                "end": end_str
            }
        }
    except Exception as e:
        logger.error(f"Gagal mendapatkan info backup di {directory}: {e}", exc_info=True)
        return {
            "file_count": 0,
            "date_range": {
                "start": None,
                "end": None
            },
            "error": str(e)
        }

# -------------------------------------------------------------------------------
# 3) SATU ENDPOINT => /status
# -------------------------------------------------------------------------------
@app.route('/status', methods=['GET'])
def status_all():
    """
    Menampilkan:
    - Uptime
    - current_time
    - Disk usage (backup & syslog)
    - CPU usage (usage_percent, core_count_logical) dari resource_monitor_state.json
    - Memory usage (usage_percent, used, free) dari resource_monitor_state.json
    - Channel aktif (channel_validation.json)
    - Info file backup (file_count, date_range dd-MM-yyyy)
    """
    try:
        # 1) Uptime & current_time
        uptime_str = hitung_uptime_sistem()
        current_time_str = get_local_time_with_timezone()

        # 2) Disk usage => backup, syslog
        backup_usage = monitor_directory_usage(BACKUP_DIR)
        syslog_usage = monitor_directory_usage(SYSLOG_DIR)

        # 3) Resource => CPU & RAM
        resource_data = parse_resource_json()
        cpu_data = {}
        mem_data = {}
        if resource_data:
            cpu_dict = resource_data.get("resource_usage", {}).get("cpu", {})
            cpu_data = {
                "usage_percent": cpu_dict.get("usage_percent", 0),
                "core_count_logical": cpu_dict.get("core_count_logical", 0)
            }

            ram_dict = resource_data.get("resource_usage", {}).get("ram", {})
            # Kita tampilkan usage_percent, used, free saja (dalam MB, misal)
            mem_data = {
                "usage_percent": ram_dict.get("usage_percent", 0),
                "used_mb": round(ram_dict.get("used", 0) / (1024 * 1024), 1),
                "free_mb": round(ram_dict.get("free", 0) / (1024 * 1024), 1)
            }

        # 4) Channel aktif
        validation_data = parse_validation_json()
        active_channels = []
        if validation_data:
            for ch_str, ch_info in validation_data.items():
                if ch_info.get("is_active") is True:
                    active_channels.append(int(ch_str))
            active_channels.sort()

        # 5) Backup info => file_count, date_range (dd-MM-yyyy)
        backup_info = get_backup_info(BACKUP_DIR)

        # Gabungkan semua
        result = {
            "uptime": uptime_str,
            "current_time": current_time_str,
            "backup_disk_usage": backup_usage,
            "syslog_disk_usage": syslog_usage,
            "cpu": cpu_data,
            "memory": mem_data,
            "active_channels": active_channels,
            "backup_info": backup_info
        }

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error di endpoint /status: {e}", exc_info=True)
        return jsonify({"error": "Terjadi kesalahan saat membaca status."}), 500

# -------------------------------------------------------------------------------
# 4) Menjalankan Flask jika diperlukan (standalone)
# -------------------------------------------------------------------------------
def run_flask():
    logger.info(f"Menjalankan Flask di {HOST}:{PORT}...")
    app.run(host=HOST, port=PORT, threaded=True)

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()