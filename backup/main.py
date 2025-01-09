#!/usr/bin/env python3
"""
main.py

Memisahkan tiga mode perekaman:
1) FULL => merekam terus (rolling potongan CHUNK_DURATION).
2) MOTION => merekam hanya saat motion, rolling tiap MAX_RECORD.
3) MOTION_OBJ => merekam hanya saat motion + (object detection, mis. "person").

Pemilihan mode via ENV BACKUP_MODE={full|motion|motion_obj}.
Tidak ada perpindahan otomatis di runtime; user menentukan mode sekali.

Freeze/Black check tetap sebelum pipeline. 
Jika freeze/black fail => channel skip.

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

from utils import setup_logger, decode_credentials
from motion_detection import MotionDetector
from backup_manager import BackupSession

# (A) Otomatis load object_detection jika BACKUP_MODE=motion_obj
BACKUP_MODE = os.getenv("BACKUP_MODE","full").lower()
NEED_OBJECT_DET = (BACKUP_MODE=="motion_obj")

# Freeze/Black flags
ENABLE_FREEZE_CHECK = os.getenv("ENABLE_FREEZE_CHECK","true").lower()=="true"
ENABLE_BLACKOUT     = os.getenv("ENABLE_BLACKOUT","true").lower()=="true"
LOOP_ENABLE         = os.getenv("LOOP_ENABLE","true").lower()=="true"

# Rolling config
CHUNK_DURATION = int(os.getenv("CHUNK_DURATION","300"))  # potongan full-backup
MAX_RECORD     = int(os.getenv("MAX_RECORD","300"))      # potongan motion-backup

# MOTION_TIMEOUT => jeda (detik) tanpa motion sebelum stop perekaman
MOTION_TIMEOUT = int(os.getenv("MOTION_TIMEOUT","5"))
# POST_MOTION_DELAY => tambahan jeda setelah motion hilang (detik)
POST_MOTION_DELAY = int(os.getenv("POST_MOTION_DELAY","10"))

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL","300"))

BLACK_DETECT_THRESHOLD = float(os.getenv("BLACK_DETECT_THRESHOLD","0.98"))
FREEZE_SENSITIVITY     = float(os.getenv("FREEZE_SENSITIVITY","6.0"))
FREEZE_RECHECK_TIMES   = int(os.getenv("FREEZE_RECHECK_TIMES","5"))
FREEZE_RECHECK_DELAY   = float(os.getenv("FREEZE_RECHECK_DELAY","3.0"))

LOG_PATH = "/mnt/Data/Syslog/rtsp/cctv/validation.log"
logger   = setup_logger("Main-Combined", LOG_PATH)

# JSON
MONITOR_STATE_FILE  = "/mnt/Data/Syslog/resource/resource_monitor_state.json"
VALIDATION_JSON     = "/mnt/Data/Syslog/rtsp/channel_validation.json"
MOTION_EVENTS_JSON  = "/mnt/Data/Syslog/rtsp/motion_events.json"

# (B) Tambahan: Penjadwalan Freeze/Black Check
FREEZE_BLACK_INTERVAL = int(os.getenv("FREEZE_BLACK_INTERVAL","0"))  # 0 => cek setiap loop
LAST_CHECK_TIMES = {}  # { channel_number : last_check_timestamp }

# Jika butuh object detection (mode=motion_obj), load modul
ObjectDetector = None
if NEED_OBJECT_DET:
    from object_detection import ObjectDetector

###############################################################################
# 1. Validasi JSON
###############################################################################
def load_validation_status():
    try:
        with open(VALIDATION_JSON,"r") as f:
            return json.load(f)
    except:
        return {}

def save_validation_status(data:dict):
    try:
        with open(VALIDATION_JSON,"w") as f:
            json.dump(data,f,indent=2)
    except Exception as e:
        logger.warning(f"[Main] Gagal menulis {VALIDATION_JSON} => {e}")

def update_validation_status(channel, info:dict):
    data = load_validation_status()
    ch_str=str(channel)
    if ch_str not in data:
        data[ch_str]={}
    data[ch_str].update(info)
    data[ch_str]["last_update"]=datetime.now().isoformat()
    save_validation_status(data)

###############################################################################
# 2. Inisialisasi MONITOR_STATE_FILE
###############################################################################
def ensure_json_initialized():
    if not os.path.exists(MONITOR_STATE_FILE):
        logger.info(f"[Init] File {MONITOR_STATE_FILE} belum ada, buat minimal.")
        scfg = {
            "stream_title": os.getenv("STREAM_TITLE","Untitled"),
            "rtsp_ip": os.getenv("RTSP_IP","127.0.0.1")
        }
        rcfg = {
            "rtsp_subtype": os.getenv("RTSP_SUBTYPE","0"),
        }
        init_data = {
            "resource_usage": {},
            "stream_config": scfg,
            "rtsp_config":   rcfg
        }
        with open(MONITOR_STATE_FILE,"w") as f:
            json.dump(init_data,f,indent=2)
    else:
        logger.info(f"[Init] File {MONITOR_STATE_FILE} sudah ada, skip init.")

###############################################################################
# 3. Load Resource+Config
###############################################################################
def load_resource_config():
    config={}
    try:
        with open(MONITOR_STATE_FILE,"r") as f:
            j=json.load(f)
        usage = j.get("resource_usage",{}).get("cpu",{}).get("usage_percent",0.0)
        config["cpu_usage"]=float(usage)

        scfg=j.get("stream_config",{})
        config["stream_title"]=scfg.get("stream_title","Untitled")
        config["rtsp_ip"]     =scfg.get("rtsp_ip","127.0.0.1")

        rcfg=j.get("rtsp_config",{})
        config["rtsp_subtype"]=rcfg.get("rtsp_subtype","0")

        user_json =rcfg.get("rtsp_user","admin")
        pass_json =rcfg.get("rtsp_password","admin123")
    except Exception as e:
        logger.warning(f"[Main] Gagal baca {MONITOR_STATE_FILE} => {e}")
        config["cpu_usage"]=0.0
        config["stream_title"]=os.getenv("STREAM_TITLE","Untitled")
        config["rtsp_ip"]     =os.getenv("RTSP_IP","127.0.0.1")
        config["rtsp_subtype"]=os.getenv("RTSP_SUBTYPE","0")
        user_json             =os.getenv("RTSP_USER","admin")
        pass_json             =os.getenv("RTSP_PASSWORD","admin123")

    # decode credentials
    try:
        user_env, pass_env=decode_credentials()
        config["rtsp_user"]     =user_env
        config["rtsp_password"] =pass_env
        logger.info(f"[Main] RTSP user/pass => {user_env}")
    except:
        config["rtsp_user"]     =user_json
        config["rtsp_password"] =pass_json

    return config

###############################################################################
# 4. Freeze & Black
###############################################################################
def check_black_frames(rtsp_url, do_blackout, duration=0.1, threshold=0.98):
    if not do_blackout:
        return True
    
    cmd=[
        "ffmpeg","-hide_banner","-loglevel","error","-y","-err_detect","ignore_err",
        "-rtsp_transport","tcp","-i",rtsp_url,
        "-vf",f"blackdetect=d={duration}:pic_th={threshold}",
        "-an","-t","5","-f","null","-"
    ]
    try:
        r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
        return (b"black_start" not in r.stderr)
    except:
        return False

def check_freeze_frames(rtsp_url, do_freeze, cpu_usage, freeze_sens=6.0, times=5, delay=3.0):
    if not do_freeze:
        return True
    if cpu_usage>85:
        logger.info("[Freeze] CPU>85 => skip freeze-check.")
        return True
    fail=0
    for i in range(times):
        if not _freeze_once(rtsp_url, freeze_sens):
            fail+=1
        if i<times-1:
            time.sleep(delay)
    return (fail<times)

def _freeze_once(rtsp_url, freeze_sens):
    cmd=[
        "ffmpeg","-hide_banner","-loglevel","error","-y","-err_detect","ignore_err",
        "-rtsp_transport","tcp","-i",rtsp_url,
        "-vf",f"freezedetect=n=-60dB:d={freeze_sens}",
        "-an","-t","5","-f","null","-"
    ]
    try:
        r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
        return (b"freeze_start" not in r.stderr)
    except:
        return False

###############################################################################
# 5. FULL Backup (rolling)
###############################################################################
class FullBackupSession:
    def __init__(self, rtsp_url, channel, stream_title):
        self.rtsp_url     = rtsp_url
        self.channel      = channel
        self.stream_title = stream_title
        self.proc         = None
        self.start_time   = None
        self.file_path    = None
        self.active       = False

    def start_chunk(self):
        import time,os
        self.start_time=time.time()
        out_file=self._make_filename()
        self.file_path=out_file
        cmd=[
            "ffmpeg","-hide_banner","-loglevel","error","-y","-err_detect","ignore_err",
            "-rtsp_transport","tcp","-i",self.rtsp_url,
            "-c","copy",
            "-metadata",f"title={self.stream_title}",
            out_file
        ]
        self.proc=subprocess.Popen(cmd)
        self.active=True
        logger.info(f"[FullBackup] ch={self.channel} => start => {out_file}")

    def _make_filename(self):
        import time,os
        backup_root="/mnt/Data/Backup"
        date_str=time.strftime("%d-%m-%Y")
        time_str=time.strftime("%H-%M-%S")
        ch_folder=f"Channel-{self.channel}"
        final_dir=os.path.join(backup_root,date_str,ch_folder)
        os.makedirs(final_dir, exist_ok=True)
        return os.path.join(final_dir,f"CH{self.channel}-{time_str}.mkv")

    def still_ok(self, chunk_dur):
        if not self.active or not self.proc:
            return False
        import time
        elapsed=time.time()-self.start_time
        return (elapsed<chunk_dur)

    def stop_chunk(self):
        if self.active and self.proc:
            self.proc.terminate()
            self.proc.wait(timeout=5)
            logger.info(f"[FullBackup] ch={self.channel} => stop => {self.file_path}")
            self.proc=None
            self.active=False

###############################################################################
# 6. Motion (Rolling)
###############################################################################
class MotionSession:
    def __init__(self, rtsp_url, channel, stream_title):
        self.rtsp_url     = rtsp_url
        self.channel      = channel
        self.stream_title = stream_title
        self.proc         = None
        self.start_time   = None
        self.file_path    = None
        self.active       = False

    def start_record(self, log_prefix="[MotionSession]"):
        import time,os
        self.start_time=time.time()
        out_file=self._make_filename()
        self.file_path=out_file
        cmd=[
            "ffmpeg","-hide_banner","-loglevel","error","-y","-err_detect","ignore_err",
            "-rtsp_transport","tcp","-i",self.rtsp_url,
            "-c","copy",
            "-metadata",f"title={self.stream_title}",
            out_file
        ]
        self.proc=subprocess.Popen(cmd)
        self.active=True
        # Gunakan log_prefix untuk membedakan motion vs object detection
        logger.info(f"{log_prefix} ch={self.channel} => start => {out_file}")

    def _make_filename(self):
        import time,os
        backup_root="/mnt/Data/Backup"
        date_str=time.strftime("%d-%m-%Y")
        time_str=time.strftime("%H-%M-%S")
        ch_folder=f"Channel-{self.channel}"
        final_dir=os.path.join(backup_root,date_str,ch_folder)
        os.makedirs(final_dir,exist_ok=True)
        return os.path.join(final_dir,f"CH{self.channel}-{time_str}.mkv")

    def still_ok(self, max_dur):
        if not self.active or not self.proc:
            return False
        import time
        elapsed=time.time()-self.start_time
        return (elapsed<max_dur)

    def stop_record(self):
        if self.active and self.proc:
            self.proc.terminate()
            self.proc.wait(timeout=5)
            logger.info(f"[MotionSession] ch={self.channel} => stop => {self.file_path}")
            self.proc=None
            self.active=False

###############################################################################
# 7. Pipeline per Channel
###############################################################################
def thread_for_channel(ch, config):
    """
    Mengerjakan satu channel:
      - Jadwal freeze/black check (jika FREEZE_BLACK_INTERVAL>0)
      - Lolos freeze/black => panggil pipeline sesuai BACKUP_MODE
    """
    cpu_usage = config["cpu_usage"]
    do_black  = ENABLE_BLACKOUT
    do_freeze = ENABLE_FREEZE_CHECK

    user    = config["rtsp_user"]
    pwd     = config["rtsp_password"]
    ip      = config["rtsp_ip"]
    subtype = config["rtsp_subtype"]
    rtsp_url= f"rtsp://{user}:{pwd}@{ip}:554/cam/realmonitor?channel={ch}&subtype={subtype}"
    logger.info(f"[Main] ch={ch} => {rtsp_url}")

    # (A) Jadwal Freeze/Black Check
    global LAST_CHECK_TIMES
    now = time.time()
    last_check = LAST_CHECK_TIMES.get(ch, 0)
    interval   = now - last_check

    # Jika FREEZE_BLACK_INTERVAL=0 => cek setiap saat (default).
    if FREEZE_BLACK_INTERVAL>0 and interval < FREEZE_BLACK_INTERVAL:
        # skip freeze/black check
        ok_black   = True
        ok_freeze  = True
        logger.info(f"[Main] ch={ch} => skip freeze/black check (recently checked)")
    else:
        # catat waktu check
        LAST_CHECK_TIMES[ch] = now

        # black
        if cpu_usage>90:
            do_black=False
            logger.info(f"[Main] ch={ch} => CPU>90 => skip blackdetect")
        ok_black=check_black_frames(rtsp_url, do_black, threshold=BLACK_DETECT_THRESHOLD)
        if not ok_black:
            err=f"ch={ch} => black => skip pipeline"
            logger.warning(f"[Main] {err}")
            update_validation_status(ch,{
                "freeze_ok":None,
                "black_ok":False,
                "livestream_link":rtsp_url,
                "error_msg":err
            })
            return

        # freeze
        if do_freeze:
            ok_freeze=check_freeze_frames(rtsp_url,True,cpu_usage,
                                          freeze_sens=FREEZE_SENSITIVITY,
                                          times=FREEZE_RECHECK_TIMES,
                                          delay=FREEZE_RECHECK_DELAY)
            if not ok_freeze:
                err=f"ch={ch} => freeze => skip pipeline"
                logger.warning(f"[Main] {err}")
                update_validation_status(ch,{
                    "freeze_ok":False,
                    "black_ok":ok_black,
                    "livestream_link":rtsp_url,
                    "error_msg":err
                })
                return
        else:
            ok_freeze=True

    # update success
    update_validation_status(ch,{
        "freeze_ok":ok_freeze,
        "black_ok":ok_black,
        "livestream_link":rtsp_url,
        "error_msg":None
    })

    # (B) Pilih pipeline
    from_main_mode = BACKUP_MODE
    if from_main_mode=="full":
        pipeline_full(ch, config, rtsp_url)
    elif from_main_mode=="motion":
        pipeline_motion(ch, config, rtsp_url, object_detection=False)
    elif from_main_mode=="motion_obj":
        pipeline_motion(ch, config, rtsp_url, object_detection=True)
    else:
        logger.warning(f"[Main] BACKUP_MODE={from_main_mode} unknown => fallback full")
        pipeline_full(ch, config, rtsp_url)

###############################################################################
# 8. Pipeline Full
###############################################################################
def pipeline_full(ch, config, rtsp_url):
    """
    Hanya full backup, rolling CHUNK_DURATION
    """
    sess=FullBackupSession(rtsp_url, ch, config["stream_title"])
    while True:
        if not sess.active:
            sess.start_chunk()
        if not sess.still_ok(CHUNK_DURATION):
            sess.stop_chunk()
            sess.start_chunk()
        time.sleep(1)

###############################################################################
# 9. Pipeline Motion (Optimized)
###############################################################################
def pipeline_motion(ch, config, rtsp_url, object_detection=False):
    """
    Merekam hanya saat motion; rolling per MAX_RECORD.
    Jika object_detection=true => cek "person" (atau object lain).
    
    Optimasi CPU:
      - Skipping frame (FRAME_SKIP)
      - Resize frame sebelum motion/object detection
      - Perbesar interval sleep
      - Tambahkan post-motion delay agar rekaman tidak langsung berhenti
        saat motion hilang. (MOTION_TIMEOUT + POST_MOTION_DELAY)

    + Perbedaan Log:
      - [MotionSession] => purely motion
      - [ObjectDetection] => motion + person
    """
    cap=cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        err=f"ch={ch} => fail open => {rtsp_url}"
        logger.error(f"[Main] {err}")
        update_validation_status(ch,{
            "error_msg":err
        })
        return

    # area_threshold lebih besar => lebih sedikit gerakan kecil
    from motion_detection import MotionDetector
    motion_det=MotionDetector(area_threshold=3000)

    obj_det=None
    if object_detection:
        from object_detection import ObjectDetector
        obj_det=ObjectDetector(
            "/app/backup/models/mobilenet_ssd/MobileNetSSD_deploy.prototxt",
            "/app/backup/models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel",
            conf_person=0.6, conf_car=0.4, conf_motor=0.4
        )

    m_sess=MotionSession(rtsp_url, ch, config["stream_title"])
    last_motion=0
    is_recording=False

    # --- PARAM OPTIMASI CPU ---
    FRAME_SKIP      = int(os.getenv("FRAME_SKIP", "5"))  # default skip 5 => analisis 1/5 frame
    DOWNSCALE_RATIO = float(os.getenv("DOWNSCALE_RATIO", "0.5")) # resize setengah
    SLEEP_INTERVAL  = float(os.getenv("MOTION_SLEEP", "0.2"))    # jeda per loop
    # --------------------------

    global MOTION_TIMEOUT, POST_MOTION_DELAY

    frame_count=0

    while True:
        ret, frame=cap.read()
        if not ret or frame is None:
            time.sleep(1)
            continue

        # Skip frames => misal hanya proses 1 dari 5 frame (FRAME_SKIP=5)
        frame_count +=1
        if frame_count % FRAME_SKIP != 0:
            time.sleep(SLEEP_INTERVAL)
            continue

        # Resize frame => turunkan resolusi untuk deteksi agar lebih cepat
        if DOWNSCALE_RATIO<1.0:
            try:
                new_w = int(frame.shape[1] * DOWNSCALE_RATIO)
                new_h = int(frame.shape[0] * DOWNSCALE_RATIO)
                frame_small = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            except Exception as e:
                logger.warning(f"[MotionPipeline] resize error => {e}")
                frame_small = frame
        else:
            frame_small = frame

        # Deteksi motion
        bboxes = motion_det.detect(frame_small)
        if bboxes:
            # catat bounding box
            ev={
                "timestamp": datetime.now().isoformat(),
                "channel": ch,
                "bboxes": bboxes
            }
            try:
                with open(MOTION_EVENTS_JSON,"a") as f:
                    f.write(json.dumps(ev)+"\n")
            except Exception as e:
                logger.error(f"[MotionPipeline] Gagal tulis {MOTION_EVENTS_JSON} => {e}")

            # Apakah pakai object detection (mode motion_obj)?
            is_obj_trigger=False
            if obj_det:
                results,_= obj_det.detect(frame_small)
                person_found= any(r[0]=="person" for r in results)
                if not person_found:
                    # object tak ditemukan => skip perekaman
                    time.sleep(SLEEP_INTERVAL)
                    continue
                else:
                    is_obj_trigger=True

            # => real motion => record
            last_motion=time.time()
            if not is_recording:
                # Bedakan log prefix
                if is_obj_trigger:
                    prefix="[ObjectDetection]"
                else:
                    prefix="[MotionSession]"
                m_sess.start_record(log_prefix=prefix)
                is_recording=True
            else:
                # rolling motion
                if not m_sess.still_ok(MAX_RECORD):
                    m_sess.stop_record()
                    if is_obj_trigger:
                        prefix="[ObjectDetection]"
                    else:
                        prefix="[MotionSession]"
                    m_sess.start_record(log_prefix=prefix)
        else:
            # no bounding => check idle => stop perekaman kalau idle lama
            if is_recording:
                idle_sec=time.time()-last_motion
                # post-buffer => total = MOTION_TIMEOUT + POST_MOTION_DELAY
                if idle_sec > (MOTION_TIMEOUT + POST_MOTION_DELAY):
                    m_sess.stop_record()
                    is_recording=False

        time.sleep(SLEEP_INTERVAL)

###############################################################################
# 10. Loop Utama
###############################################################################
def run_pipeline_loop():
    test_ch    = os.getenv("TEST_CHANNEL","off").lower()
    chan_count = int(os.getenv("CHANNEL_COUNT","1"))

    while True:
        cfg=load_resource_config()

        if test_ch=="off":
            channels = [str(i) for i in range(1, chan_count+1)]
        else:
            channels = [x.strip() for x in test_ch.split(",") if x.strip()]

        logger.info(f"[Main] Start pipeline => mode={BACKUP_MODE} => channels={channels}")
        for c in channels:
            t=threading.Thread(target=thread_for_channel, args=(c,cfg),daemon=True)
            t.start()

        if not LOOP_ENABLE:
            logger.info("[Main] LOOP_ENABLE=false => run 1x => break.")
            break

        logger.info(f"[Main] Selesai 1 putaran => tunggu {CHECK_INTERVAL} detik.")
        time.sleep(CHECK_INTERVAL)

###############################################################################
# 11. main()
###############################################################################
def main():
    ensure_json_initialized()
    run_pipeline_loop()
    logger.info("[Main] Keluar.")

if __name__=="__main__":
    main()