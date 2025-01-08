import cv2
import numpy as np

class MotionDetector:
    def __init__(self, history=500, varThreshold=16, detectShadows=True):
        self.back_sub = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=varThreshold,
            detectShadows=detectShadows
        )

    def detect(self, frame):
        fg_mask = self.back_sub.apply(frame)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        bboxes = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < 500:  # threshold area
                continue
            x, y, w, h = cv2.boundingRect(c)
            bboxes.append([x, y, w, h])
        return bboxes