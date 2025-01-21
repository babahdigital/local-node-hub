#!/usr/bin/env python3
"""
main.py

Aplikasi Flask untuk men-serve file HLS (index.m3u8, segmen .ts, dsb.)
yang dihasilkan oleh ffmpeg_manager.py.

Membaca channel_validation.json untuk menampilkan 
error/freeze/black status channel, jika ada.
"""

import os
import json
import sys
from flask import Flask, send_from_directory, redirect, abort

# Hanya kalau Anda mau logging dengan utils.py
sys.path.append("/app/scripts")
from utils import setup_category_logger

app = Flask(__name__)
logger = setup_category_logger("CCTV")

# Path JSON & folder HLS
CHANNEL_VALIDATION_PATH = "/mnt/Data/Syslog/rtsp/channel_validation.json"
HLS_OUTPUT_DIR = "/app/streamserver/hls"
HTML_BASE_DIR  = "/app/streamserver/html"

def load_json_file(filepath):
    if not os.path.isfile(filepath):
        logger.warning(f"File {filepath} tidak ditemukan.")
        return {}
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Gagal membaca file {filepath}: {e}")
        return {}

def mask_any_rtsp_in_string(text: str) -> str:
    if not text or "rtsp://" not in text:
        return text
    idx = text.find("rtsp://")
    prefix = text[:idx]
    url_part = text[idx:].split(" ", 1)[0]
    suffix = ""
    if " " in text[idx:]:
        suffix = text[idx:].split(" ", 1)[1]
    # Minimal masking => ganti user:pass jadi ****
    return prefix + "rtsp://****:****@" + suffix

@app.route("/")
def index():
    index_file = os.path.join(HTML_BASE_DIR, "index.html")
    if os.path.isfile(index_file):
        return send_from_directory(HTML_BASE_DIR, "index.html")
    else:
        return "<h1>Welcome. No index.html found.</h1>"

@app.route("/ch<int:channel>", strict_slashes=False)
def ch_no_slash(channel):
    return redirect(f"/ch{channel}/")

@app.route("/ch<int:channel>/", defaults={"filename": "index.m3u8"}, strict_slashes=False)
@app.route("/ch<int:channel>/<path:filename>")
def serve_channel_files(channel, filename):
    val_data = load_json_file(CHANNEL_VALIDATION_PATH)
    info = val_data.get(str(channel), {})

    err_msg  = info.get("error_msg")
    black_ok = info.get("black_ok", True)

    if err_msg:
        masked = mask_any_rtsp_in_string(err_msg)
        error_html = os.path.join(HTML_BASE_DIR, "error", "error.stream.html")
        if os.path.isfile(error_html):
            with open(error_html, "r") as f:
                tmpl = f.read()
            out_page = tmpl.replace("{{ channel }}", str(channel))
            out_page = out_page.replace("{{ error_msg }}", masked)
            return out_page, 200
        else:
            return f"<h1>Channel {channel} error => {masked}</h1>", 404

    if not black_ok:
        return f"<h1>Channel {channel} black_ok=false</h1>", 404

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

# Tidak ada pipeline di main.py!
# Gunicorn di Dockerfile akan memanggil: gunicorn --bind 0.0.0.0:8080 main:app