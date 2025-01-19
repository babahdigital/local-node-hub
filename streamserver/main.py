#!/usr/bin/env python3
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

sys.path.append("/app/scripts")
from utils import decode_credentials, setup_category_logger

app = Flask(__name__)
logger = setup_category_logger("CCTV")

RESOURCE_MONITOR_PATH = "/mnt/Data/Syslog/resource/resource_monitor_state.json"
CHANNEL_VALIDATION_PATH = "/mnt/Data/Syslog/rtsp/channel_validation.json"

HLS_OUTPUT_DIR = "/app/streamserver/hls"  # folder HLS
HTML_BASE_DIR  = "/app/streamserver/html" # folder HTML

HLS_TIME      = os.environ.get("HLS_TIME", "2")
HLS_LIST_SIZE = os.environ.get("HLS_LIST_SIZE", "5")

ffmpeg_processes      = {}  # {channel: Popen-object}
channel_black_status  = {}  # {channel: bool}
tracked_channels      = set()
data_lock             = threading.Lock()

resource_monitor_state_hash = None
channel_validation_hash     = None

def override_userpass(original_link, user, pwd):
    """
    Mem-parse URL rtsp, lalu mengganti user:pass.
    URL-encode agar '@' di password tidak menimbulkan dobel '@'.
    """
    parsed = urlparse(original_link)
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
    """
    Mem-parse rtsp_url, menyembunyikan user:pass di log => ****:****@host:port
    """
    parsed = urlparse(rtsp_url)
    if parsed.hostname:
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        new_netloc = f"****:****@{host}{port}"
        return urlunparse((parsed.scheme, new_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    else:
        return rtsp_url

def mask_any_rtsp_in_string(text: str) -> str:
    """Jika text mengandung 'rtsp://', kita mask agar tidak bocor password."""
    if not text or "rtsp://" not in text:
        return text
    idx = text.find("rtsp://")
    prefix = text[:idx]
    url_part = text[idx:].split(" ", 1)[0]
    suffix = ""
    if " " in text[idx:]:
        suffix = text[idx:].split(" ", 1)[1]
    masked_url = mask_url_for_log(url_part)
    return prefix + masked_url + " " + suffix

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
    """
    Menjalankan FFmpeg => output HLS di HLS_OUTPUT_DIR/ch_{channel}/index.m3u8
    Pastikan folder sudah ada agar 'failed to rename file ...' tidak muncul.
    """
    out_dir = os.path.join(HLS_OUTPUT_DIR, f"ch_{channel}")
    os.makedirs(out_dir, exist_ok=True)  # penting!

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
        f"-f hls "
        f"{os.path.join(out_dir, 'index.m3u8')}"
    )
    masked_cmd = cmd.replace(rtsp_link, masked_link)
    logger.info(f"Menjalankan FFmpeg => channel={channel}, cmd={masked_cmd}")

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

def get_channel_list_from_resource():
    cfg = load_json_file(RESOURCE_MONITOR_PATH)
    if not cfg:
        return ("default_title", [], "127.0.0.1")

    stream_config = cfg.get("stream_config", {})
    title   = stream_config.get("stream_title", "default_title")
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

            raw_link = f"rtsp://{rtsp_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
            rtsp_link = override_userpass(raw_link, user, pwd)

            if str(ch) in validation_data:
                ch_info = validation_data[str(ch)]
                # black_ok
                if ch_info.get("black_ok", False) is False:
                    black_ok = False
                # error_msg
                error_msg   = ch_info.get("error_msg", None)
                # link custom
                custom_link = ch_info.get("livestream_link", "")
                if custom_link:
                    rtsp_link = override_userpass(custom_link, user, pwd)

            # Jika error_msg => skip pipeline
            if error_msg:
                masked_err = mask_any_rtsp_in_string(error_msg)
                logger.info(f"Channel {ch} => error_msg={masked_err} => skip pipeline.")
                channel_black_status[ch] = False
                continue

            # Jika black_ok=false => skip
            channel_black_status[ch] = black_ok
            if black_ok:
                start_ffmpeg_pipeline(ch, title, rtsp_link)
            else:
                logger.info(f"Channel {ch} => black_ok=false => skip pipeline.")

def monitor_loop(interval=60):
    global resource_monitor_state_hash
    global channel_validation_hash

    while True:
        try:
            new_r_hash = get_file_hash(RESOURCE_MONITOR_PATH)
            new_v_hash = get_file_hash(CHANNEL_VALIDATION_PATH)

            with data_lock:
                # Jika channel_validation.json berubah
                if new_v_hash != channel_validation_hash:
                    channel_validation_hash = new_v_hash
                    val_data = load_json_file(CHANNEL_VALIDATION_PATH) or {}
                    update_black_ok_and_error(val_data)

                # Jika resource_monitor_state.json berubah
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
            masked_err = mask_any_rtsp_in_string(new_error)
            if prev_status:
                logger.info(f"Channel {ch} => error_msg={masked_err} => stop pipeline.")
                stop_ffmpeg_pipeline(ch)
                channel_black_status[ch] = False
            continue

        if not new_black:
            if prev_status:
                logger.info(f"Channel {ch} => black_ok=false => stop pipeline.")
                stop_ffmpeg_pipeline(ch)
                channel_black_status[ch] = False
        else:
            # black_ok => true => start pipeline kalau sebelumnya stop
            if not prev_status:
                logger.info(f"Channel {ch} => black_ok=true => start pipeline.")
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

    # Channel baru
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
                masked_err = mask_any_rtsp_in_string(error_msg)
                logger.info(f"Channel {ch} => error_msg={masked_err} => skip pipeline.")
                channel_black_status[ch] = False
                continue

            channel_black_status[ch] = black_ok
            if black_ok:
                raw_link = f"rtsp://{rtsp_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
                rtsp_link = override_userpass(raw_link, user, pwd)

                if str(ch) in val_data:
                    custom_link = val_data[str(ch)].get("livestream_link", "")
                    if custom_link:
                        rtsp_link = override_userpass(custom_link, user, pwd)

                start_ffmpeg_pipeline(ch, title, rtsp_link)
            else:
                logger.info(f"Channel {ch} => black_ok=false => skip pipeline.")

    # Channel dihapus
    removed = tracked_channels - new_set
    if removed:
        logger.info(f"channel dihapus => {removed}")
        for ch in removed:
            stop_ffmpeg_pipeline(ch)
            tracked_channels.remove(ch)
            channel_black_status.pop(ch, None)

# -----------
# FLASK ROUTES
# -----------
@app.route("/")
def index():
    index_file = os.path.join(HTML_BASE_DIR, "index.html")
    if os.path.isfile(index_file):
        return send_from_directory(HTML_BASE_DIR, "index.html")
    else:
        return "<h1>Welcome. No index.html found.</h1>"

@app.route("/ch<int:channel>", defaults={"filename": "index.m3u8"}, strict_slashes=False)
@app.route("/ch<int:channel>/<path:filename>")
def serve_channel_files(channel, filename):
    """
    Endpoint => http://host/ch1 => menampilkan file HLS (index.m3u8),
    atau segmen .ts (http://host/ch1/seg0.ts), dsb.
    """
    with data_lock:
        val_data = load_json_file(CHANNEL_VALIDATION_PATH)
        if val_data and str(channel) in val_data:
            err_msg = val_data[str(channel)].get("error_msg")
            blackok = val_data[str(channel)].get("black_ok", True)

            if err_msg:
                masked_err = mask_any_rtsp_in_string(err_msg)
                # Coba load error.stream.html
                error_html = os.path.join(HTML_BASE_DIR, "error", "error.stream.html")
                if os.path.isfile(error_html):
                    with open(error_html, "r") as f:
                        tmpl = f.read()
                    out_page = tmpl.replace("{{ channel }}", str(channel))
                    out_page = out_page.replace("{{ error_msg }}", masked_err)
                    return out_page, 200
                else:
                    # fallback => 404
                    return f"<h1>Channel {channel} error => {masked_err}</h1>", 404

            if not blackok:
                # Juga load misal error.stream.html jika mau
                # Atau kembalikan 404
                return f"<h1>Channel {channel} black_ok=false</h1>", 404

    folder_path = os.path.join(HLS_OUTPUT_DIR, f"ch_{channel}")
    return send_from_directory(folder_path, filename)

@app.errorhandler(404)
def custom_404(e):
    # Pakai file 404.html jika ada
    err_404_file = os.path.join(HTML_BASE_DIR, "error", "404.html")
    if os.path.isfile(err_404_file):
        return send_from_directory(os.path.join(HTML_BASE_DIR, "error"), "404.html"), 404
    else:
        return "<h1>404 Not Found</h1>", 404

@app.errorhandler(500)
def custom_500(e):
    return "<h1>500 Internal Server Error</h1>", 500

# -----------
# MAIN
# -----------
logger.info("Memulai pipeline & monitor loop (Gunicorn top-level)")

initial_ffmpeg_setup()

def run_monitor():
    monitor_loop(interval=60)

t = threading.Thread(target=run_monitor, daemon=True)
t.start()