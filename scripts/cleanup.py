#!/usr/bin/env python3
import shutil
import os
import re
import time
from datetime import datetime

BACKUP_PATH = "/mnt/Data/Backup"  # Sesuaikan lokasi folder backup
THRESHOLD_USAGE = 90  # Jika disk usage >90% => hapus data lama
TARGET_USAGE   = 80  # Hapus sampai usage <80%
DATE_PATTERN   = r'^\d{2}-\d{2}-\d{4}$'  # Folder nama "dd-MM-yyyy"

def get_disk_usage_percent(path="/"):
    usage = shutil.disk_usage(path)
    used_percent = (usage.used / usage.total)*100
    return used_percent

def find_day_folders(backup_path):
    """
    Mengembalikan list (datetime, fullpath) folder harian di backup_path,
    diurut ascending (terlama -> terbaru).
    """
    folders = []
    for name in os.listdir(backup_path):
        fullpath = os.path.join(backup_path, name)
        if os.path.isdir(fullpath) and re.match(DATE_PATTERN, name):
            try:
                dt = datetime.strptime(name, "%d-%m-%Y")
                folders.append((dt, fullpath))
            except:
                pass
    # Urut berdasarkan tanggal ascending
    folders.sort(key=lambda x: x[0])
    return folders

def cleanup_if_full():
    usage_percent = get_disk_usage_percent(BACKUP_PATH)
    print(f"[CLEANUP] Current usage: {usage_percent:.1f}% (threshold={THRESHOLD_USAGE}%)")

    while usage_percent > THRESHOLD_USAGE:
        day_folders = find_day_folders(BACKUP_PATH)
        if not day_folders:
            print("[CLEANUP] Tidak ada folder harian lagi. Disk masih di atas threshold!")
            break

        # Ambil folder tertua
        oldest_dt, oldest_path = day_folders[0]
        print(f"[CLEANUP] Menghapus folder paling lama: {oldest_path} (tanggal {oldest_dt.strftime('%d-%m-%Y')})")
        try:
            shutil.rmtree(oldest_path)
        except Exception as e:
            print(f"[CLEANUP] Gagal hapus {oldest_path}: {e}")
            break

        # Cek usage lagi
        usage_percent = get_disk_usage_percent(BACKUP_PATH)
        print(f"[CLEANUP] Usage setelah hapus: {usage_percent:.1f}%")
        if usage_percent < TARGET_USAGE:
            print("[CLEANUP] Sudah di bawah target usage => selesai.")
            break

if __name__=="__main__":
    cleanup_if_full()