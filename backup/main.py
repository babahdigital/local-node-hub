#!/usr/bin/env python3
"""
main.py

Membaca config dari /mnt/Data/Syslog/resource/resource_monitor_state.json
-> CPU usage, stream_config => freeze, blackout, channels, stream_title
-> Jalankan multi-thread => motion detection => rolling backup
-> Minim environment => benar2 0 human touch

utils.py => untuk logging & file_write_lock
"""

import os
import sys
import json
import time
import threading
import cv2
from datetime import datetime

# Pastikan folder scripts ada di PATH
sys.path.append("/app/scripts")

from utils import setup_logger, file_write_lock
from motion_detection import MotionDetector
from backup_manager import BackupSession

# Opsional object detection
ENABLE_OBJECT_DETECTION = os.getenv("ENABLE_OBJECT_DETECTION","false").lower()=="true"
if ENABLE_OBJECT_DETECTION:
    from object_detection import ObjectDetector

LOGGER = setup_logger("RTSP-Validation", "/mnt/Data/Syslog/rtsp/cctv/validation.log")

RESOURCE_JSON= "/mnt/Data/Syslog/resource/resource_monitor_state.json"
MOTION_EVENTS_JSON= "/mnt/Data/Syslog/rtsp/motion_events.json"

MAX_RECORD= 300   # 5 min rolling
MOTION_TIMEOUT= 5 # stop rec if no motion >5s

def load_resource_json():
    """
    Baca /mnt/Data/Syslog/resource/resource_monitor_state.json
    Return dict => {
      "cpu_usage": float,
      "stream_title": str,
      "enable_freeze": bool,
      "enable_blackout": bool,
      "test_channel": "1,3,4",
      "channel_count": 1,
      "check_interval": 60,
      ...
      "rtsp_ip": "xxx", "rtsp_user": "xxx", ...
    }
    """
    config= {}
    try:
        with open(RESOURCE_JSON,"r") as f:
            data= json.load(f)
        # CPU usage
        cpu= data.get("resource_usage",{}).get("cpu",{}).get("usage_percent",0.0)
        config["cpu_usage"]= float(cpu)

        stream_cfg= data.get("stream_config",{})
        config["stream_title"]    = stream_cfg.get("stream_title","Untitled")
        config["enable_freeze"]   = stream_cfg.get("enable_freeze", True)
        config["enable_blackout"] = stream_cfg.get("enable_blackout", True)
        config["test_channel"]    = stream_cfg.get("test_channel","1")
        config["channel_count"]   = int(stream_cfg.get("channel_count",1))
        config["check_interval"]  = int(stream_cfg.get("check_interval",60))
        config["freeze_sensitivity"]= float(stream_cfg.get("freeze_sensitivity",6.0))
        # dsb

        rtsp_cfg= data.get("rtsp_config",{})
        config["rtsp_ip"]       = rtsp_cfg.get("rtsp_ip","127.0.0.1")
        config["rtsp_user"]     = rtsp_cfg.get("rtsp_user","admin")
        config["rtsp_password"] = rtsp_cfg.get("rtsp_password","admin123")
        config["rtsp_subtype"]  = rtsp_cfg.get("rtsp_subtype","0")
    except Exception as e:
        LOGGER.error(f"[main] Gagal load resource_monitor_state.json => {e}")
        # fallback
        config["cpu_usage"]=0.0
        config["stream_title"]="Untitled"
        config["enable_freeze"]=True
        config["enable_blackout"]=True
        config["test_channel"]="1"
        config["channel_count"]=1
        config["check_interval"]=60
        config["freeze_sensitivity"]=6.0
        config["rtsp_ip"]="127.0.0.1"
        config["rtsp_user"]="admin"
        config["rtsp_password"]="admin123"
        config["rtsp_subtype"]="0"

    return config

def save_bboxes_to_json(channel, bboxes):
    evt= {
        "timestamp": datetime.now().isoformat(),
        "channel": channel,
        "bboxes": bboxes
    }
    with file_write_lock:
        try:
            with open(MOTION_EVENTS_JSON,"a") as f:
                json.dump(evt, f)
                f.write("\n")
        except Exception as e:
            LOGGER.error(f"[main] Gagal tulis bounding box => {e}")

def check_black_frames(rtsp_url, do_blackout, cpu_usage):
    # skip if do_blackout=False or cpu>90 => skip => hemat cpu
    if not do_blackout or cpu_usage>90:
        return True
    import subprocess
    cmd= [
        "ffmpeg","-hide_banner","-loglevel","error",
        "-rtsp_transport","tcp",
        "-i", rtsp_url,
        "-vf","blackdetect=d=0.1:pic_th=0.98",
        "-an","-t","5","-f","null","-"
    ]
    try:
        r= subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return (b"black_start" not in r.stderr)
    except:
        return False

