#!/usr/bin/env python3
"""
ffmpeg_manager.py

Script Manager yang bertugas menjalankan pipeline FFmpeg HLS:
- Membaca daftar channel (resource_monitor_state.json) => channels
- Membaca channel_validation.json => cek is_active, error_msg
- Menjalankan pipeline FFmpeg jika is_active=true & error_msg=None
- Hentikan pipeline jika is_active=false atau ada error_msg
- Memperbarui is_active di JSON (misal, jika kita mau set True/False)
- Loop memantau perubahan JSON setiap 60 detik.

Dijalankan di bawah Supervisor / Systemd agar terus berjalan.
"""

import os
import json
import subprocess
import shlex
import sys
import time
import threading
import hashlib
from datetime import datetime
from urllib.parse import quote, urlparse, urlunparse

# Jika utils.py berada di /app/scripts:
sys.path.append("/app/scripts")
from utils import decode_credentials, setup_category_logger

logger = setup_category_logger("CCTV-Manager")

def log_info(msg):    logger.info(msg)
def log_warning(msg): logger.warning(msg)
def log_error(msg):   logger.error(msg)

# ------------------------------ 
# 0) KONFIGURASI & PATH 
# ------------------------------
RESOURCE_MONITOR_PATH   = "/mnt/Data/Syslog/resource/resource_monitor_state.json"
CHANNEL_VALIDATION_PATH = "/mnt/Data/Syslog/rtsp/channel_validation.json"

HLS_OUTPUT_DIR = "/app/streamserver/hls"

# Anda boleh set environment berikut di Dockerfile/compose
HLS_TIME      = os.environ.get("HLS_TIME", "2")
HLS_LIST_SIZE = os.environ.get("HLS_LIST_SIZE", "5")

# Data pipeline
ffmpeg_processes     = {}   # {channel: subprocess.Popen}
tracked_channels     = set() # daftar channel
channel_states       = {}   # {channel: bool} menandakan pipeline sedang jalan atau tidak

data_lock            = threading.Lock()
resource_hash        = None
validation_hash      = None

# ------------------------------ 
# 1) HELPER => LOAD, SAVE JSON
# ------------------------------
def load_json_file(filepath):
    if not os.path.isfile(filepath):
        log_warning(f"File {filepath} tidak ditemukan.")
        return {}
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        log_error(f"Gagal membaca file {filepath}: {e}")
        return {}

def save_json_file(filepath, data):
    """
    Menyimpan data dict ke JSON. 
    Gunakan .tmp => os.replace untuk atomic save.
    """
    try:
        tmp_file = filepath + ".tmp"
        with open(tmp_file, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_file, filepath)
    except Exception as e:
        log_error(f"Gagal menulis file {filepath}: {e}")

def get_file_hash(filepath):
    if not os.path.isfile(filepath):
        return None
    import hashlib
    try:
        md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                md5.update(chunk)
        return md5.hexdigest()
    except Exception as e:
        log_error(f"get_file_hash({filepath}): {e}")
        return None

# ------------------------------ 
# 2) OVERRIDE USER/PASS & MASK
# ------------------------------
from urllib.parse import quote, urlparse, urlunparse

def override_userpass(rtsp_url, user, pwd):
    parsed = urlparse(rtsp_url)
    user_esc = quote(user, safe='')
    pwd_esc  = quote(pwd,  safe='')
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    new_netloc = f"{user_esc}:{pwd_esc}@{host}{port}"

    new_scheme = parsed.scheme or "rtsp"
    new_path   = parsed.path or ""
    new_params = parsed.params or ""
    new_query  = parsed.query or ""
    new_frag   = parsed.fragment or ""

    return urlunparse((new_scheme, new_netloc, new_path, new_params, new_query, new_frag))

def mask_url_for_log(rtsp_url: str) -> str:
    p = urlparse(rtsp_url)
    if p.hostname:
        host = p.hostname or ""
        port = f":{p.port}" if p.port else ""
        new_netloc = f"****:****@{host}{port}"
        return urlunparse((p.scheme, new_netloc, p.path, p.params, p.query, p.fragment))
    else:
        return rtsp_url

