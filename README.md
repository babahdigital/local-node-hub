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
- **Penggunaan Server Stream untuk Standby:**
    - RTSP dari kamera CCTV dikirimkan ke server stream (Nginx RTMP).
    - Server menyediakan RTMP/HLS untuk akses live stream kantor pusat dan analisis lokal.

## Struktur dan Komponen Proyek

| Komponen      | Fungsi                                                                      | Teknologi                                 |
|---------------|-----------------------------------------------------------------------------|-------------------------------------------|
| Node Lokal    | - Redirect RTSP ke pusat atau simpan backup lokal berbasis gerakan.         | RTSP, DDNS MikroTik, FFmpeg, OpenCV, TensorFlow Lite |
|               | - Monitoring kapasitas HDD dan pengelolaan file lama.                       | Flask, Psutil, Logrotate                  |
|               | - Pengelolaan log perangkat lokal.                                          | Syslog-ng, Python                         |
| Server Stream | - Menyediakan RTMP/HLS untuk live stream dan analisis backup.               | Nginx RTMP, FFmpeg                        |
| Kantor Pusat  | - Menyediakan API terpusat untuk menerima data dari node.                   | Flask API, Promtail, Grafana Loki         |
|               | - Penyimpanan log untuk analitik dan troubleshooting.                       | Grafana Loki, Promtail, Elasticsearch     |
|               | - Menampilkan live stream, status perangkat, dan analitik log di dashboard. | Vue.js, Grafana                           |
| Backup        | - Merekam video hanya saat gerakan atau objek terdeteksi.                   | OpenCV, TensorFlow Lite, FFmpeg           |
| Live Stream   | - Redirect RTSP menggunakan DDNS atau konversi ke HLS jika diperlukan.      | RTSP, FFmpeg, Nginx RTMP                  |

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
├── stream_server/              # Konfigurasi dan skrip untuk server stream
│   ├── nginx.conf              # Konfigurasi untuk Nginx RTMP
│   ├── Dockerfile              # Dockerfile untuk kontainer server stream
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

- **RTSP ke Server Stream:**
    - Kamera CCTV mengirim stream RTSP ke Nginx RTMP.
- **Frame Differencing:**
    - Mendeteksi gerakan pada stream RTMP.
- **MobileNet:**
    - Mendeteksi objek penting seperti manusia atau kendaraan.
- **Backup:**
    - Segmen video disimpan hanya jika objek penting terdeteksi.

### 2. Workflow Log dan Monitoring

- **Node Lokal:**
    - **Syslog-ng:**
        - Mengelola log dari perangkat seperti NVR dan MikroTik.
    - **Monitoring HDD:**
        - Memantau kapasitas disk dan menghapus file lama jika penuh.
- **Kantor Pusat:**
    - **Promtail:**
        - Membaca log dari Syslog-ng dan mengirimkan ke Grafana Loki.
    - **Grafana:**
        - Menampilkan log berbasis waktu untuk analitik dan troubleshooting.

### 3. Workflow Live Stream

- **RTSP ke RTMP/HLS:**
    - Nginx RTMP menyediakan link RTMP/HLS untuk kantor pusat.
- **Akses melalui DDNS Mikrotik:**
    - Link live stream dapat diakses oleh kantor pusat kapan saja.

## Kebutuhan Infrastruktur

| Komponen      | Kebutuhan Teknis                                               |
|---------------|----------------------------------------------------------------|
| Node Lokal    | - DVR/NVR dengan RTSP dan MikroTik dengan DDNS.                |
|               | - Kontainer untuk Frame Differencing, MobileNet, dan monitoring HDD. |
| Kantor Pusat  | - Server untuk Grafana Loki, Promtail, dan Elasticsearch.      |
|               | - Backend Flask API dan Vue.js untuk dashboard.                |

## Masukan untuk Pengembangan

- **Optimasi Backup:**
    - Gunakan Frame Differencing untuk memfilter frame sebelum menjalankan MobileNet.
    - Backup hanya dilakukan jika gerakan dan objek penting terdeteksi.
- **Keamanan Stream:**
    - Lindungi akses RTMP/HLS menggunakan autentikasi.
    - Gunakan protokol HTTPS untuk komunikasi yang aman.
- **Pengelolaan Log:**
    - Terapkan kebijakan retensi log berdasarkan prioritas (log kritis disimpan lebih lama).
    - Integrasikan log dari server stream ke pusat untuk monitoring.

Dengan struktur ini, sistem dapat memanfaatkan teknologi seperti OpenCV, TensorFlow Lite, dan FFmpeg secara efisien untuk memenuhi kebutuhan pengawasan dan pengelolaan log terpusat.
