#!/usr/bin/env python3
"""
main.py

Penyempurnaan:
1. Hanya merekam jika motion + ada "person" (Object Detection).
2. Detail error (freeze/blackout/fail open) dicatat di log => channel_validation.json.
3. Opsi ENABLE_JSON_LOOK => menentukan apakah test_channel & channel_count dibaca dari JSON (true)
   atau environment (false).
4. Log ditempatkan di RTSP (validation.log).

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

# File JSON resource (dari resource_monitor.py)
MONITOR_STATE_FILE  = "/mnt/Data/Syslog/resource/resource_monitor_state.json"
# File JSON channel validation => menampung info freeze_ok, black_ok, dsb.
VALIDATION_JSON     = "/mnt/Data/Syslog/rtsp/channel_validation.json"
# File JSON untuk motion event bounding boxes
MOTION_EVENTS_JSON  = "/mnt/Data/Syslog/rtsp/motion_events.json"

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

# Opsi untuk menentukan apakah baca channel dari JSON atau ENV
ENABLE_JSON_LOOK    = os.getenv("ENABLE_JSON_LOOK", "false").lower() == "true"

###############################################################################
# 2. JSON Validation Updater
###############################################################################
def load_validation_status():
    """Load channel_validation.json -> dict."""
    try:
        with open(VALIDATION_JSON, "r") as f:
            return json.load(f)
    except:
        return {}

def save_validation_status(data: dict):
    """Save dict -> channel_validation.json."""
    try:
        with open(VALIDATION_JSON, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning(f"[Main] Gagal menulis {VALIDATION_JSON} => {e}")

def update_validation_status(channel, info: dict):
    """
    Update JSON 'channel_validation.json' dengan info:
    - freeze_ok (bool),
    - black_ok (bool),
    - last_check (timestamp),
    - livestream_link,
    - error_msg (jika ada),
    dsb.
    """
    data = load_validation_status()
    ch_str = str(channel)
    if ch_str not in data:
        data[ch_str] = {}

    # perbarui
    data[ch_str].update(info)
    # tambahkan timestamp
    data[ch_str]["last_update"] = datetime.now().isoformat()

    # simpan
    save_validation_status(data)

###############################################################################
# 3. Pastikan File JSON Resource Ada
###############################################################################
def ensure_json_initialized():
    """
    Cek apakah MONITOR_STATE_FILE sudah ada.
    Jika belum, buat file minimal agar tak error saat dibaca pipeline.
    """
    if not os.path.exists(MONITOR_STATE_FILE):
        logger.info(f"[Init] File {MONITOR_STATE_FILE} belum ada, membuat file default minimal.")
        default_stream_cfg = {
            "stream_title": os.getenv("STREAM_TITLE", "Untitled"),
            "rtsp_ip":      os.getenv("RTSP_IP","127.0.0.1"),
            "test_channel": os.getenv("TEST_CHANNEL", "1"),
            "channel_count": int(os.getenv("CHANNEL_COUNT", "1")),
            "enable_freeze": ENABLE_FREEZE_CHECK,
            "enable_blackout": ENABLE_BLACKOUT
        }
        default_rtsp_cfg = {
            "rtsp_subtype": os.getenv("RTSP_SUBTYPE","0"),
            "rtsp_user":    os.getenv("RTSP_USER","admin"),
            "rtsp_password":os.getenv("RTSP_PASSWORD","admin123")
        }
        initial_data = {
            "resource_usage": {},
            "stream_config":  default_stream_cfg,
            "rtsp_config":    default_rtsp_cfg
        }
        with open(MONITOR_STATE_FILE, "w") as f:
            json.dump(initial_data, f, indent=2)
    else:
        logger.info(f"[Init] File {MONITOR_STATE_FILE} sudah ada, skip init.")

###############################################################################
# 4. Load Resource + RTSP Config
###############################################################################
def load_resource_config():
    """
    Baca data resource_monitor_state.json -> resource_usage, stream_config, rtsp_config.
    Lalu:
      - Timpa IP/user/pass dengan ENV base64 jika ada
      - Kecuali ENABLE_JSON_LOOK=false => channel_count & test_channel pakai ENV.
        Jika ENABLE_JSON_LOOK=true => channel_count & test_channel pakai JSON.
    """
    config = {}
    try:
        with open(MONITOR_STATE_FILE, "r") as f:
            j = json.load(f)

        # CPU usage
        usage = j.get("resource_usage", {}).get("cpu", {}).get("usage_percent", 0.0)
        config["cpu_usage"] = float(usage)

        scfg = j.get("stream_config", {})
        config["stream_title"]   = scfg.get("stream_title", "Untitled")
        config["rtsp_ip"]        = scfg.get("rtsp_ip", "127.0.0.1")

        # black/freeze
        config["enable_freeze"]  = scfg.get("enable_freeze", True)
        config["enable_blackout"]= scfg.get("enable_blackout", True)

        # Channel & test_channel => sesuai ENABLE_JSON_LOOK
        if ENABLE_JSON_LOOK:
            config["test_channel"]  = scfg.get("test_channel", "1")
            config["channel_count"] = int(scfg.get("channel_count", 1))
        else:
            # Abaikan JSON => pakai ENV
            config["test_channel"]  = os.getenv("TEST_CHANNEL", "off")
            config["channel_count"] = int(os.getenv("CHANNEL_COUNT", "1"))

        # rtsp_config
        rcfg = j.get("rtsp_config", {})
        config["rtsp_subtype"]   = rcfg.get("rtsp_subtype", "0")
        user_json = rcfg.get("rtsp_user", "admin")
        pass_json = rcfg.get("rtsp_password", "admin123")

    except Exception as e:
        logger.error(f"[Main] Gagal baca {MONITOR_STATE_FILE} => {e}")
        # fallback total
        config["cpu_usage"]       = 0.0
        config["stream_title"]    = os.getenv("STREAM_TITLE", "Untitled")
        config["rtsp_ip"]         = os.getenv("RTSP_IP", "127.0.0.1")
        config["enable_freeze"]   = ENABLE_FREEZE_CHECK
        config["enable_blackout"] = ENABLE_BLACKOUT

        if ENABLE_JSON_LOOK:
            # fallback JSON => minimal
            config["test_channel"]  = "1"
            config["channel_count"] = 1
        else:
            config["test_channel"]  = os.getenv("TEST_CHANNEL", "off")
            config["channel_count"] = int(os.getenv("CHANNEL_COUNT", "1"))

        config["rtsp_subtype"]    = os.getenv("RTSP_SUBTYPE", "0")
        user_json                 = os.getenv("RTSP_USER", "admin")
        pass_json                 = os.getenv("RTSP_PASSWORD", "admin123")

    # override IP & stream_title jika ENV diset
    config["rtsp_ip"]      = os.getenv("RTSP_IP", config["rtsp_ip"])
    config["stream_title"] = os.getenv("STREAM_TITLE", config["stream_title"])

    # decode credentials (base64) => fallback JSON
    try:
        user_env, pass_env = decode_credentials()
        config["rtsp_user"]     = user_env
        config["rtsp_password"] = pass_env
        logger.info(f"[Main] RTSP user/pass diambil dari ENV base64 => {user_env}")
    except Exception as ex:
        logger.warning(f"[Main] Gagal decode RTSP_USER_BASE64 => fallback JSON => {ex}")
        config["rtsp_user"]     = user_json
        config["rtsp_password"] = pass_json

    return config

###############################################################################
# 5. Fungsi Check Black/Freeze
###############################################################################
def check_black_frames(rtsp_url, do_blackout, duration=0.1, threshold=0.98):
    if not do_blackout:
        return True
    thr = float(os.getenv("BLACK_DETECT_THRESHOLD", str(threshold)))
    cmd = [
        "ffmpeg","-hide_banner","-loglevel","error",
        "-rtsp_transport","tcp","-i", rtsp_url,
        "-vf", f"blackdetect=d={duration}:pic_th={thr}",
        "-an","-t","5","-f","null","-"
    ]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return (b"black_start" not in r.stderr)
    except:
        return False

def check_freeze_frames(rtsp_url, do_freeze, cpu_usage, freeze_sens=6.0, times=5, delay=3.0):
    if not do_freeze:
        return True
    if cpu_usage > 85:
        logger.info("[FreezeCheck] CPU>85 => skip freeze-check.")
        return True

    fail_count = 0
    for i in range(times):
        if not _freeze_once(rtsp_url, freeze_sens):
            fail_count += 1
        if i < (times - 1):
            time.sleep(delay)
    return (fail_count < times)

def _freeze_once(rtsp_url, freeze_sens):
    cmd = [
        "ffmpeg","-hide_banner","-loglevel","error",
        "-rtsp_transport","tcp","-i", rtsp_url,
        "-vf", f"freezedetect=n=-60dB:d={freeze_sens}",
        "-an","-t","5","-f","null","-"
    ]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return (b"freeze_start" not in r.stderr)
    except:
        return False

###############################################################################
# 6. Motion Pipeline
###############################################################################
MOTION_DETECT_AREA = int(os.getenv("MOTION_DETECT_AREA", "3000"))  # area threshold

def save_bboxes_json(channel, bboxes):
    """
    Append bounding box event ke MOTION_EVENTS_JSON.
    """
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
        err_msg = f"ch={channel} => fail open => {rtsp_url}"
        logger.error(f"[Main] {err_msg}")
        # update validation => fail open
        update_validation_status(channel, {
            "freeze_ok": None,
            "black_ok":  None,
            "livestream_link": rtsp_url,
            "error_msg": err_msg
        })
        return

    # Motion Detector
    motion_detector = MotionDetector(area_threshold=MOTION_DETECT_AREA)

    # Object Detector (opsional)
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
    last_motion  = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(1)
            continue

        bboxes = motion_detector.detect(frame)
        if bboxes:
            # Simpan bounding box event
            save_bboxes_json(channel, bboxes)
            last_motion = time.time()

            # Jika object detection aktif => cek 'person'
            if obj_detect:
                results, _ = obj_detect.detect(frame)
                person_found = any(r[0] == "person" for r in results)
                if not person_found:
                    logger.info(f"[Main] ch={channel} => motion found, but no person => skip record")
                    time.sleep(0.2)
                    continue

            # Start / Rolling backup
            if not is_recording:
                backup_sess = BackupSession(rtsp_url, channel, config["stream_title"])
                path = backup_sess.start_recording()
                logger.info(f"[Main] ch={channel} => start record => {path}")
                is_recording = True
            else:
                if not backup_sess.still_ok(MAX_RECORD):
                    backup_sess.stop_recording()
                    backup_sess = BackupSession(rtsp_url, channel, config["stream_title"])
                    path = backup_sess.start_recording()
                    logger.info(f"[Main] ch={channel} => rolling => {path}")
        else:
            # Tidak ada motion => stop record jika idle
            if is_recording:
                idle_sec = time.time() - last_motion
                if idle_sec > MOTION_TIMEOUT:
                    backup_sess.stop_recording()
                    backup_sess = None
                    is_recording = False
                    logger.info(f"[Main] ch={channel} => stop record => no motion")

        time.sleep(0.2)

###############################################################################
# 7. Pipeline per Channel
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

    black_ok  = True
    freeze_ok = True

    # skip black jika CPU>90
    if cpu_usage > 90:
        do_blackout = False
        logger.info(f"[Main] ch={ch} => CPU>90 => skip blackdetect")

    # black check
    if do_blackout:
        black_ok = check_black_frames(rtsp_url, do_blackout, threshold=BLACK_DETECT_THRESHOLD)
        if not black_ok:
            err_msg = f"ch={ch} => black => skip pipeline"
            logger.warning(f"[Main] {err_msg}")
            update_validation_status(ch, {
                "freeze_ok": None,
                "black_ok":  False,
                "livestream_link": rtsp_url,
                "error_msg": err_msg
            })
            return

    # freeze check
    if do_freeze:
        freeze_ok = check_freeze_frames(
            rtsp_url, do_freeze, cpu_usage,
            freeze_sens=FREEZE_SENSITIVITY,
            times=FREEZE_RECHECK_TIMES,
            delay=FREEZE_RECHECK_DELAY
        )
        if not freeze_ok:
            err_msg = f"ch={ch} => freeze => skip pipeline"
            logger.warning(f"[Main] {err_msg}")
            update_validation_status(ch, {
                "freeze_ok": False,
                "black_ok":  black_ok,
                "livestream_link": rtsp_url,
                "error_msg": err_msg
            })
            return

    # Lolos => motion pipeline
    update_validation_status(ch, {
        "freeze_ok": freeze_ok,
        "black_ok":  black_ok,
        "livestream_link": rtsp_url,
        "error_msg": None
    })

    motion_pipeline(rtsp_url, ch, config)

###############################################################################
# 8. Loop Utama Pipeline
###############################################################################
def run_pipeline_loop():
    while True:
        config = load_resource_config()

        if ENABLE_JSON_LOOK:
            # channel_list => dari JSON
            test_ch    = config["test_channel"].lower()
            chan_count = config["channel_count"]
        else:
            # channel_list => dari ENV
            test_ch    = os.getenv("TEST_CHANNEL", "off").lower()
            chan_count = int(os.getenv("CHANNEL_COUNT", "1"))

        if test_ch == "off":
            channels = [str(i) for i in range(1, chan_count + 1)]
        else:
            channels = [x.strip() for x in test_ch.split(",") if x.strip()]

        logger.info(f"[Main] ENABLE_JSON_LOOK={ENABLE_JSON_LOOK} => channels={channels}")
        for c in channels:
            t = threading.Thread(target=thread_for_channel, args=(c, config), daemon=True)
            t.start()

        if not LOOP_ENABLE:
            logger.info("[Main] LOOP_ENABLE=false => jalankan 1x saja => break.")
            break

        logger.info(f"[Main] Selesai 1 putaran. Tunggu {CHECK_INTERVAL} detik sebelum re-run.")
        time.sleep(CHECK_INTERVAL)

###############################################################################
# 9. main()
###############################################################################
def main():
    ensure_json_initialized()
    run_pipeline_loop()
    logger.info("[Main] Keluar.")

if __name__=="__main__":
    main()