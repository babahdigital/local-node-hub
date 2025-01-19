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
from urllib.parse import quote, urlparse, urlunparse
from flask import Flask, send_from_directory, abort

# 1) Import decode_credentials() dari utils.py
#    dan juga setup_category_logger utk logging
sys.path.append("/app/scripts")
from utils import decode_credentials, setup_category_logger

app = Flask(__name__)

# Buat logger kategori "CCTV"
logger = setup_category_logger("CCTV")

# --------------------------------------------------------
# 0. KONFIGURASI & GLOBAL VAR
# --------------------------------------------------------
RESOURCE_MONITOR_PATH = "/mnt/Data/Syslog/resource/resource_monitor_state.json"
CHANNEL_VALIDATION_PATH = "/mnt/Data/Syslog/rtsp/channel_validation.json"

HLS_OUTPUT_DIR = "/app/streamserver/hls"
HTML_BASE_DIR  = "/app/streamserver/html"

# Variabel environment HLS
HLS_TIME      = os.environ.get("HLS_TIME", "2")
HLS_LIST_SIZE = os.environ.get("HLS_LIST_SIZE", "5")

# Data global
ffmpeg_processes      = {}   # {channel: subprocess.Popen}
channel_black_status  = {}   # {channel: bool}
tracked_channels      = set()
data_lock             = threading.Lock()

resource_monitor_state_hash = None
channel_validation_hash     = None

# --------------------------------------------------------
# 1. override_userpass pakai urlparse
# --------------------------------------------------------
def override_userpass(original_link, user, pwd):
    """
    Override user:pass di link RTSP.
    1) Parse URL dengan urlparse => abaikan user:pass lama
    2) Rebuild netloc => {user_esc}:{pwd_esc}@host:port
    3) Urlunparse => kembalikan link final
    """
    parsed = urlparse(original_link)

    # URL-encode user & pass
    user_esc = quote(user, safe='')
    pwd_esc  = quote(pwd,  safe='')

    host = parsed.hostname or ""  # ex: "172.16.10.252"
    port = f":{parsed.port}" if parsed.port else ""  # ex: ":554" or ""

    new_netloc = f"{user_esc}:{pwd_esc}@{host}{port}"
    new_scheme = parsed.scheme or "rtsp"
    new_path   = parsed.path or ""
    new_params = parsed.params or ""
    new_query  = parsed.query or ""
    new_frag   = parsed.fragment or ""

    # Re-assemble
    return urlunparse((new_scheme, new_netloc, new_path, new_params, new_query, new_frag))

# --------------------------------------------------------
# 2. HELPER FUNCTIONS
# --------------------------------------------------------
def load_json_file(filepath):
    if not os.path.isfile(filepath):
        logger.warning(f"File {filepath} tidak ditemukan.")
        return None
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Gagal membaca file {filepath}: {e}")
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
        logger.error(f"get_file_hash({filepath}): {e}")
        return None

def start_ffmpeg_pipeline(channel, title, rtsp_link):
    out_dir = os.path.join(HLS_OUTPUT_DIR, f"ch_{channel}")
    os.makedirs(out_dir, exist_ok=True)

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
        f"-f hls "
        f"{os.path.join(out_dir, 'index.m3u8')}"
    )

    logger.info(f"Menjalankan FFmpeg => channel={channel}, cmd={cmd}")
    try:
        proc = subprocess.Popen(shlex.split(cmd))
        ffmpeg_processes[channel] = proc
    except Exception as e:
        logger.error(f"Gagal start pipeline channel={channel}: {e}")

def stop_ffmpeg_pipeline(channel):
    proc = ffmpeg_processes.get(channel)
    if proc and proc.poll() is None:
        logger.info(f"Stop pipeline => channel={channel}")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    ffmpeg_processes.pop(channel, None)

