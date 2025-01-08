import cv2
import numpy as np

class MotionDetector:
    def __init__(self, history=500, varThreshold=16, detectShadows=True, area_threshold=3000):
        """
        Gunakan MOG2. Setting:
          - history=500
          - varThreshold=16
          - detectShadows=True
          - area_threshold=3000 => minimum luas gerakan
        """
        self.back_sub = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=varThreshold,
            detectShadows=detectShadows
        )
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
        self.area_threshold = area_threshold

    def detect(self, frame):
        fg_mask = self.back_sub.apply(frame)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self.kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self.kernel)

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        bboxes = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.area_threshold:
                continue
            x, y, w, h = cv2.boundingRect(c)
            bboxes.append((x, y, w, h))

        return bboxes