#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import logging
from datetime import datetime
from flask import Flask, jsonify
from threading import Thread
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import psutil  # Untuk mendapatkan uptime sistem

# Load environment variables
load_dotenv()

# Konfigurasi variabel lingkungan
BACKUP_DIR = os.getenv("BACKUP_DIR", "/mnt/Data/Backup")
SYSLOG_DIR = os.getenv("SYSLOG_DIR", "/mnt/Data/Syslog")
LOG_FILE = os.getenv("LOG_FILE", "/mnt/Data/Syslog/rtsp/hdd_monitor.log")

# Setup logger
logger = logging.getLogger("HDD-Monitor")
logger.setLevel(logging.INFO)

handler_file = RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler_file.setFormatter(formatter)
logger.addHandler(handler_file)

app = Flask(__name__)

# Fungsi untuk menghitung uptime sistem
def hitung_uptime_sistem():
    waktu_boot = datetime.fromtimestamp(psutil.boot_time())
    sekarang = datetime.now()
    uptime = sekarang - waktu_boot
    hari, sisa = divmod(uptime.total_seconds(), 86400)
    jam, sisa = divmod(sisa, 3600)
    menit, _ = divmod(sisa, 60)
    return f"{int(hari)} hari, {int(jam)} jam, {int(menit)} menit"

# Fungsi untuk mendapatkan waktu lokal dengan zona waktu
def get_local_time_with_timezone():
    now = datetime.now().astimezone()
    offset = now.utcoffset().total_seconds()
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

# Fungsi untuk memformat ukuran dalam satuan yang mudah dibaca
def format_size(bytes_):
    units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
    for unit in units:
        if bytes_ < 1024:
            return f"{int(bytes_)} {unit}"
        bytes_ /= 1024
    return f"{int(bytes_)} PiB"

# Fungsi untuk memantau kapasitas direktori
def monitor_directory_usage(directory):
    try:
        total, used, free = shutil.disk_usage(directory)
        logger.info(f"Monitoring {directory} - Total: {format_size(total)}, Used: {format_size(used)}, Free: {format_size(free)}")
        usage_percent = int((used / total) * 100) if total else 0
        free_percent = 100 - usage_percent

        # Tambahkan logging jika penggunaan lebih dari 90%
        if usage_percent > 90:
            logger.warning(f"Peringatan! Kapasitas di {directory} hampir penuh ({usage_percent}%)")

        return {
            "kapasitas": format_size(total),
            "digunakan": format_size(used),
            "bebas": format_size(free),
            "pemakaian": f"{usage_percent}%",
            "sisa": f"{free_percent}%",
        }
    except Exception as e:
        logger.error(f"Error monitoring {directory}: {e}")
        return {"error": str(e)}

# Endpoint untuk status API
@app.route('/status', methods=['GET'])
def status():
    try:
        backup_status = monitor_directory_usage(BACKUP_DIR)
        syslog_status = monitor_directory_usage(SYSLOG_DIR)
        return jsonify({
            "current_time": get_local_time_with_timezone(),
            "backup": backup_status,
            "syslog": syslog_status,
        })
    except Exception as e:
        logger.error(f"Error di endpoint /status: {e}")
        return jsonify({"error": "Terjadi kesalahan saat membaca status."}), 500

# Endpoint untuk memeriksa kesehatan sistem
@app.route('/health', methods=['GET'])
def cek_kesehatan():
    try:
        status_backup = monitor_directory_usage(BACKUP_DIR)
        status_syslog = monitor_directory_usage(SYSLOG_DIR)

        kesehatan = {
            "status": "sehat",
            "uptime": hitung_uptime_sistem(),
            "backup": {
                "status": "ok" if int(status_backup["pemakaian"].strip('%')) < 90 else "peringatan",
                "pemakaian": status_backup["pemakaian"]
            },
            "syslog": {
                "status": "ok" if int(status_syslog["pemakaian"].strip('%')) < 90 else "peringatan",
                "pemakaian": status_syslog["pemakaian"]
            },
            "waktu_saat_ini": get_local_time_with_timezone()
        }

        # Periksa apakah ada status peringatan
        if kesehatan["backup"]["status"] == "peringatan" or kesehatan["syslog"]["status"] == "peringatan":
            kesehatan["status"] = "peringatan"

        return jsonify(kesehatan)
    except Exception as e:
        logger.error(f"Error di endpoint /health: {e}")
        return jsonify({"error": "Terjadi kesalahan saat membaca kesehatan sistem."}), 500

# Jalankan aplikasi Flask
def run_flask():
    app.run(host="0.0.0.0", port=5001, threaded=True)

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()