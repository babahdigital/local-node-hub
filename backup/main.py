#!/usr/bin/env python3
"""
main.py

Script produksi untuk:
1. Baca JSON & ENV => Jalankan multi-thread channel => cek black/freeze => motion => rolling backup.
2. Opsional: Object Detection (ENABLE_OBJECT_DETECTION=true).
3. Hemat resource => tidak lagi memantau resource di sini (sudah dipindah ke resource_monitor.py).

Author: YourName
"""

import os
import sys
import time
import json
import threading
import subprocess
import cv2
from datetime import datetime

# Pastikan folder scripts ada di PATH
sys.path.append("/app/scripts")

# Import modul pendukung
from utils import setup_logger, decode_credentials
from motion_detection import MotionDetector
from backup_manager import BackupSession

# Object detection opsional
ENABLE_OBJECT_DETECTION = os.getenv("ENABLE_OBJECT_DETECTION", "false").lower() == "true"
if ENABLE_OBJECT_DETECTION:
    from object_detection import ObjectDetector

###############################################################################
# 1. Logging & Konstanta
###############################################################################
LOG_PATH = "/mnt/Data/Syslog/rtsp/cctv/validation.log"
logger   = setup_logger("Main-Combined", LOG_PATH)

# File JSON yang berisi resource_usage + stream_config (dari resource_monitor.py)
MONITOR_STATE_FILE = "/mnt/Data/Syslog/resource/resource_monitor_state.json"
MOTION_EVENTS_JSON = "/mnt/Data/Syslog/rtsp/motion_events.json"

# Rolling config (ENV)
MAX_RECORD     = int(os.getenv("MAX_RECORD", "300"))  # durasi max (detik) satu file rekaman
MOTION_TIMEOUT = int(os.getenv("MOTION_TIMEOUT", "5"))# durasi idle motion sebelum stop record

# Interval utama pipeline (cek black/freeze/motion) (default: 300 detik)
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))

# Blackdetect threshold
BLACK_DETECT_THRESHOLD = float(os.getenv("BLACK_DETECT_THRESHOLD", "0.98"))

# Freeze-check param
FREEZE_SENSITIVITY   = float(os.getenv("FREEZE_SENSITIVITY", "6.0"))
FREEZE_RECHECK_TIMES = int(os.getenv("FREEZE_RECHECK_TIMES", "5"))
FREEZE_RECHECK_DELAY = float(os.getenv("FREEZE_RECHECK_DELAY", "3.0"))

# Flags fitur
ENABLE_FREEZE_CHECK = os.getenv("ENABLE_FREEZE_CHECK","true").lower()=="true"
ENABLE_BLACKOUT     = os.getenv("ENABLE_BLACKOUT","true").lower()=="true"
LOOP_ENABLE         = os.getenv("LOOP_ENABLE","true").lower()=="true"

###############################################################################
# 2. Pastikan File JSON Exist
###############################################################################
def ensure_json_initialized():
    """
    Cek apakah MONITOR_STATE_FILE sudah ada.
    Jika belum, buat file minimal agar tak error saat dibaca pipeline.
    (Resource usage kosong, stream_config & rtsp_config diisi default.)
    """
    if not os.path.exists(MONITOR_STATE_FILE):
        logger.info(f"[Init] File {MONITOR_STATE_FILE} belum ada, membuat file default minimal.")
        default_stream_cfg = {
            "stream_title": os.getenv("STREAM_TITLE", "Untitled"),
            "test_channel": os.getenv("TEST_CHANNEL", "1"),
            "channel_count": int(os.getenv("CHANNEL_COUNT", "1")),
            "enable_freeze": ENABLE_FREEZE_CHECK,
            "enable_blackout": ENABLE_BLACKOUT
        }
        default_rtsp_cfg = {
            "rtsp_ip": os.getenv("RTSP_IP","127.0.0.1"),
            "rtsp_user": os.getenv("RTSP_USER","admin"),
            "rtsp_password": os.getenv("RTSP_PASSWORD","admin123"),
            "rtsp_subtype": os.getenv("RTSP_SUBTYPE","0")
        }
        initial_data = {
            "resource_usage": {},
            "stream_config": default_stream_cfg,
            "rtsp_config": default_rtsp_cfg
        }
        with open(MONITOR_STATE_FILE, "w") as f:
            json.dump(initial_data, f, indent=2)
    else:
        logger.info(f"[Init] File {MONITOR_STATE_FILE} sudah ada, skip init.")

