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

# Fungsi mendapatkan waktu lokal berdasarkan offset UTC
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

# Fungsi format ukuran
def format_size(bytes_):
    units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
    for unit in units:
        if bytes_ < 1024:
            return f"{int(bytes_)} {unit}"
        bytes_ /= 1024
    return f"{int(bytes_)} PiB"

# Fungsi monitoring kapasitas direktori
def monitor_directory_usage(directory):
    try:
        total, used, free = shutil.disk_usage(directory)
        usage_percent = int((used / total) * 100) if total else 0
        free_percent = 100 - usage_percent

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

# Endpoint status API
@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        "current_time": get_local_time_with_timezone(),
        "backup": monitor_directory_usage(BACKUP_DIR),
        "syslog": monitor_directory_usage(SYSLOG_DIR),
    })

def run_flask():
    app.run(host="0.0.0.0", port=5001, threaded=True)

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()