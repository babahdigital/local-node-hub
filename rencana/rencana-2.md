# Sistem Terdistribusi untuk Monitoring dan Backup CCTV dengan RTMP, Frame Differencing, dan AI YOLO

## Struktur Pekerjaan Sistem Monitoring dan Backup CCTV

### Tahap 1: Persiapan Infrastruktur

1. **Setup RTMP Server**
    - Instal dan konfigurasikan Nginx RTMP untuk menerima stream RTSP dari kamera.
    - Buat konfigurasi `nginx.conf` untuk mendukung distribusi stream RTMP.
    - Uji RTMP server dengan mengirimkan stream RTSP dari kamera menggunakan FFmpeg:
      ```bash
      ffmpeg -i "rtsp://<camera-ip>/stream" -c copy -f flv rtmp://<server-ip>/live/channel1
      ```

2. **Instalasi Kontainer**
    - Buat dan jalankan semua kontainer dengan Docker Compose.
    - Pastikan setiap kontainer memiliki akses ke path yang dibutuhkan (e.g., direktori backup, konfigurasi log).

### Tahap 2: Implementasi Deteksi Gerakan

1. **Konfigurasi Frame Differencing**
    - Jalankan algoritma frame differencing pada semua stream RTMP.
    - Deteksi gerakan sederhana berdasarkan perubahan frame.
    - Catat hasil deteksi gerakan dalam log.

2. **Optimasi untuk Paralel**
    - Gunakan paralelisme untuk memproses banyak stream RTMP secara bersamaan (contoh: batch 8 channel per proses).

### Tahap 3: Deteksi Objek dengan YOLO

1. **Integrasi YOLO**
    - Gunakan YOLO untuk mendeteksi objek spesifik (manusia, kendaraan) pada stream yang lolos dari frame differencing.
    - Pastikan YOLO hanya memproses stream prioritas untuk menghemat resource.

2. **Pengujian dan Validasi**
    - Uji deteksi YOLO pada beberapa stream prioritas.
    - Catat hasil deteksi dan bandingkan dengan log frame differencing.

### Tahap 4: Backup Otomatis dengan FFmpeg

1. **Implementasi Backup**
    - Konfigurasikan FFmpeg untuk menyimpan stream RTMP yang telah lolos deteksi gerakan dan objek.
    - Simpan hasil dalam format MP4 atau MKV tanpa re-encoding untuk menghemat CPU:
      ```bash
      ffmpeg -i rtmp://<server-ip>/live/channel1 -c copy -f mp4 /mnt/Data/Backup/Channel1_2024-12-31_15-30-00.mp4
      ```

2. **Optimasi Paralel Backup**
    - Gunakan batch untuk menyimpan banyak stream secara paralel.
    - Pastikan disk throughput cukup untuk menangani semua stream.

### Tahap 5: Monitoring dan Logging

1. **Logging Aktivitas**
    - Catat hasil deteksi gerakan, deteksi objek, dan backup ke dalam log.
    - Pisahkan log berdasarkan kategori:
      - Log deteksi gerakan.
      - Log deteksi objek (YOLO).
      - Log hasil backup.

2. **Monitoring Kapasitas HDD**
    - Jalankan monitoring kapasitas HDD untuk direktori backup.
    - Kirimkan data kapasitas ke backend lokal.

3. **Integrasi dengan Backend**
    - Kirimkan log aktivitas dan kapasitas HDD ke backend lokal untuk pelaporan.
    - Pastikan semua data dapat diakses melalui API backend.

### Tahap 6: Pengujian dan Validasi Sistem

1. **Uji Stabilitas**
    - Jalankan sistem dengan 4-8 channel terlebih dahulu untuk menguji stabilitas.
    - Tingkatkan jumlah channel secara bertahap hingga mencapai 32 channel.

2. **Pengujian Beban**
    - Simulasikan kondisi beban penuh (32 stream aktif) dan catat penggunaan resource (CPU, RAM, disk throughput).
    - Lakukan optimasi jika diperlukan, seperti membatasi proses paralel.

3. **Validasi Output**
    - Periksa file backup untuk memastikan format, struktur direktori, dan kualitas file sesuai.
    - Validasi log untuk mendeteksi kesalahan atau anomali.

### Tahap 7: Dokumentasi dan Pengelolaan

1. **Dokumentasi Sistem**
    - Dokumentasikan konfigurasi setiap kontainer, termasuk parameter penting seperti path, port, dan log.
    - Buat diagram alur sistem untuk mempermudah pengelolaan di masa depan.

2. **Manajemen Rotasi File**
    - Tambahkan mekanisme untuk menghapus file backup lama secara otomatis jika kapasitas disk mendekati batas.

3. **Pengelolaan Skala**
    - Skalakan kontainer (misalnya YOLO AI Detector) jika diperlukan untuk mendukung lebih banyak channel prioritas.
    - Sesuaikan konfigurasi batch untuk menyeimbangkan beban sistem.

