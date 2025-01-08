#!/usr/bin/env python3
"""
resource_monitor.py

Memantau resource sistem (CPU, RAM, Disk, dsb.) dan status streaming (ping IP RTSP).
Data digabung dan disimpan ke file JSON (MONITOR_STATE_FILE) dalam loop.

Fitur:
1) Merekam resource usage (psutil).
2) Ping single IP RTSP.
3) Ping ke luar (google.com) untuk cek koneksi internet.
4) Menyimpan data final ke JSON setiap RESOURCE_MONITOR_INTERVAL detik.

Menambahkan pengaturan freeze:
- CHECK_INTERVAL
- FREEZE_SENSITIVITY
- FREEZE_RECHECK_TIMES
- FREEZE_RECHECK_DELAY
- FREEZE_COOLDOWN

Menggunakan 'utils.py' untuk logging (setup_category_logger).
"""

import os
import sys
import time
import json
import psutil
import subprocess
import re
from datetime import datetime

# Pastikan folder scripts ada di PATH (agar 'utils.py' bisa diimport)
sys.path.append("/app/scripts")

from utils import setup_category_logger

###############################################################################
# 1. Konstanta / Konfigurasi
###############################################################################
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# Gunakan kategori "Resource-Monitor"
# => Akan menyertakan prefix "[Resource-Monitor]" di setiap pesan log (ke syslog)
logger = setup_category_logger("Resource-Monitor")

# File JSON untuk menyimpan data pemantauan
MONITOR_STATE_FILE = os.getenv("MONITOR_STATE_FILE",
                               "/mnt/Data/Syslog/resource/resource_monitor_state.json")

# Interval monitoring (default 5 detik)
RESOURCE_MONITOR_INTERVAL = int(os.getenv("RESOURCE_MONITOR_INTERVAL", "5"))

# Host luar untuk ping test (cek internet)
PING_OUTSIDE_HOST = os.getenv("PING_OUTSIDE_HOST", "google.com")

# Variabel Freeze
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
FREEZE_SENSITIVITY = float(os.getenv("FREEZE_SENSITIVITY", "6.0"))
FREEZE_RECHECK_TIMES = int(os.getenv("FREEZE_RECHECK_TIMES", "5"))
FREEZE_RECHECK_DELAY = float(os.getenv("FREEZE_RECHECK_DELAY", "3.0"))
FREEZE_COOLDOWN = int(os.getenv("FREEZE_COOLDOWN", "15"))

###############################################################################
# 2. Fungsi Mendapatkan Waktu Lokal
###############################################################################
def get_local_time() -> str:
    """
    Mengembalikan waktu lokal (container/host) dalam format 'dd-MM-YYYY HH:mm:ss %Z%z'.
    Jika gagal, kembalikan string "unknown".
    """
    try:
        now = datetime.now().astimezone()
        return now.strftime('%d-%m-%Y %H:%M:%S %Z%z')
    except Exception:
        logger.exception("[Resource-Monitor] Gagal mendapatkan waktu lokal.")
        return "unknown"

###############################################################################
# 3. Fungsi Ping
###############################################################################
def ping_host_with_rtt(host: str, count=1, timeout=2) -> (bool, float):
    """
    Melakukan ping ke <host> menggunakan 'ping -c <count> -W <timeout>'.

    Returns:
        (reachable: bool, rtt_ms: float|None)
          - reachable = True jika host merespon
          - rtt_ms = RTT (ms) dari satu ping, None jika tidak tersedia
    """
    try:
        cmd = ["ping", "-c", str(count), "-W", str(timeout), host]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True)
        match = re.search(r"time=([\d\.]+)\s*ms", output)
        if match:
            return True, float(match.group(1))
        else:
            return True, None
    except subprocess.CalledProcessError:
        return False, None
    except Exception:
        logger.exception(f"[Resource-Monitor] Ping error ke {host}")
        return False, None

###############################################################################
# 4. Fungsi Pengumpulan Resource
###############################################################################
def collect_resource_data():
    """
    Mengumpulkan data resource (CPU, RAM, Disk, Swap, LoadAvg, Network).
    Menyertakan timestamp_local di dalam dict.
    """
    cpu_usage_percent = psutil.cpu_percent(interval=None)
    cpu_count_logical = psutil.cpu_count(logical=True)

    mem_info = psutil.virtual_memory()
    ram_usage_percent = mem_info.percent

    disk_info = psutil.disk_usage('/')
    disk_usage_percent = disk_info.percent

    swap_info = psutil.swap_memory()

    try:
        load_1, load_5, load_15 = os.getloadavg()
    except OSError:
        load_1, load_5, load_15 = (0, 0, 0)

    net_io = psutil.net_io_counters()
    data = {
        "cpu": {
            "usage_percent": cpu_usage_percent,
            "core_count_logical": cpu_count_logical
        },
        "ram": {
            "total": mem_info.total,
            "used": mem_info.used,
            "free": mem_info.available,
            "usage_percent": ram_usage_percent
        },
        "disk": {
            "total": disk_info.total,
            "used": disk_info.used,
            "free": disk_info.free,
            "usage_percent": disk_usage_percent
        },
        "swap": {
            "total": swap_info.total,
            "used": swap_info.used,
            "free": swap_info.free,
            "usage_percent": swap_info.percent
        },
        "load_average": {
            "1min": load_1,
            "5min": load_5,
            "15min": load_15
        },
        "network": {
            "bytes_sent": net_io.bytes_sent,
            "bytes_received": net_io.bytes_recv
        },
        "timestamp_local": get_local_time()
    }
    return data

