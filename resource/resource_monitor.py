#!/usr/bin/env python3
"""
resource_monitor.py

Gabungan:
1. Pemantauan resource (CPU, RAM, Disk, dsb.) => data disimpan JSON.
2. Memetakan IP mana yang digunakan (berdasarkan NVR_ENABLE, NVR_SUBNET, RTSP_IP).
3. Ping keluar (misal google.com) untuk cek internet (beserta RTT).

Hasil pemantauan (resource_usage + stream_config) disimpan dalam 1 file JSON (MONITOR_STATE_FILE).

Tujuan:
- Memisahkan beban scanning/ping IP dari proses validasi RTSP (validate_cctv.py).
- Berjalan terus (loop) setiap RESOURCE_MONITOR_INTERVAL detik.
"""

import os
import sys
import time
import json
import psutil
import subprocess
import re
import ipaddress
from datetime import datetime
import pytz

# Pastikan folder scripts ada di PATH (jika utils.py ada di /app/scripts)
sys.path.append("/app/scripts")

from utils import setup_logger

###############################################################################
# KONSTANTA / KONFIGURASI
###############################################################################
LOG_PATH = os.getenv("LOG_PATH", "/mnt/Data/Syslog/resource/resource_monitor.log")
logger = setup_logger("Resource-Monitor", LOG_PATH)

MONITOR_STATE_FILE = os.getenv("MONITOR_STATE_FILE",
                               "/mnt/Data/Syslog/resource/resource_monitor_state.json")

RESOURCE_MONITOR_INTERVAL = int(os.getenv("RESOURCE_MONITOR_INTERVAL", "5"))
PING_OUTSIDE_HOST = os.getenv("PING_OUTSIDE_HOST", "google.com")

###############################################################################
# FUNGSI WAKTU / TIMEZONE
###############################################################################
def get_local_time() -> str:
    """
    Mengembalikan waktu lokal (container/host).
    Format: 'dd-MM-YYYY HH:mm:ss %Z%z'
    """
    try:
        now = datetime.now().astimezone()
        return now.strftime('%d-%m-%Y %H:%M:%S %Z%z')
    except Exception as e:
        logger.error(f"[Resource-Monitor] Gagal mendapatkan waktu lokal: {e}")
        return "unknown"

