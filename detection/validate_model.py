import cv2
import os

# Path ke file model
prototxt = "/app/detection/models/mobilenet_ssd/MobileNetSSD_deploy.prototxt"
caffemodel = "/app/detection/models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel"

def validate_mobilenet_model(prototxt_path, caffemodel_path):
    """
    Memeriksa apakah file prototxt dan caffemodel ada dan bisa dimuat oleh OpenCV.
    """
    # 1. Cek eksistensi file
    if not os.path.isfile(prototxt_path):
        raise FileNotFoundError(f"File prototxt tidak ditemukan: {prototxt_path}")
    if not os.path.isfile(caffemodel_path):
        raise FileNotFoundError(f"File caffemodel tidak ditemukan: {caffemodel_path}")

    # 2. Coba muat model menggunakan OpenCV
    try:
        net = cv2.dnn.readNetFromCaffe(prototxt_path, caffemodel_path)
        return net
    except Exception as e:
        raise RuntimeError(f"Kesalahan saat memuat model: {e}")

if __name__ == "__main__":
    try:
        net = validate_mobilenet_model(prototxt, caffemodel)
        print("Model MobileNet SSD valid dan berhasil dimuat.")
    except Exception as e:
        print(str(e))
        # Anda bisa melakukan sys.exit(1) di sini agar proses di Docker berhenti
        # jika model tidak valid.
        exit(1)