import cv2

class ObjectDetector:
    def __init__(self, prototxt_path, model_path, confidence_threshold=0.5):
        """
        Memuat model MobileNet SSD (Caffe) via OpenCV's DNN.
        confidence_threshold: Skor minimal agar deteksi dianggap valid
        """
        self.net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
        self.conf_threshold = confidence_threshold

        # Label 20 kelas VOC di MobileNet SSD
        # (Background, aeroplane, bicycle, bird, boat, bottle, bus, car, cat, chair,
        # cow, diningtable, dog, horse, motorbike, person, pottedplant, sheep, sofa, train, tvmonitor)
        self.CLASSES = [
            "background", "aeroplane", "bicycle", "bird", "boat",
            "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
            "dog", "horse", "motorbike", "person", "pottedplant",
            "sheep", "sofa", "train", "tvmonitor"
        ]

    def detect(self, frame):
        """
        Mendeteksi objek di frame. Mengembalikan list (label, confidence, x, y, w, h).
        """
        (h, w) = frame.shape[:2]

        # Buat blob: normalisasi, resize ke 300x300 (MobileNet SSD default)
        blob = cv2.dnn.blobFromImage(
            frame,
            0.007843,  # 1/127.5 => 0.007843
            (300, 300),
            (127.5, 127.5, 127.5),
            swapRB=True,
            crop=False
        )
        self.net.setInput(blob)
        detections = self.net.forward()

        results = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > self.conf_threshold:
                class_id = int(detections[0, 0, i, 1])
                label = self.CLASSES[class_id] if class_id < len(self.CLASSES) else "Unknown"
                
                # Hitung bounding box (x1, y1, x2, y2)
                box = detections[0, 0, i, 3:7] * [w, h, w, h]
                (startX, startY, endX, endY) = box.astype("int")

                # Pastikan koordinat dalam range
                startX = max(0, startX)
                startY = max(0, startY)
                endX = min(w - 1, endX)
                endY = min(h - 1, endY)

                results.append((
                    label, 
                    float(confidence), 
                    startX, 
                    startY, 
                    endX - startX,  # width
                    endY - startY   # height
                ))
        return results