###############################################################################
# FUNGSI PING
###############################################################################
def ping_host_with_rtt(host: str, count=1, timeout=2) -> (bool, float):
    """
    Ping <host> dengan ping -c <count> -W <timeout>.
    Return (reachable: bool, rtt_ms: float or None).
    """
    try:
        output = subprocess.check_output(
            ["ping", "-c", str(count), "-W", str(timeout), host],
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        # Cari pola time=... ms
        match = re.search(r"time=([\d\.]+)\s*ms", output)
        if match:
            return True, float(match.group(1))
        else:
            return True, None
    except subprocess.CalledProcessError:
        return False, None
    except Exception as e:
        logger.error(f"[Resource-Monitor] Ping error ke {host}: {e}")
        return False, None

def collect_subnet_ips(subnet: str, ping_timeout=1):
    """
    Scan subnet => kembalikan list IP reachable. 
    Return list of {ip, reachable, ping_time_ms}.
    """
    results = []
    try:
        net = ipaddress.ip_network(subnet, strict=False)
        for ip_obj in net.hosts():
            ip_str = str(ip_obj)
            reachable, rtt_ms = ping_host_with_rtt(ip_str, count=1, timeout=ping_timeout)
            if reachable:
                results.append({
                    "ip": ip_str,
                    "reachable": True,
                    "ping_time_ms": rtt_ms
                })
        return results
    except ValueError as ve:
        logger.error(f"[Resource-Monitor] Subnet tidak valid: {subnet} => {ve}")
        return []

###############################################################################
# FUNGSI PENGUMPULAN RESOURCE
###############################################################################
def collect_resource_data():
    """
    Mengumpulkan data resource (CPU, RAM, Disk, Swap, LoadAvg, Network).
    Menyertakan timestamp_local.
    """
    # CPU
    cpu_usage_percent = psutil.cpu_percent(interval=None)
    cpu_count_logical = psutil.cpu_count(logical=True)

    # RAM
    mem_info = psutil.virtual_memory()
    ram_usage_percent = mem_info.percent

    # Disk
    disk_info = psutil.disk_usage('/')
    disk_usage_percent = disk_info.percent

    # Swap
    swap_info = psutil.swap_memory()

    # Load average
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
# FUNGSI MENGUMPULKAN KONFIG STREAM / IP
###############################################################################
def collect_stream_info():
    """
    Mengumpulkan info environment (NVR_ENABLE, dsb.),
    lalu memetakan final_ips, channel_list dsb. tanpa validasi RTSP.
    """
    STREAM_TITLE  = os.getenv("STREAM_TITLE", "Unknown Title")
    RTSP_IP       = os.getenv("RTSP_IP", "127.0.0.1")
    NVR_SUBNET    = os.getenv("NVR_SUBNET", "192.168.1.0/24")
    TEST_CHANNEL  = os.getenv("TEST_CHANNEL", "1,3,4")
    CHANNELS      = int(os.getenv("CHANNELS", "1"))
    RTSP_SUBTYPE  = os.getenv("RTSP_SUBTYPE", "1")
    NVR_ENABLE    = (os.getenv("NVR_ENABLE", "false").lower() == "true")
    ENABLE_RTSP_VALIDATION = (os.getenv("ENABLE_RTSP_VALIDATION", "true").lower() == "true")
    SKIP_ABDULLAH_CHECK    = (os.getenv("SKIP_ABDULLAH_CHECK", "false").lower() == "true")

    # 1) Kumpulkan final_ips
    if NVR_ENABLE:
        # Subnet scanning
        final_ips = collect_subnet_ips(NVR_SUBNET, ping_timeout=1)
    else:
        # Single IP => ping
        reachable, rtt_ms = ping_host_with_rtt(RTSP_IP, count=1, timeout=2)
        final_ips = [{
            "ip": RTSP_IP,
            "reachable": reachable,
            "ping_time_ms": rtt_ms
        }]

    # 2) channel_list
    if TEST_CHANNEL.lower() == "off":
        channel_list = list(range(1, CHANNELS + 1))
    else:
        channel_list = []
        for c in TEST_CHANNEL.split(","):
            c = c.strip()
            if c.isdigit():
                channel_list.append(int(c))

    # 3) Ping ke luar (google.com), sekadar cek internet
    outside_ok, outside_rtt = ping_host_with_rtt(PING_OUTSIDE_HOST, count=1, timeout=2)

    data = {
        "stream_title": STREAM_TITLE,
        "rtsp_ip": RTSP_IP,
        "nvr_subnet": NVR_SUBNET,
        "test_channel": TEST_CHANNEL,
        "channels": CHANNELS,
        "rtsp_subtype": RTSP_SUBTYPE,
        "nvr_enable": NVR_ENABLE,
        "enable_rtsp_validation": ENABLE_RTSP_VALIDATION,
        "skip_abdullah_check": SKIP_ABDULLAH_CHECK,
        "final_ips": final_ips,
        "ping_outside_host": PING_OUTSIDE_HOST,
        "ping_outside_ok": outside_ok,
        "ping_outside_ms": outside_rtt,
        "channel_list": channel_list
    }
    return data

###############################################################################
# MAIN LOOP
###############################################################################
def main():
    logger.info("[Resource-Monitor] Memulai pemantauan resource & stream info.")
    logger.info(f"[Resource-Monitor] Output JSON => {MONITOR_STATE_FILE}")
    logger.info(f"[Resource-Monitor] Interval => {RESOURCE_MONITOR_INTERVAL} detik")

    while True:
        try:
            # 1) Resource usage
            resource_data = collect_resource_data()

            # 2) Info stream (NVR/IP, channels, dsb.)
            stream_data = collect_stream_info()

            # 3) Gabungkan
            combined_data = {
                "resource_usage": resource_data,
                "stream_config": stream_data
            }

            # 4) Tulis ke file JSON
            with open(MONITOR_STATE_FILE, "w") as f:
                json.dump(combined_data, f, indent=2)

            # 5) Log ringkasan CPU & RAM
            cpu_short = resource_data["cpu"]["usage_percent"]
            ram_short = resource_data["ram"]["usage_percent"]
            ts_local  = resource_data["timestamp_local"]
            logger.info(
                f"[Resource-Monitor] CPU={cpu_short:.1f}% RAM={ram_short:.1f}% => "
                f"Data diperbarui (LocalTime={ts_local})."
            )

        except Exception as e:
            logger.error(f"[Resource-Monitor] Gagal memproses data: {e}")

        # 6) Tunggu sebelum loop berikutnya
        time.sleep(RESOURCE_MONITOR_INTERVAL)

if __name__ == "__main__":
    main()