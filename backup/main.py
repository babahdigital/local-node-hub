#!/usr/bin/env python3
"""
main.py

1) Baca /mnt/Data/Syslog/resource/resource_monitor_state.json => CPU usage, stream_config.
2) Jika CPU usage>85 => skip freeze-check => hemat CPU
3) Jalankan multi-thread channel => black/freeze => motion => rolling backup 5 menit
4) Simpan bounding box di JSON => /mnt/Data/Syslog/rtsp/motion_events.json
5) Kustom object detection => person=0.6, car=0.4, motor=0.4
6) Stream title => set via -metadata title="KC. Ayani" => di backup_manager
"""

import os
import sys
import time
import json
import threading
import cv2
from datetime import datetime

sys.path.append("/app/scripts")
from utils import setup_logger
from motion_detection import MotionDetector
from backup_manager import BackupSession
# object detection optional
ENABLE_OBJECT_DETECTION = os.getenv("ENABLE_OBJECT_DETECTION","false").lower()=="true"
if ENABLE_OBJECT_DETECTION:
    from object_detection import ObjectDetector

LOG_PATH = "/mnt/Data/Syslog/rtsp/cctv/validation.log"
logger   = setup_logger("RTSP-Validation", LOG_PATH)

# File JSON resource monitor
RESOURCE_JSON_PATH = "/mnt/Data/Syslog/resource/resource_monitor_state.json"

# Hasil bounding box
MOTION_EVENTS_JSON= "/mnt/Data/Syslog/rtsp/motion_events.json"

# Rolling config
MAX_RECORD= 300
MOTION_TIMEOUT= 5

def load_resource_config():
    """
    Baca CPU usage, stream_config dsb. dari resource_monitor_state.json
    Return dict => { 'cpu_usage': float, 'stream_title': str, 'enable_freeze': bool, 'enable_blackout': bool, 'test_channel':..., ... }
    """
    data= {}
    try:
        with open(RESOURCE_JSON_PATH,"r") as f:
            j= json.load(f)
        # resource_usage
        cpu_usage= j.get("resource_usage",{}).get("cpu",{}).get("usage_percent",0.0)
        data["cpu_usage"] = float(cpu_usage)

        stream_cfg= j.get("stream_config",{})
        data["stream_title"]   = stream_cfg.get("stream_title","Untitled")
        data["enable_freeze"]  = stream_cfg.get("enable_freeze", True)
        data["enable_blackout"]= stream_cfg.get("enable_blackout", True)
        data["test_channel"]   = stream_cfg.get("test_channel","1,3,4").lower()
        data["channel_count"]  = int(stream_cfg.get("channel_count", 1))
        # dst...
    except Exception as e:
        logger.error(f"[main] Gagal baca resource_monitor_state.json => {e}")
        # fallback
        data["cpu_usage"]       = 0.0
        data["stream_title"]    = "Untitled"
        data["enable_freeze"]   = True
        data["enable_blackout"] = True
        data["test_channel"]    = "1"
        data["channel_count"]   = 1
    return data

# Fungsi check black
def check_black_frames(rtsp_url, do_blackout=True):
    if not do_blackout:
        return True
    import subprocess
    cmd= [
        "ffmpeg","-hide_banner","-loglevel","error",
        "-rtsp_transport","tcp",
        "-i", rtsp_url,
        "-vf","blackdetect=d=0.1:pic_th=0.98",
        "-an",
        "-t","5","-f","null","-"
    ]
    try:
        r= subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return (b"black_start" not in r.stderr)
    except:
        return False

# freeze multi-check
def check_freeze_frames(rtsp_url, do_freeze=True, cpu_usage=0.0):
    if not do_freeze:
        return True
    # misal: skip freeze-check if cpu>85 => hemat CPU
    if cpu_usage>85:
        logger.info(f"[main] CPU>85 => skip freeze-check for performance.")
        return True

    import subprocess, time
    freeze_fail= 0
    times= 5
    delay= 3.0
    for i in range(times):
        ok= _freeze_once(rtsp_url)
        if not ok:
            freeze_fail+=1
        if i<(times-1):
            time.sleep(delay)
    return (freeze_fail< times)

def _freeze_once(rtsp_url):
    import subprocess
    cmd= [
        "ffmpeg","-hide_banner","-loglevel","error",
        "-rtsp_transport","tcp",
        "-i", rtsp_url,
        "-vf", "freezedetect=n=-60dB:d=6.0", # d=6.0 => freeze_sensitivity
        "-an","-t","5","-f","null","-"
    ]
    try:
        r= subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return (b"freeze_start" not in r.stderr)
    except:
        return False

def save_bboxes_json(channel, bboxes):
    event= {
        "timestamp": datetime.now().isoformat(),
        "channel": channel,
        "bboxes": bboxes
    }
    try:
        with open(MOTION_EVENTS_JSON,"a") as f:
            f.write(json.dumps(event)+"\n")
    except Exception as e:
        logger.error(f"[main] Gagal tulis motion_events.json => {e}")

