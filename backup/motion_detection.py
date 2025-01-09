import os
import cv2
import numpy as np
import logging

logger = logging.getLogger("Main-Combined")  # logger terpusat

class MotionDetector:
    def __init__(self,
                 history=None,
                 varThreshold=None,
                 detectShadows=None,
                 area_threshold=None):
        """
        Gunakan MOG2. Setting default:
          - history=500
          - varThreshold=16
          - detectShadows=True
          - area_threshold=3000 => minimum luas gerakan

        Semua parameter bisa juga diatur via ENV:
          MOTION_HISTORY=500
          MOTION_VARTH=16
          MOTION_SHADOWS=true
          MOTION_AREA_THRESHOLD=3000
        """
        try:
            # Baca ENV atau gunakan default
            h  = int(os.getenv("MOTION_HISTORY",  "500")) if history is None else history
            vt = int(os.getenv("MOTION_VARTH",    "16"))  if varThreshold is None else varThreshold
            ds = os.getenv("MOTION_SHADOWS","true").lower()=="true" if detectShadows is None else detectShadows
            at = int(os.getenv("MOTION_AREA_THRESHOLD","3000")) if area_threshold is None else area_threshold

            self.back_sub = cv2.createBackgroundSubtractorMOG2(
                history=h,
                varThreshold=vt,
                detectShadows=ds
            )
            # Kernel untuk operasi morfologi
            self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
            self.area_threshold = at

        except Exception as e:
            logger.error(f"[MotionDetector] __init__ error => {e}")

    def detect(self, frame):
        """
        Mengembalikan list bounding box 'bboxes' ketika terdeteksi gerakan.
        Makin besar 'area_threshold', makin besar gerakan minimal yang dideteksi.
        """
        try:
            # Terapkan background subtractor
            fg_mask = self.back_sub.apply(frame)

            # Operasi morfologi untuk mengurangi noise
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN,  self.kernel)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self.kernel)

            # Temukan kontur
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            bboxes = []
            for c in contours:
                area = cv2.contourArea(c)
                # Jika area kontur < threshold => anggap noise/tidak signifikan
                if area < self.area_threshold:
                    continue
                x, y, w, h = cv2.boundingRect(c)
                bboxes.append((x, y, w, h))

            return bboxes

        except Exception as e:
            logger.error(f"[MotionDetector] detect() error => {e}")
            return []