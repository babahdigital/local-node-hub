# Centralized LiveView and Log Management Hub (CLLMH)

CLLMH mengintegrasikan pemantauan CCTV berbasis gerakan dengan pengelolaan log terpusat. Sistem ini memudahkan pemantauan kapasitas HDD, penyimpanan video hanya ketika benar-benar diperlukan, serta konsolidasi log untuk analitik dan troubleshooting.

## Konsep Utama Proyek

**Tujuan:**
- Mengelola stream CCTV dengan backup berbasis gerakan.
- Memonitor kapasitas HDD dan menghapus file lama saat penuh.
- Menyediakan dashboard terpusat untuk analitik log dan live stream.

## Arsitektur dan Komponen Proyek

| Komponen      | Fungsi                                                                      | Teknologi                                 |
|---------------|-----------------------------------------------------------------------------|-------------------------------------------|
| Node Lokal    | - Meneruskan stream RTSP dan menyimpan backup lokal berdasarkan gerakan.     | RTSP, DDNS MikroTik, FFmpeg, OpenCV       |
|               | - Mengirim log aktivitas dan status HDD ke kantor pusat.                    | Syslog-ng, Flask, Python                  |
| Kantor Pusat  | - Menyimpan log untuk analitik dan monitoring.                              | Grafana Loki, Promtail, Elasticsearch     |
|               | - Menampilkan live stream dan status perangkat di dashboard.               | Flask API, Vue.js, Google Cloud Run       |
| Live Stream   | - Memberikan akses RTSP melalui DDNS atau konversi HLS untuk browser.       | RTSP, FFmpeg, HLS                         |
| Backup        | - Merekam segmen video berbasis gerakan/objek penting (MobileNet).          | OpenCV, TensorFlow, FFmpeg               |
| Log & Monitor | - Menjalankan retry logic jika backup gagal dan memonitor kapasitas HDD.    | Flask, Python, Syslog-ng, Logrotate       |

## Node Lokal

- **RTSP NVR/DVR**: Mengirim live stream CCTV ke pusat melalui MikroTik (DDNS).  
- **hdd-monitor (Flask)**: Memonitor kapasitas HDD dan menghapus file lama saat hampir penuh.  
- **syslog-ng**: Mengirim log penting (NVR, perangkat jaringan) ke pusat.  
- **Deteksi Gerakan (OpenCV)**: Hanya merekam saat ada aktivitas (frame differencing/object detection).  

## Kantor Pusat

- **Backend API (Flask)**: Menerima data node, menyimpan di database, menyediakan endpoint untuk dashboard.  
- **Logging & Analitik (Grafana Loki/Elasticsearch)**: Mengolah log dari semua node, visualisasi di Grafana.  
- **Deployment (Google Cloud Run)**: Menjalankan Flask+Vue.js sebagai layanan terpusat.  

## Dashboard Monitoring

- **Vue.js**: Menampilkan status perangkat, kapasitas HDD, dan live stream.  
- **Grafana**: Menyediakan fitur analitik log real-time.  
- **HLS Player**: Memutar stream hasil konversi RTSP (opsional) untuk kompatibilitas browser.  

## Struktur Folder Proyek

```
/home/abdullah/
├── api/               # Backend API (Flask)
├── backup/            # Skrip backup RTSP
├── config/            # Pengaturan umum
├── doc/               # Dokumentasi
├── hdd/               # Monitoring HDD
├── syslog/            # Konfigurasi syslog-ng
├── README.md
├── LICENSE
└── docker-compose.yml
```

## Alur Implementasi Singkat

1. **Konfigurasi Node Lokal**  
    - Atur syslog-ng untuk mengirim log ke pusat.  
    - Terapkan deteksi gerakan berbasis OpenCV dan backup via FFmpeg.  

2. **Kantor Pusat**  
    - Terima log dengan syslog-ng, proses dengan Promtail, simpan di Grafana Loki.  
    - Sediakan API Flask untuk data node (status HDD, live stream).  

3. **Dashboard (Vue.js + Grafana)**  
    - Tampilkan live stream RTSP/HLS, ringkasan log, dan status HDD.  
    - Berikan analitik log real-time menggunakan query ke Grafana Loki.  

4. **Maintenance**  
    - Gunakan Logrotate untuk menjaga ukuran file log.  
    - Lakukan retry otomatis jika backup gagal.  

Dengan pendekatan ini, pengawasan CCTV menjadi efisien, log terpusat, dan manajemen kapasitas HDD lebih mudah.
