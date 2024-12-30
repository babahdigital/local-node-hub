#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import time
import logging
import socket
import json
import subprocess
import heapq
from datetime import datetime
from flask import Flask, jsonify
from threading import Thread
from logging.handlers import SysLogHandler, RotatingFileHandler
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------
# Variabel Lingkungan
# ---------------------------------------------------
POOL_NAME = os.getenv("POOL_NAME", "/mnt/Data")
BACKUP_DIR = os.getenv("BACKUP_DIR", "/mnt/Data/Backup")
SYSLOG_DIR = os.getenv("SYSLOG_DIR", "/mnt/Data/Syslog")
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", "/app/config/log_messages.json")
LOG_FILE = os.getenv("LOG_FILE", "/mnt/Data/Syslog/rtsp/hdd_monitor.log")
SYSLOG_SERVER = os.getenv("SYSLOG_SERVER", "syslog-ng")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", "1514"))
ENABLE_SYSLOG = os.getenv("ENABLE_SYSLOG", "true").lower() == "true"
AUTO_DELETE = os.getenv("AUTO_DELETE", "")  # Contoh: "/mnt/Data/Backup,/mnt/Data/Syslog"

if not os.path.exists(BACKUP_DIR):
    raise ValueError(f"Direktori backup tidak valid: {BACKUP_DIR}")

if not os.path.isfile(LOG_MESSAGES_FILE):
    raise FileNotFoundError(f"File log_messages.json tidak ditemukan: {LOG_MESSAGES_FILE}")

# ---------------------------------------------------
# Muat Pesan Log dari File JSON
# ---------------------------------------------------
def muat_log_pesan(file_path):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Kesalahan decode JSON: {e}")
    except Exception as e:
        raise RuntimeError(f"Gagal memuat log_messages: {e}")

log_messages = muat_log_pesan(LOG_MESSAGES_FILE)

# ---------------------------------------------------
# Konfigurasi Logging
# ---------------------------------------------------
logger = logging.getLogger("HDD-Monitor")
logger.setLevel(logging.INFO)

handler_file = RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5)
formatter_file = logging.Formatter('%(message)s')
handler_file.setFormatter(formatter_file)
logger.addHandler(handler_file)

def dapatkan_apakah_resolvable(host):
    try:
        socket.getaddrinfo(host, None)
        return True
    except socket.gaierror:
        return False

# Aktifkan Syslog jika diinginkan
if ENABLE_SYSLOG and SYSLOG_SERVER and dapatkan_apakah_resolvable(SYSLOG_SERVER):
    try:
        handler_syslog = SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))
        # Gunakan prefix [HDD-STATUS] agar tampilan log lebih konsisten
        formatter_syslog = logging.Formatter('[HDD-STATUS] %(message)s')
        handler_syslog.setFormatter(formatter_syslog)
        logger.addHandler(handler_syslog)
    except Exception as e:
        logger.error(f"Gagal mengaktifkan syslog: {e}")

# ---------------------------------------------------
# Flask Aplikasi
# ---------------------------------------------------
app = Flask(__name__)

