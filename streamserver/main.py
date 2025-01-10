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
from flask import Flask, send_from_directory, abort

# Pastikan kita dapat mengimpor utils.py (yang memuat decode_credentials).
# utils.py berada di /app/scripts (berdasarkan penjelasan Anda).
sys.path.append("/app/scripts")
from utils import decode_credentials  # decode user/pass RTSP base64

app = Flask(__name__)

# ----------------------------------------
# Panggil pipeline di top-level
# ----------------------------------------
print("[INFO] Inisialisasi pipeline di top-level.")
try:
    # decode_credentials() di sini
    # initial_ffmpeg_setup() di sini
    # monitor_loop (opsional) bisa di-thread
    pass
except Exception as e:
    print(f"[ERROR] Pipeline top-level: {e}")

# Routes Flask ...
@app.route("/")
def index():
    return "Hello from Gunicorn!"

# ----------------------------------------------------------------------------
# 1. KONFIGURASI
# ----------------------------------------------------------------------------
RESOURCE_MONITOR_PATH = "/mnt/Data/Syslog/resource/resource_monitor_state.json"
CHANNEL_VALIDATION_PATH = "/mnt/Data/Syslog/rtsp/channel_validation.json"
HLS_OUTPUT_DIR = "/app/streamserver/hls"

# Ambil environment variable (mis. di .env atau docker-compose)
HLS_TIME = os.environ.get("HLS_TIME", "2")
HLS_LIST_SIZE = os.environ.get("HLS_LIST_SIZE", "5")

# Data global
ffmpeg_processes = {}       # {channel: subprocess.Popen}
channel_black_status = {}   # {channel: bool} => status "boleh jalan" vs "hitam"
tracked_channels = set()    # Menyimpan channel yang sedang dipantau

# Lock global untuk mencegah race condition antara thread monitor & request
data_lock = threading.Lock()

# Variabel untuk mendeteksi perubahan file JSON
resource_monitor_state_hash = None
channel_validation_hash = None


# ----------------------------------------------------------------------------
# 2. FUNGSI HELPER
# ----------------------------------------------------------------------------
def load_json_file(filepath):
    """Membaca file JSON, return None kalau tidak ada atau error."""
    if not os.path.isfile(filepath):
        return None
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Gagal membaca file {filepath}: {e}")
        return None


