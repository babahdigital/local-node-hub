# Centralized LiveView and Log Management Hub (CLLMH)

CLLMH adalah sistem terpusat yang mengintegrasikan:

- Pemantauan CCTV berbasis gerakan menggunakan teknologi Frame Differencing dan MobileNet.
- Pengelolaan log dari semua node lokal dengan forwarding ke pusat untuk analitik.
- Penyimpanan video dan backup hanya saat diperlukan, menghemat kapasitas HDD.
- Dashboard untuk memantau status perangkat, analitik log, dan live stream.

## Konsep Utama Proyek

**Tujuan:**
- **Efisiensi Backup:**
    - Menggunakan Frame Differencing untuk mendeteksi gerakan pada CCTV.
    - Mengintegrasikan MobileNet untuk mendeteksi objek spesifik seperti manusia dan kendaraan.
    - Menghemat kapasitas HDD dengan merekam hanya aktivitas penting.
- **Manajemen Log Terpusat:**
    - Semua log dari node lokal dikirim ke pusat untuk analitik dan troubleshooting.
    - Menyediakan retry logic untuk mencegah kehilangan log jika terjadi kegagalan jaringan.
- **Monitoring dan Live Stream:**
    - Memantau kapasitas HDD di node lokal dan mengelola file lama secara otomatis.
    - Menyediakan live stream melalui DDNS MikroTik dengan opsi konversi ke HLS untuk kompatibilitas browser.

## Struktur dan Komponen Proyek

| Komponen      | Fungsi                                                                      | Teknologi                                 |
|---------------|-----------------------------------------------------------------------------|-------------------------------------------|
| Node Lokal    | - Redirect RTSP ke pusat atau simpan backup lokal berbasis gerakan.         | RTSP, DDNS MikroTik, FFmpeg, OpenCV, TensorFlow |
|               | - Monitoring kapasitas HDD dan pengelolaan file lama.                       | Flask, Psutil, Logrotate                  |
|               | - Pengelolaan log perangkat lokal.                                          | Syslog-ng, Python                         |
| Kantor Pusat  | - Menyediakan API terpusat untuk menerima data dari node.                   | Flask API, Promtail, Grafana Loki         |
|               | - Penyimpanan log untuk analitik dan troubleshooting.                       | Grafana Loki, Promtail, Elasticsearch     |
|               | - Menampilkan live stream, status perangkat, dan analitik log di dashboard. | Vue.js, Grafana                           |
| Backup        | - Merekam video hanya saat gerakan atau objek terdeteksi.                   | OpenCV, TensorFlow, FFmpeg                |
| Live Stream   | - Redirect RTSP menggunakan DDNS atau konversi ke HLS jika diperlukan.      | RTSP, FFmpeg                              |

## Struktur Folder Proyek

```
/home/abdullah/
├── api/                        # Backend API untuk komunikasi dengan pusat dan node
│   ├── config/                 # Konfigurasi Flask API
│   ├── app/                    # Aplikasi utama API
│   ├── tests/                  # Pengujian API
├── backup/                     # Skrip untuk backup RTSP stream
│   ├── scripts/                # Pipeline backup berbasis gerakan dan MobileNet
│   │   ├── frame_differencing.py   # Script utama untuk Frame Differencing
│   │   ├── mobilenet.py            # Script utama untuk MobileNet
│   │   ├── report_manager.py       # Script untuk pengelolaan pelaporan ke backend
│   │   ├── validate_cctv.py        # Script untuk validasi RTSP stream
│   ├── backup_manager.py           # Script utama untuk orchestrasi backup
│   ├── Dockerfile                  # Dockerfile untuk kontainer backup
├── config/                     # Pengaturan umum proyek
│   ├── log_messages.json       # Pesan log dinamis
│   ├── syslog/                 # Konfigurasi syslog-ng di node lokal
├── doc/                        # Dokumentasi proyek
├── hdd/                        # Monitoring HDD
│   ├── hdd_monitor.py          # Monitoring HDD dan pengelolaan file lama
│   ├── Dockerfile              # Dockerfile untuk kontainer monitoring HDD
├── syslog/                     # Konfigurasi syslog-ng untuk node lokal
│   ├── syslog-ng.conf          # Konfigurasi utama syslog-ng
│   ├── logrotate.conf          # Rotasi log untuk menghemat disk
├── ai/                         # Direktori baru untuk model AI dan skrip pendukung
│   ├── models/                 # Folder untuk menyimpan model MobileNet
│   │   ├── mobilenet_v2.tflite # File model MobileNet dalam format TensorFlow Lite
│   ├── inference.py            # Script inferensi untuk MobileNet
│   ├── requirements.txt        # Dependensi AI (TensorFlow Lite, NumPy, dll.)
│   ├── Dockerfile              # Dockerfile untuk kontainer AI (opsional jika terpisah)
├── scripts/                    # Folder untuk utility scripts
│   ├── utils.py                # Fungsi pendukung umum untuk seluruh proyek
├── README.md                   # Deskripsi proyek
├── LICENSE                     # Lisensi proyek
└── docker-compose.yml          # File utama Docker Compose
```

