# Arsitektur Proyek

## Komponen Utama

### Node Lokal (Site/Client)

**Fungsi:**
- Mengelola stream CCTV (NVR/DVR).
- Mengumpulkan status perangkat dan log.
- Meneruskan data ke kantor pusat.

**Teknologi:**
- NVR/DVR (RTSP).
- MikroTik (DDNS, port forwarding).
- hdd-monitor (Python Flask API untuk monitoring HDD).
- syslog-ng (Centralized logging).

### Kantor Pusat (Pusat Data)

**Fungsi:**
- Mengelola semua data dari node lokal.
- Menyediakan dashboard terpusat untuk monitoring dan analitik.

**Teknologi:**
- Backend: Flask + REST API.
- Frontend: Vue.js.
- Deployment: Cloud Run (Google Cloud).
- Logging: Grafana Loki atau Elasticsearch.

### Dashboard Monitoring

**Fungsi:**
- Menampilkan informasi perangkat, status, dan live stream dari semua node.
- Memberikan analitik log dan status perangkat.

**Teknologi:**
- Vue.js (Frontend).
- HLS Player untuk live stream.
- API Flask untuk pengelolaan data.

## Diagram Arsitektur

```
+-----------------------------------+
|         Dashboard Pusat           |
|    Flask API + Vue.js Frontend    |
|           (Cloud Run)             |
|                                   |
+------------------+----------------+
                   ^
                   | Data & Log (HTTP API)
                   |
+------------------v----------------+
|           Kantor Pusat            |
|  Grafana Loki / Elasticsearch     |
|  Logging dan Analitik             |
+------------------+----------------+
                   ^
   Data API & Stream | RTSP via DDNS
                   |
    +--------------v---------------+
    |        Node Lokal (1-n)      |
    | +--------------------------+ |
    | |  NVR/DVR (RTSP Streams)  | |
    | +--------------------------+ |
    | |  MikroTik (DDNS + NAT)   | |
    | +--------------------------+ |
    | |  hdd-monitor + API       | |
    | +--------------------------+ |
    | |  syslog-ng + Logrotate   | |
    | +--------------------------+ |
    +------------------------------+
```

## Teknologi yang Digunakan

### a. Node Lokal

**NVR/DVR (RTSP Streams):**
- Protokol: RTSP.
- Kegunaan: Mengirimkan live stream CCTV ke kantor pusat melalui MikroTik.

**MikroTik DDNS:**
- Layanan: MikroTik Cloud DDNS.
- Kegunaan: Memastikan koneksi stabil meskipun menggunakan IP publik dinamis.

**hdd-monitor:**
- Teknologi: Python, Flask API.
- Fungsi:
  - Memantau kapasitas HDD lokal.
  - Menghapus file backup lama.
  - Mengirim status HDD ke kantor pusat.

**syslog-ng:**
- Fungsi:
  - Mengelola log dari NVR/DVR, MikroTik, dan sistem lokal lainnya.
  - Mengirimkan log ke kantor pusat.

### b. Kantor Pusat

**Backend API:**
- Teknologi: Flask, Python.
- Fungsi:
  - Mengelola data node lokal.
  - Menyediakan endpoint API untuk dashboard dan log monitoring.
  - Menyimpan data di database (PostgreSQL/Firestore).

**Logging dan Analitik:**
- Grafana Loki:
  - Untuk mengelola log berbasis waktu dari node.
  - Visualisasi log dengan Grafana.
- Elasticsearch:
  - Analitik log lanjutan (opsional).

**Cloud Deployment:**
- Google Cloud Run:
  - Menjalankan Flask API dan Vue.js sebagai layanan cloud.

### c. Dashboard Monitoring

**Frontend:**
- Teknologi: Vue.js.
- Fitur:
  - Menampilkan live stream dari node (RTSP via HLS Player).
  - Menampilkan status perangkat dan analitik log.

**Live Stream:**
- Teknologi:
  - RTSP langsung dari DDNS.
  - HLS Player untuk kompatibilitas browser.

**Deployment:**
- Google Cloud Run:
  - Menyediakan akses ke frontend dan backend secara global.

## Konsep Pengelolaan Node dan Pusat

### a. Pengiriman Data dari Node ke Pusat

Node lokal mengirim data status, log, dan informasi live stream ke API pusat menggunakan HTTP POST secara periodik.

**Contoh:**
```json
{
  "node_id": "lokasi1",
  "streams": [
    "rtsp://abcdefg123456.sn.mynetname.net:554/cam/realmonitor?channel=1"
  ],
  "status": {
    "hdd": "80%",
    "uptime": "72h"
  },
  "log": "Log terakhir dari syslog-ng"
}
```

### b. Manajemen di Kantor Pusat

- Flask API menyimpan data setiap node ke database.
- Data ini ditampilkan di dashboard dengan Vue.js.

### c. Live Stream Management

- Stream RTSP langsung diakses melalui DDNS dan ditampilkan di dashboard.
- Tambahkan opsi konversi HLS jika diperlukan untuk kompatibilitas browser.

## Manfaat Solusi

**Efisiensi:**
- Menggunakan RTSP langsung tanpa perantara protokol tambahan.
- DDNS MikroTik meminimalkan overhead konfigurasi IP publik.