###############################################################################
# 3. Load Config dari File JSON + Override ENV
###############################################################################
def load_resource_config():
    """
    Baca data dari MONITOR_STATE_FILE -> resource_usage, stream_config, rtsp_config.
    Lalu timpa (override) dengan environment (termasuk decode base64) supaya 
    user & pass tidak lagi bergantung pada JSON.
    """
    config = {}
    try:
        with open(MONITOR_STATE_FILE, "r") as f:
            j = json.load(f)

        # CPU usage
        cpu_usage = j.get("resource_usage", {}) \
                     .get("cpu", {}) \
                     .get("usage_percent", 0.0)
        config["cpu_usage"] = float(cpu_usage)

        # stream_config
        scfg = j.get("stream_config", {})
        config["stream_title"]   = scfg.get("stream_title", "Untitled")
        config["rtsp_ip"]        = scfg.get("rtsp_ip", "127.0.0.1")
        config["test_channel"]   = scfg.get("test_channel", "1")
        config["channel_count"]  = int(scfg.get("channel_count", 1))
        config["enable_freeze"]  = scfg.get("enable_freeze", True)
        config["enable_blackout"]= scfg.get("enable_blackout", True)

        # rtsp_config
        rcfg = j.get("rtsp_config", {})
        config["rtsp_subtype"]  = rcfg.get("rtsp_subtype", "0")

        # Sebelumnya: user dan pass diambil dari JSON
        # Gantinya: kita abaikan JSON, kita decode dari ENV (base64)
        # atau fallback ke JSON jika decode gagal.
        user_json = rcfg.get("rtsp_user", "admin")
        pass_json = rcfg.get("rtsp_password", "admin123")

    except Exception as e:
        logger.error(f"[Main] Gagal baca {MONITOR_STATE_FILE} => {e}")
        # fallback jika file JSON bermasalah
        config["cpu_usage"]       = 0.0
        config["stream_title"]    = os.getenv("STREAM_TITLE", "Untitled")
        config["test_channel"]    = os.getenv("TEST_CHANNEL", "1")
        config["channel_count"]   = int(os.getenv("CHANNEL_COUNT", "1"))
        config["enable_freeze"]   = ENABLE_FREEZE_CHECK
        config["enable_blackout"] = ENABLE_BLACKOUT
        config["rtsp_ip"]         = os.getenv("RTSP_IP", "127.0.0.1")
        config["rtsp_subtype"]    = os.getenv("RTSP_SUBTYPE", "0")
        user_json                 = os.getenv("RTSP_USER", "admin")
        pass_json                 = os.getenv("RTSP_PASSWORD", "admin123")

    # -------------- Override dari ENV --------------
    # 1) IP, Subtype, Stream Title, dsb:
    #    -> Kalau ENV ada, timpa lagi.
    config["rtsp_ip"]      = os.getenv("RTSP_IP", config["rtsp_ip"])
    config["stream_title"] = os.getenv("STREAM_TITLE", config["stream_title"])
    # dsb jika diinginkan, misalnya test_channel, channel_count juga
    # config["test_channel"]  = os.getenv("TEST_CHANNEL", config["test_channel"])

    # 2) Decode credential base64 (jika ada)
    try:
        user_env, pass_env = decode_credentials()  # dari utils.py
        config["rtsp_user"]     = user_env
        config["rtsp_password"] = pass_env
        logger.info(f"[Main] RTSP user/pass diambil dari ENV base64 => {user_env}")
    except Exception as ex:
        logger.warning(f"[Main] Gagal decode RTSP_USER_BASE64 => pakai JSON fallback => {ex}")
        # fallback: ambil dari JSON
        config["rtsp_user"]     = user_json
        config["rtsp_password"] = pass_json

    return config