# ---------------------------------------------------
# Fungsi Utilitas
# ---------------------------------------------------
def dapatkan_waktu_lokal_dengan_zona():
    sekarang = datetime.now().astimezone()
    offset_detik = sekarang.utcoffset().total_seconds()
    offset_jam = int(offset_detik // 3600)
    offset_menit = int((offset_detik % 3600) // 60)
    if offset_jam == 8 and offset_menit == 0:
        zona = "WITA"
    elif offset_jam == 7 and offset_menit == 0:
        zona = "WIB"
    elif offset_jam == 9 and offset_menit == 0:
        zona = "WIT"
    else:
        zona = sekarang.tzname()
    return sekarang.strftime("%d-%m-%Y %H:%M:%S") + f" {zona}"

def format_ukuran(bytes_):
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']:
        if bytes_ < 1024:
            return f"{int(bytes_)} {unit}"
        bytes_ /= 1024
    return f"{int(bytes_)} PiB"

def format_persentase(value):
    return f"{int(value)}%"

def monitor_penggunaan_direktori(direktori):
    try:
        total_fs, digunakan_fs, bebas_fs = shutil.disk_usage(direktori)
        persentase_pemakaian = (digunakan_fs / total_fs * 100) if total_fs else 0
        return {
            "kapasitas": format_ukuran(total_fs),
            "digunakan": format_ukuran(digunakan_fs),
            "bebas": format_ukuran(bebas_fs),
            "pemakaian": format_persentase(persentase_pemakaian),
            "sisa": format_persentase(100 - persentase_pemakaian if persentase_pemakaian < 100 else 0)
        }
    except Exception as e:
        logger.error(f"Gagal memantau {direktori}: {e}")
        return {
            "kapasitas": "0 B",
            "digunakan": "0 B",
            "bebas": "0 B",
            "pemakaian": "0%",
            "sisa": "100%"
        }

# ---------------------------------------------------
# Periodik Logging (Menghindari Penumpukan Log)
# ---------------------------------------------------
def periodic_hdd_status_logging():
    while True:
        backup_status = monitor_penggunaan_direktori(BACKUP_DIR)
        logger.info(
            f"[HDD-STATUS] Bebas: {backup_status['bebas']}, "
            f"Digunakan: {backup_status['digunakan']}, "
            f"Kapasitas: {backup_status['kapasitas']}, "
            f"Pemakaian: {backup_status['pemakaian']}, "
            f"Sisa: {backup_status['sisa']}")
        time.sleep(300)  # Logging status disk setiap 5 menit

# ---------------------------------------------------
# Fungsi Deteksi ZFS
# ---------------------------------------------------
def deteksi_dataset_zfs():
    try:
        hasil = subprocess.run(
            ["zfs", "list", "-H", "-o", "name"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        dataset_list = hasil.stdout.strip().split("\n")
        dataset_under_pool = [ds for ds in dataset_list if ds.startswith(POOL_NAME)]
        if not dataset_under_pool:
            logger.warning("Tidak ada dataset di bawah POOL_NAME, pakai disk usage standar.")
            return None
        logger.info(f"Dataset ZFS terdeteksi: {dataset_under_pool}")
        return dataset_under_pool
    except subprocess.CalledProcessError as e:
        logger.error(f"Gagal deteksi dataset ZFS: {e.stderr.strip()}")
        return None
    except Exception as e:
        logger.error(f"Kesalahan deteksi dataset ZFS: {e}")
        return None

def parse_size(ukuran_str):
    satuan_ukuran = {"B":1, "K":1024, "M":1024**2, "G":1024**3, "T":1024**4, "P":1024**5}
    try:
        ukuran_str = ukuran_str.strip()
        if ukuran_str and ukuran_str[-1].upper() in satuan_ukuran:
            return float(ukuran_str[:-1]) * satuan_ukuran[ukuran_str[-1].upper()]
        return float(ukuran_str)
    except:
        logger.error(f"Tidak dapat mengurai ukuran: {ukuran_str}")
        return 0

def parse_zfs_output(output):
    properti = {}
    for baris_item in output.strip().split("\n"):
        fields = baris_item.split("\t")
        if len(fields) >= 3:
            prop, nilai, _ = fields[:3]
            properti[prop] = parse_size(nilai)
    return properti

def dapatkan_info_quota_zfs(dataset):
    try:
        hasil = subprocess.run(
            ["zfs", "get", "-Hp", "quota,used,available", dataset],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        properti = parse_zfs_output(hasil.stdout)
        quota = properti.get("quota")
        used = properti.get("used")
        available = properti.get("available")
        if None in (quota, used, available):
            logger.error("Informasi quota ZFS tidak lengkap. Gunakan disk_usage fallback.")
            return shutil.disk_usage(BACKUP_DIR)
        return quota, used, available
    except subprocess.CalledProcessError as e:
        logger.error(f"Gagal info quota ZFS: {e.stderr.strip()}")
        return shutil.disk_usage(BACKUP_DIR)
    except Exception as e:
        logger.error(f"Kesalahan ZFS: {e}")
        return shutil.disk_usage(BACKUP_DIR)

# ---------------------------------------------------
# Fungsi Penghapusan File Lama
# ---------------------------------------------------
def hapus_file_terlama(directory, jumlah=500):
    def file_mtimes(root_dir):
        for root, _, files in os.walk(root_dir):
            for f_ in files:
                try:
                    path_ = os.path.join(root, f_)
                    yield (os.path.getmtime(path_), path_)
                except Exception as e:
                    logger.warning(f"Gagal akses {path_}: {e}")
    if not os.path.isdir(directory):
        logger.warning(f"Dir {directory} tidak ditemukan.")
        return

    oldest_files = heapq.nsmallest(jumlah, file_mtimes(directory), key=lambda x: x[0])
    for _, file_path in oldest_files:
        try:
            os.remove(file_path)
            logger.info(log_messages["hdd_monitor"]["disk_usage"]["file_deleted"].format(
                relative_path=os.path.relpath(file_path, directory)
            ))
        except Exception as e:
            logger.warning(log_messages["hdd_monitor"]["disk_usage"]["file_deletion_failed"].format(
                file_path=file_path,
                error=str(e)
            ))

# ---------------------------------------------------
# Logika Monitor HDD (ZFS / Fisik)
# ---------------------------------------------------
def hitung_interval_monitor_dinamis(persentase):
    if persentase > 90:
        return 30
    elif persentase > 85:
        return 45
    return 60

def monitor_penggunaan_disk():
    try:
        dataset_backup = deteksi_dataset_zfs()
        auto_delete_dirs = [d.strip() for d in AUTO_DELETE.split(",") if d.strip()]
        logger.info(f"Direktori auto-delete: {auto_delete_dirs}")

        while True:
            # Jika ada dataset ZFS
            if dataset_backup:
                for dataset in dataset_backup:
                    info_quota = dapatkan_info_quota_zfs(dataset)
                    if isinstance(info_quota, tuple):
                        total, used, free = info_quota
                    else:
                        total, used, free = shutil.disk_usage(BACKUP_DIR)
                    pemakaian = (used / total * 100) if total else 0

                    # Log ringkas di loop
                    logger.info(
                        f"[HDD-STATUS] ZFS Dataset {dataset} - Pemakaian: {format_persentase(pemakaian)}, "
                        f"Digunakan: {format_ukuran(used)}, Bebas: {format_ukuran(free)}")
                    if pemakaian >= 90:
                        logger.warning(f"Pemakaian di atas 90% di {dataset}: {format_persentase(pemakaian)}. Hapus file terlama.")
                        for dir_ in auto_delete_dirs:
                            hapus_file_terlama(dir_)
                    interval = hitung_interval_monitor_dinamis(pemakaian)

            # Jika bukan dataset ZFS (fisik)
            else:
                total, used, free = shutil.disk_usage(BACKUP_DIR)
                pemakaian = (used / total * 100) if total else 0

                # Log ringkas di loop
                logger.info(
                    f"[HDD-STATUS] Fisik - Pemakaian: {format_persentase(pemakaian)}, "
                    f"Digunakan: {format_ukuran(used)}, Bebas: {format_ukuran(free)}")
                if pemakaian >= 90:
                    logger.warning(f"Pemakaian di atas 90% Fisik: {format_persentase(pemakaian)}. Hapus file terlama.")
                    for dir_ in auto_delete_dirs:
                        hapus_file_terlama(dir_)
                interval = hitung_interval_monitor_dinamis(pemakaian)

            # Monitor syslog
            syslog_status = monitor_penggunaan_direktori(SYSLOG_DIR)
            logger.info(
                log_messages["hdd_monitor"]["disk_usage"]["syslog_usage"].format(
                    usage_percent=syslog_status["pemakaian"],
                    total=syslog_status["kapasitas"],
                    used=syslog_status["digunakan"],
                    free=syslog_status["bebas"]
                )
            )

            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info(log_messages["hdd_monitor"]["monitor_stopped"])
        exit(0)
    except Exception as ee:
        logger.error(f"Kesalahan monitor: {ee}")

# ---------------------------------------------------
# Endpoint Flask
# ---------------------------------------------------
@app.route('/status', methods=['GET'])
def status():
    sekarang = dapatkan_waktu_lokal_dengan_zona()
    return jsonify({
        "current_time": sekarang,
        "backup": monitor_penggunaan_direktori(BACKUP_DIR),
        "syslog": monitor_penggunaan_direktori(SYSLOG_DIR)
    })

@app.route('/status/backup', methods=['GET'])
def status_backup_route():
    sekarang = dapatkan_waktu_lokal_dengan_zona()
    backup_status = monitor_penggunaan_direktori(BACKUP_DIR)
    # Logging detail hanya satu kali di endpoint agar tidak double
    logger.info(
        f"[HDD-STATUS] Endpoint /status/backup dipanggil. Bebas: {backup_status['bebas']}, "
        f"Digunakan: {backup_status['digunakan']}, Kapasitas: {backup_status['kapasitas']}, "
        f"Pemakaian: {backup_status['pemakaian']}, Sisa: {backup_status['sisa']}"
    )
    return jsonify({"current_time": sekarang, "backup": backup_status})

@app.route('/status/syslog', methods=['GET'])
def status_syslog_route():
    sekarang = dapatkan_waktu_lokal_dengan_zona()
    status_syslog = monitor_penggunaan_direktori(SYSLOG_DIR)
    return jsonify({
        "current_time": sekarang,
        "syslog": status_syslog
    })

# ---------------------------------------------------
# Main
# ---------------------------------------------------
def jalankan_aplikasi_flask():
    app.run(host="0.0.0.0", port=5000, threaded=True)

if __name__ == "__main__":
    # Thread Flask
    flask_thread = Thread(target=jalankan_aplikasi_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Thread Periodik Logging
    periodic_thread = Thread(target=periodic_hdd_status_logging)
    periodic_thread.daemon = True
    periodic_thread.start()

    # Monitor Penggunaan Disk
    monitor_penggunaan_disk()