def motion_pipeline(rtsp_url, channel, stream_title, cpu_usage):
    cap= cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        logger.error(f"[main] channel={channel} => fail open => {rtsp_url}")
        return

    from motion_detection import MotionDetector
    motion= MotionDetector(area_threshold=3000)  # area 3000 => minimal false alarm

    obj_detect= None
    if ENABLE_OBJECT_DETECTION:
        from object_detection import ObjectDetector
        # threshold person=0.6 => cukup ketat
        obj_detect= ObjectDetector("/app/detection/models/mobilenet_ssd/MobileNetSSD_deploy.prototxt",
                                  "/app/detection/models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel",
                                  conf_person=0.6, conf_car=0.4, conf_motor=0.4)

    backup_sess= None
    is_recording= False
    last_motion= 0

    while True:
        ret, frame= cap.read()
        if not ret or frame is None:
            time.sleep(1)
            continue

        bboxes= motion.detect(frame)
        if bboxes:
            save_bboxes_json(channel, bboxes)
            last_motion= time.time()

            # if object detection => filter only person
            if obj_detect:
                detections= obj_detect.detect(frame)
                # if no person => skip backup
                person_found= any(lab=="person" for (lab,conf,x,y,w,h) in detections)
                if not person_found:
                    time.sleep(0.2)
                    continue

            # Rolling backup
            from backup_manager import BackupSession
            if not is_recording:
                backup_sess= BackupSession(rtsp_url, channel)
                backup_sess.stream_title= stream_title  # agar metadata title
                path= backup_sess.start_recording()
                logger.info(f"[main] ch={channel} => Start record => {path}")
                is_recording= True
            else:
                if not backup_sess.still_ok(MAX_RECORD):
                    backup_sess.stop_recording()
                    backup_sess= BackupSession(rtsp_url, channel)
                    backup_sess.stream_title= stream_title
                    path= backup_sess.start_recording()
                    logger.info(f"[main] ch={channel} => Rolling => {path}")
        else:
            # no bounding box => if rec => check time
            if is_recording:
                elapsed= time.time()- last_motion
                if elapsed> MOTION_TIMEOUT:
                    backup_sess.stop_recording()
                    backup_sess= None
                    is_recording= False
                    logger.info(f"[main] ch={channel} => stop record => no motion")

        time.sleep(0.2)

def thread_for_channel(ch, config):
    user=  os.getenv("RTSP_USER","admin")
    pwd=   os.getenv("RTSP_PASSWORD","admin123")
    ip=    os.getenv("RTSP_IP","172.16.10.252")
    sub=   os.getenv("RTSP_SUBTYPE","0")

    rtsp_url= f"rtsp://{user}:{pwd}@{ip}:554/cam/realmonitor?channel={ch}&subtype={sub}"
    logger.info(f"[main] channel={ch} => {rtsp_url}")

    # 1) check blackout => skip if CPU usage>90 misal
    do_blackout= config.get("enable_blackout", True)
    cpu_usage=  config.get("cpu_usage", 0.0)
    if cpu_usage>90:
        do_blackout= False  # skip => hemat CPU
        logger.info(f"[main] channel={ch} => CPU>90 => skip blackdetect")

    if do_blackout:
        ok_black= check_black_frames(rtsp_url)
        if not ok_black:
            logger.warning(f"[main] channel={ch} => black => skip pipeline")
            return

    # 2) check freeze => skip if usage>85 or config "enable_freeze"=false
    do_freeze= config.get("enable_freeze", True)
    if cpu_usage>85:
        do_freeze= False
        logger.info(f"[main] channel={ch} => CPU>85 => skip freeze-check")

    if do_freeze:
        ok_fz= check_freeze_frames(rtsp_url, do_freeze, cpu_usage)
        if not ok_fz:
            logger.warning(f"[main] channel={ch} => freeze => skip pipeline")
            return

    # 3) motion pipeline => backup
    stream_title= config.get("stream_title","Unknown")
    motion_pipeline(rtsp_url, ch, stream_title, cpu_usage)

def run_validation_once(config):
    test_channel   = config.get("test_channel","1").lower()
    channel_count  = config.get("channel_count",1)

    if test_channel=="off":
        channels= [str(i) for i in range(1,channel_count+1)]
    else:
        channels= [x.strip() for x in test_channel.split(",") if x.strip()]

    for c in channels:
        t= threading.Thread(target=thread_for_channel, args=(c, config), daemon=True)
        t.start()
    logger.info("[main] threads started for all channels")

def main():
    logger.info("[main] Loading resource_monitor_state.json config")
    config= load_resource_config()
    # Jalankan run_validation_once => multi-thread
    loop_enable= True
    interval= 300
    # Atau Anda bisa load dari config...
    loop_enable= os.getenv("LOOP_ENABLE","true").lower()=="true"
    interval= int(os.getenv("CHECK_INTERVAL","300"))

    if loop_enable:
        run_validation_once(config)
        while True:
            logger.info(f"[main] multi-channel => wait {interval}s")
            time.sleep(interval)
    else:
        run_validation_once(config)
        while True:
            time.sleep(10)

if __name__=="__main__":
    main()