# ------------------------------ 
# 3) START & STOP FFmpeg
# ------------------------------
def start_ffmpeg_pipeline(channel, title, rtsp_link):
    out_dir = os.path.join(HLS_OUTPUT_DIR, f"ch_{channel}")
    os.makedirs(out_dir, exist_ok=True)

    masked_link = mask_url_for_log(rtsp_link)
    cmd = (
        f"ffmpeg -y "
        f"-loglevel error "
        f"-rtsp_transport tcp "
        f"-i '{rtsp_link}' "
        f"-c copy "
        f"-hls_time {HLS_TIME} "
        f"-hls_list_size {HLS_LIST_SIZE} "
        f"-hls_flags delete_segments+program_date_time "
        f"-metadata title='{title} | CH {channel}' "
        f"-f hls {os.path.join(out_dir, 'index.m3u8')}"
    )
    masked_cmd = cmd.replace(rtsp_link, masked_link)
    log_info(f"Menjalankan FFmpeg => channel={channel}, cmd={masked_cmd}")

    try:
        proc = subprocess.Popen(shlex.split(cmd))
        ffmpeg_processes[channel] = proc
        # Set pipeline states => True
        channel_states[channel] = True
        # is_active=true di JSON
        set_is_active_in_json(channel, True)
    except Exception as e:
        log_error(f"Gagal start pipeline channel={channel}: {e}")

def stop_ffmpeg_pipeline(channel):
    proc = ffmpeg_processes.get(channel)
    if proc and proc.poll() is None:
        log_info(f"Stop pipeline => channel={channel}")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    ffmpeg_processes.pop(channel, None)
    # Set pipeline states => False
    channel_states[channel] = False
    # is_active=false di JSON
    set_is_active_in_json(channel, False)

def set_is_active_in_json(channel, active: bool):
    data = load_json_file(CHANNEL_VALIDATION_PATH)
    ch_str = str(channel)
    if ch_str not in data:
        data[ch_str] = {}
    data[ch_str]["is_active"] = active
    data[ch_str]["last_update"] = datetime.now().isoformat()
    save_json_file(CHANNEL_VALIDATION_PATH, data)

# ------------------------------ 
# 4) AMBIL CHANNEL DARI resource_monitor_state.json
# ------------------------------
def get_channels_from_resource():
    j = load_json_file(RESOURCE_MONITOR_PATH)
    if not j:
        return ("DefaultTitle", [], "127.0.0.1")

    scfg     = j.get("stream_config", {})
    rtsp_ip  = scfg.get("rtsp_ip", "127.0.0.1")
    title    = scfg.get("stream_title", "DefaultTitle")

    test_ch  = scfg.get("test_channel", "off")
    ch_count = scfg.get("channel_count", 0)
    ch_list  = scfg.get("channel_list", [])

    if test_ch.lower() != "off":
        arr = [int(x.strip()) for x in test_ch.split(",") if x.strip().isdigit()]
        return (title, arr, rtsp_ip)
    else:
        if ch_count and ch_list:
            return (title, ch_list[:ch_count], rtsp_ip)
        else:
            return (title, [], rtsp_ip)

# ------------------------------ 
# 5) INITIAL SETUP => pipeline
# ------------------------------
def initial_ffmpeg_setup():
    log_info("Memulai pipeline & monitor di ffmpeg_manager (versi is_active).")

    title, channels, rtsp_ip = get_channels_from_resource()
    log_info(f"[initial_ffmpeg_setup] => channels={channels}, title={title}, rtsp_ip={rtsp_ip}")

    try:
        user, pwd = decode_credentials()
    except Exception as e:
        log_error(f"decode_credentials => {e}")
        log_warning("Tidak jalan pipeline => credential invalid.")
        return

    val_data = load_json_file(CHANNEL_VALIDATION_PATH)

    with data_lock:
        for ch in channels:
            tracked_channels.add(ch)

            info = val_data.get(str(ch), {})
            # Baca is_active & error_msg
            is_active = info.get("is_active", False)
            err_msg   = info.get("error_msg")
            if err_msg:
                log_info(f"Channel {ch} => error_msg => skip pipeline.")
                channel_states[ch] = False
                set_is_active_in_json(ch, False)
                continue

            # is_active => jika true => jalankan pipeline
            if is_active:
                # override userpass
                raw_link = info.get("livestream_link")
                if not raw_link:
                    # fallback => "rtsp://...:554/cam/realmonitor?channel=ch"
                    raw_link = f"rtsp://{rtsp_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
                rtsp_link = override_userpass(raw_link, user, pwd)
                start_ffmpeg_pipeline(ch, title, rtsp_link)
            else:
                log_info(f"Channel {ch} => is_active=false => skip pipeline.")
                channel_states[ch] = False
                set_is_active_in_json(ch, False)

