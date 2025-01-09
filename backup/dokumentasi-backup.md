# Dokumentasi Lengkap CCTV AI Recording

## 1. Latar Belakang dan Tujuan

### Kebutuhan Sistem CCTV Modern

- **Efisiensi Storage**: Hanya merekam saat ada kejadian penting (motion/object).
- **Pendeteksian Cerdas**: Mampu mengenali objek seperti person, car, motor untuk meminimalisasi false alarm.
- **Validasi Kualitas Rekaman**: Menjamin rekaman tidak blank (black screen) ataupun freeze.
- **Penghematan CPU**: Sistem bisa menangani banyak channel secara paralel.

### Permasalahan & Solusi

- Sebelumnya, CPU usage tinggi saat melakukan object detection di semua frame resolusi tinggi.
- Diperlukan dual-stream (subtype=1 resolusi rendah untuk analisis, subtype=0 resolusi tinggi untuk perekaman) agar CPU tetap adem.
- Diperlukan freeze/black check di main-stream untuk memastikan hasil rekaman tidak rusak.
- Tuning parameter (seperti MOTION_TIMEOUT, POST_MOTION_DELAY) agar perekaman tidak berhenti cepat dan mengurangi insiden terlewat.

## 2. Arsitektur dan Alur Proses

### 2.1 Arsitektur Tingkat Tinggi

- **NVR/Kamera** menyediakan 2 stream per channel:
    - Main-stream (subtype=0): resolusi penuh (Full HD/4K) untuk perekaman.
    - Sub-stream (subtype=1): resolusi lebih rendah untuk analisis gerakan/objek.
- **Script main.py (Inti Sistem)**:
    - Membaca ENV (konfigurasi) → memulai thread per channel.
    - Validasi freeze/black untuk main-stream sebelum pipeline.
    - Menentukan pipeline sesuai mode: full, motion, motion_obj, atau motion_obj_dual.
    - motion_obj_dual menggunakan sub-stream untuk analisis dan main-stream untuk merekam.

#### Pipeline (contoh pipeline_motion_dual):

- Membuka sub-stream untuk motion/object detection (CPU ringan).
- Jika motion + objek relevan terdeteksi, rekam main-stream.
- Berhenti merekam setelah tidak ada gerakan melebihi MOTION_TIMEOUT + POST_MOTION_DELAY.

#### Perekaman dilakukan dengan:

- **FFmpeg**: -c copy menyalin RTSP ke file MKV tanpa re-encode.
- **Rolling segment**: ‘MAX_RECORD‘ untuk mode motion, ‘CHUNK_DURATION‘ untuk mode full.

#### Parameter (ENV) dapat di-tweak untuk:

- **Frame skip (FRAME_SKIP)**: melewatkan frame untuk analisis.
- **Downscale ratio (DOWNSCALE_RATIO)**: mengecilkan resolusi sebelum analisis.
- **Confidence threshold object detection (CONF_PERSON, dsb.)**.
- **MOTION_TIMEOUT, POST_MOTION_DELAY** agar perekaman tidak langsung berhenti saat masih ada orang.

### 2.2 Alur Detil “Dual-Stream”

- thread_for_channel → cek freeze/black di main-stream.
- Jika lolos, panggil pipeline_motion_dual:
    - Buka sub-stream (subtype=1) via OpenCV.
    - Jalankan motion detection + object detection.
    - Jika ada gerakan dan objek (contoh “person”), panggil MotionSession.start_record() di main-stream.
    - Stop rekaman saat idle melebihi ‘MOTION_TIMEOUT + POST_MOTION_DELAY‘.

#### Keuntungan:

- Analisis (paling berat) di resolusi lebih kecil (sub-stream).
- Rekaman tetap resolusi penuh (main-stream).
- CPU usage jauh turun, sistem bisa menangani banyak channel.

## 3. Dokumentasi Script main.py & ENV

### 3.1 Struktur Script main.py

- **Import & Setup**:
    - Import library: cv2, subprocess, dsb.
    - Baca ENV: BACKUP_MODE, FRAME_SKIP, dsb.
- **Utility Freeze/Black**:
    - check_black_frames(rtsp_url, ...) memanggil FFmpeg blackdetect.
    - check_freeze_frames(rtsp_url, ...) memanggil FFmpeg freezedetect.
- **Class: FullBackupSession, MotionSession**:
    - Masing-masing mendefinisikan start_record() atau start_chunk() untuk perekaman FFmpeg.
- **Fungsi Pipeline**:
    - pipeline_full: Rekam terus, rolling CHUNK_DURATION.
    - pipeline_motion: Rekam saat motion saja.
    - pipeline_motion_dual: Buka sub-stream (analisis), rekam main-stream.
- **thread_for_channel(ch, config)**:
    - Cek freeze/black main-stream (skip jika belum interval).
    - Jalankan pipeline sesuai BACKUP_MODE.
- **run_pipeline_loop()**:
    - Loop per channel (1..CHANNEL_COUNT) atau sesuai TEST_CHANNEL.
    - Menjalankan thread_for_channel di thread terpisah.
    - Mengulangi tiap CHECK_INTERVAL jika LOOP_ENABLE=true.

### 3.2 Environment Variables