def check_freeze(rtsp_url, do_freeze, cpu_usage, freeze_sens):
    # skip if do_freeze=False or cpu_usage>85 => skip freeze => hemat CPU
    if not do_freeze or cpu_usage>85:
        return True
    import subprocess, time
    freeze_fail=0
    times=5
    delay=3
    for i in range(times):
        cmd= [
            "ffmpeg","-hide_banner","-loglevel","error",
            "-rtsp_transport","tcp",
            "-i", rtsp_url,
            "-vf", f"freezedetect=n=-60dB:d={freeze_sens}",
            "-an","-t","5","-f","null","-"
        ]
        try:
            rr= subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            ok= (b"freeze_start" not in rr.stderr)
            if not ok:
                freeze_fail+=1
        except:
            freeze_fail+=1
        if i<(times-1):
            time.sleep(delay)
    return (freeze_fail<times)

def motion_pipeline(rtsp_url, ch, config):
    cap= cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        LOGGER.error(f"[main] ch={ch} => fail open => {rtsp_url}")
        return

    motion= MotionDetector(area_threshold=3000)
    # object detection
    obj_detect= None
    if ENABLE_OBJECT_DETECTION:
        from object_detection import ObjectDetector
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
            save_bboxes_to_json(ch, bboxes)
            last_motion= time.time()

            # check object detection => if no person => skip
            if obj_detect:
                detections= obj_detect.detect(frame)
                person_found= any((lab=="person") for (lab,conf,x,y,w,h) in detections)
                if not person_found:
                    time.sleep(0.2)
                    continue

            if not is_recording:
                backup_sess= BackupSession(rtsp_url, ch, config["stream_title"])
                path= backup_sess.start_recording()
                LOGGER.info(f"[main] ch={ch} => start record => {path}")
                is_recording= True
            else:
                if not backup_sess.still_ok(MAX_RECORD):
                    backup_sess.stop_recording()
                    backup_sess= BackupSession(rtsp_url, ch, config["stream_title"])
                    path= backup_sess.start_recording()
                    LOGGER.info(f"[main] ch={ch} => rolling => {path}")
        else:
            # no bounding box => if recording => check last motion
            if is_recording:
                if (time.time()- last_motion)> MOTION_TIMEOUT:
                    backup_sess.stop_recording()
                    backup_sess= None
                    is_recording= False
                    LOGGER.info(f"[main] ch={ch} => stop rec => no motion")
        time.sleep(0.2)

def thread_for_channel(ch, config):
    rtsp_url= f"rtsp://{config['rtsp_user']}:{config['rtsp_password']}@{config['rtsp_ip']}:554/cam/realmonitor?channel={ch}&subtype={config['rtsp_subtype']}"
    LOGGER.info(f"[main] ch={ch} => {rtsp_url}")

    cpu_usage= config["cpu_usage"]
    do_blackout= config.get("enable_blackout",True)
    if not check_black_frames(rtsp_url, do_blackout, cpu_usage):
        LOGGER.warning(f"[main] ch={ch} => black => skip pipeline")
        return

    do_freeze= config.get("enable_freeze",True)
    freeze_sens= float(config.get("freeze_sensitivity",6.0))
    if not check_freeze(rtsp_url, do_freeze, cpu_usage, freeze_sens):
        LOGGER.warning(f"[main] ch={ch} => freeze => skip pipeline")
        return

    motion_pipeline(rtsp_url, ch, config)

def run_validation_once(config):
    test_channel  = config.get("test_channel","1").lower()
    channel_count = config.get("channel_count",1)

    if test_channel=="off":
        channels= [str(i) for i in range(1, channel_count+1)]
    else:
        channels= [x.strip() for x in test_channel.split(",") if x.strip()]

    for c in channels:
        t= threading.Thread(target=thread_for_channel, args=(c, config), daemon=True)
        t.start()
    LOGGER.info("[main] threads started for all channels")

def main():
    # Baca config dari resource_monitor_state.json
    config= load_resource_json()
    interval= config.get("check_interval", 60)  # default 60
    loop= True  # tidak perlu ENV lagi

    run_validation_once(config)
    while loop:
        LOGGER.info(f"[main] multi-thread => wait {interval}s => 0 human touch.")
        time.sleep(interval)

if __name__=="__main__":
    main()