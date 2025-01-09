#!/usr/bin/env python3
# stream_server.py

import os
import json
import subprocess
import shlex
from flask import Flask, send_from_directory, abort

# >>> Tambahkan import utils <<<
from utils import decode_credentials  # <-- mengambil user & password RTSP
# Jika Anda ingin log dari utils, misalnya:
# from utils import setup_category_logger
# logger = setup_category_logger("STREAMING-HLS")

app = Flask(__name__)

# Path ke JSON config
RESOURCE_MONITOR_PATH = "/mnt/Data/Syslog/resource/resource_monitor_state.json"
CHANNEL_VALIDATION_PATH = "/mnt/Data/Syslog/rtsp/channel_validation.json"

# Path untuk output HLS
HLS_OUTPUT_DIR = "/opt/app/hls_output"

# Baca environment variable untuk HLS
HLS_TIME = os.environ.get("HLS_TIME", "2")
HLS_LIST_SIZE = os.environ.get("HLS_LIST_SIZE", "5")


def load_json_file(filepath):
    """Helper untuk load JSON file."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Gagal membaca file {filepath}: {e}")
        return None


def get_channels_to_stream():
    """
    Berdasarkan file resource_monitor_state.json, tentukan channel-channel
    yang akan distream. Jika 'test_channel' != 'off', maka gunakan daftar channel 
    dari 'test_channel'. Jika 'test_channel' == 'off', gunakan 'channel_count' 
    dan 'channel_list'.
    """
    config = load_json_file(RESOURCE_MONITOR_PATH)
    if not config:
        return {"title": "default_title", "channels": []}

    stream_config = config.get("stream_config", {})
    rtsp_ip = stream_config.get("rtsp_ip", "")
    test_channel = stream_config.get("test_channel", "off")
    channel_count = stream_config.get("channel_count", 0)
    channel_list = stream_config.get("channel_list", [])

    # stream_title, sekalian akan kita gunakan sebagai penamaan output file
    stream_title = stream_config.get("stream_title", "default_title")

    if test_channel.lower() != "off":
        # jika test_channel = "1, 2, 3" => ambil channel dari sini
        ch_list = [ch.strip() for ch in test_channel.split(",")]
        ch_list = [int(ch) for ch in ch_list if ch.isdigit()]
        return {
            "title": stream_title,
            "channels": ch_list
        }
    else:
        # gunakan channel_count dan channel_list
        if channel_count and channel_list:
            return {
                "title": stream_title,
                "channels": channel_list[:channel_count]
            }
        else:
            return {
                "title": stream_title,
                "channels": []
            }


def validate_channels_and_start_ffmpeg(title, channels):
    """
    - Baca channel_validation.json untuk cek apakah channel black_ok atau tidak.
    - Jika black_ok = false, skip pipeline HLS.
    - Jika black_ok = true, jalankan FFmpeg untuk output HLS.
    - RTSP user/pass diambil via decode_credentials() (credentials.sh).
    """
    # 1. Coba decode user & pass (dari environment)
    try:
        user, pwd = decode_credentials()  # from utils
    except Exception as e:
        print(f"[ERROR] Gagal decode kredensial RTSP: {e}")
        print("[WARNING] Semua channel akan dilewati karena kredensial tidak valid.")
        return

    validation_data = load_json_file(CHANNEL_VALIDATION_PATH)
    if not validation_data:
        print("[WARNING] Gagal memuat channel_validation.json. Semua channel dianggap tidak valid.")
        return

    for ch in channels:
        ch_str = str(ch)
        if ch_str not in validation_data:
            print(f"[WARNING] Channel {ch} tidak ada di channel_validation.json. Skip.")
            continue

        black_ok = validation_data[ch_str].get("black_ok", False)
        original_link = validation_data[ch_str].get("livestream_link", "")

        if not black_ok:
            print(f"[INFO] Channel {ch} => black_ok=False. Skip pipeline.")
            continue

        # ----------------------------------------------------------------------------
        # 2. Override user:pass => Bangun link baru dari original_link di channel_validation
        #    - Contoh di channel_validation: "rtsp://babahdigital:Admin123@@172.16.10.252:554/..."
        #    - Kita ganti "babahdigital:Admin123@" menjadi user:pwd dari decode_credentials.
        # ----------------------------------------------------------------------------
        # Langkah sederhana: buang skema "rtsp://" => buang user:pass => sisakan IP:port/...
        # Sehingga kita bisa menambah "rtsp://{user}:{pwd}@" + sisanya.

        if "://" in original_link:
            after_scheme = original_link.split("://", 1)[1]
        else:
            after_scheme = original_link

        # Cek apakah ada '@' => jika ada, berarti link memuat user:pass.
        if '@' in after_scheme:
            # misal "babahdigital:Admin123@@172.16.10.252:554/cam/realmonitor?channel=15&subtype=0"
            after_userpass = after_scheme.split('@', 1)[1]  # "172.16.10.252:554/cam/realmonitor?channel=15&subtype=0"
        else:
            after_userpass = after_scheme

        # Bangun link baru
        rtsp_link = f"rtsp://{user}:{pwd}@{after_userpass}"

        # ----------------------------------------------------------------------------
        # 3. Buat folder output HLS khusus untuk channel ini
        # ----------------------------------------------------------------------------
        out_dir = os.path.join(HLS_OUTPUT_DIR, f"ch_{ch}")
        os.makedirs(out_dir, exist_ok=True)

        # 4. Siapkan perintah FFmpeg
        cmd = (
            f"ffmpeg -y "
            f"-i '{rtsp_link}' "
            f"-c:v libx264 -c:a aac -ac 1 -ar 44100 "
            f"-hls_time {HLS_TIME} "
            f"-hls_list_size {HLS_LIST_SIZE} "
            f"-hls_flags delete_segments+program_date_time "
            f"-metadata title='{title} | CH {ch}' "
            f"-f hls {os.path.join(out_dir, 'index.m3u8')}"
        )

        print(f"[INFO] Menjalankan FFmpeg untuk channel {ch}: {cmd}")

        # 5. Jalankan di background
        subprocess.Popen(shlex.split(cmd))

    print("[INFO] FFmpeg pipeline setup selesai.")


@app.route("/hls/<int:channel>/<path:filename>")
def serve_hls_files(channel, filename):
    """
    Endpoint untuk menghidangkan file HLS (ts segment, m3u8).
    Kalau channel black_ok=false, kita kembalikan error/halaman HTML stating "link mati".
    """
    validation_data = load_json_file(CHANNEL_VALIDATION_PATH)
    if not validation_data:
        return abort(500, "Gagal memuat channel_validation.json")

    ch_str = str(channel)
    channel_info = validation_data.get(ch_str, {})
    black_ok = channel_info.get("black_ok", False)

    if not black_ok:
        return f"<h1>Channel {channel} tidak tersedia (black_ok=false)</h1>", 404

    channel_path = os.path.join(HLS_OUTPUT_DIR, f"ch_{channel}")
    return send_from_directory(channel_path, filename)


@app.route("/")
def index():
    return """
    <h1>Simple HLS Server</h1>
    <p>Gunakan endpoint <code>/hls/&lt;channel&gt;/index.m3u8</code> untuk mengakses playlist HLS.</p>
    """


def main():
    # 1. Dapatkan channel yang hendak di-stream dari resource_monitor_state.json
    data = get_channels_to_stream()
    title = data["title"]
    channels = data["channels"]

    print(f"[INFO] Akan memproses channels: {channels} | Title: {title}")

    # 2. Validasi & jalankan FFmpeg
    validate_channels_and_start_ffmpeg(title, channels)

    # 3. Jalankan Flask server
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()