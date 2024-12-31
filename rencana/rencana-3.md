# Sistem Terdistribusi untuk Monitoring dan Backup CCTV dengan RTMP, Frame Differencing, MobileNet, Grafana Loki, dan Elasticsearch Ingest Node

## Tahap 1: Persiapan Infrastruktur

### Setup RTMP Server
1. Instal dan konfigurasikan Nginx RTMP untuk menerima stream RTSP dari kamera.
2. Tambahkan konfigurasi `nginx.conf` untuk distribusi RTMP.
3. Uji server RTMP:
    ```bash
    ffmpeg -i "rtsp://<camera-ip>/stream" -c copy -f flv rtmp://<server-ip>/live/channel1
    ```

### Instalasi Kontainer
1. Siapkan Docker Compose untuk menjalankan semua kontainer, termasuk RTMP server, Grafana Loki, Elasticsearch, dan Promtail.
2. Pastikan setiap kontainer memiliki akses ke direktori penting, seperti direktori backup dan log.

## Tahap 2: Implementasi Deteksi Gerakan

### Konfigurasi Frame Differencing
1. Gunakan OpenCV untuk menjalankan algoritma frame differencing pada stream RTMP.
2. Catat hasil deteksi dalam log lokal.

### Integrasi MobileNet
1. MobileNet digunakan untuk meningkatkan akurasi deteksi gerakan.
2. MobileNet lebih ringan dibandingkan YOLO dan cocok untuk deteksi aktivitas umum.

### Bandingkan MobileNet dengan YOLO
| Kriteria            | MobileNet     | YOLO                          |
|---------------------|---------------|-------------------------------|
| Kecepatan           | Sangat cepat  | Relatif lambat pada CPU       |
| Penggunaan Resource | Rendah        | Tinggi                        |
| Fokus Deteksi       | Aktivitas gerakan | Jenis objek spesifik (manusia, dll.) |
| Kapan Digunakan     | Ketika deteksi umum sudah memadai | Jika spesifikasi objek diperlukan |

## Tahap 3: Backup Otomatis dengan FFmpeg

### Implementasi Backup
1. Gunakan FFmpeg untuk menyimpan stream RTMP ke file lokal:
    ```bash
    ffmpeg -i rtmp://<server-ip>/live/channel1 -c copy -f mp4 /mnt/Data/Backup/Channel1_<timestamp>.mp4
    ```

### Optimasi Paralel Backup
1. Jalankan proses backup dalam batch untuk memaksimalkan throughput disk.

## Tahap 4: Monitoring dan Logging

### Grafana Loki untuk Monitoring Log
1. Gunakan Promtail untuk mengumpulkan log dari file Syslog atau aplikasi.
2. Contoh konfigurasi `promtail-config.yaml`:
    ```yaml
    server:
      http_listen_port: 9080
    clients:
      - url: http://loki:3100/loki/api/v1/push
    scrape_configs:
      - job_name: syslog
         static_configs:
            - targets:
                 - localhost
              labels:
                 job: syslog
                 __path__: /var/log/syslog-ng/*.log
    ```

### Elasticsearch Ingest Node untuk Analitik Log
1. Gunakan Elasticsearch Ingest Node untuk menyimpan dan memfilter log dengan pipeline sederhana.
2. Contoh pipeline:
    ```json
    {
      "description": "Pipeline untuk memfilter log",
      "processors": [
         {
            "grok": {
              "field": "message",
              "patterns": ["%{COMMONAPACHELOG}"]
            }
         }
      ]
    }
    ```

### Penggunaan Bersama Loki dan Elasticsearch
| Kriteria            | Grafana Loki  | Elasticsearch Ingest Node     |
|---------------------|---------------|-------------------------------|
| Hemat Resource      | Lebih hemat   | Lebih tinggi                  |
| Kompleksitas        | Rendah        | Sedang                        |
| Visualisasi         | Fokus pada log berbasis waktu | Mendukung analitik penuh |
| Transformasi Log    | Minimal       | Lebih kaya                    |

## Tahap 5: Pengujian dan Validasi Sistem

### Uji Stabilitas
1. Mulai dengan 4-8 channel, tingkatkan hingga 32 channel.

### Pengujian Beban
1. Simulasikan kondisi beban penuh dengan 32 stream aktif.
2. Pantau penggunaan CPU, RAM, dan throughput disk.

### Validasi Output
1. Periksa file backup dan log untuk memastikan format serta kualitas data.

## Tahap 6: Dokumentasi dan Pengelolaan

### Dokumentasi Sistem
1. Catat konfigurasi setiap kontainer dan pipeline log.
2. Buat diagram alur data.

### Manajemen Rotasi File
1. Tambahkan mekanisme penghapusan otomatis untuk file backup lama jika kapasitas disk penuh.

## Kelebihan Sistem
| Fitur               | Grafana Loki  | Elasticsearch Ingest Node     |
|---------------------|---------------|-------------------------------|
| Logging Sederhana   | Mendukung log berbasis waktu | Mendukung log kompleks |
| Resource Ringan     | Ya            | Tidak                         |
| Kemampuan Pencarian | Terbatas      | Full-text search              |
| Visualisasi         | Dashboard Grafana | Kibana (opsional)           |
| Pengembangan        | Cepat dan ringan | Fleksibel untuk jangka panjang |

## Rekomendasi
1. Gunakan Grafana Loki untuk monitoring log berbasis waktu dan resource minimal.
2. Tambahkan Elasticsearch Ingest Node untuk analitik log tingkat lanjut dan pencarian log yang kompleks.

Dengan langkah-langkah ini, sistem Anda dapat dikembangkan secara efisien untuk kebutuhan saat ini dan di masa depan.