#!/usr/bin/env python3
"""
main.py (Multi-thread, tanpa NVR_ENABLE, bounding box disimpan ke JSON).

1) Baca ENV => blackdetect, freeze check, motion detection
2) Hasil bounding box disimpan ke file JSON (untuk analisis), 
   sementara log di Docker cukup ringkas.
3) multi-channel concurrency.
"""

import os
import sys
import time
import json
import subprocess
import threading
import cv2
from datetime import datetime

sys.path.append("/app/scripts")
from utils import setup_logger
from motion_detection import MotionDetector
from backup_manager import BackupSession  # class handle rolling backup

# Opsional object detection
ENABLE_OBJECT_DETECTION = os.getenv("ENABLE_OBJECT_DETECTION","false").lower()=="true"
if ENABLE_OBJECT_DETECTION:
    from object_detection import ObjectDetector

LOG_PATH = "/mnt/Data/Syslog/rtsp/cctv/validation.log"
logger = setup_logger("RTSP-Validation", LOG_PATH)

# ENV
RTSP_IP       = os.getenv("RTSP_IP","172.16.10.252")
RTSP_USER     = os.getenv("RTSP_USER","admin")
RTSP_PASSWORD = os.getenv("RTSP_PASSWORD","admin123")
TEST_CHANNEL  = os.getenv("TEST_CHANNEL","1,3,4").lower()
CHANNELS      = int(os.getenv("CHANNELS","1"))
RTSP_SUBTYPE  = os.getenv("RTSP_SUBTYPE","0")

LOOP_ENABLE   = os.getenv("LOOP_ENABLE","true").lower()=="true"
CHECK_INTERVAL= int(os.getenv("CHECK_INTERVAL","300"))

ENABLE_BLACKOUT      = os.getenv("ENABLE_BLACKOUT","true").lower()=="true"
ENABLE_FREEZE_CHECK  = os.getenv("ENABLE_FREEZE_CHECK","true").lower()=="true"
FREEZE_SENSITIVITY   = float(os.getenv("FREEZE_SENSITIVITY","6.0"))
FREEZE_RECHECK_TIMES = int(os.getenv("FREEZE_RECHECK_TIMES","5"))
FREEZE_RECHECK_DELAY = float(os.getenv("FREEZE_RECHECK_DELAY","3.0"))
FREEZE_COOLDOWN      = int(os.getenv("FREEZE_COOLDOWN","15"))

# Backup rolling config
MAX_RECORD= 300  # 5 menit
MOTION_TIMEOUT= 5

# File JSON tempat menyimpan bounding box
MOTION_EVENTS_JSON = "/mnt/Data/Syslog/rtsp/motion_events.json"

###############################################################
def save_motion_event_to_json(channel, bboxes):
    """
    Menyimpan bounding boxes ke file JSON (append).
    Format 1 event / baris => line-based JSON.
    """
    event_data= {
        "timestamp": datetime.now().isoformat(),
        "channel": channel,
        "bboxes": bboxes
    }
    # Append line-based JSON
    try:
        with open(MOTION_EVENTS_JSON, "a") as f:
            f.write(json.dumps(event_data) + "\n")
    except Exception as e:
        logger.error(f"[main] Gagal tulis motion_events.json => {e}")

def check_black_frames(rtsp_url, timeout=5):
    if not ENABLE_BLACKOUT:
        return True
    cmd= [
        "ffmpeg","-hide_banner","-loglevel","error",
        "-rtsp_transport","tcp",
        "-i", rtsp_url,
        "-vf","blackdetect=d=0.1:pic_th=0.98",
        "-an",
        "-t", str(timeout),
        "-f","null","-"
    ]
    try:
        r= subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout+5)
        return (b"black_start" not in r.stderr)
    except subprocess.TimeoutExpired:
        logger.error(f"[main] blackdetect TIMEOUT => {rtsp_url}")
        return False
    except Exception as e:
        logger.error(f"[main] blackdetect error => {e}")
        return False

def check_freeze_frames(rtsp_url):
    if not ENABLE_FREEZE_CHECK:
        return True

    freeze_fail=0
    for i in range(FREEZE_RECHECK_TIMES):
        ok= _check_freeze_once(rtsp_url, FREEZE_SENSITIVITY, timeout=5)
        if not ok:
            freeze_fail+=1
        if i<(FREEZE_RECHECK_TIMES-1):
            time.sleep(FREEZE_RECHECK_DELAY)

    return (freeze_fail< FREEZE_RECHECK_TIMES)

