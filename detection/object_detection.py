import cv2
import numpy as np

class ObjectDetector:
    """
    Class berbasis MobileNet SSD (Caffe) untuk deteksi objek.
    Memiliki method 'detect(frame)' yang mengembalikan list:
      [(label, confidence, x, y, w, h), ...]
    """

    def __init__(self, prototxt_path, model_path, confidence_threshold=0.3):
        """
        Lebih "longgar" -> default 0.3 agar tidak terlalu ketat.
        """
        print("[INFO] loading MobileNet SSD model...")
        self.net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
        self.conf_threshold = confidence_threshold

        # 21 classes bawaan MobileNet SSD (VOC)
        self.CLASSES = [
            "background", "aeroplane", "bicycle", "bird", "boat",
            "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
            "dog", "horse", "motorbike", "person", "pottedplant",
            "sheep", "sofa", "train", "tvmonitor"
        ]

    def detect(self, frame):
        """
        Mendeteksi objek di 'frame'.
        Return list of (label, confidence, x, y, w, h).
        """
        (h, w) = frame.shape[:2]

        # Buat blob: normalisasi, resize 300x300 (MobileNet SSD default)
        blob = cv2.dnn.blobFromImage(
            frame,
            scalefactor=0.007843,  # 1 / 127.5
            size=(300, 300),
            mean=127.5
        )
        self.net.setInput(blob)
        detections = self.net.forward()

        results = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence < self.conf_threshold:
                continue

            class_id = int(detections[0, 0, i, 1])
            label = "Unknown"
            if 0 <= class_id < len(self.CLASSES):
                label = self.CLASSES[class_id]

            # Bounding box di frame aslinya
            box = detections[0, 0, i, 3:7] * [w, h, w, h]
            (startX, startY, endX, endY) = box.astype("int")

            startX = max(0, startX)
            startY = max(0, startY)
            endX = min(w - 1, endX)
            endY = min(h - 1, endY)

            boxW = endX - startX
            boxH = endY - startY

            results.append((label, float(confidence), startX, startY, boxW, boxH))

        return results

if __name__ == "__main__":
    print("object_detection.py biasanya diimport oleh main.py, bukan dipanggil langsung.")