# --------------------------------------------------------
# 3. Ambil Daftar Channel
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
    channel_list  = stream_config.get("channel_list", [])

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
# 4. Setup Awal => jalankan pipeline
# --------------------------------------------------------
def initial_ffmpeg_setup():
    title, channels, rtsp_ip = get_channel_list_from_resource()
    logger.info(f"initial_ffmpeg_setup => channels={channels}, title={title}, rtsp_ip={rtsp_ip}")

    try:
        user, pwd = decode_credentials()
    except Exception as e:
        logger.error(f"decode_credentials => {e}")
        logger.warning("Pipeline tidak jalan => credential invalid.")
        return

    validation_data = load_json_file(CHANNEL_VALIDATION_PATH) or {}

    with data_lock:
        for ch in channels:
            tracked_channels.add(ch)
            black_ok  = True
            error_msg = None

            # Bentuk link minimal => "rtsp://{host}:554/cam/...?channel=ch"
            # Tanpa user:pass => agar override_userpass yang handle
            raw_link = f"rtsp://{rtsp_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
            rtsp_link = override_userpass(raw_link, user, pwd)

            if str(ch) in validation_data:
                ch_info = validation_data[str(ch)]
                if ch_info.get("black_ok", False) is False:
                    black_ok = False
                custom_link = ch_info.get("livestream_link", "")
                error_msg   = ch_info.get("error_msg", None)

                if custom_link:
                    rtsp_link = override_userpass(custom_link, user, pwd)

            if error_msg:
                logger.info(f"Channel {ch} => error_msg={error_msg} => skip pipeline.")
                channel_black_status[ch] = False
                continue

            channel_black_status[ch] = black_ok
            if black_ok:
                start_ffmpeg_pipeline(ch, title, rtsp_link)
            else:
                logger.info(f"Channel {ch} => black_ok=false => skip pipeline.")

# --------------------------------------------------------
# 5. Monitor Loop => pantau perubahan file
# --------------------------------------------------------
def monitor_loop(interval=60):
    global resource_monitor_state_hash
    global channel_validation_hash

    while True:
        try:
            new_r_hash = get_file_hash(RESOURCE_MONITOR_PATH)
            new_v_hash = get_file_hash(CHANNEL_VALIDATION_PATH)

            with data_lock:
                if new_v_hash != channel_validation_hash:
                    channel_validation_hash = new_v_hash
                    val_data = load_json_file(CHANNEL_VALIDATION_PATH) or {}
                    update_black_ok_and_error(val_data)

                if new_r_hash != resource_monitor_state_hash:
                    resource_monitor_state_hash = new_r_hash
                    title, new_channels, rtsp_ip = get_channel_list_from_resource()
                    update_channels(title, new_channels, rtsp_ip)

        except Exception as e:
            logger.error(f"monitor_loop => {e}")

        time.sleep(interval)

def update_black_ok_and_error(val_data):
    try:
        user, pwd = decode_credentials()
    except Exception as e:
        logger.error(f"decode_credentials => {e}")
        return

    for ch in list(tracked_channels):
        prev_status = channel_black_status.get(ch, True)
        new_black   = True
        new_error   = None

        if str(ch) in val_data:
            ch_info  = val_data[str(ch)]
            if ch_info.get("black_ok", False) is False:
                new_black = False
            new_error = ch_info.get("error_msg", None)

        if new_error:
            if prev_status is True:
                logger.info(f"Channel {ch} => error_msg={new_error} => stop pipeline.")
                stop_ffmpeg_pipeline(ch)
                channel_black_status[ch] = False
            continue

        if not new_black:
            if prev_status is True:
                logger.info(f"Channel {ch} => black_ok => false => stop pipeline.")
                stop_ffmpeg_pipeline(ch)
                channel_black_status[ch] = False
        else:
            if not prev_status:
                logger.info(f"Channel {ch} => black_ok => true => start pipeline.")
                ch_info = val_data.get(str(ch), {})
                custom_link = ch_info.get("livestream_link", "")
                if custom_link:
                    rtsp_link = override_userpass(custom_link, user, pwd)
                else:
                    _, _, fallback_ip = get_channel_list_from_resource()
                    raw_link = f"rtsp://{fallback_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
                    rtsp_link = override_userpass(raw_link, user, pwd)

                start_ffmpeg_pipeline(ch, "AutoTitle", rtsp_link)
                channel_black_status[ch] = True

