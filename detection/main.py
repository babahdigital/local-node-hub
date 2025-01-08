import os
import cv2
import json
import time
import threading
import sys
from datetime import datetime

from motion_detection import MotionDetector

# Pastikan folder scripts ada di PATH (untuk utils.py).
sys.path.append("/app/scripts")

from utils import setup_category_logger, file_write_lock

###############################################################################
# 1. Setup Logger
###############################################################################
# Gunakan kategori "Resource-Monitor" atau "RTSP", atau "default"—sesuaikan dengan LOG_CATEGORIES di utils.py
logger = setup_category_logger("Resource-Monitor")

# File detection JSON
DETECTION_JSON_PATH = "/mnt/Data/Syslog/resource/detection_events.json"
# File resource state JSON
RESOURCE_STATE_JSON = "/mnt/Data/Syslog/resource/resource_monitor_state.json"

###############################################################################
# 2. Fungsi Menyimpan Event Gerakan
###############################################################################
def save_motion_event(channel, bounding_boxes):
    """
    Append ke detection_events.json satu baris JSON tiap kali gerakan terdeteksi.
    """
    event_data = {
        "timestamp": datetime.now().isoformat(),
        "channel": channel,
        "bounding_boxes": bounding_boxes
    }
    with file_write_lock:
        try:
            with open(DETECTION_JSON_PATH, "a") as f:
                f.write(json.dumps(event_data) + "\n")
        except Exception as e:
            logger.error(f"Gagal menulis event gerakan ke {DETECTION_JSON_PATH}: {e}")

###############################################################################
# 3. Fungsi Thread: detect_motion_in_channel
###############################################################################
def detect_motion_in_channel(channel, host_ip, motion_detector):
    stream_url = f"http://{host_ip}/ch{channel}/"
    logger.info(f"[THREAD-{channel}] Membuka stream: {stream_url}")

    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        logger.error(f"[THREAD-{channel}] ERROR: Gagal membuka stream.")
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning(f"[THREAD-{channel}] Stream terputus/frame kosong.")
                break

            # Deteksi gerakan
            bboxes = motion_detector.detect(frame, area_threshold=500)
            if bboxes:
                logger.info(f"[THREAD-{channel}] Gerakan terdeteksi: {bboxes}")
                save_motion_event(channel, bboxes)

            # time.sleep(0.01) # Optional: jeda kecil
    except KeyboardInterrupt:
        logger.warning(f"[THREAD-{channel}] Dihentikan oleh user (Ctrl+C).")
    finally:
        cap.release()
        logger.info(f"[THREAD-{channel}] Selesai.")

###############################################################################
# 4. Fungsi Memuat Channels Dari JSON
###############################################################################
def load_channels_from_json(json_path=RESOURCE_STATE_JSON):
    """
    Membaca 'resource_monitor_state.json', ambil 'stream_config.channel_list'.
    """
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        stream_config = data.get("stream_config", {})
        channel_list = stream_config.get("channel_list", [])
        return [str(ch) for ch in channel_list]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Gagal memuat channel dari {json_path}: {e}")
        return []

###############################################################################
# 5. Main
###############################################################################
def main():
    host_ip = os.getenv("HOST_IP", "127.0.0.1")
    motion_detector = MotionDetector(history=500, varThreshold=16, detectShadows=True)

    while True:
        channels = load_channels_from_json()
        if not channels:
            logger.info("[MAIN] Tidak ada data channel. Tunggu 10 detik...")
            time.sleep(10)
            continue

        logger.info(f"[MAIN] Ditemukan channel: {channels}")

        # Buat threads untuk masing-masing channel
        threads = []
        for ch in channels:
            t = threading.Thread(
                target=detect_motion_in_channel,
                args=(ch, host_ip, motion_detector),
                daemon=True
            )
            t.start()
            threads.append(t)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.warning("[MAIN] Dihentikan oleh user (Ctrl+C).")
            break

    logger.info("[MAIN] Program selesai.")

if __name__ == "__main__":
    main()