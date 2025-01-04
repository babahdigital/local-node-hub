import cv2
import numpy as np
import os
from utils import setup_logger

# Konfigurasi logger
LOG_PATH = os.getenv("MOTION_LOG_PATH", "/mnt/Data/Syslog/cctv/motion_detection.log")
logger = setup_logger("Motion-Detection", LOG_PATH)

# Load MobileNet model
def load_mobilenet_model():
    prototxt = "/app/models/mobilenet_ssd/MobileNetSSD_deploy.prototxt"
    model = "/app/models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel"
    net = cv2.dnn.readNetFromCaffe(prototxt, model)
    return net

def detect_objects(frame, net):
    """
    Deteksi objek menggunakan MobileNet pada frame.
    """
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()

    objects_detected = []
    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > 0.5:  # Confidence threshold
            idx = int(detections[0, 0, i, 1])
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (startX, startY, endX, endY) = box.astype("int")
            objects_detected.append((idx, confidence, (startX, startY, endX, endY)))
    return objects_detected

def motion_detection(rtsp_url):
    """
    Proses frame differencing untuk deteksi gerakan.
    """
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        logger.error(f"Tidak dapat membuka RTSP stream: {rtsp_url}")
        return

    _, prev_frame = cap.read()
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    net = load_mobilenet_model()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            logger.error("Gagal membaca frame dari RTSP stream.")
            break

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(prev_gray, gray_frame)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        non_zero_count = cv2.countNonZero(thresh)

        if non_zero_count > 50:  # Threshold gerakan
            logger.info("Gerakan terdeteksi, menganalisis dengan MobileNet...")
            objects = detect_objects(frame, net)
            for idx, confidence, box in objects:
                logger.info(f"Objek terdeteksi: ID={idx}, Confidence={confidence:.2f}, Box={box}")

        prev_gray = gray_frame

    cap.release()

if __name__ == "__main__":
    RTSP_URL = f"rtsp://{os.getenv('RTSP_USER')}:{os.getenv('RTSP_PASSWORD')}@{os.getenv('RTSP_IP')}:554/cam/realmonitor?channel=1&subtype={os.getenv('RTSP_SUBTYPE', '1')}"
    motion_detection(RTSP_URL)