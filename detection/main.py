import os
import cv2
import json
import time
import threading
import sys
from datetime import datetime

from motion_detection import MotionDetector
from object_detection import ObjectDetector

# Pastikan folder scripts ada di PATH (untuk utils.py).
sys.path.append("/app/scripts")
from utils import setup_category_logger, file_write_lock

logger = setup_category_logger("Resource-Monitor")

DETECTION_JSON_PATH = "/mnt/Data/Syslog/resource/detection_events.json"
RESOURCE_STATE_JSON = "/mnt/Data/Syslog/resource/resource_monitor_state.json"

def save_motion_event(channel, bounding_boxes, object_label=None, object_conf=None):
    """
    Menyimpan event gerakan + label objek (jika ada).
    """
    event_data = {
        "timestamp": datetime.now().isoformat(),
        "channel": channel,
        "bounding_boxes": bounding_boxes
    }
    if object_label:
        event_data["object_label"] = object_label
        event_data["object_confidence"] = object_conf

    with file_write_lock:
        try:
            with open(DETECTION_JSON_PATH, "a") as f:
                f.write(json.dumps(event_data) + "\n")
        except Exception as e:
            logger.error(f"Gagal menulis event gerakan ke {DETECTION_JSON_PATH}: {e}")

def detect_motion_in_channel(channel, host_ip, motion_detector, object_detector=None):
    """
    Thread function:
    1) Baca stream.
    2) Motion detection.
    3) Jika ada gerakan, opsional panggil object_detector untuk validasi.
    """
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

            bboxes = motion_detector.detect(frame, area_threshold=500)
            if bboxes:
                # Ada gerakan, cek AI object detection jika disediakan
                if object_detector:
                    # Panggil object_detector
                    detections = object_detector.detect(frame)
                    # Contoh: cari apakah ada "person"
                    person_detected = False
                    best_conf = 0.0
                    for (label, conf, x, y, w, h) in detections:
                        if label == "person" and conf > best_conf:
                            best_conf = conf
                            person_detected = True
                    
                    if person_detected:
                        logger.info(f"[THREAD-{channel}] Person terdeteksi (conf={best_conf:.2f}). Bboxes: {bboxes}")
                        # Simpan event
                        save_motion_event(channel, bboxes, "person", best_conf)
                    else:
                        # Gerakan ada, tapi bukan "person" => skip
                        logger.info(f"[THREAD-{channel}] Ada gerakan, tapi no person => skip log.")
                else:
                    # Tanpa object_detector, log saja
                    logger.info(f"[THREAD-{channel}] Gerakan terdeteksi: {bboxes}")
                    save_motion_event(channel, bboxes)

            # time.sleep(0.01)
    except KeyboardInterrupt:
        logger.warning(f"[THREAD-{channel}] Dihentikan oleh user (Ctrl+C).")
    finally:
        cap.release()
        logger.info(f"[THREAD-{channel}] Selesai.")

def load_channels_from_json(json_path=RESOURCE_STATE_JSON):
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        stream_config = data.get("stream_config", {})
        channel_list = stream_config.get("channel_list", [])
        return [str(ch) for ch in channel_list]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Gagal memuat channel dari {json_path}: {e}")
        return []

def main():
    host_ip = os.getenv("HOST_IP", "127.0.0.1")
    motion_detector = MotionDetector(history=500, varThreshold=16, detectShadows=True)

    # Inisialisasi object detector (MobileNet SSD)
    prototxt_path = "/app/detection/models/mobilenet_ssd/MobileNetSSD_deploy.prototxt"
    caffemodel_path = "/app/detection/models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel"
    object_detector = ObjectDetector(prototxt_path, caffemodel_path, confidence_threshold=0.5)

    while True:
        channels = load_channels_from_json()
        if not channels:
            logger.info("[MAIN] Tidak ada data channel. Tunggu 10 detik...")
            time.sleep(10)
            continue

        logger.info(f"[MAIN] Ditemukan channel: {channels}")

        threads = []
        for ch in channels:
            t = threading.Thread(
                target=detect_motion_in_channel,
                args=(ch, host_ip, motion_detector, object_detector),
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