###############################################################################
# 4. Black/Freeze Check
###############################################################################
def check_black_frames(rtsp_url, do_blackout, duration=0.1, threshold=0.98):
    """
    Return True jika stream BUKAN black screen.
    - Menggunakan ffmpeg blackdetect => jika terdeteksi black, return False.
    - do_blackout=False => skip check => return True.
    """
    if not do_blackout:
        return True

    thr = float(os.getenv("BLACK_DETECT_THRESHOLD", str(threshold)))
    cmd = [
        "ffmpeg","-hide_banner","-loglevel","error",
        "-rtsp_transport","tcp",
        "-i", rtsp_url,
        "-vf", f"blackdetect=d={duration}:pic_th={thr}",
        "-an","-t","5","-f","null","-"
    ]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return (b"black_start" not in r.stderr)
    except Exception:
        return False

def check_freeze_frames(rtsp_url, do_freeze, cpu_usage,
                       freeze_sens=6.0, times=5, delay=3.0):
    """
    Return True jika stream BUKAN freeze.
    - do_freeze=False => skip => return True
    - cpu_usage>85 => skip => return True (demi hemat resource)
    - Jalankan ffmpeg freezedetect beberapa kali => kalau freeze_start terdeteksi => False.
    """
    if not do_freeze:
        return True
    if cpu_usage > 85:
        logger.info("[FreezeCheck] CPU>85 => skip freeze-check.")
        return True

    freeze_fail = 0
    for i in range(times):
        if not _freeze_once(rtsp_url, freeze_sens):
            freeze_fail += 1
        if i < (times - 1):
            time.sleep(delay)
    return (freeze_fail < times)

def _freeze_once(rtsp_url, freeze_sens):
    cmd = [
        "ffmpeg","-hide_banner","-loglevel","error",
        "-rtsp_transport","tcp",
        "-i", rtsp_url,
        "-vf", f"freezedetect=n=-60dB:d={freeze_sens}",
        "-an","-t","5","-f","null","-"
    ]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return (b"freeze_start" not in r.stderr)
    except Exception:
        return False

###############################################################################
# 5. Motion Pipeline
###############################################################################
MOTION_DETECT_AREA = int(os.getenv("MOTION_DETECT_AREA", "3000"))  # area threshold

