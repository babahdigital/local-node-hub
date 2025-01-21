#!/usr/bin/env python3
"""
ffmpeg_manager.py

Script Manager yang bertugas menjalankan pipeline FFmpeg HLS. 
- Mengambil daftar channel dari resource_monitor_state.json
- Mengecek validasi (black_ok, error_msg) di channel_validation.json
- (Opsional) Melakukan freeze-check sebelum start pipeline
- Menjalankan pipeline FFmpeg (start_ffmpeg_pipeline) atau menghentikannya
- Loop monitor tiap 60 detik untuk update channel

Dijalankan di bawah Supervisor / Systemd / service lain agar 
tetap berjalan di background tanpa tergantung Gunicorn worker.
"""

import os
import json
import subprocess
import shlex
import sys
import time
import threading
import hashlib
from urllib.parse import quote, urlparse, urlunparse

# -----------------------------
# 0) SETUP PATH UNTUK utils.py
# -----------------------------
# Misal utils.py berada di /app/scripts
# Jika utils.py ada di /app/streamserver, ubah path.
sys.path.append("/app/scripts")

# Import dari utils
from utils import decode_credentials, setup_category_logger

###########################################################
#  Logging
###########################################################
logger = setup_category_logger("CCTV-Manager")

def log_info(msg):
    logger.info(msg)

def log_warning(msg):
    logger.warning(msg)

def log_error(msg):
    logger.error(msg)

###########################################################
#  Konfigurasi & PATH
###########################################################
RESOURCE_MONITOR_PATH   = "/mnt/Data/Syslog/resource/resource_monitor_state.json"
CHANNEL_VALIDATION_PATH = "/mnt/Data/Syslog/rtsp/channel_validation.json"

HLS_OUTPUT_DIR = "/app/streamserver/hls"

HLS_TIME      = os.environ.get("HLS_TIME", "2")
HLS_LIST_SIZE = os.environ.get("HLS_LIST_SIZE", "5")

ENABLE_FREEZE_CHECK   = os.environ.get("ENABLE_FREEZE_CHECK", "true").lower() == "true"
FREEZE_SENSITIVITY    = float(os.environ.get("FREEZE_SENSITIVITY", "6.0"))
FREEZE_RECHECK_TIMES  = int(os.environ.get("FREEZE_RECHECK_TIMES", "5"))
FREEZE_RECHECK_DELAY  = float(os.environ.get("FREEZE_RECHECK_DELAY", "3.0"))

# Data pipeline
ffmpeg_processes     = {}   # {channel: subprocess.Popen}
channel_black_status = {}   # {channel: bool}
tracked_channels     = set()

data_lock            = threading.Lock()
freeze_errors        = {}   # {channel: "Pesan freeze error"}

resource_monitor_state_hash = None
channel_validation_hash     = None

###########################################################
# 1) override_userpass & mask
###########################################################
def override_userpass(original_link, user, pwd):
    """
    Mem-parse RTSP link, override user:pass 
    agar password dengan '@' tidak memunculkan dobel '@'.
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
    Masking user:pass di RTSP link agar tidak tampil di log.
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
    """Mask substring 'rtsp://...' di dalam text."""
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

###########################################################
# 2) Load JSON, hash 
###########################################################
def load_json_file(filepath):
    if not os.path.isfile(filepath):
        log_warning(f"File {filepath} tidak ditemukan.")
        return None
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        log_error(f"Gagal membaca file {filepath}: {e}")
        return None

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

###########################################################
# 3) Start & Stop FFmpeg
###########################################################
def start_ffmpeg_pipeline(channel, title, rtsp_link):
    """
    Menjalankan FFmpeg => output HLS ch_{channel}/index.m3u8
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
    log_info(f"Menjalankan FFmpeg => channel={channel}, cmd={masked_cmd}")
    try:
        proc = subprocess.Popen(shlex.split(cmd))
        ffmpeg_processes[channel] = proc
    except Exception as e:
        log_error(f"Gagal start pipeline channel={channel}: {e}")

def stop_ffmpeg_pipeline(channel):
    """
    Stop pipeline channel tertentu.
    """
    proc = ffmpeg_processes.get(channel)
    if proc and proc.poll() is None:
        log_info(f"Stop pipeline => channel={channel}")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    ffmpeg_processes.pop(channel, None)

###########################################################
# 4) Freeze-check
###########################################################
def check_freeze_frames(rtsp_url, freeze_sens, times, delay):
    """
    Lakukan freeze-check berulang (times kali).
    Return True jika TIDAK freeze (alias freeze fails < times).
    Return False jika freeze terdeteksi di semua attempt.
    """
    fails = 0
    for i in range(times):
        if not _freeze_once(rtsp_url, freeze_sens):
            fails += 1
        if i < times - 1:
            time.sleep(delay)
    return (fails < times)