## Output Akhir

| Output              | Deskripsi                                                                 |
|---------------------|---------------------------------------------------------------------------|
| Stream Terdistribusi| Semua stream RTSP terhubung ke RTMP server.                               |
| Backup Selektif     | File backup dalam format MP4/MKV hanya dibuat jika gerakan atau objek tertentu terdeteksi. |
| Monitoring Terpusat | Semua aktivitas sistem, kapasitas HDD, dan hasil backup tercatat dalam log dan tersedia di backend lokal. |
| Sistem Skalabel     | Sistem mampu menangani hingga 32 channel dengan konfigurasi yang fleksibel dan efisien. |

Sistem Terdistribusi untuk Monitoring dan Backup CCTV dengan RTMP, Frame Differencing, dan AI YOLO

## Kesimpulan Sistem

Sistem ini dirancang untuk mendukung pengelolaan 32 channel CCTV dengan pendekatan yang efisien melalui kombinasi teknologi RTMP server, deteksi gerakan berbasis frame differencing, deteksi objek menggunakan AI YOLO, dan backup otomatis dengan FFmpeg. Sistem ini mampu:

- Mengelola Stream CCTV: RTMP server menerima dan mendistribusikan stream dari semua channel.
- Efisiensi Resource: Deteksi awal menggunakan frame differencing untuk mengurangi beban sistem.
- Deteksi Lanjutan: YOLO AI diterapkan untuk stream prioritas untuk mendeteksi objek tertentu (misalnya manusia atau kendaraan).
- Backup Otomatis: Stream yang relevan disimpan ke dalam format file MP4/MKV.
- Monitoring Terintegrasi: Status sistem (kapasitas HDD, keberhasilan backup, dll.) dikirimkan ke backend lokal untuk analisis dan pelaporan.

## Fungsi Setiap Kontainer

1. **RTMP Server**
    - Fungsi:
        - Menerima stream RTSP dari semua kamera.
        - Mengonversi RTSP ke RTMP untuk distribusi.
        - Menyediakan stream RTMP untuk konsumsi komponen lain (deteksi gerakan, AI, backup).
    - Teknologi:
        - Nginx dengan Modul RTMP.
    - Kebutuhan Resource:
        - Ringan, memerlukan sedikit CPU/RAM.

2. **Frame Differencing**
    - Fungsi:
        - Mendeteksi gerakan dasar pada stream RTMP menggunakan algoritma perbandingan frame.
        - Menyediakan hasil deteksi awal (gerakan ya/tidak) untuk diteruskan ke komponen selanjutnya.
    - Teknologi:
        - Python dengan OpenCV.
    - Kebutuhan Resource:
        - Sangat ringan, memproses hingga 32 stream dengan CPU rendah.

3. **YOLO AI Detector**
    - Fungsi:
        - Melakukan deteksi objek (manusia, kendaraan, dll.) pada stream yang lolos deteksi gerakan.
        - Memberikan keputusan apakah stream tersebut perlu di-backup atau tidak.
    - Teknologi:
        - Python dengan PyTorch dan YOLOv5 Nano.
    - Kebutuhan Resource:
        - Memerlukan CPU/GPU tergantung jumlah channel paralel.
        - Disarankan maksimal 4-8 channel untuk CPU, atau lebih jika menggunakan GPU.

4. **FFmpeg Backup**
    - Fungsi:
        - Menyimpan stream RTMP yang telah lolos dari deteksi gerakan dan deteksi objek.
        - Menghasilkan file backup dalam format MP4 atau MKV tanpa re-encoding.
    - Teknologi:
        - FFmpeg.
    - Kebutuhan Resource:
        - Sangat ringan, hanya membaca dan menulis data video tanpa proses encoding.

5. **Log & Monitoring**
    - Fungsi:
        - Mencatat aktivitas sistem (deteksi gerakan, deteksi objek, backup).
        - Memantau kapasitas HDD dan mengirimkan data ke backend lokal.
        - Memberikan laporan status sistem dan keberhasilan backup.
    - Teknologi:
        - Python dengan Flask dan Psutil.
    - Kebutuhan Resource:
        - Sangat ringan, hanya memproses data log dan monitoring.

## Implementasi dan Pengembangan

### Fokus Pengembangan Awal:
- Pastikan RTMP server berjalan stabil.
- Uji deteksi gerakan dan integrasi YOLO untuk stream prioritas.

### Skalabilitas:
- Tambahkan kontainer YOLO AI jika diperlukan lebih banyak deteksi paralel.
- Sesuaikan batas proses paralel di FFmpeg sesuai kapasitas sistem.

### Monitoring Berkelanjutan:
- Integrasikan log dan monitoring dengan dashboard backend lokal untuk analisis lebih lanjut.

Dengan dokumentasi ini, Anda dapat melanjutkan pengembangan dan pengelolaan sistem secara terstruktur.
