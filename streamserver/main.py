#!/usr/bin/env python3
# stream_server.py

import os
import json
import subprocess
import shlex
import sys
import time
import threading
import hashlib
from flask import Flask, send_from_directory, abort, redirect

# Import utils untuk decode_credentials (pastikan utils.py ada di /app/scripts).
sys.path.append("/app/scripts")
from utils import decode_credentials

app = Flask(__name__)

# --------------------------------------------------------
# 0. KONFIGURASI & GLOBAL VAR
# --------------------------------------------------------
RESOURCE_MONITOR_PATH = "/mnt/Data/Syslog/resource/resource_monitor_state.json"
CHANNEL_VALIDATION_PATH = "/mnt/Data/Syslog/rtsp/channel_validation.json"

HLS_OUTPUT_DIR = "/app/streamserver/hls"   # folder untuk output HLS
HTML_BASE_DIR = "/app/streamserver/html"   # folder untuk file HTML (index, error, dsb.)

# Variabel environment HLS
HLS_TIME = os.environ.get("HLS_TIME", "2")
HLS_LIST_SIZE = os.environ.get("HLS_LIST_SIZE", "5")

# Data global untuk pipeline
ffmpeg_processes = {}      # {channel: subprocess.Popen}
channel_black_status = {}  # {channel: bool} => black_ok
tracked_channels = set()   # set of channel yang dipantau

data_lock = threading.Lock()  # lock untuk thread-safety
resource_monitor_state_hash = None
channel_validation_hash = None

# --------------------------------------------------------
# 1. HELPER FUNGSI
# --------------------------------------------------------
def load_json_file(filepath):
    if not os.path.isfile(filepath):
        return None
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Gagal membaca file {filepath}: {e}")
        return None

def get_file_hash(filepath):
    if not os.path.isfile(filepath):
        return None
    try:
        import hashlib
        md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                md5.update(chunk)
        return md5.hexdigest()
    except Exception as e:
        print(f"[ERROR] get_file_hash({filepath}): {e}")
        return None

def override_userpass(original_link, user, pwd):
    """Override user:pass di link RTSP."""
    if "://" in original_link:
        after_scheme = original_link.split("://", 1)[1]
    else:
        after_scheme = original_link

    if '@' in after_scheme:
        after_userpass = after_scheme.split('@', 1)[1]
    else:
        after_userpass = after_scheme

    return f"rtsp://{user}:{pwd}@{after_userpass}"

def start_ffmpeg_pipeline(channel, title, rtsp_link):
    out_dir = os.path.join(HLS_OUTPUT_DIR, f"ch_{channel}")
    os.makedirs(out_dir, exist_ok=True)

    # Ganti -stimeout => -rw_timeout 
    # -an => disable audio
    # -rtsp_transport tcp => pakai TCP
    # -timeout X => jika versi FFmpeg mendukung -timeout
    # (Jika -timeout pun tidak dikenali, coba hapus param itu.)

    cmd = (
        f"ffmpeg -y "
        f"-rtsp_transport tcp "
        f"-rw_timeout 5000000 "        
        f"-i '{rtsp_link}' "
        f"-c:v libx264 -an "
        f"-hls_time {HLS_TIME} "
        f"-hls_list_size {HLS_LIST_SIZE} "
        f"-hls_flags delete_segments+program_date_time "
        f"-metadata title='{title} | CH {channel}' "
        f"-f hls {os.path.join(out_dir, 'index.m3u8')}"
    )

    print(f"[INFO] Menjalankan FFmpeg => channel={channel}, cmd={cmd}")
    proc = subprocess.Popen(shlex.split(cmd))
    ffmpeg_processes[channel] = proc

def stop_ffmpeg_pipeline(channel):
    proc = ffmpeg_processes.get(channel)
    if proc and proc.poll() is None:
        print(f"[INFO] Menghentikan FFmpeg => channel={channel}")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    ffmpeg_processes.pop(channel, None)

