import cv2
import numpy as np

class ObjectDetector:
    """
    MobileNet SSD. 
    threshold: person=0.6, car=0.4, motorbike=0.4
    """
    def __init__(self, prototxt_path, model_path,
                 conf_person=0.6, conf_car=0.4, conf_motor=0.4):
        print("[INFO] loading MobileNet SSD model...")
        self.net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
        self.conf_person = conf_person
        self.conf_car    = conf_car
        self.conf_motor  = conf_motor

        self.CLASSES = [
            "background", "aeroplane", "bicycle", "bird", "boat",
            "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
            "dog", "horse", "motorbike", "person", "pottedplant",
            "sheep", "sofa", "train", "tvmonitor"
        ]

    def detect(self, frame):
        (h,w)= frame.shape[:2]
        blob= cv2.dnn.blobFromImage(
            frame, 0.007843, (300,300), 127.5
        )
        self.net.setInput(blob)
        detections= self.net.forward()

        results= []
        for i in range(detections.shape[2]):
            raw_conf= detections[0,0,i,2]
            if raw_conf>100:
                raw_conf/=100.0

            class_id= int(detections[0,0,i,1])
            if class_id<0 or class_id>=len(self.CLASSES):
                continue
            label= self.CLASSES[class_id]

            # Tersedia threshold
            pass_check= False
            if label=="person" and raw_conf>= self.conf_person:
                pass_check= True
            elif label=="car" and raw_conf>= self.conf_car:
                pass_check= True
            elif label=="motorbike" and raw_conf>= self.conf_motor:
                pass_check= True

            if not pass_check:
                continue

            box= detections[0,0,i,3:7]* [w,h,w,h]
            (startX,startY,endX,endY)= box.astype("int")
            startX, startY= max(0,startX), max(0,startY)
            endX, endY    = min(w-1,endX), min(h-1,endY)
            results.append((label, float(raw_conf), startX, startY, endX-startX, endY-startY))

        return results