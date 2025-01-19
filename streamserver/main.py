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
from flask import Flask, send_from_directory, abort, redirect

# Pastikan utils.py tersedia di /app/scripts
sys.path.append("/app/scripts")
from utils import decode_credentials, setup_category_logger

app = Flask(__name__)
logger = setup_category_logger("CCTV")

# -------------------------------------------------------
# 0. KONFIGURASI DAN PATH
# -------------------------------------------------------
RESOURCE_MONITOR_PATH   = "/mnt/Data/Syslog/resource/resource_monitor_state.json"
CHANNEL_VALIDATION_PATH = "/mnt/Data/Syslog/rtsp/channel_validation.json"

HLS_OUTPUT_DIR = "/app/streamserver/hls"
HTML_BASE_DIR  = "/app/streamserver/html"

HLS_TIME      = os.environ.get("HLS_TIME", "2")
HLS_LIST_SIZE = os.environ.get("HLS_LIST_SIZE", "5")

# Opsi freeze-check (ON/OFF). Anda bisa atur di environment
ENABLE_FREEZE_CHECK   = os.environ.get("ENABLE_FREEZE_CHECK", "true").lower() == "true"
FREEZE_SENSITIVITY    = float(os.environ.get("FREEZE_SENSITIVITY", "6.0"))
FREEZE_RECHECK_TIMES  = int(os.environ.get("FREEZE_RECHECK_TIMES", "5"))
FREEZE_RECHECK_DELAY  = float(os.environ.get("FREEZE_RECHECK_DELAY", "3.0"))

# Data pipeline
ffmpeg_processes     = {}   # {channel: subprocess.Popen}
channel_black_status = {}   # {channel: bool}
tracked_channels     = set()

# Lock & ephemeral error freeze
data_lock            = threading.Lock()
freeze_errors        = {}   # {channel: "Pesan freeze error"} - ephemeral

resource_monitor_state_hash = None
channel_validation_hash     = None

# -------------------------------------------------------
# 1. FUNGSI OVERRIDE DAN MASKING
# -------------------------------------------------------
def override_userpass(original_link, user, pwd):
    """
    Override user:pass di RTSP link, agar '@' di password
    tidak memunculkan '@' ganda. Memakai urlparse + quote.
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
    Mem-parse rtsp_url, lalu mengaburkan username & password di log.
    Contoh => rtsp://****:****@host:port/cam/...
    """
    parsed = urlparse(rtsp_url)
    if parsed.hostname:
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        new_netloc = f"****:****@{host}{port}"
        return urlunparse((parsed.scheme, new_netloc, parsed.path,
                           parsed.params, parsed.query, parsed.fragment))
    else:
        return rtsp_url

def mask_any_rtsp_in_string(text: str) -> str:
    """Jika dalam text ada substring 'rtsp://', kita mask URL-nya."""
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

