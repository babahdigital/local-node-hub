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


# ----- Adaptive parameter manager -----
class AdaptiveParams:
    def __init__(self, motion_detector, object_detector):
        self.motion_detector = motion_detector
        self.object_detector = object_detector

        # Statistik
        self.total_motion = 0
        self.total_person_detected = 0

        # Waktu update adaptif
        self.last_update_time = time.time()
        self.update_interval = 60  # setiap 60 detik update param

    def record_event(self, motion_found, person_found):
        if motion_found:
            self.total_motion += 1
        if person_found:
            self.total_person_detected += 1

        now = time.time()
        if now - self.last_update_time > self.update_interval:
            self.update_adaptive()
            self.last_update_time = now

    def update_adaptive(self):
        if self.total_motion == 0:
            return

        ratio = self.total_person_detected / float(self.total_motion)
        logger.info(f"[ADAPTIVE] ratio person= {ratio:.2f} (person/motion). Update threshold..")

        if ratio < 0.1:
            old_conf = self.object_detector.conf_threshold
            new_conf = max(0.05, old_conf * 0.9)
            self.object_detector.set_conf_threshold(new_conf)

            old_area = self.motion_detector.area_threshold
            new_area = max(100, old_area - 50)
            self.motion_detector.set_area_threshold(new_area)

            logger.info(f"[ADAPTIVE] Turunkan conf_threshold: {old_conf:.2f}->{new_conf:.2f}, area: {old_area}->{new_area}")
        elif ratio > 0.5:
            old_conf = self.object_detector.conf_threshold
            new_conf = min(1.0, old_conf * 1.1)
            self.object_detector.set_conf_threshold(new_conf)

            old_area = self.motion_detector.area_threshold
            new_area = old_area + 50
            self.motion_detector.set_area_threshold(new_area)

            logger.info(f"[ADAPTIVE] Naikkan conf_threshold: {old_conf:.2f}->{new_conf:.2f}, area: {old_area}->{new_area}")

        # Reset
        self.total_motion = 0
        self.total_person_detected = 0


def save_motion_event(channel, bounding_boxes, object_label=None, object_conf=None):
    event_data = {
        "timestamp": datetime.now().isoformat(),
        "channel": channel,
        "bounding_boxes": bounding_boxes
    }
    if object_label:
        event_data["object_label"] = object_label
        # confidence kita simpan 0..1, di log pun boleh *100 jika mau
        event_data["object_confidence"] = round(object_conf, 3)

    with file_write_lock:
        try:
            with open(DETECTION_JSON_PATH, "a") as f:
                f.write(json.dumps(event_data) + "\n")
        except Exception as e:
            logger.error(f"Gagal menulis event gerakan ke {DETECTION_JSON_PATH}: {e}")


def detect_motion_in_channel(channel, host_ip, motion_detector, object_detector=None, adaptive=None):
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

            bboxes = motion_detector.detect(frame)
            motion_found = (len(bboxes) > 0)
            person_found = False

            if bboxes and object_detector:
                local_person_detected = False
                best_conf = 0.0

                # 1) ROI detection
                for (mx, my, mw, mh) in bboxes:
                    sub_frame = frame[my:my+mh, mx:mx+mw]
                    detections = object_detector.detect(sub_frame)

                    if detections:
                        logger.info(f"[THREAD-{channel}] ROI => {len(detections)} obj")
                    for (label, conf, sx, sy, sw, sh) in detections:
                        logger.info(f"[THREAD-{channel}] ROI label={label}, conf={conf:.2f}")
                        if label == "person" and conf > best_conf:
                            best_conf = conf
                            local_person_detected = True

                # 2) Fallback full-frame if no person
                if not local_person_detected:
                    logger.info(f"[THREAD-{channel}] ROI tidak temukan 'person'. Coba full-frame detection.")
                    full_detections = object_detector.detect(frame)
                    if full_detections:
                        logger.info(f"[THREAD-{channel}] FULL => {len(full_detections)} obj")
                    for (label, conf, x, y, w, h) in full_detections:
                        logger.info(f"[THREAD-{channel}] FULL label={label}, conf={conf:.2f}")
                        if label == "person" and conf > best_conf:
                            best_conf = conf
                            local_person_detected = True

                if local_person_detected:
                    person_found = True
                    logger.info(f"[THREAD-{channel}] Person terdeteksi (conf={best_conf*100:.2f}%). Bboxes: {bboxes}")
                    save_motion_event(channel, bboxes, "person", best_conf)
                else:
                    logger.info(f"[THREAD-{channel}] Ada gerakan, tapi no person => skip log.")
            elif bboxes and not object_detector:
                # Tanpa object detector
                logger.info(f"[THREAD-{channel}] Gerakan terdeteksi: {bboxes}")
                save_motion_event(channel, bboxes)

            # Rekam event di adaptif
            if adaptive:
                adaptive.record_event(motion_found, person_found)

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

    # Inisialisasi motion detector
    motion_detector = MotionDetector(history=500, varThreshold=16, detectShadows=True)

    # Inisialisasi object detector
    prototxt_path = "/app/detection/models/mobilenet_ssd/MobileNetSSD_deploy.prototxt"
    caffemodel_path = "/app/detection/models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel"
    object_detector = ObjectDetector(prototxt_path, caffemodel_path, confidence_threshold=0.2)

    # Manager adaptif
    adaptive_manager = AdaptiveParams(motion_detector, object_detector)

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
                args=(ch, host_ip, motion_detector, object_detector, adaptive_manager),
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