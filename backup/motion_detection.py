import os
import cv2
import numpy as np
import logging
from datetime import datetime

logger = logging.getLogger("Main-Combined")

class MotionDetector:
    def __init__(self, history=None, varThreshold=None, detectShadows=None, area_threshold=None):
        """
        Gunakan MOG2. Setting default:
          - history=500  (ENV MOTION_HISTORY)
          - varThreshold=16 (ENV MOTION_VARTH)
          - detectShadows=True (ENV MOTION_SHADOWS)
          - area_threshold=5000 (ENV MOTION_AREA_THRESHOLD)

        Night-mode opsional:
          - NIGHT_MODE_ENABLE, NIGHT_START_HOUR, NIGHT_END_HOUR,
            NIGHT_AREA_THRESHOLD, NIGHT_BLUR_ENABLE, NIGHT_BLUR_KERNEL
        """
        try:
            # 1) Baca ENV
            h_env  = int(os.getenv("MOTION_HISTORY", "500"))
            vt_env = int(os.getenv("MOTION_VARTH", "16"))
            ds_env = (os.getenv("MOTION_SHADOWS","true").lower()=="true")
            at_env = int(os.getenv("MOTION_AREA_THRESHOLD","5000"))

            # override param
            h  = h_env  if history       is None else history
            vt = vt_env if varThreshold  is None else varThreshold
            ds = ds_env if detectShadows is None else detectShadows
            at = at_env if area_threshold is None else area_threshold

            self.back_sub = cv2.createBackgroundSubtractorMOG2(history=h, varThreshold=vt, detectShadows=ds)
            self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))

            self.area_threshold_day = at

            # Night Mode param
            self.night_mode_enable    = (os.getenv("NIGHT_MODE_ENABLE","false").lower()=="true")
            self.night_start_hour     = int(os.getenv("NIGHT_START_HOUR","19"))
            self.night_end_hour       = int(os.getenv("NIGHT_END_HOUR","6"))
            self.night_area_threshold = int(os.getenv("NIGHT_AREA_THRESHOLD","8000"))
            self.night_blur_enable    = (os.getenv("NIGHT_BLUR_ENABLE","false").lower()=="true")
            self.night_blur_kernel    = int(os.getenv("NIGHT_BLUR_KERNEL","5"))

            logger.info(
                f"[MotionDetector] Init => hist={h}, varThr={vt}, ds={ds}, "
                f"day_area={self.area_threshold_day}, night_mode={self.night_mode_enable}, "
                f"night_area={self.night_area_threshold}, blur={self.night_blur_enable}, "
                f"blur_kernel={self.night_blur_kernel}, night={self.night_start_hour}-{self.night_end_hour}"
            )
        except Exception as e:
            logger.error(f"[MotionDetector] __init__ error => {e}")

    def detect(self, frame):
        """
        1) Cek night-mode => pakai threshold & blur jika malam.
        2) MOG2 => morph open+close => findContours => saring by area.
        """
        try:
            current_hour = datetime.now().hour
            is_night = False
            if self.night_mode_enable:
                if self.night_start_hour < self.night_end_hour:
                    # misal start=6, end=18 => siang
                    is_night = (self.night_start_hour <= current_hour < self.night_end_hour)
                else:
                    # typical => start=19, end=6 => jam >=19 atau <6 => malam
                    if (current_hour >= self.night_start_hour or current_hour < self.night_end_hour):
                        is_night = True

            if is_night:
                area_thr = self.night_area_threshold
            else:
                area_thr = self.area_threshold_day

            frame_proc = frame
            if is_night and self.night_blur_enable:
                k = self.night_blur_kernel
                frame_proc = cv2.GaussianBlur(frame, (k,k), 0)

            fg_mask = self.back_sub.apply(frame_proc)

            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN,  self.kernel)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self.kernel)

            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            bboxes = []
            for c in contours:
                area = cv2.contourArea(c)
                if area< area_thr:
                    continue
                x, y, w, h = cv2.boundingRect(c)
                bboxes.append((x,y,w,h))

            return bboxes
        except Exception as e:
            logger.error(f"[MotionDetector] detect() error => {e}")
            return []