# -------------------------------------------------------
# 2. FUNGSI UTILITAS (LOAD JSON, HASH, FFmpeg)
# -------------------------------------------------------
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
    import hashlib
    md5 = hashlib.md5()
    try:
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
    """
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

# -------------------------------------------------------
# 3. FUNGSI FREEZE CHECK
# -------------------------------------------------------
def check_freeze_frames(rtsp_url: str, freeze_sens: float, times: int, delay: float) -> bool:
    """
    Mengecek freeze dengan multiple re-check.
    Memanggil ffmpeg freezedetect => "freeze_start" di stderr berarti freeze terdeteksi.
    Return True jika TIDAK freeze.
    Return False jika freeze.
    """
    fail = 0
    for i in range(times):
        if not _freeze_once(rtsp_url, freeze_sens):
            fail += 1
        if i < times - 1:
            time.sleep(delay)
    # jika fail < times => berarti ada re-check yg ok
    # Kita definisikan: fail=times => semua attempt freeze => berarti freeze
    return (fail < times)

def _freeze_once(rtsp_url: str, freeze_sens: float) -> bool:
    """
    Satu kali check freeze selama ~5 detik.
    """
    cmd = [
        "ffmpeg","-hide_banner","-loglevel","error","-y","-err_detect","ignore_err",
        "-rtsp_transport","tcp","-i", rtsp_url,
        "-vf", f"freezedetect=n=-60dB:d={freeze_sens}",
        "-an","-t","5","-f","null","-"
    ]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        # Jika "freeze_start" muncul => artinya freeze terdeteksi
        if b"freeze_start" in r.stderr:
            logger.info("[FREEZE] freeze_start terdeteksi di stderr")
            return False
        return True
    except Exception as e:
        logger.error(f"[FREEZE] error => {e}")
        return False

# -------------------------------------------------------
# 4. AMBIL CHANNEL
# -------------------------------------------------------
def get_channel_list_from_resource():
    cfg = load_json_file(RESOURCE_MONITOR_PATH)
    if not cfg:
        return ("default_title", [], "127.0.0.1")

    scfg = cfg.get("stream_config", {})
    title   = scfg.get("stream_title", "default_title")
    rtsp_ip = scfg.get("rtsp_ip", "127.0.0.1")

    test_ch      = scfg.get("test_channel", "off")
    channel_cnt  = scfg.get("channel_count", 0)
    channel_list = scfg.get("channel_list", [])

    if test_ch.lower() != "off":
        arr = [x.strip() for x in test_ch.split(",")]
        arr = [int(x) for x in arr if x.isdigit()]
        return (title, arr, rtsp_ip)
    else:
        if channel_cnt and channel_list:
            return (title, channel_list[:channel_cnt], rtsp_ip)
        else:
            return (title, [], rtsp_ip)

# -------------------------------------------------------
# 5. SETUP AWAL (pipeline)
# -------------------------------------------------------
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
                info = validation_data[str(ch)]
                if info.get("black_ok", False) is False:
                    black_ok = False
                error_msg   = info.get("error_msg", None)
                custom_link = info.get("livestream_link", "")
                if custom_link:
                    rtsp_link = override_userpass(custom_link, user, pwd)

            # Ephemeral freeze check
            if ENABLE_FREEZE_CHECK and black_ok and not error_msg:
                # Lakukan freeze check => jika freeze => skip
                freeze_ok = check_freeze_frames(rtsp_link, FREEZE_SENSITIVITY, FREEZE_RECHECK_TIMES, FREEZE_RECHECK_DELAY)
                if not freeze_ok:
                    # tandai ephemeral error freeze
                    freeze_errors[ch] = f"ch={ch} => freeze => skip pipeline."
                    logger.info(f"[FREEZE] Channel {ch} => freeze => skip pipeline.")
                    black_ok = False

            if error_msg:
                masked_err = mask_any_rtsp_in_string(error_msg)
                logger.info(f"Channel {ch} => error_msg={masked_err} => skip pipeline.")
                channel_black_status[ch] = False
                continue

            channel_black_status[ch] = black_ok
            if black_ok:
                start_ffmpeg_pipeline(ch, title, rtsp_link)
            else:
                logger.info(f"Channel {ch} => black_ok=false => skip pipeline.")

# -------------------------------------------------------
# 6. MONITOR LOOP
# -------------------------------------------------------
def monitor_loop(interval=60):
    global resource_monitor_state_hash, channel_validation_hash

    while True:
        try:
            new_r_hash = get_file_hash(RESOURCE_MONITOR_PATH)
            new_v_hash = get_file_hash(CHANNEL_VALIDATION_PATH)

            with data_lock:
                # 1) update black_ok, error, freeze dsb
                if new_v_hash != channel_validation_hash:
                    channel_validation_hash = new_v_hash
                    val_data = load_json_file(CHANNEL_VALIDATION_PATH) or {}
                    update_black_ok_and_error(val_data)

                # 2) update penambahan/penghapusan channel
                if new_r_hash != resource_monitor_state_hash:
                    resource_monitor_state_hash = new_r_hash
                    title, new_channels, rtsp_ip = get_channel_list_from_resource()
                    update_channels(title, new_channels, rtsp_ip)

        except Exception as e:
            logger.error(f"monitor_loop => {e}")

        time.sleep(interval)

def update_black_ok_and_error(val_data):
    """
    - Jika ada error_msg => stop pipeline.
    - Jika black_ok=false => stop pipeline.
    - Jika black_ok=true dan pipeline belum jalan => start pipeline + freeze check.
    - Juga cek ephemeral freeze error => jika masih ada, skip.
    """
    try:
        user, pwd = decode_credentials()
    except Exception as e:
        logger.error(f"decode_credentials => {e}")
        return

    for ch in list(tracked_channels):
        prev_status = channel_black_status.get(ch, True)
        new_black   = True
        new_error   = None

        # Lihat validation
        if str(ch) in val_data:
            info = val_data[str(ch)]
            if info.get("black_ok", False) is False:
                new_black = False
            new_error = info.get("error_msg", None)

        # Ephemeral freeze error => kita simpan di freeze_errors
        ephemeral_err = freeze_errors.get(ch, None)
        if ephemeral_err:
            # Anggap freeze error => pipeline off
            new_black = False
            new_error = ephemeral_err

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
            # black_ok => true => pipeline jalan
            if not prev_status:
                # Lakukan freeze check lagi
                # Hanya jika ephemeral freeze tidak tercatat
                raw_link = f"rtsp://127.0.0.1:554/cam/realmonitor?channel={ch}&subtype=0"
                _, _, fallback_ip = get_channel_list_from_resource()
                raw_link = f"rtsp://{fallback_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
                # cek ada custom
                if str(ch) in val_data:
                    custom = val_data[str(ch)].get("livestream_link", "")
                    if custom:
                        raw_link = custom
                rtsp_link = override_userpass(raw_link, user, pwd)

                if ENABLE_FREEZE_CHECK:
                    freeze_ok = check_freeze_frames(rtsp_link, FREEZE_SENSITIVITY, FREEZE_RECHECK_TIMES, FREEZE_RECHECK_DELAY)
                    if not freeze_ok:
                        freeze_errors[ch] = f"ch={ch} => freeze => skip pipeline."
                        logger.info(f"[FREEZE] Channel {ch} => freeze => skip pipeline.")
                        channel_black_status[ch] = False
                        continue

                logger.info(f"Channel {ch} => black_ok=true => start pipeline.")
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
                info = val_data[str(ch)]
                if info.get("black_ok", False) is False:
                    black_ok = False
                error_msg = info.get("error_msg", None)

            # Ephemeral freeze error => reset dulu
            if ch in freeze_errors:
                freeze_errors.pop(ch)

            if error_msg:
                masked_err = mask_any_rtsp_in_string(error_msg)
                logger.info(f"Channel {ch} => error_msg={masked_err} => skip pipeline.")
                channel_black_status[ch] = False
                continue

            channel_black_status[ch] = black_ok
            if black_ok:
                raw_link = f"rtsp://{rtsp_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
                # cek custom link
                if str(ch) in val_data:
                    custom = val_data[str(ch)].get("livestream_link", "")
                    if custom:
                        raw_link = custom
                rtsp_link = override_userpass(raw_link, user, pwd)

                # freeze check
                if ENABLE_FREEZE_CHECK:
                    freeze_ok = check_freeze_frames(rtsp_link, FREEZE_SENSITIVITY, FREEZE_RECHECK_TIMES, FREEZE_RECHECK_DELAY)
                    if not freeze_ok:
                        freeze_errors[ch] = f"ch={ch} => freeze => skip pipeline."
                        logger.info(f"[FREEZE] Channel {ch} => freeze => skip pipeline.")
                        channel_black_status[ch] = False
                        continue

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
            # Hapus ephemeral freeze error
            if ch in freeze_errors:
                freeze_errors.pop(ch)

# -------------------------------------------------------
# 7. FLASK ROUTES
# -------------------------------------------------------
@app.route("/")
def index():
    index_file = os.path.join(HTML_BASE_DIR, "index.html")
    if os.path.isfile(index_file):
        return send_from_directory(HTML_BASE_DIR, "index.html")
    else:
        return "<h1>Welcome. No index.html found.</h1>"

# Agar http://host/ch1 (tanpa slash) redirect ke /ch1/
@app.route("/ch<int:channel>", strict_slashes=False)
def ch_no_slash(channel):
    return redirect(f"/ch{channel}/")

@app.route("/ch<int:channel>/", defaults={"filename": "index.m3u8"}, strict_slashes=False)
@app.route("/ch<int:channel>/<path:filename>")
def serve_channel_files(channel, filename):
    with data_lock:
        # Cek ephemeral freeze
        if channel in freeze_errors:
            # Tampilkan error freeze
            masked_err = freeze_errors[channel]
            error_html = os.path.join(HTML_BASE_DIR, "error", "error.stream.html")
            if os.path.isfile(error_html):
                with open(error_html, "r") as f:
                    tmpl = f.read()
                out_page = tmpl.replace("{{ channel }}", str(channel))
                out_page = out_page.replace("{{ error_msg }}", masked_err)
                return out_page, 200
            else:
                return f"<h1>Channel {channel} freeze error => {masked_err}</h1>", 404

        # Lanjut => cek channel_validation
        val_data = load_json_file(CHANNEL_VALIDATION_PATH)
        if val_data and str(channel) in val_data:
            info     = val_data[str(channel)]
            err_msg  = info.get("error_msg")
            black_ok = info.get("black_ok", True)

            if err_msg:
                masked_err = mask_any_rtsp_in_string(err_msg)
                error_html = os.path.join(HTML_BASE_DIR, "error", "error.stream.html")
                if os.path.isfile(error_html):
                    with open(error_html, "r") as f:
                        tmpl = f.read()
                    out_page = tmpl.replace("{{ channel }}", str(channel))
                    out_page = out_page.replace("{{ error_msg }}", masked_err)
                    return out_page, 200
                else:
                    return f"<h1>Channel {channel} error => {masked_err}</h1>", 404

            if not black_ok:
                return f"<h1>Channel {channel} black_ok=false</h1>", 404

    # Jika semua ok => layani HLS
    folder_path = os.path.join(HLS_OUTPUT_DIR, f"ch_{channel}")
    return send_from_directory(folder_path, filename)

@app.errorhandler(404)
def custom_404(e):
    err_404_file = os.path.join(HTML_BASE_DIR, "error", "404.html")
    if os.path.isfile(err_404_file):
        return send_from_directory(os.path.join(HTML_BASE_DIR, "error"), "404.html"), 404
    else:
        return "<h1>404 Not Found</h1>", 404

@app.errorhandler(500)
def custom_500(e):
    err_50x_file = os.path.join(HTML_BASE_DIR, "error", "50x.html")
    if os.path.isfile(err_50x_file):
        return send_from_directory(os.path.join(HTML_BASE_DIR, "error"), "50x.html"), 500
    else:
        return "<h1>500 Internal Server Error</h1>", 500

# -------------------------------------------------------
# 8. MAIN: Pipeline & Monitor
# -------------------------------------------------------
logger.info("Memulai pipeline & monitor loop (Gunicorn top-level)")

# Jalankan pipeline awal
initial_ffmpeg_setup()

# Jalankan monitor loop di background
def run_monitor():
    monitor_loop(interval=60)

t = threading.Thread(target=run_monitor, daemon=True)
t.start()