def _freeze_once(rtsp_url, freeze_sens):
    """
    Sekali freeze-check 5 detik (freezedetect).
    """
    cmd = [
        "ffmpeg","-hide_banner","-loglevel","error","-y","-err_detect","ignore_err",
        "-rtsp_transport","tcp","-i", rtsp_url,
        "-vf", f"freezedetect=n=-60dB:d={freeze_sens}",
        "-an","-t","5","-f","null","-"
    ]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        if b"freeze_start" in r.stderr:
            log_info("[FREEZE] freeze_start terdeteksi.")
            return False
        return True
    except Exception as e:
        log_error(f"[FREEZE] error => {e}")
        return False

###########################################################
# 5) Baca resource => get_channel_list_from_resource
###########################################################
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

###########################################################
# 6) initial_ffmpeg_setup => jalankan pipeline
###########################################################
def initial_ffmpeg_setup():
    """
    Membaca resource_monitor_state.json => channels,
    validation => black_ok / error_msg
    freeze-check => optional
    start pipeline.
    """
    log_info("Memulai pipeline & monitor (ffmpeg_manager service).")

    title, channels, rtsp_ip = get_channel_list_from_resource()
    log_info(f"initial_ffmpeg_setup => channels={channels}, title={title}, rtsp_ip={rtsp_ip}")

    try:
        user, pwd = decode_credentials()
    except Exception as e:
        log_error(f"decode_credentials => {e}")
        log_warning("Pipeline tidak jalan => credential invalid.")
        return

    validation_data = load_json_file(CHANNEL_VALIDATION_PATH) or {}

    with data_lock:
        for ch in channels:
            tracked_channels.add(ch)
            black_ok  = True
            error_msg = None

            raw_link = f"rtsp://{rtsp_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
            rtsp_link = override_userpass(raw_link, user, pwd)

            # Cek validation => black_ok / error_msg / custom link
            if str(ch) in validation_data:
                info = validation_data[str(ch)]
                if info.get("black_ok", False) is False:
                    black_ok = False
                error_msg   = info.get("error_msg", None)
                custom_link = info.get("livestream_link", "")
                if custom_link:
                    rtsp_link = override_userpass(custom_link, user, pwd)

            # Freeze check => ephemeral
            if ENABLE_FREEZE_CHECK and black_ok and not error_msg:
                freeze_ok = check_freeze_frames(rtsp_link, FREEZE_SENSITIVITY, FREEZE_RECHECK_TIMES, FREEZE_RECHECK_DELAY)
                if not freeze_ok:
                    freeze_errors[ch] = f"ch={ch} => freeze => skip pipeline."
                    log_info(f"[FREEZE] Channel {ch} => freeze => skip pipeline.")
                    black_ok = False

            if error_msg:
                err_masked = mask_any_rtsp_in_string(error_msg)
                log_info(f"Channel {ch} => error_msg={err_masked} => skip pipeline.")
                channel_black_status[ch] = False
                continue

            channel_black_status[ch] = black_ok
            if black_ok:
                start_ffmpeg_pipeline(ch, title, rtsp_link)
            else:
                log_info(f"Channel {ch} => black_ok=false => skip pipeline.")

###########################################################
# 7) monitor_loop => update black_ok / freeze / add/remove
###########################################################
def monitor_loop(interval=60):
    global resource_monitor_state_hash, channel_validation_hash

    while True:
        try:
            new_r_hash = get_file_hash(RESOURCE_MONITOR_PATH)
            new_v_hash = get_file_hash(CHANNEL_VALIDATION_PATH)

            with data_lock:
                # 1) update black_ok & error
                if new_v_hash != channel_validation_hash:
                    channel_validation_hash = new_v_hash
                    val_data = load_json_file(CHANNEL_VALIDATION_PATH) or {}
                    update_black_ok_and_error(val_data)

                # 2) add/remove channel
                if new_r_hash != resource_monitor_state_hash:
                    resource_monitor_state_hash = new_r_hash
                    title, new_channels, rtsp_ip = get_channel_list_from_resource()
                    update_channels(title, new_channels, rtsp_ip)

        except Exception as e:
            log_error(f"monitor_loop => {e}")

        time.sleep(interval)

