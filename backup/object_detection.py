import cv2
import numpy as np
import os

# (A) Global Net agar model hanya sekali diload per runtime
GLOBAL_NET = None  

def load_global_net(prototxt_path, model_path):
    """
    Meload MobileNet SSD sekali saja di GLOBAL_NET.
    Jika sudah pernah load, langsung pakai GLOBAL_NET.
    """
    global GLOBAL_NET
    if GLOBAL_NET is None:
        print("[INFO] loading MobileNet SSD model (GLOBAL) ...")
        net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
        GLOBAL_NET = net
    return GLOBAL_NET


class ObjectDetector:
    """
    MobileNet SSD:
    - person, car, motorbike dengan confidence default:
      person=0.6, car=0.4, motorbike=0.4

    - Bisa dioverride via constructor, atau
      jika parameter = None, maka baca ENV:
        CONF_PERSON, CONF_CAR, CONF_MOTOR
    """

    def __init__(self,
                 prototxt_path,
                 model_path,
                 conf_person=None,
                 conf_car=None,
                 conf_motor=None,
                 use_global=True):
        """
        use_global=True => gunakan GLOBAL_NET agar model tidak diload berulang.
        """
        # (B) Pilih pakai global net atau local
        if use_global:
            self.net = load_global_net(prototxt_path, model_path)
        else:
            print("[INFO] loading MobileNet SSD model (LOCAL) ...")
            self.net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)

        # (C) Baca ENV jika parameter None
        if conf_person is None:
            conf_person = float(os.getenv("CONF_PERSON", "0.6"))
        if conf_car is None:
            conf_car = float(os.getenv("CONF_CAR", "0.4"))
        if conf_motor is None:
            conf_motor = float(os.getenv("CONF_MOTOR", "0.4"))

        self.conf_person = conf_person
        self.conf_car    = conf_car
        self.conf_motor  = conf_motor

        # (D) Daftar label MobileNet SSD
        self.CLASSES = [
            "background", "aeroplane", "bicycle", "bird", "boat",
            "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
            "dog", "horse", "motorbike", "person", "pottedplant",
            "sheep", "sofa", "train", "tvmonitor"
        ]

    def detect(self, frame):
        """
        Mengembalikan (results, None) agar kompatibel dgn main.py:
          results = list of (label, conf, x, y, w, h)
        """
        (h, w) = frame.shape[:2]

        # (E) Buat blob 300x300 untuk MobileNet SSD
        blob = cv2.dnn.blobFromImage(
            frame, 
            scalefactor=0.007843,    # skala normalisasi
            size=(300, 300),         # input size model
            mean=127.5
        )
        self.net.setInput(blob)
        detections = self.net.forward()

        results = []
        for i in range(detections.shape[2]):
            raw_conf = detections[0, 0, i, 2]
            # kadang ada bug conf > 1xx => normalisasi
            if raw_conf > 100:
                raw_conf /= 100.0

            class_id = int(detections[0, 0, i, 1])
            # validasi class_id
            if not (0 <= class_id < len(self.CLASSES)):
                continue

            label = self.CLASSES[class_id]
            # (F) Check confidence threshold per label
            pass_check = False
            if label == "person" and raw_conf >= self.conf_person:
                pass_check = True
            elif label == "car" and raw_conf >= self.conf_car:
                pass_check = True
            elif label == "motorbike" and raw_conf >= self.conf_motor:
                pass_check = True

            if not pass_check:
                continue

            # (G) Bikin bounding box
            box = detections[0, 0, i, 3:7] * [w, h, w, h]
            (startX, startY, endX, endY) = box.astype("int")

            # Clamp agar tidak out of range
            startX = max(0, startX)
            startY = max(0, startY)
            endX   = min(w - 1, endX)
            endY   = min(h - 1, endY)
            bbox_w = endX - startX
            bbox_h = endY - startY

            results.append((
                label, 
                float(raw_conf), 
                startX, 
                startY, 
                bbox_w, 
                bbox_h
            ))

        return (results, None)