def save_bboxes_json(channel, bboxes):
    event = {
        "timestamp": datetime.now().isoformat(),
        "channel": channel,
        "bboxes": bboxes
    }
    try:
        with open(MOTION_EVENTS_JSON, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        logger.error(f"[Main] Gagal tulis {MOTION_EVENTS_JSON} => {e}")

def motion_pipeline(rtsp_url, channel, config):
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        logger.error(f"[Main] ch={channel} => fail open => {rtsp_url}")
        return

    from motion_detection import MotionDetector
    motion_detector = MotionDetector(area_threshold=MOTION_DETECT_AREA)

    obj_detect = None
    if ENABLE_OBJECT_DETECTION:
        from object_detection import ObjectDetector
        obj_detect = ObjectDetector(
            "/app/backup/models/mobilenet_ssd/MobileNetSSD_deploy.prototxt",
            "/app/backup/models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel",
            conf_person=0.6, conf_car=0.4, conf_motor=0.4
        )

    backup_sess = None
    is_recording = False
    last_motion = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(1)
            continue

        bboxes = motion_detector.detect(frame)
        if bboxes:
            save_bboxes_json(channel, bboxes)
            last_motion = time.time()

            if obj_detect:
                detections = obj_detect.detect(frame)  # ([(label, conf, x, y, w, h)], None)
                # Misal hanya peduli "person"
                if detections and len(detections[0]) > 0:
                    person_found = any(det[0] == "person" for det in detections[0])
                    if not person_found:
                        time.sleep(0.2)
                        continue
                else:
                    time.sleep(0.2)
                    continue

            # Rolling backup
            if not is_recording:
                backup_sess = BackupSession(rtsp_url, channel, config["stream_title"])
                path = backup_sess.start_recording()
                logger.info(f"[Main] ch={channel} => start record => {path}")
                is_recording = True
            else:
                # Cek durasi => jika lewat MAX_RECORD => rolling
                if not backup_sess.still_ok(MAX_RECORD):
                    backup_sess.stop_recording()
                    backup_sess = BackupSession(rtsp_url, channel, config["stream_title"])
                    path = backup_sess.start_recording()
                    logger.info(f"[Main] ch={channel} => rolling => {path}")
        else:
            # tidak ada motion => jika sedang record, cek last_motion
            if is_recording:
                if (time.time() - last_motion) > MOTION_TIMEOUT:
                    backup_sess.stop_recording()
                    backup_sess = None
                    is_recording = False
                    logger.info(f"[Main] ch={channel} => stop record => no motion")

        time.sleep(0.2)

###############################################################################
# 6. Pipeline per Channel
###############################################################################
def thread_for_channel(ch, config):
    cpu_usage   = config["cpu_usage"]
    do_blackout = config["enable_blackout"]
    do_freeze   = config["enable_freeze"]

    user    = config["rtsp_user"]
    pwd     = config["rtsp_password"]
    ip      = config["rtsp_ip"]
    subtype = config["rtsp_subtype"]
    rtsp_url= f"rtsp://{user}:{pwd}@{ip}:554/cam/realmonitor?channel={ch}&subtype={subtype}"

    logger.info(f"[Main] channel={ch} => {rtsp_url}")

    # 1) Black check => skip jika CPU>90
    if cpu_usage > 90:
        do_blackout = False
        logger.info(f"[Main] ch={ch} => CPU>90 => skip blackdetect")
    if not check_black_frames(rtsp_url, do_blackout, threshold=BLACK_DETECT_THRESHOLD):
        logger.warning(f"[Main] ch={ch} => black => skip pipeline")
        return

    # 2) Freeze check
    if not check_freeze_frames(
        rtsp_url, do_freeze, cpu_usage,
        freeze_sens=FREEZE_SENSITIVITY,
        times=FREEZE_RECHECK_TIMES,
        delay=FREEZE_RECHECK_DELAY
    ):
        logger.warning(f"[Main] ch={ch} => freeze => skip pipeline")
        return

    # 3) Motion pipeline
    motion_pipeline(rtsp_url, ch, config)

###############################################################################
# 7. Loop Utama Pipeline
###############################################################################
def run_pipeline_loop():
    while True:
        config = load_resource_config()

        test_ch    = config["test_channel"].lower()
        chan_count = config["channel_count"]

        # Jika "off", berarti kita ambil range 1..chan_count
        if test_ch == "off":
            channels = [str(i) for i in range(1, chan_count + 1)]
        else:
            channels = [x.strip() for x in test_ch.split(",") if x.strip()]

        logger.info("[Main] Mulai threads untuk channels => " + str(channels))
        for c in channels:
            t = threading.Thread(target=thread_for_channel, args=(c, config), daemon=True)
            t.start()

        if not LOOP_ENABLE:
            logger.info("[Main] LOOP_ENABLE=false => jalankan 1x saja => break.")
            break

        logger.info(f"[Main] Selesai 1 putaran. Tunggu {CHECK_INTERVAL} detik sebelum re-run.")
        time.sleep(CHECK_INTERVAL)

###############################################################################
# 8. main()
###############################################################################
def main():
    # 1) Cek/Init file JSON agar pipeline tidak error saat resource_monitor_state.json belum ada
    ensure_json_initialized()

    # 2) Jalankan pipeline loop
    run_pipeline_loop()

    logger.info("[Main] Keluar.")

if __name__=="__main__":
    main()