## Workflows dan Model Transaksi

### 1. Workflow Backup Berdasarkan Gerakan

- **Ambil Stream RTSP dari NVR/DVR:**
    - Stream diteruskan ke node lokal melalui DDNS MikroTik.
- **Jalankan Frame Differencing:**
    - Deteksi gerakan menggunakan OpenCV.
- **Opsional: Jalankan MobileNet:**
    - Deteksi objek penting seperti manusia atau kendaraan.
- **Simpan Segmen Video:**
    - Segmen video disimpan di node lokal atau dikirim ke pusat menggunakan FFmpeg.

### 2. Workflow Log dan Monitoring

- **Node Lokal:**
    - **Syslog-ng:**
        - Mengelola log dari perangkat seperti NVR dan MikroTik, lalu mengirimnya ke pusat.
    - **Monitoring HDD:**
        - Memantau kapasitas disk dan menghapus file lama jika penuh.
- **Kantor Pusat:**
    - **Promtail:**
        - Membaca log dari Syslog-ng dan mengirimkan ke Grafana Loki.
    - **Grafana:**
        - Menampilkan log berbasis waktu untuk analitik dan troubleshooting.

### 3. Workflow Live Stream

- **Redirect RTSP Stream:**
    - Gunakan DDNS MikroTik untuk mengakses RTSP stream dari NVR/DVR.
- **Kompatibilitas Browser (Opsional):**
    - Konversi stream RTSP ke HLS menggunakan FFmpeg jika diperlukan.

## Kebutuhan Infrastruktur

| Komponen      | Kebutuhan Teknis                                               |
|---------------|----------------------------------------------------------------|
| Node Lokal    | - DVR/NVR dengan RTSP dan MikroTik dengan DDNS.                |
|               | - Kontainer untuk Frame Differencing, MobileNet, dan monitoring HDD. |
| Kantor Pusat  | - Server untuk Grafana Loki, Promtail, dan Elasticsearch.      |
|               | - Backend Flask API dan Vue.js untuk dashboard.                |

## Masukan untuk Pengembangan

- **Optimasi Pipeline Backup:**
    - Gunakan Frame Differencing untuk memfilter frame sebelum menjalankan MobileNet.
    - Backup hanya dilakukan jika gerakan dan objek penting terdeteksi.
- **Keamanan API:**
    - Batasi akses API dengan IP whitelist dan autentikasi sederhana.
- **Retensi Log:**
    - Terapkan kebijakan retensi log berdasarkan prioritas (misalnya, log kritis disimpan lebih lama).

Dengan struktur ini, sistem dapat memanfaatkan teknologi seperti OpenCV, TensorFlow Lite, dan FFmpeg secara efisien untuk memenuhi kebutuhan pengawasan dan pengelolaan log terpusat.
