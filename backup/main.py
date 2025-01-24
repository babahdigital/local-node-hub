#!/usr/bin/env python3
"""
main.py

Menambahkan logic:
 - Re-try pipeline per-channel jika gagal (fail open, black, freeze).
 - Jika persentase channel mati > FAIL_THRESHOLD%, sys.exit(1) => Docker restart.
 - Freeze & Blackdetect pakai param durasi, threshold dari ENV.
 - Mendukung mode 'motion_dual' dgn analisis sub-stream, rekam main-stream, 
   dan (opsional) black/freeze juga di sub-stream agar lebih ringan.

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

# Pastikan folder scripts ada di PATH
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
    # Sembunyikan user & password
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
        # Event log menampung info-level. Freeze/Black/Validation dialihkan ke validation.log
        if record.levelno >= logging.ERROR:
            return False
        msg = record.getMessage()
        if ("[FREEZE]" in msg) or ("[BLACK]" in msg) or ("[VALIDATION]" in msg) or ("RTSP user/pass =>" in msg):
            return False
        return True

handler_validation = logging.FileHandler(VALIDATION_LOG_PATH)
handler_validation.setLevel(logging.DEBUG)
handler_validation.addFilter(FilterValidation())
fmt_val = logging.Formatter(
    "%(asctime)s [%(levelname)s] [%(name)s] %(message)s", "%d-%m-%Y %H:%M:%S"
)
handler_validation.setFormatter(fmt_val)
logger.addHandler(handler_validation)

handler_error = logging.FileHandler(ERROR_LOG_PATH)
handler_error.setLevel(logging.DEBUG)
handler_error.addFilter(FilterError())
fmt_err = logging.Formatter(
    "%(asctime)s [%(levelname)s] [%(name)s] %(message)s", "%d-%m-%Y %H:%M:%S"
)
handler_error.setFormatter(fmt_err)
logger.addHandler(handler_error)

handler_event = logging.FileHandler(EVENT_LOG_PATH)
handler_event.setLevel(logging.DEBUG)
handler_event.addFilter(FilterEvent())
fmt_evt = logging.Formatter(
    "%(asctime)s [%(levelname)s] [%(name)s] %(message)s", "%d-%m-%Y %H:%M:%S"
)
handler_event.setFormatter(fmt_evt)
logger.addHandler(handler_event)


######################################################
# 2. Environment
######################################################
BACKUP_MODE  = os.getenv("BACKUP_MODE","full").lower()

ENABLE_FREEZE_CHECK = (os.getenv("ENABLE_FREEZE_CHECK","true").lower()=="true")
ENABLE_BLACKOUT     = (os.getenv("ENABLE_BLACKOUT","true").lower()=="true")
LOOP_ENABLE         = (os.getenv("LOOP_ENABLE","true").lower()=="true")

CHUNK_DURATION      = int(os.getenv("CHUNK_DURATION","300"))
MAX_RECORD          = int(os.getenv("MAX_RECORD","300"))
MOTION_TIMEOUT      = int(os.getenv("MOTION_TIMEOUT","5"))
POST_MOTION_DELAY   = int(os.getenv("POST_MOTION_DELAY","0"))
CHECK_INTERVAL      = int(os.getenv("CHECK_INTERVAL","60"))
RESTART_DELAY       = int(os.getenv("RESTART_DELAY","30"))

BLACK_DURATION          = float(os.getenv("BLACK_DURATION","1.0"))
BLACK_DETECT_THRESHOLD  = float(os.getenv("BLACK_DETECT_THRESHOLD","0.98"))

FREEZE_DURATION       = float(os.getenv("FREEZE_DURATION","6.0"))
FREEZE_RECHECK_TIMES  = int(os.getenv("FREEZE_RECHECK_TIMES","5"))
FREEZE_RECHECK_DELAY  = float(os.getenv("FREEZE_RECHECK_DELAY","3.0"))
FREEZE_BLACK_INTERVAL = int(os.getenv("FREEZE_BLACK_INTERVAL","0"))

FAIL_THRESHOLD_PCT = float(os.getenv("FAIL_THRESHOLD","50"))

# Penghematan CPU / motion
FRAME_SKIP       = int(os.getenv("FRAME_SKIP","5"))
DOWNSCALE_RATIO  = float(os.getenv("DOWNSCALE_RATIO","0.5"))
MOTION_SLEEP     = float(os.getenv("MOTION_SLEEP","0.2"))
MOTION_AREA      = int(os.getenv("MOTION_AREA_THRESHOLD","3000"))

# Interval re-check freeze/black + update JSON
IN_PIPELINE_UPDATE_INTERVAL = int(os.getenv("IN_PIPELINE_UPDATE_INTERVAL", "10"))

logger.info("[VALIDATION] BACKUP_MODE=%s", BACKUP_MODE)


######################################################
# 3. channel_validation JSON
######################################################
VALIDATION_JSON = "/mnt/Data/Syslog/rtsp/channel_validation.json"
validation_lock = Lock()

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
            cnt += 1
    return cnt

def check_restart_if_too_many_fail(channels):
    """
    Jika persentase channel yang is_active=false >= FAIL_THRESHOLD_PCT => sys.exit(1)
    """
    total = len(channels)
    if total <= 0:
        return
    inact = get_inactive_count(channels)
    pct   = (inact / total) * 100.0
    if pct >= FAIL_THRESHOLD_PCT:
        logger.warning("[Main] %d/%d (%.1f%%) channel inactive >= threshold=%.1f => restart container!",
                       inact, total, pct, FAIL_THRESHOLD_PCT)
        sys.exit(1)


######################################################
# 4. Pastikan JSON resource
######################################################
MONITOR_STATE_FILE = "/mnt/Data/Syslog/resource/resource_monitor_state.json"

def ensure_json_initialized():
    if not os.path.exists(MONITOR_STATE_FILE):
        logger.info("[VALIDATION] File %s belum ada, buat minimal.", MONITOR_STATE_FILE)
        scfg = {
            "stream_title": os.getenv("STREAM_TITLE","Untitled"),
            "rtsp_ip":      os.getenv("RTSP_IP","127.0.0.1")
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
    config = {}
    try:
        with open(MONITOR_STATE_FILE,"r") as f:
            j = json.load(f)
        usage = j.get("resource_usage",{}).get("cpu",{}).get("usage_percent",0.0)
        config["cpu_usage"] = float(usage)

        scfg = j.get("stream_config",{})
        config["stream_title"] = scfg.get("stream_title","Untitled")
        config["rtsp_ip"]      = scfg.get("rtsp_ip","127.0.0.1")

        rcfg = j.get("rtsp_config",{})
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
    Return True jika TIDAK black,
    Return False jika black terdeteksi atau command error.
    """
    if not do_blackout:
        return True  # skip => anggap ok
    dur = duration if duration else BLACK_DURATION
    thr = threshold if threshold else BLACK_DETECT_THRESHOLD

    cmd = [
        "ffmpeg","-hide_banner","-loglevel","error","-y","-err_detect","ignore_err",
        "-rtsp_transport","tcp","-i", rtsp_url,
        "-vf", f"blackdetect=d={dur}:pic_th={thr}",
        "-an","-t","5","-f","null","-"
    ]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        if b"black_start" in r.stderr:
            logger.info("[BLACK] blackdetect => black_start triggered (pic_th=%.2f, d=%.1f)",
                        thr, dur)
        return (b"black_start" not in r.stderr)
    except Exception as e:
        logger.error("[BLACK] blackdetect error => %s", e)
        return False

