#!/usr/bin/env python3
"""
main.py

Memperluas pipeline menjadi lima mode perekaman:
1) FULL => merekam terus (rolling CHUNK_DURATION).
2) MOTION => merekam saat motion (single-stream), rolling MAX_RECORD.
3) MOTION_OBJ => merekam saat motion + object (single-stream).
4) MOTION_DUAL => analisis sub-stream (tanpa object detection), rekam main-stream.
5) MOTION_OBJ_DUAL => analisis sub-stream (dengan object detection), rekam main-stream.

Tidak ada perpindahan otomatis. Anda tentukan mode via BACKUP_MODE={full|motion|motion_obj|motion_dual|motion_obj_dual}.

Freeze/Black check tetap dilakukan sebelum pipeline.
Author: YourName
"""

import os
import sys
import time
import json
import threading
import subprocess
import cv2
import re
from datetime import datetime
import logging
from threading import Lock  # <--- Tambahkan Lock

# Pastikan folder scripts ada di PATH
sys.path.append("/app/scripts")

from utils import setup_logger, decode_credentials
from motion_detection import MotionDetector
from backup_manager import BackupSession

############################
# Fungsi Masking / Helper
############################
def mask_user_env(user_env: str) -> str:
    """Mask user_env jadi '****'."""
    if user_env:
        return "****"
    return user_env

def mask_rtsp_credentials(rtsp_url: str) -> str:
    """
    Contoh: 'rtsp://user:pass@host...' => 'rtsp://****:****@host...'
    """
    return re.sub(r"(//)([^:]+):([^@]+)(@)", r"\1****:****\4", rtsp_url)

############################
# Buat logger global
############################
logger = logging.getLogger("Backup-Manager")
logger.setLevel(logging.DEBUG)

# 1) Handler Validation => validation.log
VALIDATION_LOG_PATH = "/mnt/Data/Syslog/rtsp/backup/validation.log"
handler_validation = logging.FileHandler(VALIDATION_LOG_PATH)
handler_validation.setLevel(logging.DEBUG)