def update_black_ok_and_error(val_data):
    """
    - error_msg => stop pipeline
    - black_ok=false => stop pipeline
    - black_ok=true => start pipeline (freeze-check)
    - ephemeral freeze => skip
    """
    try:
        user, pwd = decode_credentials()
    except Exception as e:
        log_error(f"decode_credentials => {e}")
        return

    for ch in list(tracked_channels):
        prev_status = channel_black_status.get(ch, True)
        new_black   = True
        new_error   = None

        if str(ch) in val_data:
            info = val_data[str(ch)]
            if info.get("black_ok", False) is False:
                new_black = False
            new_error = info.get("error_msg", None)

        ephemeral_err = freeze_errors.get(ch, None)
        if ephemeral_err:
            new_black = False
            new_error = ephemeral_err

        if new_error:
            err_masked = mask_any_rtsp_in_string(new_error)
            if prev_status:
                log_info(f"Channel {ch} => error_msg={err_masked} => stop pipeline.")
                stop_ffmpeg_pipeline(ch)
                channel_black_status[ch] = False
            continue

        if not new_black:
            if prev_status:
                log_info(f"Channel {ch} => black_ok=false => stop pipeline.")
                stop_ffmpeg_pipeline(ch)
                channel_black_status[ch] = False
        else:
            if not prev_status:
                # re-check freeze
                _, _, fallback_ip = get_channel_list_from_resource()
                raw_link = f"rtsp://{fallback_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
                if str(ch) in val_data:
                    c = val_data[str(ch)]
                    cust = c.get("livestream_link", "")
                    if cust:
                        raw_link = cust
                rtsp_link = override_userpass(raw_link, user, pwd)

                if ENABLE_FREEZE_CHECK:
                    freeze_ok = check_freeze_frames(rtsp_link, FREEZE_SENSITIVITY, FREEZE_RECHECK_TIMES, FREEZE_RECHECK_DELAY)
                    if not freeze_ok:
                        freeze_errors[ch] = f"ch={ch} => freeze => skip pipeline."
                        log_info(f"[FREEZE] Channel {ch} => freeze => skip pipeline.")
                        channel_black_status[ch] = False
                        continue

                log_info(f"Channel {ch} => black_ok=true => start pipeline.")
                start_ffmpeg_pipeline(ch, "AutoTitle", rtsp_link)
                channel_black_status[ch] = True

def update_channels(title, new_channels, rtsp_ip):
    """
    Penambahan/penghapusan channel => jalankan/hentikan pipeline
    """
    try:
        user, pwd = decode_credentials()
    except Exception as e:
        log_error(f"decode_credentials => {e}")
        return

    val_data = load_json_file(CHANNEL_VALIDATION_PATH) or {}
    new_set  = set(new_channels)

    # channel baru
    added = new_set - tracked_channels
    if added:
        log_info(f"channel baru => {added}")
        for ch in added:
            tracked_channels.add(ch)
            black_ok  = True
            error_msg = None

            if str(ch) in val_data:
                info = val_data[str(ch)]
                if info.get("black_ok", False) is False:
                    black_ok = False
                error_msg = info.get("error_msg", None)

            if ch in freeze_errors:
                freeze_errors.pop(ch)

            if error_msg:
                err_masked = mask_any_rtsp_in_string(error_msg)
                log_info(f"Channel {ch} => error_msg={err_masked} => skip pipeline.")
                channel_black_status[ch] = False
                continue

            channel_black_status[ch] = black_ok
            if black_ok:
                raw_link = f"rtsp://{rtsp_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
                if str(ch) in val_data:
                    cust = val_data[str(ch)].get("livestream_link", "")
                    if cust:
                        raw_link = cust
                rtsp_link = override_userpass(raw_link, user, pwd)

                if ENABLE_FREEZE_CHECK:
                    freeze_ok = check_freeze_frames(rtsp_link, FREEZE_SENSITIVITY, FREEZE_RECHECK_TIMES, FREEZE_RECHECK_DELAY)
                    if not freeze_ok:
                        freeze_errors[ch] = f"ch={ch} => freeze => skip pipeline."
                        log_info(f"[FREEZE] Channel {ch} => freeze => skip pipeline.")
                        channel_black_status[ch] = False
                        continue

                start_ffmpeg_pipeline(ch, title, rtsp_link)
            else:
                log_info(f"Channel {ch} => black_ok=false => skip pipeline.")

    # channel dihapus
    removed = tracked_channels - new_set
    if removed:
        log_info(f"channel dihapus => {removed}")
        for ch in removed:
            stop_ffmpeg_pipeline(ch)
            tracked_channels.remove(ch)
            channel_black_status.pop(ch, None)
            if ch in freeze_errors:
                freeze_errors.pop(ch)

###########################################################
# 9) Fungsi main_service => dipanggil supervisord
###########################################################
def main_service():
    """
    Fungsi utama => jalankan initial_ffmpeg_setup + monitor_loop.
    Dijalankan oleh supervisor (atau systemd). 
    """
    # Jalankan pipeline awal
    initial_ffmpeg_setup()

    # Jalankan monitor loop di thread
    t = threading.Thread(target=monitor_loop, kwargs={"interval":60}, daemon=True)
    t.start()

    # Idle loop agar script tidak exit
    while True:
        time.sleep(1)

if __name__=="__main__":
    main_service()