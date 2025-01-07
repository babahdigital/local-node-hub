# Simple Motion + Object Detection Example

## Deskripsi Proyek

Proyek ini menampilkan pipeline sederhana yang memanfaatkan OpenCV untuk:

- **Motion Detection** menggunakan BackgroundSubtractorMOG2.
- **Object Detection** menggunakan MobileNet SSD yang di-load melalui cv2.dnn.

### Skenario Dasar

1. Menangkap video stream (dari webcam atau RTSP).
2. Script mendeteksi gerakan. Jika ada gerakan, object detection dijalankan, menandai bounding box objek yang terdeteksi.

Tujuan utama contoh ini adalah memberikan kerangka bagi pengembangan CCTV streaming, integrasi backup/rekaman, serta analisis sederhana dengan OpenCV. Anda bebas memodifikasi atau mengembangkannya lebih lanjut (misal menambahkan notifikasi, integrasi dengan ffmpeg, HLS streaming, dsb.).

### Struktur Proyek

```
detection
├── Dockerfile
├── main.py
├── models
│   └── mobilenet_ssd
│       ├── MobileNetSSD_deploy.caffemodel
│       └── MobileNetSSD_deploy.prototxt
├── motion_detection.py
├── object_detection.py
├── README.md
├── requirements.txt
└── validate_model.py
scripts
└── utils.py
config
└── log_messages.json
syslog
├── config
│   └── syslog-ng.conf
├── Dockerfile
└── entrypoint.sh
```

### Penjelasan File

- **requirements.txt**: Daftar pustaka Python yang diperlukan (numpy, opencv-python, dll.).
- **motion_detection.py**: Class `MotionDetector` menggunakan BackgroundSubtractorMOG2 untuk mendeteksi gerakan.
- **object_detection.py**: Class `ObjectDetector` memuat model MobileNet SSD menggunakan cv2.dnn.
- **main.py**: File utama untuk mengeksekusi pipeline.
- **model/**: Folder untuk menaruh model MobileNetSSD_deploy.prototxt dan MobileNetSSD_deploy.caffemodel.

## Arsitektur Teknologi

1. **OpenCV**: Digunakan untuk membaca frame, menjalankan motion detection, object detection, dan menampilkan hasil deteksi.
2. **MobileNet SSD (Caffe Model)**: Dimuat lewat cv2.dnn.readNetFromCaffe untuk mendeteksi 20 kelas umum.
3. **Python + Numpy**: Python sebagai bahasa pemrograman utama, Numpy untuk manipulasi array gambar.
4. **Integrasi dengan Komponen Lain**: FFmpeg/Nginx, Docker, Database/Logging.

## Detail Pengembangan

### Motion Detection (motion_detection.py)

Menggunakan `cv2.createBackgroundSubtractorMOG2`:
```python
self.back_sub = cv2.createBackgroundSubtractorMOG2(
    history=history, varThreshold=var_threshold, detectShadows=detect_shadows
)
```
Method `.detect(frame)`:
- Menerapkan subtractor pada frame.
- Melakukan morphological operations untuk menghilangkan noise.
- Menemukan contour pada mask.
- Mengembalikan list bounding box dari gerakan yang signifikan.

### Object Detection (object_detection.py)

MobileNet SSD adalah model Caffe untuk 20 kelas umum.
Method `.detect(frame)`:
- Membuat “blob” dari frame: `cv2.dnn.blobFromImage(...)`.
- `self.net.setInput(blob)` → `self.net.forward()`.
- Loop setiap detection di output net, jika confidence > threshold, simpan bounding box + nama class.

### Integrasi (main.py)

- Membuka VideoCapture.
- Looping frame → jalankan `MotionDetector.detect(...)`.
- Jika ada gerakan, panggil `ObjectDetector.detect(...)`.
- Gambar bounding box & label di frame, tampilkan dengan `cv2.imshow`.

## Pengembangan Lanjutan

- **Event-based recording**: Jalankan FFmpeg/penulisan file saat ada motion.
- **Notifikasi**: Kirim push notif/email bila “person” terdeteksi.
- **Web Dashboard**: Streaming frame ke halaman web dengan Flask/WebSocket.
- **Database**: Simpan log deteksi ke SQLite/MySQL beserta timestamp.

## Referensi & Resource

- **OpenCV DNN**: [OpenCV DNN module documentation](https://docs.opencv.org/master/d6/d0f/group__dnn.html)
- **MobileNet SSD**: [MobileNet-SSD (original repo)](https://github.com/chuanqi305/MobileNet-SSD)
- **Background Subtraction**: [OpenCV BackgroundSubtractor Docs](https://docs.opencv.org/master/d1/dc5/tutorial_background_subtraction.html)