def update_channels(title, new_channels, rtsp_ip):
    try:
        user, pwd = decode_credentials()
    except Exception as e:
        logger.error(f"decode_credentials => {e}")
        return

    val_data = load_json_file(CHANNEL_VALIDATION_PATH) or {}
    new_set  = set(new_channels)

    added = new_set - tracked_channels
    if added:
        logger.info(f"channel baru => {added}")
        for ch in added:
            tracked_channels.add(ch)
            black_ok  = True
            error_msg = None

            if str(ch) in val_data:
                ch_info = val_data[str(ch)]
                if ch_info.get("black_ok", False) is False:
                    black_ok = False
                error_msg = ch_info.get("error_msg", None)

            if error_msg:
                logger.info(f"Channel {ch} => error_msg={error_msg} => skip pipeline.")
                channel_black_status[ch] = False
                continue

            channel_black_status[ch] = black_ok
            if black_ok:
                raw_link = f"rtsp://{rtsp_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
                rtsp_link = override_userpass(raw_link, user, pwd)

                if str(ch) in val_data:
                    custom = val_data[str(ch)].get("livestream_link","")
                    if custom:
                        rtsp_link = override_userpass(custom, user, pwd)

                start_ffmpeg_pipeline(ch, title, rtsp_link)
            else:
                logger.info(f"Channel {ch} => black_ok=false => skip pipeline.")

    removed = tracked_channels - new_set
    if removed:
        logger.info(f"channel dihapus => {removed}")
        for ch in removed:
            stop_ffmpeg_pipeline(ch)
            tracked_channels.remove(ch)
            channel_black_status.pop(ch, None)

# --------------------------------------------------------
# 6. FLASK ROUTES
# --------------------------------------------------------
@app.route("/")
def index():
    index_file = os.path.join(HTML_BASE_DIR, "index.html")
    if os.path.isfile(index_file):
        return send_from_directory(HTML_BASE_DIR, "index.html")
    else:
        return "<h1>Welcome. No index.html found.</h1>"

@app.route("/ch<int:channel>/", defaults={"filename": "index.m3u8"}, strict_slashes=False)
@app.route("/ch<int:channel>/<path:filename>")
def serve_channel_files(channel, filename):
    with data_lock:
        val_data = load_json_file(CHANNEL_VALIDATION_PATH)
        if val_data and str(channel) in val_data:
            if val_data[str(channel)].get("error_msg"):
                return f"<h1>Channel {channel} error => {val_data[str(channel)]['error_msg']}</h1>", 404
            if val_data[str(channel)].get("black_ok", True) is False:
                return f"<h1>Channel {channel} black_ok=false</h1>", 404

    folder_path = os.path.join(HLS_OUTPUT_DIR, f"ch_{channel}")
    return send_from_directory(folder_path, filename)

@app.route("/hls/<int:channel>/<path:filename>")
def serve_hls_compat(channel, filename):
    with data_lock:
        val_data = load_json_file(CHANNEL_VALIDATION_PATH)
        if val_data and str(channel) in val_data:
            if val_data[str(channel)].get("error_msg"):
                return f"<h1>Channel {channel} error => {val_data[str(channel)]['error_msg']}</h1>", 404
            if val_data[str(channel)].get("black_ok", True) is False:
                return f"<h1>Channel {channel} black_ok=false</h1>", 404

    folder_path = os.path.join(HLS_OUTPUT_DIR, f"ch_{channel}")
    return send_from_directory(folder_path, filename)

@app.errorhandler(404)
def custom_404(e):
    return "<h1>404 Not Found</h1>", 404

@app.errorhandler(500)
def custom_500(e):
    return "<h1>500 Internal Server Error</h1>", 500

# --------------------------------------------------------
# 7. MAIN: Pipeline & Monitor
# --------------------------------------------------------
logger.info("Memulai pipeline & monitor loop (Gunicorn top-level)")

# 1) Jalankan pipeline awal
initial_ffmpeg_setup()

# 2) Jalankan monitor loop di background
def run_monitor():
    monitor_loop(interval=60)

t = threading.Thread(target=run_monitor, daemon=True)
t.start()

# 3) Gunicorn akan mencari 'app' ini.
# Gunakan 1 worker => pipeline tidak berulang.