# ------------------------------ 
# 6) MONITOR LOOP
# ------------------------------
def monitor_loop(interval=60):
    global resource_hash, validation_hash
    while True:
        try:
            # Hash file resource
            new_res = get_file_hash(RESOURCE_MONITOR_PATH)
            # Hash file validation
            new_val = get_file_hash(CHANNEL_VALIDATION_PATH)

            with data_lock:
                # Cek channel_validation
                if new_val != validation_hash:
                    validation_hash = new_val
                    val_data = load_json_file(CHANNEL_VALIDATION_PATH)
                    update_channels_state(val_data)

                # Cek resource => add/remove channel
                if new_res != resource_hash:
                    resource_hash = new_res
                    title, new_ch_list, rtsp_ip = get_channels_from_resource()
                    update_channels_list(title, new_ch_list, rtsp_ip)

        except Exception as e:
            log_error(f"monitor_loop => {e}")

        time.sleep(interval)

def update_channels_state(val_data: dict):
    """
    Baca is_active, error_msg => jalankan/hentikan pipeline
    """
    try:
        user, pwd = decode_credentials()
    except Exception as e:
        log_error(f"decode_credentials => {e}")
        return

    for ch in tracked_channels:
        info = val_data.get(str(ch), {})
        is_active = info.get("is_active", False)
        err_msg   = info.get("error_msg", None)

        prev_state = channel_states.get(ch, False)

        # Jika ada error => stop pipeline
        if err_msg:
            if prev_state:
                log_info(f"Channel {ch} => error_msg => stop pipeline.")
                stop_ffmpeg_pipeline(ch)
            else:
                # Pastikan is_active=false di JSON
                set_is_active_in_json(ch, False)
            continue

        if is_active:
            # jika sebelumnya tidak aktif => start pipeline
            if not prev_state:
                # ambil link atau fallback
                raw_link = info.get("livestream_link")
                # fallback
                if not raw_link:
                    _, _, fallback_ip = get_channels_from_resource()
                    raw_link = f"rtsp://{fallback_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
                rtsp_link = override_userpass(raw_link, user, pwd)
                log_info(f"Channel {ch} => is_active=true => start pipeline.")
                start_ffmpeg_pipeline(ch, "AutoTitle", rtsp_link)
        else:
            # if prev_state => stop pipeline
            if prev_state:
                log_info(f"Channel {ch} => is_active=false => stop pipeline.")
                stop_ffmpeg_pipeline(ch)

def update_channels_list(title, new_ch_list, rtsp_ip):
    """
    Menangani penambahan/penghapusan channel di resource_monitor_state.json
    """
    val_data = load_json_file(CHANNEL_VALIDATION_PATH)

    new_set = set(new_ch_list)
    added   = new_set - tracked_channels
    removed = tracked_channels - new_set

    if added:
        log_info(f"Channel baru => {added}")
        for ch in added:
            tracked_channels.add(ch)
            info = val_data.get(str(ch), {})
            is_active = info.get("is_active", False)
            err_msg   = info.get("error_msg", None)

            if err_msg:
                log_info(f"Channel {ch} => error_msg => skip pipeline.")
                channel_states[ch] = False
                set_is_active_in_json(ch, False)
                continue

            # is_active => jika true => start pipeline
            if is_active:
                from utils import decode_credentials
                try:
                    user, pwd = decode_credentials()
                except:
                    log_error("decode_credentials => error => skip pipeline")
                    set_is_active_in_json(ch, False)
                    channel_states[ch] = False
                    continue

                raw_link = info.get("livestream_link")
                if not raw_link:
                    raw_link = f"rtsp://{rtsp_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
                rtsp_link = override_userpass(raw_link, user, pwd)
                log_info(f"Channel {ch} => added => is_active=true => start pipeline.")
                start_ffmpeg_pipeline(ch, title, rtsp_link)
            else:
                log_info(f"Channel {ch} => added => is_active=false => skip pipeline.")
                channel_states[ch] = False
                set_is_active_in_json(ch, False)

    if removed:
        log_info(f"Channel dihapus => {removed}")
        for ch in removed:
            stop_ffmpeg_pipeline(ch)
            tracked_channels.remove(ch)
            channel_states.pop(ch, None)

# ------------------------------
# 7) MAIN SERVICE
# ------------------------------
def main_service():
    initial_ffmpeg_setup()
    t = threading.Thread(target=monitor_loop, kwargs={"interval":60}, daemon=True)
    t.start()

    # Idle loop
    while True:
        time.sleep(1)

if __name__=="__main__":
    main_service()