**Skalabilitas:**
- Sistem dapat berkembang dengan mudah untuk menambahkan lebih banyak node.
- Cloud Run memastikan skala otomatis untuk API dan dashboard.

**Sentralisasi:**
- Semua data, log, dan live stream dikelola di kantor pusat.
- Dashboard memberikan visibilitas lengkap ke seluruh sistem.

## Konsep Logging dan Analitik di Pusat

### 1. Pengelolaan Log di Node Lokal

**Node Lokal:**
- Menggunakan syslog-ng untuk mengelola log perangkat lokal (NVR, MikroTik, dan aplikasi seperti hdd-monitor).
- Log yang relevan dikirimkan ke kantor pusat menggunakan protokol syslog (UDP/TCP) pada port tertentu (e.g., 1514).

**Contoh log yang dikirim:**
- Aktivitas NVR/DVR.
- Status backup dan kapasitas HDD.
- Koneksi dan aktivitas MikroTik.

**Keuntungan:**
- Node lokal hanya mengelola log minimal, mengurangi beban analitik di sisi lokal.
- Semua log dikirimkan ke pusat untuk analitik lebih lanjut.

### 2. Pengelolaan Log di Kantor Pusat

**Koleksi Log dengan Grafana Loki:**
- Log dari semua node diterima oleh Grafana Loki di kantor pusat.
- Promtail digunakan untuk membaca log yang diterima oleh syslog-ng di kantor pusat dan mengirimkan ke Grafana Loki.

**Pipeline:**
```
Node Lokal → Syslog-ng (di pusat) → Promtail → Grafana Loki → Grafana Dashboard
```

**Konfigurasi Promtail:**

File `promtail-config.yaml`:
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
          job: "syslog-ng"
          __path__: "/mnt/Data/Syslog/**/*.log"
```

**Visualisasi dengan Grafana:**
- Tambahkan Grafana Loki sebagai data source.
- Buat panel log untuk memvisualisasikan log berdasarkan node, jenis log (e.g., RTSP, backup, MikroTik), atau level log (e.g., debug, error).

### 3. Arsitektur Terpusat

```
+-------------------+
| Kantor Pusat      |
|                   |
| +---------------+ |
| | Grafana       | | <--- Dashboard visualisasi log dari Grafana Loki
| +---------------+ |
|        |           |
| +---------------+  |
| | Grafana Loki  |  |
| +---------------+  |
|        |           |
| +---------------+  |
| | Promtail      |  | <--- Membaca log dari syslog-ng
| +---------------+  |
|        |           |
| +---------------+  |
| | Syslog-ng     |  | <--- Log dikumpulkan dari Node Lokal
| +---------------+  |
+-------------------+
```

### 4. Langkah Implementasi

#### a. Node Lokal

**Konfigurasi Syslog-ng untuk Mengirim Log ke Pusat:**

File `syslog-ng.conf` di node lokal:
```plaintext
destination d_remote {
  tcp("192.168.100.1" port(1514));
};

log {
  source(s_local);
  destination(d_remote);
};
```

**Filter Log di Node Lokal:**
- Pastikan hanya log penting yang dikirim ke pusat untuk mengurangi beban jaringan.

#### b. Kantor Pusat

**Konfigurasi Syslog-ng untuk Menerima Log:**

File `syslog-ng.conf` di pusat:
```plaintext
source s_network {
  network(
    ip("0.0.0.0")
    port(1514)
    transport("tcp")
  );
};

destination d_logs {
  file("/mnt/Data/Syslog/${HOST}/${YEAR}/${MONTH}/${DAY}.log"
       create-dirs(yes));
};

log {
  source(s_network);
  destination(d_logs);
};
```

**Setup Promtail untuk Membaca Log:**
- Gunakan konfigurasi `promtail-config.yaml` seperti di atas untuk membaca log dari `/mnt/Data/Syslog`.

**Setup Grafana Loki:**
- Jalankan Grafana Loki menggunakan Docker Compose:

```yaml
loki:
  image: grafana/loki:2.7.0
  container_name: loki
  ports:
    - "3100:3100"
  volumes:
    - ./loki-config.yaml:/etc/loki/local-config.yaml
```

**Visualisasi Log di Grafana:**
- Tambahkan Grafana Loki sebagai data source di Grafana.
- Buat panel log dengan query seperti:

```arduino
{job="syslog-ng"}
```

## Manfaat Pendekatan Ini

**Efisiensi Sentralisasi:**
- Node lokal hanya mengelola log dasar.
- Semua analitik log dilakukan di kantor pusat.

**Skalabilitas:**
- Menambah node baru hanya memerlukan konfigurasi syslog di node tersebut.

**Monitoring yang Kaya:**
- Grafana Dashboard memberikan visualisasi real-time log dari semua node.

## Teknologi Terkait

**Node Lokal:**
- Syslog-ng, Logrotate, Python/Flask (untuk status perangkat).

**Kantor Pusat:**
- Grafana Loki, Promtail, Grafana, dan Elasticsearch (opsional untuk analitik lebih mendalam).

**Frontend:**
- Vue.js dengan API dari Flask untuk menampilkan log summary dan live stream.