# --------------------------------------------------------
# 2. AMBIL CHANNEL
# --------------------------------------------------------
def get_channel_list_from_resource():
    cfg = load_json_file(RESOURCE_MONITOR_PATH)
    if not cfg:
        return ("default_title", [], "127.0.0.1")

    stream_config = cfg.get("stream_config", {})
    title = stream_config.get("stream_title", "default_title")
    rtsp_ip = stream_config.get("rtsp_ip", "127.0.0.1")

    test_channel = stream_config.get("test_channel", "off")
    channel_count = stream_config.get("channel_count", 0)
    channel_list = stream_config.get("channel_list", [])

    if test_channel.lower() != "off":
        ch_list = [x.strip() for x in test_channel.split(",")]
        ch_list = [int(x) for x in ch_list if x.isdigit()]
        return (title, ch_list, rtsp_ip)
    else:
        if channel_count and channel_list:
            return (title, channel_list[:channel_count], rtsp_ip)
        else:
            return (title, [], rtsp_ip)

# --------------------------------------------------------
# 3. SETUP AWAL
# --------------------------------------------------------
def initial_ffmpeg_setup():
    title, channels, rtsp_ip = get_channel_list_from_resource()
    print(f"[INFO] initial_ffmpeg_setup => channels={channels}, title={title}, rtsp_ip={rtsp_ip}")

    try:
        user, pwd = decode_credentials()
    except Exception as e:
        print(f"[ERROR] decode_credentials => {e}")
        print("[WARNING] Pipeline tidak jalan krn credential invalid.")
        return

    validation_data = load_json_file(CHANNEL_VALIDATION_PATH) or {}

    with data_lock:
        for ch in channels:
            tracked_channels.add(ch)
            black_ok = True
            # fallback link
            rtsp_link = f"rtsp://{user}:{pwd}@{rtsp_ip}:554/cam/realmonitor?channel={ch}&subtype=0"

            if str(ch) in validation_data:
                if validation_data[str(ch)].get("black_ok", False) is False:
                    black_ok = False
                link_in_json = validation_data[str(ch)].get("livestream_link", "")
                if link_in_json:
                    rtsp_link = override_userpass(link_in_json, user, pwd)

            channel_black_status[ch] = black_ok
            if black_ok:
                start_ffmpeg_pipeline(ch, title, rtsp_link)
            else:
                print(f"[INFO] Channel {ch} => black_ok=false, skip pipeline.")

# --------------------------------------------------------
# 4. MONITOR LOOP
# --------------------------------------------------------
def monitor_loop(interval=60):
    global resource_monitor_state_hash
    global channel_validation_hash

    while True:
        try:
            new_resource_hash = get_file_hash(RESOURCE_MONITOR_PATH)
            new_validation_hash = get_file_hash(CHANNEL_VALIDATION_PATH)

            with data_lock:
                if new_validation_hash != channel_validation_hash:
                    channel_validation_hash = new_validation_hash
                    val_data = load_json_file(CHANNEL_VALIDATION_PATH) or {}
                    update_black_ok(val_data)

                if new_resource_hash != resource_monitor_state_hash:
                    resource_monitor_state_hash = new_resource_hash
                    title, new_channels, rtsp_ip = get_channel_list_from_resource()
                    update_channels(title, new_channels, rtsp_ip)

        except Exception as e:
            print(f"[ERROR] monitor_loop => {e}")

        time.sleep(interval)

def update_black_ok(val_data):
    try:
        user, pwd = decode_credentials()
    except Exception as e:
        print(f"[ERROR] decode_credentials => {e}")
        return

    for ch in list(tracked_channels):
        prev_black = channel_black_status.get(ch, True)
        new_black = True
        if str(ch) in val_data:
            if val_data[str(ch)].get("black_ok", False) is False:
                new_black = False

        if new_black != prev_black:
            if not new_black:
                print(f"[INFO] Channel {ch} => black_ok => false => stop pipeline.")
                stop_ffmpeg_pipeline(ch)
                channel_black_status[ch] = False
            else:
                print(f"[INFO] Channel {ch} => black_ok => true => start pipeline.")
                link_in_json = val_data[str(ch)].get("livestream_link", "") if str(ch) in val_data else ""
                if link_in_json:
                    rtsp_link = override_userpass(link_in_json, user, pwd)
                else:
                    _, _, fallback_ip = get_channel_list_from_resource()
                    rtsp_link = f"rtsp://{user}:{pwd}@{fallback_ip}:554/cam/realmonitor?channel={ch}&subtype=0"

                start_ffmpeg_pipeline(ch, "AutoTitle", rtsp_link)
                channel_black_status[ch] = True

