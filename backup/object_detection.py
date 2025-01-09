import cv2
import numpy as np
import os
import logging

logger = logging.getLogger("Main-Combined")  # logger terpusat

GLOBAL_NET = None

def load_global_net(prototxt_path, model_path):
    """
    Meload MobileNet SSD sekali saja di GLOBAL_NET.
    Jika sudah pernah load, langsung pakai GLOBAL_NET.
    """
    global GLOBAL_NET
    if GLOBAL_NET is None:
        try:
            logger.info("[INFO] loading MobileNet SSD model (GLOBAL) ...")
            net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
            GLOBAL_NET = net
        except Exception as e:
            logger.error(f"[ObjectDetector] load_global_net error => {e}")
            GLOBAL_NET = None
    return GLOBAL_NET

class ObjectDetector:
    """
    MobileNet SSD:
    - Default confidence threshold:
        person=0.6, car=0.4, motorbike=0.4
    
    - Dapat dioverride via constructor param, atau
      jika None => baca ENV (CONF_PERSON, CONF_CAR, CONF_MOTOR).

    - Clamping bounding box agar tidak invalid.
    """

    def __init__(self,
                 prototxt_path,
                 model_path,
                 conf_person=None,
                 conf_car=None,
                 conf_motor=None,
                 use_global=True):
        if use_global:
            self.net = load_global_net(prototxt_path, model_path)
        else:
            logger.info("[INFO] loading MobileNet SSD model (LOCAL) ...")
            try:
                self.net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
            except Exception as e:
                logger.error(f"[ObjectDetector] local load error => {e}")
                self.net = None

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

        # Daftar label MobileNet SSD
        self.CLASSES = [
            "background", "aeroplane", "bicycle", "bird", "boat",
            "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
            "dog", "horse", "motorbike", "person", "pottedplant",
            "sheep", "sofa", "train", "tvmonitor"
        ]

    def detect(self, frame):
        """
        Return (results, None)
        results => list of (label, conf, x, y, w, h)
        """
        if self.net is None:
            logger.error("[ObjectDetector] net is None => cannot detect")
            return ([], None)

        (h, w) = frame.shape[:2]

        try:
            blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), 127.5)
            self.net.setInput(blob)
            detections = self.net.forward()
        except Exception as e:
            logger.error(f"[ObjectDetector] detect forward error => {e}")
            return ([], None)

        results = []
        for i in range(detections.shape[2]):
            raw_conf = detections[0, 0, i, 2]
            if raw_conf > 100:
                raw_conf /= 100.0

            class_id = int(detections[0, 0, i, 1])
            if not (0 <= class_id < len(self.CLASSES)):
                continue

            label = self.CLASSES[class_id]

            pass_check = False
            if label == "person" and raw_conf >= self.conf_person:
                pass_check = True
            elif label == "car" and raw_conf >= self.conf_car:
                pass_check = True
            elif label == "motorbike" and raw_conf >= self.conf_motor:
                pass_check = True

            if not pass_check:
                continue

            # bounding box => clamp
            box = detections[0, 0, i, 3:7] * [w, h, w, h]
            max_dim = float(max(w, h))
            box = np.clip(box, 0, max_dim)

            (startX, startY, endX, endY) = box.astype("int")
            endX   = min(endX, w - 1)
            endY   = min(endY, h - 1)
            startX = max(0, startX)
            startY = max(0, startY)
            bbox_w = endX - startX
            bbox_h = endY - startY

            if bbox_w < 1 or bbox_h < 1:
                continue

            results.append((label, float(raw_conf), startX, startY, bbox_w, bbox_h))

        return (results, None)