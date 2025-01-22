#!/usr/bin/env python3
"""
main.py

Aplikasi Flask untuk men-serve file HLS (index.m3u8, segmen .ts, dsb.)
yang dihasilkan oleh ffmpeg_manager.py.

Membaca channel_validation.json untuk menampilkan 
error/freeze/black (jika ada) tapi di sini kita fokus `is_active` + `error_msg`.
Menampilkan is_active agar front-end tahu pipeline aktif/tidak.

Endpoint "/status" => menampilkan ringkasan info channel.
"""

import os
import json
import sys
from flask import Flask, send_from_directory, redirect, url_for, jsonify

# Opsional: logging pakai utils
sys.path.append("/app/scripts")
from utils import setup_category_logger, load_json_file

app = Flask(__name__)
logger = setup_category_logger("CCTV")

CHANNEL_VALIDATION_PATH = os.getenv("CHANNEL_VALIDATION_PATH", "/mnt/Data/Syslog/rtsp/channel_validation.json")
HLS_OUTPUT_DIR          = os.getenv("HLS_OUTPUT_DIR", "/app/streamserver/hls")
HTML_BASE_DIR           = os.getenv("HTML_BASE_DIR", "/app/streamserver/html")

def mask_any_rtsp_in_string(text: str) -> str:
    if not text or "rtsp://" not in text:
        return text
    idx = text.find("rtsp://")
    prefix = text[:idx]
    url_part = text[idx:].split(" ", 1)[0]
    suffix = ""
    if " " in text[idx:]:
        suffix = text[idx:].split(" ", 1)[1]
    # Minim => "rtsp://****:****@"
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
    # redirect ke /chX/
    return redirect(f"/ch{channel}/")

@app.route("/ch<int:channel>/", defaults={"filename": "index.m3u8"}, strict_slashes=False)
@app.route("/ch<int:channel>/<path:filename>")
def serve_channel_files(channel, filename):
    data = load_json_file(CHANNEL_VALIDATION_PATH)
    info = data.get(str(channel), {})

    err_msg   = info.get("error_msg")
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

    if not is_active:
        return f"<h1>Channel {channel} is_active=false => pipeline off</h1>", 404

    folder_path = os.path.join(HLS_OUTPUT_DIR, f"ch_{channel}")
    return send_from_directory(folder_path, filename)

@app.route("/status", methods=["GET"])
def status_all_channels():
    """
    Mengembalikan ringkasan info channel:
    {
      "1": {
        "is_active": true,
        "error_msg": null,
        "last_update": "2025-01-21T14:00:00...",
        "hls_url": "http://IP:8080/ch1/",
        "livestream_link": "rtsp://****:****@..."
      },
      ...
    }
    """
    data = load_json_file(CHANNEL_VALIDATION_PATH)
    result = {}
    for ch_str, info in data.items():
        try:
            ch_num = int(ch_str)
        except:
            ch_num = ch_str

        hls_url = url_for("serve_channel_files", channel=ch_num, filename="", _external=True)

        err = info.get("error_msg")
        if err:
            err = mask_any_rtsp_in_string(err)

        row = {
            "is_active": info.get("is_active", False),
            "error_msg": err,
            "last_update": info.get("last_update"),
            "hls_url": hls_url
        }
        # Livestream link
        raw_link = info.get("livestream_link")
        if raw_link:
            row["livestream_link"] = mask_any_rtsp_in_string(raw_link)

        result[ch_str] = row
    return jsonify(result)

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