def update_channels(title, new_channels, rtsp_ip):
    try:
        user, pwd = decode_credentials()
    except Exception as e:
        print(f"[ERROR] decode_credentials => {e}")
        return

    val_data = load_json_file(CHANNEL_VALIDATION_PATH) or {}
    new_set = set(new_channels)

    added = new_set - tracked_channels
    if added:
        print(f"[INFO] channel baru => {added}")
        for ch in added:
            tracked_channels.add(ch)
            black_ok = True
            if str(ch) in val_data:
                if val_data[str(ch)].get("black_ok", False) is False:
                    black_ok = False
            channel_black_status[ch] = black_ok

            link_in_json = val_data[str(ch)].get("livestream_link", "") if str(ch) in val_data else ""
            if black_ok:
                if link_in_json:
                    rtsp_link = override_userpass(link_in_json, user, pwd)
                else:
                    rtsp_link = f"rtsp://{user}:{pwd}@{rtsp_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
                start_ffmpeg_pipeline(ch, title, rtsp_link)
            else:
                print(f"[INFO] Channel {ch} => black_ok=false => skip pipeline.")

    removed = tracked_channels - new_set
    if removed:
        print(f"[INFO] channel dihapus => {removed}")
        for ch in removed:
            stop_ffmpeg_pipeline(ch)
            tracked_channels.remove(ch)
            channel_black_status.pop(ch, None)

# --------------------------------------------------------
# 5. FLASK ROUTES + HTML
# --------------------------------------------------------
@app.route("/ch<int:channel>/")
def direct_channel(channel):
    return redirect(f"/hls/{channel}/index.m3u8")

@app.route("/hls/<int:channel>/<path:filename>")
def serve_hls_files(channel, filename):
    with data_lock:
        val_data = load_json_file(CHANNEL_VALIDATION_PATH)
        if val_data:
            ch_str = str(channel)
            if ch_str in val_data:
                if val_data[ch_str].get("black_ok", True) is False:
                    return "<h1>Channel black_ok=false</h1>", 404

        folder_path = os.path.join(HLS_OUTPUT_DIR, f"ch_{channel}")
        return send_from_directory(folder_path, filename)

@app.route("/")
def serve_index_html():
    index_file = os.path.join(HTML_BASE_DIR, "index.html")
    if os.path.isfile(index_file):
        return send_from_directory(HTML_BASE_DIR, "index.html")
    else:
        return "<h1>Welcome. No index.html found.</h1>"

@app.errorhandler(404)
def custom_404(e):
    error_404 = os.path.join(HTML_BASE_DIR, "error", "404.html")
    if os.path.isfile(error_404):
        return send_from_directory(os.path.join(HTML_BASE_DIR, "error"), "404.html"), 404
    else:
        return "<h1>404 Not Found</h1>", 404

@app.errorhandler(500)
def custom_500(e):
    error_50x = os.path.join(HTML_BASE_DIR, "error", "50x.html")
    if os.path.isfile(error_50x):
        return send_from_directory(os.path.join(HTML_BASE_DIR, "error"), "50x.html"), 500
    else:
        return "<h1>500 Internal Server Error</h1>", 500

# --------------------------------------------------------
# 6. TOP-LEVEL CODE => PIPELINE & MONITOR
# --------------------------------------------------------
print("[INFO] Menjalankan pipeline & monitor di top-level import (Gunicorn)")

# 6.1 Inisialisasi pipeline (FFmpeg)
initial_ffmpeg_setup()

# 6.2 Jalankan monitor loop di background
def run_monitor():
    monitor_loop(interval=60)

t = threading.Thread(target=run_monitor, daemon=True)
t.start()

# --------------------------------------------------------
# 7. DEFINISI app => DIPAKAI GUNICORN
# --------------------------------------------------------
# Gunicorn akan mencari `app = Flask(__name__)`.
# Selesai!