| Nama                  | Fungsi                                           | Contoh Nilai |
|-----------------------|--------------------------------------------------|--------------|
| RTSP_SUBTYPE          | 0 = main-stream, 1 = sub-stream                  | 0            |
| BACKUP_MODE           | {full, motion, motion_obj, motion_obj_dual}      | motion_obj_dual |
| FRAME_SKIP            | 1 dari N frame yang dianalisis                   | 8            |
| DOWNSCALE_RATIO       | Mengecilkan resolusi sebelum deteksi             | 0.4          |
| MOTION_SLEEP          | Jeda (detik) per loop analisis                   | 0.3          |
| MOTION_TIMEOUT        | Batas idle gerakan sebelum stop                  | 20           |
| POST_MOTION_DELAY     | Tambahan jeda, total idle = MOTION_TIMEOUT + POST_DELAY | 20           |
| ENABLE_FREEZE_CHECK   | Cek freeze (true/false)                          | true         |
| ENABLE_BLACKOUT       | Cek black screen (true/false)                    | true         |
| FREEZE_BLACK_INTERVAL | Interval skip freeze/black check (detik)         | 1800         |
| CONF_PERSON           | Confidence threshold untuk person                | 0.8          |
| MOTION_AREA_THRESHOLD | Batas area gerakan min (piksel)                  | 5000 (opsional) |

## 4. Validasi Freeze/Black

### Proses

- Sebelum pipeline, script memanggil check_black_frames() dan check_freeze_frames() pada main-stream.
- Memakai FFmpeg filter:
    - blackdetect => mendeteksi blank
    - freezedetect => mendeteksi freeze
- FREEZE_BLACK_INTERVAL menghindari check setiap loop (mis. sekali 30 menit).

### Tujuan

- Menjamin perekaman tidak menghasilkan file yang isinya freeze atau blank.
- Jika freeze/black, channel di-skip (tidak merekam).

## 5. Motion & Object Detection

### 5.1 Motion Detection (MOG2)

- motion_detection.py menggunakan cv2.createBackgroundSubtractorMOG2.
- Parameter area_threshold, history, varThreshold, dsb. bisa diatur via ENV.
- Hanya frame yang melebihi area_threshold gerakan akan dianggap motion.

### 5.2 Object Detection (MobileNet SSD)

- object_detection.py memuat model Caffe MobileNet-SSD:
    - Label: “person”, “car”, “motorbike”, dsb.
    - Threshold ENV: CONF_PERSON=0.8, CONF_CAR=0.5, CONF_MOTOR=0.5.
- Dipanggil jika BACKUP_MODE adalah motion_obj atau motion_obj_dual.
- Object detection mempersempit perekaman hanya jika motion + objek ditemukan.

## 6. Optimasi CPU: Dual Stream

### Menghemat CPU

- Sub-stream (resolusi lebih rendah) untuk analisis motion/object.
- Menghindari decode resolusi tinggi yang sangat memberatkan.

### Tetap Rekam Resolusi Tinggi

- Hasil perekaman main-stream (subtype=0) dilakukan -c copy, tanpa re-encode.

### Pipeline motion_obj_dual

- Sub-stream => cap_sub.read() → motion + object detect.
- Jika ada gerakan/objek => panggil MotionSession.start_record() ke main-stream.
- Efek: CPU usage “adem”, tetapi kualitas rekaman tetap optimal.

## 7. Tuning untuk Mengurangi Sinyal Palsu & Tidak Memotong Rekaman Terlalu Cepat

- Naikkan CONF_PERSON ke 0.75–0.8 → Kurangi false alarm deteksi orang.
- Perbesar area_threshold di motion detection (mis. 5000) → Abaikan gerakan kecil (ranting, kucing).
- Perpanjang perekaman → MOTION_TIMEOUT=20, POST_MOTION_DELAY=20 → perekaman baru stop 40 detik setelah gerakan benar-benar hilang.

## 8. Hasil Akhir & Kesimpulan Percakapan

- **CPU Usage Sangat Rendah (“adem”)**:
    - Karena sub-stream + frame skipping + downscale.
- **Freeze/Black Check di main-stream**:
    - Memastikan rekaman tidak rusak.
- **Motion/Object Detection**:
    - Menghindari perekaman nonstop, hemat storage.
    - Dapat di-tune agar lebih selektif (kurangi sinyal palsu).
- **Dokumentasi & ENV**:
    - Memudahkan penyesuaian parameter tanpa perlu mengubah kode sumber.

### Rangkuman Percakapan:

- Kita mulai dari mode perekaman “motion” dan “object detection” yang memakan CPU tinggi.
- Dikembangkanlah “dual-stream” untuk analisis sub-stream, sehingga CPU usage turun drastis.
- Freeze/black check tetap di main-stream agar rekaman pasti valid.
- Tuning threshold (CONF_PERSON), MOTION_TIMEOUT, dsb. untuk menyeimbangkan false alarm vs. coverage.
- Akhirnya, sistem benar-benar “adem” (CPU > 95% idle) dan tetap memenuhi kebutuhan CCTV AI.

## 9. Penutup

Dokumentasi ini menjabarkan keseluruhan konsep, arsitektur, dan cara kerja script perekaman CCTV berbasis AI. Dengan pengaturan dual-stream, freeze/black check, motion/object detection, serta parameter ENV yang luwes, sistem ini mampu menghemat storage, mencegah false alarm, memastikan rekaman tidak rusak, dan menjaga CPU usage tetap rendah.

Selamat mengoperasikan sistem CCTV AI ini—semoga menjadi solusi andal untuk pengawasan, perekaman, dan analitik video cerdas.
