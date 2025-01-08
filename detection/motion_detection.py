import cv2
import numpy as np

class MotionDetector:
    def __init__(self, history=500, varThreshold=16, detectShadows=True):
        """
        Deteksi gerakan menggunakan BackgroundSubtractorMOG2.
        """
        self.back_sub = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=varThreshold,
            detectShadows=detectShadows
        )
        # Kernel morphological (untuk mengurangi noise)
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    def detect(self, frame, area_threshold=500):
        """
        Menerapkan background subtraction + morph. 
        Kembalikan list bounding boxes (x,y,w,h) dengan area >= area_threshold.
        """
        fg_mask = self.back_sub.apply(frame)

        # Morph open + close
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self.kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self.kernel)

        # Temukan kontur
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        bboxes = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < area_threshold:
                continue
            x, y, w, h = cv2.boundingRect(c)
            bboxes.append([x, y, w, h])

        return bboxes