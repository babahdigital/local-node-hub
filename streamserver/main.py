#!/usr/bin/env python3
"""
main.py

Aplikasi Flask untuk men-serve:
- File HLS (index.m3u8, segmen .ts) yang dihasilkan oleh ffmpeg_manager.py
- File statis (gambar, css, js, dsb.)
- Endpoint error & status

Membaca data channel dari channel_validation.json:
- is_active, error_msg, last_update, dsb.
- Menyajikan status channel di /status + men-serve HLS di /ch<int>/.

Juga men-serve snapshot (jika ada) di /snapshots/<filename>.

Penggunaan:
-----------
- Pastikan folder /app/streamserver/html/snapshots berisi file 'ch_<channel>.jpg'
  hasil snapshot_cctv.py.
- Tambahkan 'default-thumb.jpg' di /app/streamserver/html/img sebagai fallback thumbnail.

Author: (Anda)
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

# Environment variable atau default
CHANNEL_VALIDATION_PATH = os.getenv("CHANNEL_VALIDATION_PATH", "/mnt/Data/Syslog/rtsp/channel_validation.json")
HLS_OUTPUT_DIR          = os.getenv("HLS_OUTPUT_DIR", "/app/streamserver/hls")
HTML_BASE_DIR           = os.getenv("HTML_BASE_DIR", "/app/streamserver/html")

def mask_any_rtsp_in_string(text: str) -> str:
    """
    Mask substring 'rtsp://...' => 'rtsp://****:****@'
    agar password tidak bocor di log / error.
    """
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

# --------------------------------------------------------------------
# 1. Serve file statis: img, css, js, snapshots
# --------------------------------------------------------------------
@app.route("/img/<path:filename>")
def serve_images(filename):
    """
    Men-serve file gambar dari HTML_BASE_DIR/img
    Contoh akses: /img/logo.png
    """
    img_dir = os.path.join(HTML_BASE_DIR, "img")
    return send_from_directory(img_dir, filename)

@app.route("/css/<path:filename>")
def serve_css(filename):
    css_dir = os.path.join(HTML_BASE_DIR, "css")
    return send_from_directory(css_dir, filename)

@app.route("/js/<path:filename>")
def serve_js(filename):
    js_dir = os.path.join(HTML_BASE_DIR, "js")
    return send_from_directory(js_dir, filename)

@app.route("/snapshots/<path:filename>")
def serve_snapshots(filename):
    """
    Men-serve hasil snapshot cctv (.jpg) dari /snapshots.
    """
    snap_dir = os.path.join(HTML_BASE_DIR, "snapshots")
    return send_from_directory(snap_dir, filename)

# --------------------------------------------------------------------
# 2. Route HLS => /ch<int:channel>/
# --------------------------------------------------------------------
@app.route("/ch<int:channel>", strict_slashes=False)
def ch_no_slash(channel):
    return redirect(f"/ch{channel}/")

@app.route("/ch<int:channel>/", defaults={"filename": "index.m3u8"}, strict_slashes=False)
@app.route("/ch<int:channel>/<path:filename>")
def serve_channel_files(channel, filename):
    """
    Men-serve index.m3u8 & segmen .ts di /ch<int>/.
    Validasi is_active & error_msg sebelum di-serve.
    """
    data = load_json_file(CHANNEL_VALIDATION_PATH)
    info = data.get(str(channel), {})

    err_msg   = info.get("error_msg")
    is_active = info.get("is_active", False)

    if err_msg:
        masked = mask_any_rtsp_in_string(err_msg)
        err_file = os.path.join(HTML_BASE_DIR, "error", "error.stream.html")
        if os.path.isfile(err_file):
            with open(err_file, "r") as f:
                tmpl = f.read()
            out_html = tmpl.replace("{{ channel }}", str(channel))
            out_html = out_html.replace("{{ error_msg }}", masked)
            out_html = out_html.replace("{{ is_active }}", str(is_active))
            return out_html, 200
        else:
            return f"<h1>Channel {channel} error => {masked}</h1>", 404

    if not is_active:
        return f"<h1>Channel {channel} is_active=false => pipeline off</h1>", 404

    folder_path = os.path.join(HLS_OUTPUT_DIR, f"ch_{channel}")
    return send_from_directory(folder_path, filename)

# --------------------------------------------------------------------
# 3. Endpoint /status => ringkasan channel
# --------------------------------------------------------------------
@app.route("/status", methods=["GET"])
def status_all_channels():
    """
    Mengembalikan ringkasan info channel dalam format JSON:
    {
      "1": {
        "is_active": true,
        "error_msg": null,
        "last_update": "...",
        "hls_url": "http://host:port/ch1/",
        "livestream_link": "rtsp://****:****@...",
        "thumbnail_url": "http://host:port/snapshots/ch_1.jpg"
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

        # Livestream link di-mask
        raw_link = info.get("livestream_link", "")
        masked_link = mask_any_rtsp_in_string(raw_link) if raw_link else None

        # Cek snapshot => ch_<channel>.jpg
        snapshot_filename = f"ch_{ch_str}.jpg"
        snapshot_path = os.path.join(HTML_BASE_DIR, "snapshots", snapshot_filename)
        if os.path.isfile(snapshot_path):
            thumbnail_url = url_for("serve_snapshots", filename=snapshot_filename, _external=True)
        else:
            # Fallback default
            thumbnail_url = url_for("serve_images", filename="default-thumb.jpg", _external=True)

        result[ch_str] = {
            "is_active": info.get("is_active", False),
            "error_msg": err,
            "last_update": info.get("last_update"),
            "hls_url": hls_url,
            "livestream_link": masked_link,
            "thumbnail_url": thumbnail_url
        }
    return jsonify(result)

# --------------------------------------------------------------------
# 4. Custom error
# --------------------------------------------------------------------
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

# --------------------------------------------------------------------
if __name__ == "__main__":
    # Hanya jika mau jalankan Flask dev server (bukan Gunicorn)
    app.run(host="0.0.0.0", port=8080, debug=True)