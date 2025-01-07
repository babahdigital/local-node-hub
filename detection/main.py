import cv2
from motion_detection import MotionDetector
from object_detection import ObjectDetector
from live_stream import run_live_stream  # jika ingin pakai fungsi streaming

def main():
    stream_url = "http://127.0.0.1:8080/ch1/"
    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        print("Gagal membuka stream!")
        return

    motion_detector = MotionDetector()
    object_detector = ObjectDetector()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Deteksi motion
        motion_bboxes = motion_detector.detect(frame)
        if motion_bboxes:
            # Deteksi object
            detections = object_detector.detect(frame)
            # Lakukan penandaan bounding box, simpan log, dsb.

        cv2.imshow("Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()