def _check_freeze_once(rtsp_url, freeze_sens, timeout=5):
    filter_str= f"freezedetect=n=-60dB:d={freeze_sens}"
    cmd= [
        "ffmpeg","-hide_banner","-loglevel","error",
        "-rtsp_transport","tcp",
        "-i", rtsp_url,
        "-vf", filter_str,
        "-an",
        "-t", str(timeout),
        "-f","null","-"
    ]
    try:
        r= subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout+5)
        return (b"freeze_start" not in r.stderr)
    except subprocess.TimeoutExpired:
        logger.error(f"[main] freezedetect TIMEOUT => {rtsp_url}")
        return False
    except Exception as e:
        logger.error(f"[main] freezedetect error => {e}")
        return False

def motion_pipeline(rtsp_url, ch):
    cap= cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        logger.error(f"[main] channel={ch} => fail open {rtsp_url}")
        return

    motion= MotionDetector(history=500, varThreshold=16, detectShadows=True, area_threshold=1000)
    obj_detect= None
    if ENABLE_OBJECT_DETECTION:
        from object_detection import ObjectDetector
        # threshold person=0.5, car=0.3, motor=0.3
        obj_detect= ObjectDetector("/app/detection/models/mobilenet_ssd/MobileNetSSD_deploy.prototxt",
                                   "/app/detection/models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel",
                                   conf_person=0.5, conf_car=0.3, conf_motor=0.3)

    backup_sess= None
    is_recording= False
    last_motion= 0

    while True:
        ret, frame= cap.read()
        if not ret or frame is None:
            logger.warning(f"[main] channel={ch} => read() fail => sleep1")
            time.sleep(1)
            continue

        bboxes= motion.detect(frame)
        if bboxes:
            # simpan bboxes ke JSON, log ringkas
            save_motion_event_to_json(ch, bboxes)
            # logger.info(f"[main] channel={ch} => motion bboxes=...") # dihapus agar tak memenuhi docker logs
            logger.debug(f"[main] channel={ch} => motion -> bounding box detail saved to JSON.")
            last_motion= time.time()

            # AI => if needed
            if obj_detect:
                # per label checking
                detections= obj_detect.detect(frame)
                # if no relevant => skip => no recording
                # example: if only person => do backup
                person_found= any((lab=="person") for (lab, conf, x, y, w, h) in detections)
                if not person_found:
                    time.sleep(0.2)
                    continue

            # start or rolling
            if not is_recording:
                backup_sess= BackupSession(rtsp_url, ch)
                path= backup_sess.start_recording()
                logger.info(f"[main] channel={ch} => Start record => {path}")
                is_recording= True
            else:
                # check 5 min
                if not backup_sess.still_ok(MAX_RECORD):
                    # rolling
                    backup_sess.stop_recording()
                    backup_sess= BackupSession(rtsp_url, ch)
                    path= backup_sess.start_recording()
                    logger.info(f"[main] channel={ch} => Rolling record => {path}")
        else:
            # no motion
            if is_recording:
                elapsed= time.time()- last_motion
                if elapsed> MOTION_TIMEOUT:
                    # stop
                    backup_sess.stop_recording()
                    backup_sess= None
                    is_recording= False
                    logger.info(f"[main] channel={ch} => stop record => no motion")

        time.sleep(0.2)

def thread_for_channel(ch):
    # Bentuk rtsp_url
    rtsp_url= f"rtsp://{RTSP_USER}:{RTSP_PASSWORD}@{RTSP_IP}:554/cam/realmonitor?channel={ch}&subtype={RTSP_SUBTYPE}"
    logger.info(f"[main] channel={ch} => {rtsp_url}")

    # black => if fail => skip
    if not check_black_frames(rtsp_url):
        logger.warning(f"[main] channel={ch} => black frames => skip pipeline.")
        return

    # freeze => re-check
    ok_freeze= check_freeze_frames(rtsp_url)
    if not ok_freeze:
        logger.warning(f"[main] channel={ch} => freeze => skip pipeline.")
        return

    # normal => motion
    motion_pipeline(rtsp_url, ch)

def run_validation_once():
    if TEST_CHANNEL=="off":
        c_count= CHANNELS
        channels= [str(i) for i in range(1,c_count+1)]
    else:
        channels= [x.strip() for x in TEST_CHANNEL.split(",") if x.strip()]

    for c in channels:
        t= threading.Thread(target=thread_for_channel, args=(c,), daemon=True)
        t.start()
    logger.info("[main] threads started for all channels")

def main():
    loop= LOOP_ENABLE
    interval= CHECK_INTERVAL

    if loop:
        run_validation_once()
        while True:
            logger.info(f"[main] multi-thread => wait {interval}s")
            time.sleep(interval)
    else:
        run_validation_once()
        while True:
            time.sleep(10)

if __name__=="__main__":
    main()