def get_file_hash(filepath):
    """
    Membuat hash (MD5) dari isi file.
    Digunakan untuk mengecek apakah file berubah tanpa harus parse JSON setiap kali.
    """
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
    """
    Override user:pass di link RTSP.
    - Apabila link: "rtsp://lama:pass@172.16.10.252:554/..."
      kita ganti jadi: "rtsp://{user}:{pwd}@172.16.10.252:554/..."
    """
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
    """
    Menjalankan FFmpeg pipeline untuk channel `channel`.
    Simpan proses Popen di ffmpeg_processes[channel].
    """
    out_dir = os.path.join(HLS_OUTPUT_DIR, f"ch_{channel}")
    os.makedirs(out_dir, exist_ok=True)

    cmd = (
        f"ffmpeg -y "
        f"-i '{rtsp_link}' "
        f"-c:v libx264 -c:a aac -ac 1 -ar 44100 "
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
    """
    Menghentikan proses FFmpeg untuk channel `channel` jika masih jalan.
    """
    proc = ffmpeg_processes.get(channel)
    if proc and proc.poll() is None:
        print(f"[INFO] Menghentikan FFmpeg => channel={channel}")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    ffmpeg_processes.pop(channel, None)


# ----------------------------------------------------------------------------
# 3. LOAD CHANNEL DARI RESOURCE_MONITOR_STATE
# ----------------------------------------------------------------------------
def get_channel_list_from_resource():
    """
    Baca `resource_monitor_state.json` => return (title, channels, rtsp_ip).
    Logika:
      - test_channel != off => parse manual (mis: "1,3,4").
      - else => gunakan channel_count + channel_list.
    """
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
        # "1,3,4" => [1,3,4]
        ch_list = [x.strip() for x in test_channel.split(",")]
        ch_list = [int(x) for x in ch_list if x.isdigit()]
        return (title, ch_list, rtsp_ip)
    else:
        if channel_count and channel_list:
            return (title, channel_list[:channel_count], rtsp_ip)
        else:
            return (title, [], rtsp_ip)


# ----------------------------------------------------------------------------
# 4. SETUP AWAL (DIPANGGIL DI main)
# ----------------------------------------------------------------------------
def initial_ffmpeg_setup():
    """
    Jalankan pipeline FFmpeg untuk channel2 awal.
    Baca resource_monitor_state.json dan channel_validation.json.
    Skip jika black_ok=false.
    """
    title, channels, rtsp_ip = get_channel_list_from_resource()
    print(f"[INFO] initial_ffmpeg_setup => channels={channels}, title={title}, rtsp_ip={rtsp_ip}")

    try:
        user, pwd = decode_credentials()  # <-- dari utils.py
    except Exception as e:
        print(f"[ERROR] decode_credentials => {e}")
        print("[WARNING] Pipeline tidak dimulai karena kredensial tidak valid.")
        return

    validation_data = load_json_file(CHANNEL_VALIDATION_PATH) or {}

    with data_lock:
        for ch in channels:
            tracked_channels.add(ch)
            black_ok = True  # default
            # RTSP fallback link
            rtsp_link = f"rtsp://{user}:{pwd}@{rtsp_ip}:554/cam/realmonitor?channel={ch}&subtype=0"

            # Jika channel ada di validation_data dan black_ok=false => skip
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


# ----------------------------------------------------------------------------
# 5. MONITOR LOOP
# ----------------------------------------------------------------------------
def monitor_loop(interval=60):
    """
    Loop berkala:
      - Cek channel_validation.json => update black_ok => stop/start pipeline.
      - Cek resource_monitor_state.json => tambah/hapus channel.
      - Gunakan hash file agar tidak parse JSON setiap kali.
    """
    global resource_monitor_state_hash
    global channel_validation_hash

    while True:
        try:
            new_resource_hash = get_file_hash(RESOURCE_MONITOR_PATH)
            new_validation_hash = get_file_hash(CHANNEL_VALIDATION_PATH)

            with data_lock:
                # 1) channel_validation.json
                if new_validation_hash != channel_validation_hash:
                    val_data = load_json_file(CHANNEL_VALIDATION_PATH) or {}
                    channel_validation_hash = new_validation_hash
                    update_black_ok(val_data)

                # 2) resource_monitor_state.json
                if new_resource_hash != resource_monitor_state_hash:
                    resource_monitor_state_hash = new_resource_hash
                    title, new_channels, rtsp_ip = get_channel_list_from_resource()
                    update_channels(title, new_channels, rtsp_ip)

        except Exception as e:
            print(f"[ERROR] monitor_loop => {e}")

        time.sleep(interval)


def update_black_ok(val_data):
    """
    Update pipeline jika black_ok berubah (true->false => stop, false->true => start).
    """
    try:
        user, pwd = decode_credentials()
    except Exception as e:
        print(f"[ERROR] decode_credentials => {e}")
        return

    for ch in list(tracked_channels):
        prev_black = channel_black_status.get(ch, True)
        new_black = True  # default
        if str(ch) in val_data:
            if val_data[str(ch)].get("black_ok", False) is False:
                new_black = False

        if new_black != prev_black:
            if not new_black:
                print(f"[INFO] Channel {ch} => black_ok berubah => stop pipeline.")
                stop_ffmpeg_pipeline(ch)
                channel_black_status[ch] = False
            else:
                print(f"[INFO] Channel {ch} => black_ok berubah => start pipeline.")
                link_in_json = ""
                if str(ch) in val_data:
                    link_in_json = val_data[str(ch)].get("livestream_link", "")
                if link_in_json:
                    rtsp_link = override_userpass(link_in_json, user, pwd)
                else:
                    # fallback
                    _, _, fallback_ip = get_channel_list_from_resource()
                    rtsp_link = f"rtsp://{user}:{pwd}@{fallback_ip}:554/cam/realmonitor?channel={ch}&subtype=0"

                start_ffmpeg_pipeline(ch, "AutoTitle", rtsp_link)
                channel_black_status[ch] = True


def update_channels(title, new_channels, rtsp_ip):
    """
    Tambah channel baru, hapus channel lama.
    Kemudian jalankan/stop pipeline sesuai black_ok.
    """
    try:
        user, pwd = decode_credentials()
    except Exception as e:
        print(f"[ERROR] decode_credentials => {e}")
        return

    val_data = load_json_file(CHANNEL_VALIDATION_PATH) or {}

    new_set = set(new_channels)
    # Channel baru => belum ada di tracked_channels
    added_channels = new_set - tracked_channels
    if added_channels:
        print(f"[INFO] Ada channel baru => {added_channels}")
        for ch in added_channels:
            tracked_channels.add(ch)
            black_ok = True
            link_in_json = ""
            if str(ch) in val_data:
                if val_data[str(ch)].get("black_ok", False) is False:
                    black_ok = False
                link_in_json = val_data[str(ch)].get("livestream_link", "")

            channel_black_status[ch] = black_ok
            if black_ok:
                if link_in_json:
                    rtsp_link = override_userpass(link_in_json, user, pwd)
                else:
                    rtsp_link = f"rtsp://{user}:{pwd}@{rtsp_ip}:554/cam/realmonitor?channel={ch}&subtype=0"
                start_ffmpeg_pipeline(ch, title, rtsp_link)
            else:
                print(f"[INFO] Channel {ch} => black_ok=false, skip pipeline.")

    # Channel dihapus => ada di tracked_channels, tapi hilang di new_set
    removed_channels = tracked_channels - new_set
    if removed_channels:
        print(f"[INFO] Ada channel yang dihapus => {removed_channels}")
        for ch in removed_channels:
            stop_ffmpeg_pipeline(ch)
            tracked_channels.remove(ch)
            channel_black_status.pop(ch, None)


# ----------------------------------------------------------------------------
# 6. FLASK ROUTES
# ----------------------------------------------------------------------------
@app.route("/hls/<int:channel>/<path:filename>")
def serve_hls_files(channel, filename):
    """
    Endpoint untuk melayani file .m3u8/.ts.
    Jika channel ada di validation dan black_ok=false => 404
    """
    with data_lock:
        val_data = load_json_file(CHANNEL_VALIDATION_PATH)
        if val_data is not None:
            ch_str = str(channel)
            if ch_str in val_data:
                if val_data[ch_str].get("black_ok", True) is False:
                    return f"<h1>Channel {channel} tidak tersedia (black_ok=false)</h1>", 404

        channel_path = os.path.join(HLS_OUTPUT_DIR, f"ch_{channel}")
        return send_from_directory(channel_path, filename)


@app.route("/")
def index():
    return """
    <h1>Simple HLS Server with Periodic Validation</h1>
    <p>/hls/&lt;channel&gt;/index.m3u8 untuk akses playlist HLS</p>
    """


# ----------------------------------------------------------------------------
# 7. ENTRYPOINT
# ----------------------------------------------------------------------------
def main():
    global resource_monitor_state_hash
    global channel_validation_hash

    # 1) Setup awal pipeline FFmpeg
    initial_ffmpeg_setup()

    # 2) Simpan hash awal file (untuk optimasi)
    resource_monitor_state_hash = get_file_hash(RESOURCE_MONITOR_PATH)
    channel_validation_hash = get_file_hash(CHANNEL_VALIDATION_PATH)

    # 3) Jalankan thread monitor (tiap 60 detik)
    t = threading.Thread(target=monitor_loop, kwargs={"interval": 60}, daemon=True)
    t.start()

    print("[INFO] Flask server starting on port 5001...")
    # 4) Jalankan Flask dev server (untuk Production, gunakan Gunicorn!)
    app.run(host="0.0.0.0", port=8080, debug=False)