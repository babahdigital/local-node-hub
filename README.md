# Centralized LiveView and Log Management Hub (CLLMH)

CLLMH adalah sistem terpusat yang mengintegrasikan:

- Pemantauan CCTV berbasis gerakan.
- Pengelolaan log dari semua node.
- Penyimpanan video dan backup hanya ketika benar-benar diperlukan.
- Dashboard untuk monitoring status perangkat, analitik log, dan live stream.

## Konsep Utama Proyek

**Tujuan:**
- Efisiensi Backup:
    - Menggunakan Frame Differencing untuk mendeteksi gerakan pada CCTV.
    - Menghemat kapasitas HDD dengan merekam hanya saat ada aktivitas penting.
- Manajemen Log Terpusat:
    - Semua log dari node lokal dikirim ke pusat untuk analitik dan troubleshooting.
    - Menyediakan retry logic untuk menghindari kehilangan log.
- Monitoring dan Live Stream:
    - Memantau kapasitas HDD di node lokal.
    - Menyediakan live stream melalui DDNS dan kompatibilitas browser (opsional HLS).

## Struktur dan Komponen Proyek

| Komponen      | Fungsi                                                                      | Teknologi                                 |
|---------------|-----------------------------------------------------------------------------|-------------------------------------------|
| Node Lokal    | - Redirect RTSP ke pusat atau simpan backup lokal berdasarkan gerakan (Frame Differencing). | RTSP, DDNS MikroTik, FFmpeg, OpenCV       |
|               | - Monitoring kapasitas HDD dan pengelolaan file lama.                       | Flask, Psutil, Logrotate                  |
|               | - Pengelolaan log perangkat lokal (syslog-ng).                              | Syslog-ng, Python                         |
| Kantor Pusat  | - Menyediakan API terpusat untuk menerima data node.                        | Flask API, Google Cloud Run               |
|               | - Penyimpanan log untuk analitik dan troubleshooting.                       | Grafana Loki, Promtail, Elasticsearch     |
|               | - Menampilkan live stream, status perangkat, dan analitik log di dashboard. | Vue.js, Grafana                           |
| Live Stream   | - Redirect RTSP menggunakan DDNS atau konversi ke HLS jika diperlukan.      | RTSP, FFmpeg                              |
| Backup        | - Merekam video hanya saat gerakan atau objek terdeteksi (Frame Differencing + MobileNet). | OpenCV, TensorFlow, FFmpeg               |

## Struktur Folder Proyek

```
/home/abdullah/
├── api/                        # Backend API untuk komunikasi dengan pusat dan node
│   ├── config/                 # Konfigurasi Flask API
│   ├── app/                    # Aplikasi utama API
│   ├── tests/                  # Pengujian API
├── backup/                     # Skrip untuk backup RTSP stream
│   ├── scripts/                # Pipeline backup berbasis gerakan
│   ├── Dockerfile              # Dockerfile untuk kontainer backup
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
    - Jika gerakan terdeteksi, simpan segmen video menggunakan FFmpeg.
- **Opsional: Jalankan MobileNet:**
    - Deteksi objek relevan seperti manusia atau kendaraan untuk menghindari penyimpanan gerakan yang tidak penting.
- **Simpan Segmen Video:**
    - Segmen video disimpan di node lokal atau langsung dikirim ke pusat.

### 2. Workflow Log dan Monitoring

- **Node Lokal:**
    - **Syslog-ng:**
        - Mengelola log dari perangkat seperti NVR, MikroTik, dan aplikasi lokal.
        - Mengirim log ke pusat menggunakan TCP/UDP.
    - **Monitoring HDD:**
        - Memantau kapasitas disk.
        - Menghapus file lama jika kapasitas hampir penuh.
- **Kantor Pusat:**
    - **Promtail:**
        - Membaca log dari syslog-ng dan mengirimkannya ke Grafana Loki.
    - **Grafana:**
        - Menampilkan log berbasis waktu untuk analitik dan troubleshooting.

### 3. Workflow Live Stream

- **Redirect RTSP Stream:**
    - Gunakan DDNS MikroTik untuk mengakses RTSP stream dari NVR/DVR.
- **Kompatibilitas Browser (Opsional):**
    - Konversi stream RTSP ke HLS menggunakan FFmpeg jika diperlukan.

## Model Transaksi

| Transaksi       | Deskripsi                                                   | Aktivitas                                |
|-----------------|-------------------------------------------------------------|------------------------------------------|
| Backup Stream   | Node lokal merekam segmen video berbasis gerakan.           | Frame Differencing, FFmpeg               |
| Log Management  | Node lokal mengirim log ke pusat untuk analitik.            | Syslog-ng, Promtail                      |
| Monitoring HDD  | Node lokal memantau kapasitas disk dan menghapus file lama secara otomatis. | Psutil, Flask API                        |
| Live Stream     | Stream RTSP diteruskan ke pusat untuk monitoring.           | RTSP, DDNS MikroTik                      |
| Analitik di Pusat | Pusat mengelola data dari semua node dan menampilkannya di dashboard. | Grafana Loki, Elasticsearch, Vue.js      |

## Kebutuhan Infrastruktur

| Komponen      | Kebutuhan Teknis                                               |
|---------------|----------------------------------------------------------------|
| Node Lokal    | - DVR/NVR dengan RTSP dan MikroTik dengan DDNS.                |
|               | - Kontainer untuk Frame Differencing dan monitoring HDD.       |
| Kantor Pusat  | - Server untuk Grafana Loki, Promtail, dan Elasticsearch.      |
|               | - Backend Flask API dan Vue.js untuk dashboard.                |

Dengan pendekatan ini, pengawasan CCTV menjadi efisien, log terpusat, dan manajemen kapasitas HDD lebih mudah.