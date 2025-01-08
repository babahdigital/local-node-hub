import cv2
import numpy as np

class MotionDetector:
    def __init__(self, history=500, varThreshold=16, detectShadows=True, area_threshold=3000):
        """
        - area_threshold ditingkatkan ke 3000 agar gerakan kecil (misal ranting kecil) diabaikan.
        """
        self.back_sub = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=varThreshold,
            detectShadows=detectShadows
        )
        # Kernel morphological lebih besar agar noise kecil terhapus
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self.area_threshold = area_threshold

    def detect(self, frame):
        # Background Subtraction
        fg_mask = self.back_sub.apply(frame)
        # Morph open + close lebih agresif
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self.kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self.kernel)
        # Find contours
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        bboxes = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.area_threshold:
                continue
            x, y, w, h = cv2.boundingRect(c)
            bboxes.append((x, y, w, h))
        return bboxes