def check_freeze_frames(rtsp_url, do_freeze, cpu_usage, freeze_sens=None, times=None, delay=None):
    """
    Return True jika TIDAK freeze,
    Return False jika freeze terdeteksi atau command error.
    """
    if not do_freeze:
        return True  # skip => ok
    if cpu_usage > 90:
        logger.info("[FREEZE] CPU>90 => skip freeze-check => treat as freeze_ok=True.")
        return True
    sens = freeze_sens if freeze_sens else FREEZE_DURATION
    tms  = times if times else FREEZE_RECHECK_TIMES
    dly  = delay if delay else FREEZE_RECHECK_DELAY

    fail = 0
    for i in range(tms):
        if not _freeze_once(rtsp_url, sens):
            fail += 1
        if i < (tms - 1):
            time.sleep(dly)
    return (fail < tms)

def _freeze_once(rtsp_url, freeze_sens):
    cmd = [
        "ffmpeg","-hide_banner","-loglevel","error","-y","-err_detect","ignore_err",
        "-rtsp_transport","tcp","-i", rtsp_url,
        "-vf", f"freezedetect=n=-60dB:d={freeze_sens}",
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
# (BackupSession di backup_manager.py)


######################################################
# 7. pipeline_xxx
######################################################
from motion_detection import MotionDetector

def pipeline_motion_dual(ch, config, main_url, with_object=False):
    """
    Baca sub-stream => if motion => rekam main_url => rolling MAX_RECORD.
    + Re-check freeze/black + update JSON real-time tiap interval.
    Stop if idle > (MOTION_TIMEOUT+POST_MOTION_DELAY).

    is_active => pipeline ok (sub-stream terbuka).
    recording => True/False tergantung motion.

    PERUBAHAN: 
     - black/freeze detect juga di sub_url => CPU lebih ringan.
    """
    import time
    from backup_manager import BackupSession

    user = config["rtsp_user"]
    pwd  = config["rtsp_password"]
    ip   = config["rtsp_ip"]
    sub_url = f"rtsp://{user}:{pwd}@{ip}:554/cam/realmonitor?channel={ch}&subtype=1"
    masked_sub = mask_rtsp_credentials(sub_url)
    logger.info("[EVENT] [DualStream] ch=%s => sub=%s", ch, masked_sub)

    # Buka sub-stream
    cap_sub = cv2.VideoCapture(sub_url)
    if not cap_sub.isOpened():
        masked_err = f"ch={ch} => fail open sub => {masked_sub}"
        logger.error("[DualStream] %s", masked_err)
        update_validation_status(ch, {
            "error_msg": masked_err,
            "is_active": False,
            "recording": False
        })
        raise RuntimeError(masked_err)

    motion_det = MotionDetector(area_threshold=MOTION_AREA)
    obj_det = None
    if with_object:
        from object_detection import ObjectDetector
        obj_det = ObjectDetector(
            "/app/backup/models/mobilenet_ssd/MobileNetSSD_deploy.prototxt",
            "/app/backup/models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel",
            conf_person=float(os.getenv("CONF_PERSON","0.6")),
            conf_car=float(os.getenv("CONF_CAR","0.4")),
            conf_motor=float(os.getenv("CONF_MOTOR","0.4"))
        )

    # Merekam main_url
    sess = BackupSession(main_url, ch, config["stream_title"])
    is_recording = False
    last_motion = 0
    frame_count = 0

    next_recheck = time.time() + IN_PIPELINE_UPDATE_INTERVAL

    while True:
        ret, frame = cap_sub.read()
        if not ret or frame is None:
            time.sleep(1)
            continue

        frame_count += 1
        if frame_count % FRAME_SKIP != 0:
            time.sleep(MOTION_SLEEP)
        else:
            # downscale
            if DOWNSCALE_RATIO < 1.0:
                try:
                    new_w = int(frame.shape[1]*DOWNSCALE_RATIO)
                    new_h = int(frame.shape[0]*DOWNSCALE_RATIO)
                    frame_small = cv2.resize(frame,(new_w,new_h), interpolation=cv2.INTER_AREA)
                except:
                    frame_small=frame
            else:
                frame_small=frame

            # motion detect
            bboxes = motion_det.detect(frame_small)
            motion_found=False
            if bboxes:
                if with_object and obj_det:
                    results,_ = obj_det.detect(frame_small)
                    person_found = any(r[0]=="person" for r in results)
                    if person_found:
                        motion_found=True
                else:
                    motion_found=True

            if motion_found:
                last_motion = time.time()
                if not is_recording:
                    sess.start_recording()
                    is_recording=True
                else:
                    # rolling
                    if not sess.still_ok(MAX_RECORD):
                        sess.stop_recording()
                        sess.start_recording()
            else:
                if is_recording:
                    idle_sec = time.time()-last_motion
                    if idle_sec > (MOTION_TIMEOUT + POST_MOTION_DELAY):
                        sess.stop_recording()
                        is_recording=False

        # Re-check freeze/black + update JSON => tapi check di sub-stream 
        # (supaya CPU lebih ringan)
        if time.time() >= next_recheck:
            cpu_usage = config.get("cpu_usage", 0.0)
            do_black  = ENABLE_BLACKOUT
            do_freeze = ENABLE_FREEZE_CHECK

            # DIUBAH => check black/freeze di sub_url
            ok_black  = check_black_frames(sub_url, do_black)
            ok_freeze = check_freeze_frames(sub_url, do_freeze, cpu_usage)

            if not (ok_black and ok_freeze):
                logger.warning("[pipeline_motion_dual] ch=%s => freeze/black => exit pipeline", ch)
                sess.stop_recording()
                raise Exception("re-check freeze/black fail in pipeline_motion_dual (sub-stream)")

            # Update JSON
            update_validation_status(ch, {
                "is_active": True,
                "recording": is_recording,
                "freeze_check_enabled": do_freeze,
                "black_check_enabled":  do_black,
                "freeze_ok": ok_freeze,
                "black_ok": ok_black,
                # Livestream link => main_url, sub_url, 
                # terserah, disini kita simpan main_url
                "livestream_link": mask_rtsp_credentials(main_url),
                "error_msg": None
            })

            next_recheck = time.time() + IN_PIPELINE_UPDATE_INTERVAL

        time.sleep(MOTION_SLEEP)


########################
# Pipeline lainnya
########################
# (pipeline_full, pipeline_motion, dsb.)
from backup_manager import BackupSession

def pipeline_full(ch, config, rtsp_url):
    # Tidak diubah, re-check black/freeze di main
    ...
    # (SAMA seperti versi sebelumnya)


def pipeline_motion(ch, config, rtsp_url, object_detection=False):
    # Tidak diubah, re-check black/freeze di main
    ...
    # (SAMA seperti versi sebelumnya)


######################################################
# --- LAST_CHECK_TIMES & thread_for_channel
######################################################
LAST_CHECK_TIMES = {}

def thread_for_channel(ch, config):
    # Sama seperti versi sebelumnya, 
    # tapi hati-hati => "motion_dual" kini check sub_url di pipeline

    while True:
        # Mark is_active=false
        update_validation_status(ch, {
            "is_active": False,
            "recording": False
        })

        user = config["rtsp_user"]
        pwd  = config["rtsp_password"]
        ip   = config["rtsp_ip"]
        subtype = config["rtsp_subtype"]
        raw_url = f"rtsp://{user}:{pwd}@{ip}:554/cam/realmonitor?channel={ch}&subtype={subtype}"
        masked_url = mask_rtsp_credentials(raw_url)
        logger.info("[EVENT] [Main] ch=%s => %s", ch, masked_url)

        cpu_usage = config["cpu_usage"]
        do_black  = ENABLE_BLACKOUT
        do_freeze = ENABLE_FREEZE_CHECK

        global LAST_CHECK_TIMES
        now = time.time()
        last_chk = LAST_CHECK_TIMES.get(ch, 0)
        interval = now - last_chk

        # Skip freeze/black check if interval<FREEZE_BLACK_INTERVAL
        if FREEZE_BLACK_INTERVAL>0 and interval < FREEZE_BLACK_INTERVAL:
            ok_black  = True
            ok_freeze = True
            logger.info("[VALIDATION] ch=%s => skip freeze/black => interval=%.1f < %d",
                        ch, interval, FREEZE_BLACK_INTERVAL)
        else:
            LAST_CHECK_TIMES[ch] = now
            if cpu_usage>90:
                do_black=False
                logger.info("[VALIDATION] ch=%s => CPU>90 => skip blackdetect", ch)

            ok_black = check_black_frames(raw_url, do_black)
            if not ok_black:
                masked_err = f"ch={ch} => black => skip => {masked_url}"
                logger.warning("[VALIDATION] %s", masked_err)
                update_validation_status(ch, {
                    "freeze_ok": None,
                    "black_ok": False,
                    "livestream_link": masked_url,
                    "error_msg": masked_err,
                    "is_active": False,
                    "recording": False
                })
                # cek fail persentase
                check_restart_if_too_many_fail(range(1, int(os.getenv("CHANNEL_COUNT","1"))+1))
                time.sleep(RESTART_DELAY)
                continue

            if do_freeze:
                ok_freeze = check_freeze_frames(raw_url, True, cpu_usage)
                if not ok_freeze:
                    masked_err = f"ch={ch} => freeze => skip => {masked_url}"
                    logger.warning("[VALIDATION] %s", masked_err)
                    update_validation_status(ch, {
                        "freeze_ok": False,
                        "black_ok":  ok_black,
                        "livestream_link": masked_url,
                        "error_msg": masked_err,
                        "is_active": False,
                        "recording": False
                    })
                    check_restart_if_too_many_fail(range(1, int(os.getenv("CHANNEL_COUNT","1"))+1))
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
            "is_active": True,
            "recording": False
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
                # Gunakan pipeline_motion_dual yg sdh diubah => black/freeze check di sub_url
                pipeline_motion_dual(ch, config, raw_url, with_object=False)
            elif BACKUP_MODE=="motion_obj_dual":
                pipeline_motion_dual(ch, config, raw_url, with_object=True)
            else:
                logger.warning("[VALIDATION] BACKUP_MODE=%s unknown => fallback full", BACKUP_MODE)
                pipeline_full(ch, config, raw_url)
        except Exception as e:
            logger.error("[Main] pipeline error ch=%s => %s", ch, e)
            update_validation_status(ch, {
                "is_active": False,
                "recording": False,
                "error_msg": f"{e}"
            })

        # pipeline exit => is_active false
        update_validation_status(ch, {
            "is_active": False,
            "recording": False
        })
        logger.info("[VALIDATION] ch=%s => pipeline exit => re-try in %ds", ch, RESTART_DELAY)

        # cek fail persentase
        check_restart_if_too_many_fail(range(1, int(os.getenv("CHANNEL_COUNT","1"))+1))
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

    # spawn threads
    for c in channels:
        t = threading.Thread(target=thread_for_channel, args=(c,config), daemon=True)
        t.start()

    while LOOP_ENABLE:
        logger.info("[EVENT] [Main] pipeline threads running => sleep %d sec", CHECK_INTERVAL)
        time.sleep(CHECK_INTERVAL)
        # reload config jika diperlukan
        # config = load_resource_config()

    logger.info("[EVENT] [Main] LOOP_ENABLE=false => exit main loop")


def main():
    ensure_json_initialized()
    run_pipeline_loop()
    logger.info("[EVENT] [Main] Keluar.")

if __name__=="__main__":
    main()