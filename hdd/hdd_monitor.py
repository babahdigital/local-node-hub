#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import time
import logging
import socket  # Added for server name resolution check
from logging.handlers import SysLogHandler, RotatingFileHandler
import json
from flask import Flask, jsonify
from threading import Thread
from datetime import datetime
import subprocess
import heapq

def get_local_time_with_zone():
    now = datetime.now()
    offset_hours = now.astimezone().utcoffset().total_seconds() / 3600
    if offset_hours == 8:
        zone = "WITA"
    elif offset_hours == 7:
        zone = "WIB"
    else:
        zone = "UTC"
    return now.strftime("%d-%m-%Y %H:%M:%S") + f" {zone}"

def format_size(bytes):
    for unit in ['B', 'KiB', 'MiB', 'GiB']:
        if bytes < 1024:
            return f"{bytes:.0f} {unit}"
        bytes /= 1024
    return f"{bytes:.2f} GiB"

def format_percent(value):
    return f"{int(value)}%"

def calculate_dynamic_max_capacity(total_gb):
    if total_gb > 500:
        return 95
    elif total_gb > 100:
        return 92
    return 90

def calculate_dynamic_rotate_threshold(usage_percent):
    if usage_percent > 85:
        return 10
    elif usage_percent > 80:
        return 7
    return 5

def calculate_dynamic_monitor_interval(usage_percent):
    if usage_percent > 90:
        return 30
    elif usage_percent > 85:
        return 45
    return 60

def get_zfs_quota_info(dataset):
    try:
        result = subprocess.run(
            ["zfs", "get", "-Hp", "quota,used,available", dataset],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        lines = result.stdout.strip().split("\n")
        quota = used = available = None
        for line in lines:
            fields = line.split()
            if "quota" in fields:
                quota = int(fields[2])
            elif "used" in fields:
                used = int(fields[2])
            elif "available" in fields:
                available = int(fields[2])
        return quota, used, available
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get ZFS quota info: {e}")
        return None, None, None

BACKUP_DIR = os.getenv("BACKUP_DIR", "/mnt/Data/Backup")
DATASET_NAME = os.getenv("DATASET_NAME", None)
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", "/app/config/log_messages.json")
LOG_FILE = "/mnt/Data/Syslog/rtsp/hdd_monitor.log"
SYSLOG_SERVER = os.getenv("SYSLOG_SERVER", "syslog-ng")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", "1514"))
ENABLE_SYSLOG = os.getenv("ENABLE_SYSLOG", "true").lower() == "true"
SYSLOG_DIR = os.getenv("SYSLOG_DIR", "/mnt/Data/Syslog")

if not os.path.exists(BACKUP_DIR):
    raise ValueError(f"Invalid backup dir: {BACKUP_DIR}")

if not os.path.exists(LOG_MESSAGES_FILE):
    raise FileNotFoundError(f"Log messages file not found: {LOG_MESSAGES_FILE}")

def load_log_messages(file_path):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load log messages: {e}")

log_messages = load_log_messages(LOG_MESSAGES_FILE)

logger = logging.getLogger("HDD-Monitor")
logger.setLevel(logging.INFO)

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5)
file_formatter = logging.Formatter('%(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Check if SYSLOG_SERVER is resolvable before creating syslog handler
def is_resolvable(host):
    try:
        socket.getaddrinfo(host, None)
        return True
    except socket.gaierror:
        return False

if ENABLE_SYSLOG and SYSLOG_SERVER and is_resolvable(SYSLOG_SERVER):
    try:
        syslog_handler = SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))
        syslog_formatter = logging.Formatter('[HDD-MONITOR] %(message)s')
        syslog_handler.setFormatter(syslog_formatter)
        logger.addHandler(syslog_handler)
    except Exception as e:
        logger.error(f"Unable to enable syslog: {e}")
else:
    logger.warning("Syslog disabled or server not resolvable.")

def monitor_disk_usage():
    try:
        while True:
            if DATASET_NAME:
                total, used, free = get_zfs_quota_info(DATASET_NAME)
                if not total or not used or not free:
                    logger.error("Failed to retrieve ZFS quota info.")
                    time.sleep(60)
                    continue
            else:
                total, used, free = shutil.disk_usage(BACKUP_DIR)

            usage_percent = (used / total) * 100
            max_capacity = calculate_dynamic_max_capacity(total / (1024**3))
            rotate_threshold = calculate_dynamic_rotate_threshold(usage_percent)
            monitor_interval = calculate_dynamic_monitor_interval(usage_percent)

            logger.info(log_messages["hdd_monitor"]["disk_usage"]["usage"].format(
                usage_percent=format_percent(usage_percent),
                total=format_size(total),
                used=format_size(used),
                free=format_size(free)
            ))

            if usage_percent < max_capacity - rotate_threshold:
                time.sleep(monitor_interval)
                continue

            all_files = []
            for root, _, files in os.walk(BACKUP_DIR):
                for file in files:
                    all_files.append(os.path.join(root, file))

            heapq.heapify(all_files)
            oldest_files = heapq.nsmallest(500, all_files, key=os.path.getmtime)

            for file in oldest_files:
                try:
                    os.remove(file)
                    logger.info(log_messages["hdd_monitor"]["disk_usage"]["file_deleted"].format(
                        relative_path=os.path.relpath(file, BACKUP_DIR)
                    ))
                except Exception as e:
                    logger.warning(log_messages["hdd_monitor"]["disk_usage"]["file_deletion_failed"].format(
                        file_path=file,
                        error=e
                    ))
            time.sleep(monitor_interval)
    except KeyboardInterrupt:
        logger.info(log_messages["hdd_monitor"]["monitor_stopped"])
        exit(0)

def monitor_directory_usage(directory):
    total, used, free = shutil.disk_usage(directory)
    usage_percent = (used / total) * 100
    return {
        "total": format_size(total),
        "used": format_size(used),
        "free": format_size(free),
        "usage_percent": format_percent(usage_percent)
    }

app = Flask(__name__)

@app.route('/status', methods=['GET'])
def status():
    current_time = get_local_time_with_zone()
    backup_status = monitor_directory_usage(BACKUP_DIR)
    syslog_status = monitor_directory_usage(SYSLOG_DIR)
    return jsonify({
        "current_time": current_time,
        "backup": backup_status,
        "syslog": syslog_status
    })

@app.route('/status/backup', methods=['GET'])
def status_backup():
    current_time = get_local_time_with_zone()
    backup_status = monitor_directory_usage(BACKUP_DIR)
    return jsonify({
        "current_time": current_time,
        "backup": backup_status
    })

@app.route('/status/syslog', methods=['GET'])
def status_syslog():
    current_time = get_local_time_with_zone()
    syslog_status = monitor_directory_usage(SYSLOG_DIR)
    return jsonify({
        "current_time": current_time,
        "syslog": syslog_status
    })

if __name__ == "__main__":
    flask_thread = Thread(target=lambda: app.run(host="0.0.0.0", port=5000))
    flask_thread.daemon = True
    flask_thread.start()
    monitor_disk_usage()