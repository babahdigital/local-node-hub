#!/usr/bin/env python3
"""
main.py

- Multi-thread => concurrency channel
- blackdetect & freeze check opsional => ENABLE_BLACKOUT, ENABLE_FREEZE_CHECK
- Motion detection => bounding box -> disimpan ke JSON, log ringkas
- Backup => rolling 5 menit (MAX_RECORD=300), stop if no motion 5s
- AI => hamper only person>=0.6, car/motor>=0.4
- Less false positive => area_threshold=3000, morphological kernel=5x5
"""

import os
import sys
import json
import time
import subprocess
import threading
import cv2
from datetime import datetime

sys.path.append("/app/scripts")
from utils import setup_logger
from motion_detection import MotionDetector
from backup_manager import BackupSession

ENABLE_OBJECT_DETECTION = os.getenv("ENABLE_OBJECT_DETECTION","false").lower()=="true"
if ENABLE_OBJECT_DETECTION:
    from object_detection import ObjectDetector

LOG_PATH= "/mnt/Data/Syslog/rtsp/cctv/validation.log"
logger= setup_logger("RTSP-Validation", LOG_PATH)

# ENV
RTSP_IP       = os.getenv("RTSP_IP","172.16.10.252")
RTSP_USER     = os.getenv("RTSP_USER","admin")
RTSP_PASSWORD = os.getenv("RTSP_PASSWORD","admin123")
TEST_CHANNEL  = os.getenv("TEST_CHANNEL","1,3,4").lower()
CHANNELS      = int(os.getenv("CHANNELS","1"))
RTSP_SUBTYPE  = os.getenv("RTSP_SUBTYPE","0")

LOOP_ENABLE   = os.getenv("LOOP_ENABLE","true").lower()=="true"
CHECK_INTERVAL= int(os.getenv("CHECK_INTERVAL","300"))

ENABLE_BLACKOUT       = os.getenv("ENABLE_BLACKOUT","true").lower()=="true"
ENABLE_FREEZE_CHECK   = os.getenv("ENABLE_FREEZE_CHECK","true").lower()=="true"
FREEZE_SENSITIVITY    = float(os.getenv("FREEZE_SENSITIVITY","6.0"))
FREEZE_RECHECK_TIMES  = int(os.getenv("FREEZE_RECHECK_TIMES","5"))
FREEZE_RECHECK_DELAY  = float(os.getenv("FREEZE_RECHECK_DELAY","3.0"))

# Rolling backup config
MAX_RECORD= 300   # 5 min
MOTION_TIMEOUT= 5 # stop if no motion > 5s

MOTION_EVENTS_JSON= "/mnt/Data/Syslog/rtsp/motion_events.json"

def save_bbox_json(channel, bboxes):
    """
    Simpan bounding boxes ke file JSON line-based
    """
    event= {
        "timestamp": datetime.now().isoformat(),
        "channel": channel,
        "bboxes": bboxes
    }
    try:
        with open(MOTION_EVENTS_JSON, "a") as f:
            f.write(json.dumps(event)+"\n")
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
        ok= _check_freeze_once(rtsp_url, FREEZE_SENSITIVITY, 5)
        if not ok:
            freeze_fail+=1
        if i<(FREEZE_RECHECK_TIMES-1):
            time.sleep(FREEZE_RECHECK_DELAY)
    return (freeze_fail<FREEZE_RECHECK_TIMES)

def _check_freeze_once(rtsp_url, freeze_sens, timeout=5):
    try:
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
        logger.error(f"[main] channel={ch} => fail open stream.")
        return

    motion= MotionDetector(area_threshold=3000)  # bigger => less false positive
    obj_detect= None
    if ENABLE_OBJECT_DETECTION:
        from object_detection import ObjectDetector
        obj_detect= ObjectDetector("/app/detection/models/mobilenet_ssd/MobileNetSSD_deploy.prototxt",
                                  "/app/detection/models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel",
                                  conf_person=0.6, conf_car=0.4, conf_motor=0.4)

    backup_sess= None
    is_recording= False
    last_motion=0

    while True:
        ret, frame= cap.read()
        if not ret or frame is None:
            logger.warning(f"[main] channel={ch} => read fail => sleep1")
            time.sleep(1)
            continue

        bboxes= motion.detect(frame)
        if bboxes:
            # save bounding boxes to JSON
            save_bbox_json(ch, bboxes)
            last_motion= time.time()

            # AI check?
            if obj_detect:
                detections= obj_detect.detect(frame)
                # misal: only record if person found
                person_found= any(lab=="person" for (lab,conf,x,y,w,h) in detections)
                if not person_found:
                    time.sleep(0.2)
                    continue

            if not is_recording:
                # Start new backup
                backup_sess= BackupSession(rtsp_url, ch)
                path= backup_sess.start_recording()
                logger.info(f"[main] channel={ch} => start record => {path}")
                is_recording= True
            else:
                # Rolling if >5 min
                if not backup_sess.still_ok(MAX_RECORD):
                    backup_sess.stop_recording()
                    backup_sess= BackupSession(rtsp_url, ch)
                    path= backup_sess.start_recording()
                    logger.info(f"[main] channel={ch} => rolling => {path}")
        else:
            # no bounding box => if recording => check time
            if is_recording:
                elapsed= time.time()- last_motion
                if elapsed> MOTION_TIMEOUT:
                    backup_sess.stop_recording()
                    backup_sess= None
                    is_recording= False
                    logger.info(f"[main] channel={ch} => stop rec => no motion")

        time.sleep(0.2)

def thread_for_channel(ch):
    rtsp_url= f"rtsp://{RTSP_USER}:{RTSP_PASSWORD}@{RTSP_IP}:554/cam/realmonitor?channel={ch}&subtype={RTSP_SUBTYPE}"
    logger.info(f"[main] channel={ch} => {rtsp_url}")

    # black
    if not check_black_frames(rtsp_url):
        logger.warning(f"[main] channel={ch} => black => skip")
        return

    # freeze
    if not check_freeze_frames(rtsp_url):
        logger.warning(f"[main] channel={ch} => freeze => skip")
        return

    # motion
    motion_pipeline(rtsp_url, ch)

def run_validation_once():
    # channels
    if TEST_CHANNEL=="off":
        c_count= CHANNELS
        channels= [str(i) for i in range(1,c_count+1)]
    else:
        channels= [x.strip() for x in TEST_CHANNEL.split(",") if x.strip()]

    for c in channels:
        t= threading.Thread(target=thread_for_channel, args=(c,), daemon=True)
        t.start()
    logger.info("[main] threads started for all channels.")

def main():
    if LOOP_ENABLE:
        run_validation_once()
        while True:
            logger.info(f"[main] multi-channel => wait {CHECK_INTERVAL}s")
            time.sleep(CHECK_INTERVAL)
    else:
        run_validation_once()
        while True:
            time.sleep(10)

if __name__=="__main__":
    main()