import cv2

# Path ke file model
prototxt = "/app/models/mobilenet_ssd/MobileNetSSD_deploy.prototxt"
caffemodel = "/app/models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel"

try:
    # Muat model menggunakan OpenCV
    net = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
    print("Model MobileNet SSD valid dan berhasil dimuat.")
except Exception as e:
    print(f"Kesalahan saat memuat model: {e}")