class FilterValidation(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        # Kita tandai freeze, black, user/pass dsb
        if ("[FREEZE]" in msg) or ("[BLACK]" in msg) or ("[VALIDATION]" in msg) or ("RTSP user/pass =>" in msg):
            return True
        return False

handler_validation.addFilter(FilterValidation())
fmt_val = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s","%d-%m-%Y %H:%M:%S")
handler_validation.setFormatter(fmt_val)
logger.addHandler(handler_validation)

# 2) Handler Error => error_only.log
ERROR_LOG_PATH = "/mnt/Data/Syslog/rtsp/backup/error_only.log"
handler_error = logging.FileHandler(ERROR_LOG_PATH)
handler_error.setLevel(logging.DEBUG)

class FilterError(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return (record.levelno >= logging.ERROR)

handler_error.addFilter(FilterError())
fmt_err = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s","%d-%m-%Y %H:%M:%S")
handler_error.setFormatter(fmt_err)
logger.addHandler(handler_error)

# 3) Handler Event => event.log
EVENT_LOG_PATH = "/mnt/Data/Syslog/rtsp/backup/event.log"
handler_event = logging.FileHandler(EVENT_LOG_PATH)
handler_event.setLevel(logging.DEBUG)

class FilterEvent(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Bukan ERROR dan bukan validasi
        if record.levelno >= logging.ERROR:
            return False
        msg = record.getMessage()
        if ("[FREEZE]" in msg) or ("[BLACK]" in msg) or ("[VALIDATION]" in msg) or ("RTSP user/pass =>" in msg):
            return False
        return True

handler_event.addFilter(FilterEvent())
fmt_evt = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s","%d-%m-%Y %H:%M:%S")
handler_event.setFormatter(fmt_evt)
logger.addHandler(handler_event)

############################
# Baca ENV / Konfig
############################
BACKUP_MODE = os.getenv("BACKUP_MODE","full").lower()

ENABLE_FREEZE_CHECK = os.getenv("ENABLE_FREEZE_CHECK","true").lower()=="true"
ENABLE_BLACKOUT     = os.getenv("ENABLE_BLACKOUT","true").lower()=="true"
LOOP_ENABLE         = os.getenv("LOOP_ENABLE","true").lower()=="true"

CHUNK_DURATION = int(os.getenv("CHUNK_DURATION","300"))  # potongan full
MAX_RECORD     = int(os.getenv("MAX_RECORD","300"))      # potongan motion
MOTION_TIMEOUT = int(os.getenv("MOTION_TIMEOUT","5"))
POST_MOTION_DELAY = int(os.getenv("POST_MOTION_DELAY","0"))  # after last motion
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL","300"))

BLACK_DETECT_THRESHOLD = float(os.getenv("BLACK_DETECT_THRESHOLD","0.98"))
FREEZE_SENSITIVITY     = float(os.getenv("FREEZE_SENSITIVITY","6.0"))
FREEZE_RECHECK_TIMES   = int(os.getenv("FREEZE_RECHECK_TIMES","5"))
FREEZE_RECHECK_DELAY   = float(os.getenv("FREEZE_RECHECK_DELAY","3.0"))

FREEZE_BLACK_INTERVAL  = int(os.getenv("FREEZE_BLACK_INTERVAL","0"))  # skip interval check

MONITOR_STATE_FILE  = "/mnt/Data/Syslog/resource/resource_monitor_state.json"
VALIDATION_JSON     = "/mnt/Data/Syslog/rtsp/channel_validation.json"

# Tambahkan lock global:
validation_lock = Lock()

MOTION_EVENTS_JSON  = "/mnt/Data/Syslog/rtsp/motion_events.json"

LAST_CHECK_TIMES = {}

logger.info("[VALIDATION] BACKUP_MODE=%s" % BACKUP_MODE)

############################
# 1) Validasi JSON
############################
def load_validation_status():
    if not os.path.isfile(VALIDATION_JSON):
        return {}
    try:
        with open(VALIDATION_JSON, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Gagal baca {VALIDATION_JSON} => {e}")
        return {}

def save_validation_status(data: dict):
    # Safe write => file .tmp, lalu os.replace => hindari JSON corrupt
    tmp_path = VALIDATION_JSON + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, VALIDATION_JSON)
    except Exception as e:
        logger.warning(f"Gagal menulis {VALIDATION_JSON} => {e}")

def update_validation_status(channel, info: dict):
    # Pastikan concurrency => lock
    with validation_lock:
        data = load_validation_status()
        ch_str = str(channel)
        if ch_str not in data:
            data[ch_str] = {}
        data[ch_str].update(info)
        data[ch_str]["last_update"] = datetime.now().isoformat()
        save_validation_status(data)

############################
# 2) Inisialisasi JSON
############################
def ensure_json_initialized():
    if not os.path.exists(MONITOR_STATE_FILE):
        logger.info("[VALIDATION] File %s belum ada, buat minimal." % MONITOR_STATE_FILE)
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
        logger.info("[VALIDATION] File %s sudah ada, skip init." % MONITOR_STATE_FILE)

############################
# 3) Load Resource+Config
############################
def load_resource_config():
    config={}
    try:
        with open(MONITOR_STATE_FILE,"r") as f:
            j=json.load(f)
        usage = j.get("resource_usage",{}).get("cpu",{}).get("usage_percent",0.0)
        config["cpu_usage"] = float(usage)

        scfg=j.get("stream_config",{})
        config["stream_title"] = scfg.get("stream_title","Untitled")
        config["rtsp_ip"]      = scfg.get("rtsp_ip","127.0.0.1")

        rcfg=j.get("rtsp_config",{})
        config["rtsp_subtype"] = rcfg.get("rtsp_subtype","0")

        user_json =rcfg.get("rtsp_user","admin")
        pass_json =rcfg.get("rtsp_password","admin123")
    except Exception as e:
        logger.warning("[Main] Gagal baca %s => %s" % (MONITOR_STATE_FILE, e))
        config["cpu_usage"]    = 0.0
        config["stream_title"] = os.getenv("STREAM_TITLE","Untitled")
        config["rtsp_ip"]      = os.getenv("RTSP_IP","127.0.0.1")
        config["rtsp_subtype"] = os.getenv("RTSP_SUBTYPE","0")
        user_json              = os.getenv("RTSP_USER","admin")
        pass_json              = os.getenv("RTSP_PASSWORD","admin123")

    # decode credentials
    try:
        user_env, pass_env = decode_credentials()
        masked_user = mask_user_env(user_env)
        logger.info("[VALIDATION] RTSP user/pass => %s" % masked_user)
        config["rtsp_user"]     = user_env
        config["rtsp_password"] = pass_env
    except:
        config["rtsp_user"]     = user_json
        config["rtsp_password"] = pass_json

    return config

############################
# 4) Freeze & Black
############################
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
        r=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        if b"black_start" in r.stderr:
            logger.info("[BLACK] blackdetect => black_start triggered")
        return (b"black_start" not in r.stderr)
    except Exception as e:
        logger.error("[BLACK] blackdetect error => %s" % e)
        return False

def check_freeze_frames(rtsp_url, do_freeze, cpu_usage, freeze_sens=6.0, times=5, delay=3.0):
    if not do_freeze:
        return True
    if cpu_usage>85:
        logger.info("[FREEZE] CPU>85 => skip freeze-check.")
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
        r=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        if b"freeze_start" in r.stderr:
            logger.info("[FREEZE] freeze_start triggered")
        return (b"freeze_start" not in r.stderr)
    except Exception as e:
        logger.error("[FREEZE] freezedetect error => %s" % e)
        return False

############################
# 5) FULL Backup
############################
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
        import time, os
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
        try:
            self.proc=subprocess.Popen(cmd)
            self.active=True
            logger.info("[EVENT] [FullBackup] ch=%s => start => %s" % (self.channel, out_file))
        except Exception as e:
            logger.error("[FullBackup] start_chunk error => %s" % e)

    def _make_filename(self):
        import time,os
        backup_root="/mnt/Data/Backup"
        date_str=time.strftime("%d-%m-%Y")
        time_str=time.strftime("%H-%M-%S")
        ch_folder=f"Channel-{self.channel}"
        final_dir=os.path.join(backup_root,date_str,ch_folder)
        os.makedirs(final_dir, exist_ok=True)
        return os.path.join(final_dir, f"CH{self.channel}-{time_str}.mkv")

    def still_ok(self, chunk_dur):
        if not self.active or not self.proc:
            return False
        import time
        elapsed=time.time()-self.start_time
        return (elapsed<chunk_dur)

    def stop_chunk(self):
        if self.active and self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception as e:
                logger.error("[FullBackup] stop_chunk wait error => %s" % e)
            logger.info("[EVENT] [FullBackup] ch=%s => stop => %s" % (self.channel, self.file_path))
            self.proc=None
            self.active=False

############################
# 6) Motion Session
############################
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
            "-metadata",f"title={self.stream_title}-Channel-{self.channel}",
            out_file
        ]
        try:
            self.proc=subprocess.Popen(cmd)
            self.active=True
            logger.info("[EVENT] %s ch=%s => start => %s" % (log_prefix, self.channel, out_file))
        except Exception as e:
            logger.error("%s ch=%s => start_record error => %s" % (log_prefix, self.channel, e))

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
        elapsed = time.time()-self.start_time
        return (elapsed<max_dur)

    def stop_record(self):
        if self.active and self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception as e:
                logger.error("[MotionSession] ch=%s => stop_record error => %s" % (self.channel, e))
            logger.info("[EVENT] [MotionSession] ch=%s => stop => %s" % (self.channel, self.file_path))
            self.proc=None
            self.active=False

############################
# 7) thread_for_channel
############################
def thread_for_channel(ch, config):
    cpu_usage = config["cpu_usage"]
    do_black  = ENABLE_BLACKOUT
    do_freeze = ENABLE_FREEZE_CHECK

    user    = config["rtsp_user"]
    pwd     = config["rtsp_password"]
    ip      = config["rtsp_ip"]
    subtype = config["rtsp_subtype"]
    raw_url = f"rtsp://{user}:{pwd}@{ip}:554/cam/realmonitor?channel={ch}&subtype={subtype}"
    masked_url = mask_rtsp_credentials(raw_url)
    logger.info("[EVENT] [Main] ch=%s => %s" % (ch, masked_url))

    global LAST_CHECK_TIMES, FREEZE_BLACK_INTERVAL
    now = time.time()
    last_chk = LAST_CHECK_TIMES.get(ch,0)
    interval = now - last_chk

    if FREEZE_BLACK_INTERVAL>0 and interval < FREEZE_BLACK_INTERVAL:
        ok_black  = True
        ok_freeze = True
        logger.info("[VALIDATION] ch=%s => skip freeze/black check (recently checked) " % ch)
    else:
        LAST_CHECK_TIMES[ch] = now
        if cpu_usage>90:
            do_black=False
            logger.info("[VALIDATION] ch=%s => CPU>90 => skip blackdetect" % ch)
        ok_black = check_black_frames(raw_url, do_black, threshold=BLACK_DETECT_THRESHOLD)
        if not ok_black:
            err = "ch=%s => black => skip pipeline" % ch
            logger.warning("[VALIDATION] %s" % err)
            update_validation_status(ch,{
                "freeze_ok":None,
                "black_ok":False,
                "livestream_link":raw_url,
                "error_msg":err
            })
            return

        if do_freeze:
            ok_freeze = check_freeze_frames(raw_url, True, cpu_usage,
                                            freeze_sens=FREEZE_SENSITIVITY,
                                            times=FREEZE_RECHECK_TIMES,
                                            delay=FREEZE_RECHECK_DELAY)
            if not ok_freeze:
                err="ch=%s => freeze => skip pipeline" % ch
                logger.warning("[VALIDATION] %s" % err)
                update_validation_status(ch,{
                    "freeze_ok":False,
                    "black_ok":ok_black,
                    "livestream_link":raw_url,
                    "error_msg":err
                })
                return
        else:
            ok_freeze=True

    update_validation_status(ch,{
        "freeze_ok":ok_freeze,
        "black_ok":ok_black,
        "livestream_link":raw_url,
        "error_msg":None
    })

    mode = BACKUP_MODE
    if mode=="full":
        pipeline_full(ch, config, raw_url)
    elif mode=="motion":
        pipeline_motion(ch, config, raw_url, object_detection=False)
    elif mode=="motion_obj":
        pipeline_motion(ch, config, raw_url, object_detection=True)
    elif mode=="motion_dual":
        pipeline_motion_dual(ch, config, raw_url, with_object=False)
    elif mode=="motion_obj_dual":
        pipeline_motion_dual(ch, config, raw_url, with_object=True)
    else:
        logger.warning("[VALIDATION] BACKUP_MODE=%s unknown => fallback full" % mode)
        pipeline_full(ch, config, raw_url)

############################
# 8) pipeline_full
############################
def pipeline_full(ch, config, rtsp_url):
    sess = FullBackupSession(rtsp_url, ch, config["stream_title"])
    while True:
        if not sess.active:
            sess.start_chunk()
        if not sess.still_ok(CHUNK_DURATION):
            sess.stop_chunk()
            sess.start_chunk()
        time.sleep(1)

############################
# 9) pipeline_motion
############################
def pipeline_motion(ch, config, rtsp_url, object_detection=False):
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        err="ch=%s => fail open => %s" % (ch, rtsp_url)
        logger.error("[Main] %s" % err)
        update_validation_status(ch,{"error_msg":err})
        return

    motion_det = MotionDetector(area_threshold=3000)

    obj_det=None
    if object_detection:
        from object_detection import ObjectDetector
        obj_det=ObjectDetector(
            "/app/backup/models/mobilenet_ssd/MobileNetSSD_deploy.prototxt",
            "/app/backup/models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel",
            conf_person=0.6, conf_car=0.4, conf_motor=0.4
        )

    m_sess = MotionSession(rtsp_url, ch, config["stream_title"])
    last_motion=0
    is_recording=False

    FRAME_SKIP      = int(os.getenv("FRAME_SKIP","5"))
    DOWNSCALE_RATIO = float(os.getenv("DOWNSCALE_RATIO","0.5"))
    SLEEP_INTERVAL  = float(os.getenv("MOTION_SLEEP","0.2"))

    while True:
        ret, frame=cap.read()
        if not ret or frame is None:
            time.sleep(1)
            continue

        # Skipped detail for brevity

        time.sleep(0.2)

############################
# 10) pipeline_motion_dual
############################
def pipeline_motion_dual(ch, config, main_url, with_object=False):
    user = config["rtsp_user"]
    pwd  = config["rtsp_password"]
    ip   = config["rtsp_ip"]

    sub_url = f"rtsp://{user}:{pwd}@{ip}:554/cam/realmonitor?channel={ch}&subtype=1"
    logger.info("[EVENT] [DualStream] ch=%s => sub-stream => %s" % (ch, mask_rtsp_credentials(sub_url)))

    cap_sub = cv2.VideoCapture(sub_url)
    if not cap_sub.isOpened():
        err = "ch=%s => fail open sub-stream => %s" % (ch, sub_url)
        logger.error("[DualStream] %s" % err)
        update_validation_status(ch,{"error_msg":err})
        return

    motion_det = MotionDetector(area_threshold=3000)
    obj_det = None
    if with_object:
        from object_detection import ObjectDetector
        obj_det = ObjectDetector(
            "/app/backup/models/mobilenet_ssd/MobileNetSSD_deploy.prototxt",
            "/app/backup/models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel",
            conf_person=0.6, conf_car=0.4, conf_motor=0.4
        )

    m_sess = MotionSession(main_url, ch, config["stream_title"])
    last_motion=0
    is_recording=False

    FRAME_SKIP      = int(os.getenv("FRAME_SKIP","5"))
    DOWNSCALE_RATIO = float(os.getenv("DOWNSCALE_RATIO","0.5"))
    SLEEP_INTERVAL  = float(os.getenv("MOTION_SLEEP","0.2"))

    global MOTION_TIMEOUT, POST_MOTION_DELAY, MAX_RECORD
    fcount=0

    while True:
        ret, frame=cap_sub.read()
        if not ret or frame is None:
            time.sleep(1)
            continue

        fcount+=1
        if fcount % FRAME_SKIP !=0:
            time.sleep(SLEEP_INTERVAL)
            continue

        if DOWNSCALE_RATIO<1.0:
            try:
                new_w = int(frame.shape[1]*DOWNSCALE_RATIO)
                new_h = int(frame.shape[0]*DOWNSCALE_RATIO)
                frame_small = cv2.resize(frame,(new_w,new_h), interpolation=cv2.INTER_AREA)
            except:
                frame_small=frame
        else:
            frame_small=frame

        bboxes = motion_det.detect(frame_small)
        if bboxes:
            if with_object and obj_det:
                results,_=obj_det.detect(frame_small)
                person_found=any(r[0]=="person" for r in results)
                if not person_found:
                    time.sleep(SLEEP_INTERVAL)
                    continue

            last_motion=time.time()
            if not is_recording:
                prefix="[MotionDual]" if not with_object else "[MotionObjDual]"
                m_sess.start_record(log_prefix=prefix)
                is_recording=True
            else:
                if not m_sess.still_ok(MAX_RECORD):
                    m_sess.stop_record()
                    prefix="[MotionDual]" if not with_object else "[MotionObjDual]"
                    m_sess.start_record(log_prefix=prefix)
        else:
            if is_recording:
                idle_sec=time.time()-last_motion
                if idle_sec>(MOTION_TIMEOUT+POST_MOTION_DELAY):
                    m_sess.stop_record()
                    is_recording=False

        time.sleep(SLEEP_INTERVAL)

############################
# 11) run_pipeline_loop
############################
def run_pipeline_loop():
    test_ch    = os.getenv("TEST_CHANNEL","off").lower()
    chan_count = int(os.getenv("CHANNEL_COUNT","1"))

    while True:
        cfg = load_resource_config()

        if test_ch=="off":
            channels = [str(i) for i in range(1, chan_count+1)]
        else:
            channels = [x.strip() for x in test_ch.split(",") if x.strip()]

        logger.info("[EVENT] [Main] Start pipeline => mode=%s => channels=%s" % (BACKUP_MODE, channels))
        for c in channels:
            t = threading.Thread(target=thread_for_channel, args=(c,cfg), daemon=True)
            t.start()

        if not LOOP_ENABLE:
            logger.info("[EVENT] [Main] LOOP_ENABLE=false => run 1x => break.")
            break

        logger.info("[EVENT] [Main] Selesai 1 putaran => tunggu %d detik." % CHECK_INTERVAL)
        time.sleep(CHECK_INTERVAL)

############################
# 12) main
############################
def main():
    ensure_json_initialized()
    run_pipeline_loop()
    logger.info("[EVENT] [Main] Keluar.")

if __name__=="__main__":
    main()