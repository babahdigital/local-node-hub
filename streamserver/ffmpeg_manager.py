#!/usr/bin/env python3
"""
ffmpeg_manager.py

Script Manager yang bertugas menjalankan pipeline FFmpeg HLS:
- Membaca daftar channel dari resource_monitor_state.json => (title, channels, rtsp_ip).
- Membaca channel_validation.json => cek is_active, error_msg, dsb.
- Menjalankan pipeline FFmpeg jika is_active=true & error_msg=None.
- Hentikan pipeline jika is_active=false atau ada error_msg.
- Tidak menulis balik ke channel_validation.json (hanya membaca).
- Memantau perubahan JSON tiap 60 detik => update pipeline (add/remove channel).
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

# Pastikan utils.py ada di /app/scripts
sys.path.append("/app/scripts")
from utils import decode_credentials, setup_category_logger, load_json_file

logger = setup_category_logger("CCTV-Manager")

def log_info(msg):
    logger.info(msg)
def log_warning(msg):
    logger.warning(msg)
def log_error(msg):
    logger.error(msg)

# ----------------------------------------------------------------------------
# 0) KONFIGURASI & PATH
# ----------------------------------------------------------------------------
RESOURCE_MONITOR_PATH   = os.getenv("RESOURCE_MONITOR_PATH", "/mnt/Data/Syslog/resource/resource_monitor_state.json")
CHANNEL_VALIDATION_PATH = os.getenv("CHANNEL_VALIDATION_PATH", "/mnt/Data/Syslog/rtsp/channel_validation.json")
HLS_OUTPUT_DIR          = os.getenv("HLS_OUTPUT_DIR", "/app/streamserver/hls")

# Param HLS
HLS_TIME      = os.getenv("HLS_TIME", "2")
HLS_LIST_SIZE = os.getenv("HLS_LIST_SIZE", "5")

# Pipeline states
ffmpeg_processes = {}   # {channel: subprocess.Popen}
tracked_channels = set()  # channel yang terdaftar
channel_states   = {}   # {channel: bool} => pipeline running or not?

# Lock & hash file
data_lock        = threading.Lock()
resource_hash    = None
validation_hash  = None

# ----------------------------------------------------------------------------
# 1) Fungsi get_file_hash
# ----------------------------------------------------------------------------
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

# ----------------------------------------------------------------------------
# 2) override_userpass & mask_url_for_log
# ----------------------------------------------------------------------------
def override_userpass(rtsp_url, user, pwd):
    """
    Mem-parse RTSP link, override user:pass agar '@' di password
    tidak memunculkan double '@'.
    """
    parsed = urlparse(rtsp_url)
    user_esc = quote(user, safe='')
    pwd_esc  = quote(pwd,  safe='')

    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    new_netloc = f"{user_esc}:{pwd_esc}@{host}{port}"

    return urlunparse((
        parsed.scheme or "rtsp",
        new_netloc,
        parsed.path or "",
        parsed.params or "",
        parsed.query or "",
        parsed.fragment or ""
    ))

def mask_url_for_log(rtsp_url: str) -> str:
    """
    Masking user:pass di RTSP link agar tidak tampil di log.
    """
    p = urlparse(rtsp_url)
    if p.hostname:
        host = p.hostname or ""
        port = f":{p.port}" if p.port else ""
        new_netloc = f"****:****@{host}{port}"
        return urlunparse((
            p.scheme,
            new_netloc,
            p.path,
            p.params,
            p.query,
            p.fragment
        ))
    else:
        return rtsp_url

# ----------------------------------------------------------------------------
# 3) START & STOP FFmpeg
# ----------------------------------------------------------------------------
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
        channel_states[channel]   = True
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
    channel_states[channel] = False

# ----------------------------------------------------------------------------
# 4) Ambil channel & title dari resource_monitor_state.json
# ----------------------------------------------------------------------------
def get_channels_from_resource():
    data = load_json_file(RESOURCE_MONITOR_PATH)
    if not data:
        return ("DefaultTitle", [], "127.0.0.1")

    scfg     = data.get("stream_config", {})
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

# ----------------------------------------------------------------------------
# 5) initial_ffmpeg_setup
# ----------------------------------------------------------------------------
def initial_ffmpeg_setup():
    log_info("Memulai pipeline & monitor (ffmpeg_manager).")

    title, channels, rtsp_ip = get_channels_from_resource()
    log_info(f"[initial_ffmpeg_setup] => channels={channels}, title={title}, rtsp_ip={rtsp_ip}")

    # Contoh: pakai user=RTSP_USER1_BASE64, pass=RTSP_PASSWORD_BASE64
    try:
        user, pwd = decode_credentials(
            user_var="RTSP_USER1_BASE64",
            pass_var="RTSP_PASSWORD_BASE64"
        )
    except Exception as e:
        log_error(f"decode_credentials => {e}")
        log_warning("Pipeline tidak jalan => credential invalid.")
        return

    val_data = load_json_file(CHANNEL_VALIDATION_PATH)

    with data_lock:
        for ch in channels:
            tracked_channels.add(ch)
            info = val_data.get(str(ch), {})

            is_active = info.get("is_active", False)
            err_msg   = info.get("error_msg")

            if err_msg:
                log_info(f"Channel {ch} => error_msg => skip pipeline.")
                channel_states[ch] = False
                continue

            if is_active:
                raw_link = info.get("livestream_link")
                if not raw_link:
                    raw_link = f"rtsp://{rtsp_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
                rtsp_link = override_userpass(raw_link, user, pwd)
                start_ffmpeg_pipeline(ch, title, rtsp_link)
            else:
                log_info(f"Channel {ch} => is_active=false => skip pipeline.")
                channel_states[ch] = False

# ----------------------------------------------------------------------------
# 6) monitor_loop => pantau perubahan JSON
# ----------------------------------------------------------------------------
def monitor_loop(interval=60):
    global resource_hash, validation_hash

    while True:
        try:
            # Cek hash file resource
            new_res = get_file_hash(RESOURCE_MONITOR_PATH)
            # Cek hash file channel_validation
            new_val = get_file_hash(CHANNEL_VALIDATION_PATH)

            with data_lock:
                # Jika channel_validation.json berubah => cek state
                if new_val != validation_hash:
                    validation_hash = new_val
                    val_data = load_json_file(CHANNEL_VALIDATION_PATH)
                    update_channels_state(val_data)

                # Jika resource_monitor_state.json berubah => update channels
                if new_res != resource_hash:
                    resource_hash = new_res
                    title, new_ch_list, rtsp_ip = get_channels_from_resource()
                    update_channels_list(title, new_ch_list, rtsp_ip)

        except Exception as e:
            log_error(f"monitor_loop => {e}")

        time.sleep(interval)

# ----------------------------------------------------------------------------
# 7) update_channels_state => cek is_active/error_msg
# ----------------------------------------------------------------------------
def update_channels_state(val_data: dict):
    """
    Memulai/menghentikan pipeline berdasarkan is_active & error_msg.
    """
    try:
        user, pwd = decode_credentials(
            user_var="RTSP_USER1_BASE64",
            pass_var="RTSP_PASSWORD_BASE64"
        )
    except Exception as e:
        log_error(f"decode_credentials => {e}")
        return

    local_title, _, fallback_ip = get_channels_from_resource()

    for ch in tracked_channels:
        info = val_data.get(str(ch), {})
        is_active = info.get("is_active", False)
        err_msg   = info.get("error_msg", None)

        prev_state = channel_states.get(ch, False)

        if err_msg:
            # Stop pipeline jika sedang jalan
            if prev_state:
                log_info(f"Channel {ch} => error_msg => stop pipeline.")
                stop_ffmpeg_pipeline(ch)
            continue

        if is_active:
            if not prev_state:
                raw_link = info.get("livestream_link")
                if not raw_link:
                    raw_link = f"rtsp://{fallback_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
                rtsp_link = override_userpass(raw_link, user, pwd)
                log_info(f"Channel {ch} => is_active=true => start pipeline.")
                start_ffmpeg_pipeline(ch, local_title, rtsp_link)
        else:
            # is_active=false => stop pipeline jika prev_state=true
            if prev_state:
                log_info(f"Channel {ch} => is_active=false => stop pipeline.")
                stop_ffmpeg_pipeline(ch)

# ----------------------------------------------------------------------------
# 8) update_channels_list => add/remove channel
# ----------------------------------------------------------------------------
def update_channels_list(title, new_ch_list, rtsp_ip):
    val_data = load_json_file(CHANNEL_VALIDATION_PATH)

    new_set  = set(new_ch_list)
    added    = new_set - tracked_channels
    removed  = tracked_channels - new_set

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
                continue

            if is_active:
                try:
                    user, pwd = decode_credentials(
                        user_var="RTSP_USER1_BASE64",
                        pass_var="RTSP_PASSWORD_BASE64"
                    )
                except Exception as e:
                    log_error(f"decode_credentials => {e}")
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

    if removed:
        log_info(f"Channel dihapus => {removed}")
        for ch in removed:
            stop_ffmpeg_pipeline(ch)
            tracked_channels.remove(ch)
            channel_states.pop(ch, None)

# ----------------------------------------------------------------------------
# 9) main_service
# ----------------------------------------------------------------------------
def main_service():
    initial_ffmpeg_setup()
    t = threading.Thread(target=monitor_loop, kwargs={"interval":60}, daemon=True)
    t.start()

    # Idle loop agar script tidak exit
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main_service()