###############################################################################
# 5. Fungsi Mengumpulkan Konfigurasi Stream
###############################################################################
def collect_stream_info():
    """
    Mengumpulkan info streaming/IP dari environment:
      - Ping single IP RTSP_IP.
      - Ping luar => cek internet.

    Return dict yang menyertakan info freeze parameters dan ping ke luar.
    """
    STREAM_TITLE  = os.getenv("STREAM_TITLE", "Unknown Title")
    RTSP_IP       = os.getenv("RTSP_IP", "127.0.0.1")
    TEST_CHANNEL  = os.getenv("TEST_CHANNEL", "1,3,4")
    CHANNELS      = int(os.getenv("CHANNELS", "1"))
    RTSP_SUBTYPE  = os.getenv("RTSP_SUBTYPE", "1")
    ENABLE_RTSP_VALIDATION = (os.getenv("ENABLE_RTSP_VALIDATION", "true").lower() == "true")
    SKIP_ABDULLAH_CHECK    = (os.getenv("SKIP_ABDULLAH_CHECK", "false").lower() == "true")

    # Ping single IP RTSP_IP
    reachable, rtt_ms = ping_host_with_rtt(RTSP_IP, count=1, timeout=2)
    final_ips = [{
        "ip": RTSP_IP,
        "reachable": reachable,
        "ping_time_ms": rtt_ms
    }]

    # channel_list
    if TEST_CHANNEL.lower() == "off":
        channel_list = list(range(1, CHANNELS + 1))
    else:
        channel_list = []
        for c in TEST_CHANNEL.split(","):
            if c.strip().isdigit():
                channel_list.append(int(c.strip()))

    # Ping keluar => cek internet
    outside_ok, outside_rtt = ping_host_with_rtt(
        os.getenv("PING_OUTSIDE_HOST", "google.com"), count=1, timeout=2
    )

    data = {
        "stream_title": STREAM_TITLE,
        "rtsp_ip": RTSP_IP,
        "test_channel": TEST_CHANNEL,
        "channels": CHANNELS,
        "rtsp_subtype": RTSP_SUBTYPE,
        "enable_rtsp_validation": ENABLE_RTSP_VALIDATION,
        "skip_abdullah_check": SKIP_ABDULLAH_CHECK,
        "final_ips": final_ips,
        "ping_outside_host": PING_OUTSIDE_HOST,
        "ping_outside_ok": outside_ok,
        "ping_outside_ms": outside_rtt,
        "channel_list": channel_list,
        "freeze_settings": {
            "check_interval": CHECK_INTERVAL,
            "freeze_sensitivity": FREEZE_SENSITIVITY,
            "freeze_recheck_times": FREEZE_RECHECK_TIMES,
            "freeze_recheck_delay": FREEZE_RECHECK_DELAY,
            "freeze_cooldown": FREEZE_COOLDOWN
        }
    }
    return data

###############################################################################
# 6. Fungsi Utama (Loop)
###############################################################################
def main():
    """
    Main loop:
    - Setiap RESOURCE_MONITOR_INTERVAL detik, kumpulkan resource_data dan stream_data.
    - Gabungkan, tulis ke MONITOR_STATE_FILE (JSON).
    - Cetak ringkasan CPU/RAM ke log.
    """
    logger.info("[Resource-Monitor] Memulai pemantauan resource & stream info.")
    logger.info(f"[Resource-Monitor] Output JSON => {MONITOR_STATE_FILE}")
    logger.info(f"[Resource-Monitor] Interval => {RESOURCE_MONITOR_INTERVAL} detik")

    if DEBUG_MODE:
        logger.info("[Resource-Monitor] DEBUG_MODE aktif: level DEBUG.")

    while True:
        try:
            resource_data = collect_resource_data()
            stream_data = collect_stream_info()

            combined_data = {
                "resource_usage": resource_data,
                "stream_config": stream_data
            }

            # Tulis ke JSON
            with open(MONITOR_STATE_FILE, "w") as f:
                json.dump(combined_data, f, indent=2)

            # Ringkasan CPU & RAM di log
            cpu_short = resource_data["cpu"]["usage_percent"]
            ram_short = resource_data["ram"]["usage_percent"]
            ts_local  = resource_data["timestamp_local"]
            logger.info(
                f"[Resource-Monitor] CPU={cpu_short:.1f}% RAM={ram_short:.1f}% => "
                f"Data diperbarui (LocalTime={ts_local})."
            )

        except Exception:
            logger.exception("[Resource-Monitor] Gagal memproses data.")

        time.sleep(RESOURCE_MONITOR_INTERVAL)


if __name__ == "__main__":
    main()