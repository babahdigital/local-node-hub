#!/usr/bin/env python3
"""
main.py

Aplikasi Flask untuk men-serve file HLS (index.m3u8, segmen .ts, dsb.)
yang dihasilkan oleh ffmpeg_manager.py.

Membaca channel_validation.json untuk menampilkan 
error/freeze/black status channel, jika ada.
Menampilkan is_active (jika ada) agar front-end tahu pipeline aktif/tidak.

Endpoint tambahan "/status" => menampilkan ringkasan info channel.
"""

import os
import json
import sys
from flask import Flask, send_from_directory, redirect, url_for

# Opsional: logging pakai utils.py
sys.path.append("/app/scripts")
from utils import setup_category_logger

app = Flask(__name__)
logger = setup_category_logger("CCTV")

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
    data = load_json_file(CHANNEL_VALIDATION_PATH)
    info = data.get(str(channel), {})

    err_msg   = info.get("error_msg")
    black_ok  = info.get("black_ok", True)  # jika Anda masih pakai
    is_active = info.get("is_active", False)

    if err_msg:
        masked = mask_any_rtsp_in_string(err_msg)
        error_html = os.path.join(HTML_BASE_DIR, "error", "error.stream.html")
        if os.path.isfile(error_html):
            with open(error_html, "r") as f:
                tmpl = f.read()
            out_page = tmpl.replace("{{ channel }}", str(channel))
            out_page = out_page.replace("{{ error_msg }}", masked)
            out_page = out_page.replace("{{ is_active }}", str(is_active))
            return out_page, 200
        else:
            return f"<h1>Channel {channel} error => {masked}</h1>", 404

    if not black_ok:
        return f"<h1>Channel {channel} black_ok=false (is_active={is_active})</h1>", 404
    # Atau jika Anda pakai is_active, boleh begini:
    if not is_active:
        return f"<h1>Channel {channel} is_active=false => pipeline off</h1>", 404

    folder_path = os.path.join(HLS_OUTPUT_DIR, f"ch_{channel}")
    return send_from_directory(folder_path, filename)

# Endpoint ringkasan status
from flask import jsonify, request

@app.route("/status", methods=["GET"])
def status_all_channels():
    """
    Kembalikan ringkasan info: black_ok, error_msg, is_active, last_update
    plus link HLS => /chX/
    """
    data = load_json_file(CHANNEL_VALIDATION_PATH)
    result = {}
    for ch_str, info in data.items():
        ch_num = ch_str
        try:
            ch_num = int(ch_str)
        except:
            pass
        
        hls_url = url_for("serve_channel_files", channel=ch_num, filename="", _external=True)
        err = info.get("error_msg")
        if err:
            err = mask_any_rtsp_in_string(err)

        result[ch_str] = {
            "black_ok": info.get("black_ok", True),
            "error_msg": err,
            "is_active": info.get("is_active", False),
            "last_update": info.get("last_update"),
            "hls_url": hls_url
        }
        # Livestream link (masked)
        raw_link = info.get("livestream_link")
        if raw_link:
            raw_link = mask_any_rtsp_in_string(raw_link)
            result[ch_str]["livestream_link"] = raw_link

    return jsonify(result)  # Mengembalikan JSON response

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