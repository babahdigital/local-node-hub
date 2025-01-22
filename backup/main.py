#!/usr/bin/env python3
"""
main.py

Menambahkan logic:
 - Re-try pipeline per-channel jika gagal (mis. fail open).
 - Jika persentase channel mati > FAIL_THRESHOLD%, kita sys.exit(1) => Docker restart.
 - Freeze dan Blackdetect lebih fleksibel (durasi, threshold).
 - Menyertakan logika 'motion' & 'motion_dual' secara lengkap.

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
from threading import Lock

sys.path.append("/app/scripts")

from utils import decode_credentials
from motion_detection import MotionDetector
from backup_manager import BackupSession

######################################################
# 0. Masking / Helper
######################################################
def mask_user_env(user_env: str) -> str:
    return "****" if user_env else user_env

def mask_rtsp_credentials(rtsp_url: str) -> str:
    return re.sub(r"(//)([^:]+):([^@]+)(@)", r"\1****:****\4", rtsp_url)

######################################################
# 1. Logger
######################################################
logger = logging.getLogger("Backup-Manager")
logger.setLevel(logging.DEBUG)

VALIDATION_LOG_PATH = "/mnt/Data/Syslog/rtsp/backup/validation.log"
ERROR_LOG_PATH      = "/mnt/Data/Syslog/rtsp/backup/error_only.log"
EVENT_LOG_PATH      = "/mnt/Data/Syslog/rtsp/backup/event.log"

class FilterValidation(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        if ("[FREEZE]" in msg) or ("[BLACK]" in msg) or ("[VALIDATION]" in msg) or ("RTSP user/pass =>" in msg):
            return True
        return False

class FilterError(logging.Filter):
    def filter(self, record):
        return (record.levelno >= logging.ERROR)

class FilterEvent(logging.Filter):
    def filter(self, record):
        if record.levelno >= logging.ERROR:
            return False
        msg = record.getMessage()
        if ("[FREEZE]" in msg) or ("[BLACK]" in msg) or ("[VALIDATION]" in msg) or ("RTSP user/pass =>" in msg):
            return False
        return True

handler_validation = logging.FileHandler(VALIDATION_LOG_PATH)
handler_validation.setLevel(logging.DEBUG)
handler_validation.addFilter(FilterValidation())
fmt_val = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s","%d-%m-%Y %H:%M:%S")
handler_validation.setFormatter(fmt_val)
logger.addHandler(handler_validation)

handler_error = logging.FileHandler(ERROR_LOG_PATH)
handler_error.setLevel(logging.DEBUG)
handler_error.addFilter(FilterError())
fmt_err = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s","%d-%m-%Y %H:%M:%S")
handler_error.setFormatter(fmt_err)
logger.addHandler(handler_error)

handler_event = logging.FileHandler(EVENT_LOG_PATH)
handler_event.setLevel(logging.DEBUG)
handler_event.addFilter(FilterEvent())
fmt_evt = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s","%d-%m-%Y %H:%M:%S")
handler_event.setFormatter(fmt_evt)
logger.addHandler(handler_event)

######################################################
# 2. Environment Variables
######################################################
BACKUP_MODE  = os.getenv("BACKUP_MODE","full").lower()

ENABLE_FREEZE_CHECK = (os.getenv("ENABLE_FREEZE_CHECK","true").lower()=="true")
ENABLE_BLACKOUT     = (os.getenv("ENABLE_BLACKOUT","true").lower()=="true")
LOOP_ENABLE         = (os.getenv("LOOP_ENABLE","true").lower()=="true")

CHUNK_DURATION = int(os.getenv("CHUNK_DURATION","300"))
MAX_RECORD     = int(os.getenv("MAX_RECORD","300"))
MOTION_TIMEOUT = int(os.getenv("MOTION_TIMEOUT","5"))
POST_MOTION_DELAY = int(os.getenv("POST_MOTION_DELAY","0"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL","60"))
RESTART_DELAY  = int(os.getenv("RESTART_DELAY","30"))

BLACK_DURATION          = float(os.getenv("BLACK_DURATION","1.0"))
BLACK_DETECT_THRESHOLD  = float(os.getenv("BLACK_DETECT_THRESHOLD","0.98"))

FREEZE_DURATION       = float(os.getenv("FREEZE_DURATION","6.0"))
FREEZE_RECHECK_TIMES  = int(os.getenv("FREEZE_RECHECK_TIMES","5"))
FREEZE_RECHECK_DELAY  = float(os.getenv("FREEZE_RECHECK_DELAY","3.0"))
FREEZE_BLACK_INTERVAL = int(os.getenv("FREEZE_BLACK_INTERVAL","0"))

FAIL_THRESHOLD_PCT = float(os.getenv("FAIL_THRESHOLD","50"))

# Parameter penghematan CPU / motion
FRAME_SKIP       = int(os.getenv("FRAME_SKIP","5"))         # skip frame
DOWNSCALE_RATIO  = float(os.getenv("DOWNSCALE_RATIO","0.5"))# scale-down
MOTION_SLEEP     = float(os.getenv("MOTION_SLEEP","0.2"))   # jeda loop motion
MOTION_AREA      = int(os.getenv("MOTION_AREA_THRESHOLD","3000")) # area thresh

validation_lock = Lock()
LAST_CHECK_TIMES = {}

logger.info("[VALIDATION] BACKUP_MODE=%s", BACKUP_MODE)

######################################################
# 3. channel_validation JSON
######################################################
def load_validation_status():
    if not os.path.isfile(VALIDATION_JSON):
        return {}
    try:
        with open(VALIDATION_JSON,"r") as f:
            return json.load(f)
    except:
        logger.warning("Gagal baca %s", VALIDATION_JSON)
        return {}

def save_validation_status(data: dict):
    tmp_path = VALIDATION_JSON + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, VALIDATION_JSON)
    except Exception as e:
        logger.warning("Gagal menulis %s => %s", VALIDATION_JSON, e)

def update_validation_status(channel, info: dict):
    with validation_lock:
        data = load_validation_status()
        cstr = str(channel)
        if cstr not in data:
            data[cstr] = {}
        data[cstr].update(info)
        data[cstr]["last_update"] = datetime.now().isoformat()
        save_validation_status(data)

def get_inactive_count(channels):
    data = load_validation_status()
    cnt = 0
    for c in channels:
        st = data.get(str(c), {})
        if not st.get("is_active", False):
            cnt+=1
    return cnt

def check_restart_if_too_many_fail(channels):
    """
    Jika persentase channel yang is_active=false >= FAIL_THRESHOLD_PCT => sys.exit(1)
    """
    total = len(channels)
    if total<=0:
        return
    inact = get_inactive_count(channels)
    pct   = (inact/total)*100.0
    if pct>= FAIL_THRESHOLD_PCT:
        logger.warning("[Main] %d/%d (%.1f%%) channel inactive >= threshold=%.1f => restart container!",
                       inact, total, pct, FAIL_THRESHOLD_PCT)
        sys.exit(1)

######################################################
# 4. Ensure JSON
######################################################
MONITOR_STATE_FILE = "/mnt/Data/Syslog/resource/resource_monitor_state.json"
def ensure_json_initialized():
    if not os.path.exists(MONITOR_STATE_FILE):
        logger.info("[VALIDATION] File %s belum ada, buat minimal.", MONITOR_STATE_FILE)
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
        logger.info("[VALIDATION] File %s sudah ada, skip init.", MONITOR_STATE_FILE)

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

        user_json = rcfg.get("rtsp_user","admin")
        pass_json = rcfg.get("rtsp_password","admin123")
    except Exception as e:
        logger.warning("[Main] Gagal baca %s => %s", MONITOR_STATE_FILE, e)
        config["cpu_usage"]    = 0.0
        config["stream_title"] = os.getenv("STREAM_TITLE","Untitled")
        config["rtsp_ip"]      = os.getenv("RTSP_IP","127.0.0.1")
        config["rtsp_subtype"] = os.getenv("RTSP_SUBTYPE","0")
        user_json              = os.getenv("RTSP_USER","admin")
        pass_json              = os.getenv("RTSP_PASSWORD","admin123")

    try:
        user_env, pass_env = decode_credentials()
        masked_user = mask_user_env(user_env)
        logger.info("[VALIDATION] RTSP user/pass => %s", masked_user)
        config["rtsp_user"]     = user_env
        config["rtsp_password"] = pass_env
    except:
        config["rtsp_user"]     = user_json
        config["rtsp_password"] = pass_json

    return config

######################################################
# 5. Freeze / Black
######################################################
def check_black_frames(rtsp_url, do_blackout, duration=None, threshold=None):
    """
    duration => blackdetect minimal, default pakai BLACK_DURATION
    threshold => pic_th, default BLACK_DETECT_THRESHOLD
    """
    if not do_blackout:
        return True
    dur = duration if duration else BLACK_DURATION
    thr = threshold if threshold else BLACK_DETECT_THRESHOLD

    cmd = [
        "ffmpeg","-hide_banner","-loglevel","error","-y","-err_detect","ignore_err",
        "-rtsp_transport","tcp","-i",rtsp_url,
        "-vf",f"blackdetect=d={dur}:pic_th={thr}",
        "-an","-t","5","-f","null","-"
    ]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        if b"black_start" in r.stderr:
            logger.info("[BLACK] blackdetect => black_start triggered (pic_th=%.2f, d=%.1f)", thr, dur)
        return (b"black_start" not in r.stderr)
    except Exception as e:
        logger.error("[BLACK] blackdetect error => %s", e)
        return False

def check_freeze_frames(rtsp_url, do_freeze, cpu_usage, freeze_sens=None, times=None, delay=None):
    """
    freeze_sens => freeze minimal durasi => default FREEZE_DURATION
    times => FREEZE_RECHECK_TIMES
    delay => FREEZE_RECHECK_DELAY
    """
    if not do_freeze:
        return True
    if cpu_usage>90:
        logger.info("[FREEZE] CPU>90 => skip freeze-check => treat as freeze_ok=True.")
        return True
    sens = freeze_sens if freeze_sens else FREEZE_DURATION
    tms  = times if times else FREEZE_RECHECK_TIMES
    dly  = delay if delay else FREEZE_RECHECK_DELAY

    fail=0
    for i in range(tms):
        if not _freeze_once(rtsp_url, sens):
            fail+=1
        if i<(tms-1):
            time.sleep(dly)
    return (fail<tms)

def _freeze_once(rtsp_url, freeze_sens):
    cmd = [
        "ffmpeg","-hide_banner","-loglevel","error","-y","-err_detect","ignore_err",
        "-rtsp_transport","tcp","-i",rtsp_url,
        "-vf",f"freezedetect=n=-60dB:d={freeze_sens}",
        "-an","-t","5","-f","null","-"
    ]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        if b"freeze_start" in r.stderr:
            logger.info("[FREEZE] freeze_start triggered (d=%.1f)", freeze_sens)
        return (b"freeze_start" not in r.stderr)
    except Exception as e:
        logger.error("[FREEZE] freezedetect error => %s", e)
        return False

######################################################
# 6. Pipeline Classes
######################################################
class FullBackupSession:
    def __init__(self, rtsp_url, channel, stream_title):
        self.rtsp_url = rtsp_url
        self.channel  = channel
        self.stream_title = stream_title
        self.proc     = None
        self.start_time = None
        self.file_path  = None
        self.active     = False

    def start_chunk(self):
        self.start_time = time.time()
        out_file = self._make_filename()
        self.file_path = out_file
        cmd = [
            "ffmpeg","-hide_banner","-loglevel","error","-y","-err_detect","ignore_err",
            "-rtsp_transport","tcp","-i", self.rtsp_url,
            "-c","copy",
            "-metadata", f"title={self.stream_title}",
            out_file
        ]
        try:
            self.proc = subprocess.Popen(cmd)
            self.active = True
            logger.info("[EVENT] [FullBackup] ch=%s => start => %s", self.channel, out_file)
        except Exception as e:
            logger.error("[FullBackup] start_chunk error => %s", e)

    def _make_filename(self):
        import time, os
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
        elapsed = time.time() - self.start_time
        return (elapsed<chunk_dur)

    def stop_chunk(self):
        if self.active and self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception as e:
                logger.error("[FullBackup] stop_chunk wait error => %s", e)
            logger.info("[EVENT] [FullBackup] ch=%s => stop => %s", self.channel, self.file_path)
            self.proc=None
            self.active=False

class MotionSession:
    def __init__(self, rtsp_url, channel, stream_title):
        self.rtsp_url = rtsp_url
        self.channel  = channel
        self.stream_title = stream_title
        self.proc     = None
        self.start_time = None
        self.file_path  = None
        self.active     = False

    def start_record(self, log_prefix="[MotionSession]"):
        self.start_time = time.time()
        out_file = self._make_filename()
        self.file_path = out_file
        cmd = [
            "ffmpeg","-hide_banner","-loglevel","error","-y","-err_detect","ignore_err",
            "-rtsp_transport","tcp","-i", self.rtsp_url,
            "-c","copy",
            "-metadata", f"title={self.stream_title}-Channel-{self.channel}",
            out_file
        ]
        try:
            self.proc = subprocess.Popen(cmd)
            self.active = True
            logger.info("%s ch=%s => start => %s", log_prefix, self.channel, out_file)
        except Exception as e:
            logger.error("%s ch=%s => start_record error => %s", log_prefix, self.channel, e)

    def _make_filename(self):
        import time, os
        backup_root="/mnt/Data/Backup"
        date_str=time.strftime("%d-%m-%Y")
        time_str=time.strftime("%H-%M-%S")
        ch_folder=f"Channel-{self.channel}"
        final_dir=os.path.join(backup_root,date_str,ch_folder)
        os.makedirs(final_dir, exist_ok=True)
        return os.path.join(final_dir, f"CH{self.channel}-{time_str}.mkv")

    def still_ok(self, max_dur):
        if not self.active or not self.proc:
            return False
        elapsed = time.time()-self.start_time
        return (elapsed<max_dur)

    def stop_record(self):
        if self.active and self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception as e:
                logger.error("[MotionSession] ch=%s => stop_record error => %s", self.channel, e)
            logger.info("[EVENT] [MotionSession] ch=%s => stop => %s", self.channel, self.file_path)
            self.proc=None
            self.active=False

######################################################
# 7. pipeline_xxx
######################################################
def pipeline_full(ch, config, rtsp_url):
    """
    Mode FULL => selalu merekam rolling CHUNK_DURATION
    """
    sess = FullBackupSession(rtsp_url, ch, config["stream_title"])
    while True:
        if not sess.active:
            sess.start_chunk()
        if not sess.still_ok(CHUNK_DURATION):
            sess.stop_chunk()
            sess.start_chunk()
        time.sleep(1)

def pipeline_motion(ch, config, rtsp_url, object_detection=False):
    """
    Mode MOTION => 
     - Baca stream (rtsp_url) 
     - Jika motion => start_record => rolling MAX_RECORD
     - Stop jika idle > MOTION_TIMEOUT + POST_MOTION_DELAY
    """
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        masked_err = f"ch={ch} => fail open => {mask_rtsp_credentials(rtsp_url)}"
        logger.error("[Main] %s", masked_err)
        update_validation_status(ch,{"error_msg": masked_err, "is_active":False})
        raise RuntimeError(masked_err)

    # Motion detection
    motion_det = MotionDetector(area_threshold=MOTION_AREA)  # param area
    obj_det=None
    if object_detection:
        from object_detection import ObjectDetector
        obj_det=ObjectDetector(
            "/app/backup/models/mobilenet_ssd/MobileNetSSD_deploy.prototxt",
            "/app/backup/models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel",
            conf_person=0.6, conf_car=0.4, conf_motor=0.4
        )

    m_sess = MotionSession(rtsp_url, ch, config["stream_title"])
    is_recording = False
    last_motion  = 0
    frame_count  = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(1)
            continue

        # skip frames
        frame_count += 1
        if frame_count % FRAME_SKIP != 0:
            time.sleep(MOTION_SLEEP)
            continue

        # downscale
        if DOWNSCALE_RATIO<1.0:
            try:
                new_w = int(frame.shape[1]*DOWNSCALE_RATIO)
                new_h = int(frame.shape[0]*DOWNSCALE_RATIO)
                frame_small = cv2.resize(frame,(new_w,new_h), interpolation=cv2.INTER_AREA)
            except:
                frame_small=frame
        else:
            frame_small=frame

        # deteksi motion
        bboxes = motion_det.detect(frame_small)
        if bboxes:
            # jika object_detection => cek 'person'
            if obj_det:
                results,_ = obj_det.detect(frame_small)
                person_found = any(r[0]=="person" for r in results)
                if not person_found:
                    # skip record
                    time.sleep(MOTION_SLEEP)
                    continue

            last_motion = time.time()
            if not is_recording:
                # start record
                m_sess.start_record(log_prefix="[MotionSession]")
                is_recording = True
            else:
                # rolling
                if not m_sess.still_ok(MAX_RECORD):
                    m_sess.stop_record()
                    m_sess.start_record(log_prefix="[MotionSession]")
        else:
            # no motion => stop if idle
            if is_recording:
                idle_sec = time.time() - last_motion
                if idle_sec> (MOTION_TIMEOUT + POST_MOTION_DELAY):
                    m_sess.stop_record()
                    is_recording=False

        time.sleep(MOTION_SLEEP)

def pipeline_motion_dual(ch, config, main_url, with_object=False):
    """
    Mode MOTION_DUAL => 
     - Analisis motion di sub-stream (channel=?&subtype=1)
     - Jika motion => rekam main_url => rolling MAX_RECORD
     - Stop jika idle > MOTION_TIMEOUT + POST_MOTION_DELAY
    """
    user = config["rtsp_user"]
    pwd  = config["rtsp_password"]
    ip   = config["rtsp_ip"]
    sub_url = f"rtsp://{user}:{pwd}@{ip}:554/cam/realmonitor?channel={ch}&subtype=1"
    masked_sub = mask_rtsp_credentials(sub_url)
    logger.info("[EVENT] [DualStream] ch=%s => sub=%s", ch, masked_sub)

    cap_sub = cv2.VideoCapture(sub_url)
    if not cap_sub.isOpened():
        masked_err = f"ch={ch} => fail open sub => {masked_sub}"
        logger.error("[DualStream] %s", masked_err)
        update_validation_status(ch, {"error_msg": masked_err, "is_active":False})
        raise RuntimeError(masked_err)

    motion_det = MotionDetector(area_threshold=MOTION_AREA)
    obj_det=None
    if with_object:
        from object_detection import ObjectDetector
        obj_det=ObjectDetector(
            "/app/backup/models/mobilenet_ssd/MobileNetSSD_deploy.prototxt",
            "/app/backup/models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel",
            conf_person=0.6, conf_car=0.4, conf_motor=0.4
        )

    # rekam main_url
    m_sess = MotionSession(main_url, ch, config["stream_title"])
    is_recording = False
    last_motion  = 0
    frame_count  = 0

    while True:
        ret, frame = cap_sub.read()
        if not ret or frame is None:
            time.sleep(1)
            continue

        frame_count+=1
        if frame_count % FRAME_SKIP !=0:
            time.sleep(MOTION_SLEEP)
            continue

        # downscale
        if DOWNSCALE_RATIO<1.0:
            try:
                new_w=int(frame.shape[1]*DOWNSCALE_RATIO)
                new_h=int(frame.shape[0]*DOWNSCALE_RATIO)
                frame_small=cv2.resize(frame,(new_w,new_h), interpolation=cv2.INTER_AREA)
            except:
                frame_small=frame
        else:
            frame_small=frame

        # deteksi motion sub-stream
        bboxes = motion_det.detect(frame_small)
        if bboxes:
            # optional object detection
            if with_object and obj_det:
                results,_=obj_det.detect(frame_small)
                person_found=any(r[0]=="person" for r in results)
                if not person_found:
                    time.sleep(MOTION_SLEEP)
                    continue

            last_motion=time.time()
            if not is_recording:
                prefix="[MotionDual]" if not with_object else "[MotionObjDual]"
                m_sess.start_record(log_prefix=prefix)
                is_recording=True
            else:
                # rolling
                if not m_sess.still_ok(MAX_RECORD):
                    m_sess.stop_record()
                    prefix="[MotionDual]" if not with_object else "[MotionObjDual]"
                    m_sess.start_record(log_prefix=prefix)
        else:
            # no motion => stop if idle
            if is_recording:
                idle_sec = time.time()-last_motion
                if idle_sec> (MOTION_TIMEOUT+POST_MOTION_DELAY):
                    m_sess.stop_record()
                    is_recording=False

        time.sleep(MOTION_SLEEP)

######################################################
# 8. Thread for Channel w/ re-try + check fail
######################################################
def thread_for_channel(ch, config):
    test_ch    = os.getenv("TEST_CHANNEL","off").lower()
    chan_count = int(os.getenv("CHANNEL_COUNT","1"))
    if test_ch=="off":
        channels = list(range(1, chan_count+1))
    else:
        channels = [int(x.strip()) for x in test_ch.split(",") if x.strip().isdigit()]

    while True:
        # set is_active=false
        update_validation_status(ch, {"is_active": False})

        user    = config["rtsp_user"]
        pwd     = config["rtsp_password"]
        ip      = config["rtsp_ip"]
        subtype = config["rtsp_subtype"]
        raw_url = f"rtsp://{user}:{pwd}@{ip}:554/cam/realmonitor?channel={ch}&subtype={subtype}"
        masked_url = mask_rtsp_credentials(raw_url)
        logger.info("[EVENT] [Main] ch=%s => %s", ch, masked_url)

        cpu_usage = config["cpu_usage"]
        do_black  = ENABLE_BLACKOUT
        do_freeze = ENABLE_FREEZE_CHECK

        now = time.time()
        last_chk = LAST_CHECK_TIMES.get(ch,0)
        interval = now - last_chk
        if FREEZE_BLACK_INTERVAL>0 and interval < FREEZE_BLACK_INTERVAL:
            ok_black  = True
            ok_freeze = True
            logger.info("[VALIDATION] ch=%s => skip freeze/black => interval=%.1f < %d",
                        ch, interval, FREEZE_BLACK_INTERVAL)
        else:
            LAST_CHECK_TIMES[ch] = now
            # CPU check
            if cpu_usage>90:
                do_black=False
                logger.info("[VALIDATION] ch=%s => CPU>90 => skip blackdetect", ch)

            # black
            ok_black = check_black_frames(raw_url, do_black,
                                          duration=BLACK_DURATION,
                                          threshold=BLACK_DETECT_THRESHOLD)
            if not ok_black:
                masked_err = f"ch={ch} => black => skip => {masked_url}"
                logger.warning("[VALIDATION] %s", masked_err)
                update_validation_status(ch, {
                    "freeze_ok": None,
                    "black_ok": False,
                    "livestream_link": masked_url,
                    "error_msg": masked_err,
                    "is_active": False
                })
                check_restart_if_too_many_fail(channels)
                time.sleep(RESTART_DELAY)
                continue

            # freeze
            if do_freeze:
                ok_freeze = check_freeze_frames(raw_url, True, cpu_usage,
                                                freeze_sens=FREEZE_DURATION,
                                                times=FREEZE_RECHECK_TIMES,
                                                delay=FREEZE_RECHECK_DELAY)
                if not ok_freeze:
                    masked_err = f"ch={ch} => freeze => skip => {masked_url}"
                    logger.warning("[VALIDATION] %s", masked_err)
                    update_validation_status(ch, {
                        "freeze_ok": False,
                        "black_ok":  ok_black,
                        "livestream_link": masked_url,
                        "error_msg": masked_err,
                        "is_active": False
                    })
                    check_restart_if_too_many_fail(channels)
                    time.sleep(RESTART_DELAY)
                    continue
            else:
                ok_freeze = True

        # freeze/black pass => is_active=true
        update_validation_status(ch, {
            "freeze_ok": ok_freeze,
            "black_ok":  ok_black,
            "livestream_link": masked_url,
            "error_msg": None,
            "is_active": True
        })

        # pipeline
        try:
            if   BACKUP_MODE=="full":
                pipeline_full(ch, config, raw_url)
            elif BACKUP_MODE=="motion":
                pipeline_motion(ch, config, raw_url, object_detection=False)
            elif BACKUP_MODE=="motion_obj":
                pipeline_motion(ch, config, raw_url, object_detection=True)
            elif BACKUP_MODE=="motion_dual":
                pipeline_motion_dual(ch, config, raw_url, with_object=False)
            elif BACKUP_MODE=="motion_obj_dual":
                pipeline_motion_dual(ch, config, raw_url, with_object=True)
            else:
                logger.warning("[VALIDATION] BACKUP_MODE=%s unknown => fallback full", BACKUP_MODE)
                pipeline_full(ch, config, raw_url)
        except Exception as e:
            logger.error("[Main] pipeline error ch=%s => %s", ch, e)

        update_validation_status(ch, {"is_active": False})
        logger.info("[VALIDATION] ch=%s => pipeline exit => re-try in %ds", ch, RESTART_DELAY)

        check_restart_if_too_many_fail(channels)
        time.sleep(RESTART_DELAY)

######################################################
# 9. run_pipeline_loop
######################################################
def run_pipeline_loop():
    test_ch    = os.getenv("TEST_CHANNEL","off").lower()
    chan_count = int(os.getenv("CHANNEL_COUNT","1"))

    if test_ch=="off":
        channels = [i for i in range(1, chan_count+1)]
    else:
        channels = [int(x.strip()) for x in test_ch.split(",") if x.strip().isdigit()]

    config = load_resource_config()

    for c in channels:
        t = threading.Thread(target=thread_for_channel, args=(c,config), daemon=True)
        t.start()

    while LOOP_ENABLE:
        logger.info("[EVENT] [Main] pipeline threads running => sleep %d sec", CHECK_INTERVAL)
        time.sleep(CHECK_INTERVAL)
        # Opsi: reload config setiap loop
        # config = load_resource_config()

    logger.info("[EVENT] [Main] LOOP_ENABLE=false => exit main loop")

def main():
    ensure_json_initialized()
    run_pipeline_loop()
    logger.info("[EVENT] [Main] Keluar.")

if __name__=="__main__":
    main()