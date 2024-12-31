# Step-by-Step Implementation untuk Node Lokal

Berikut adalah langkah-langkah detail untuk memastikan semua komponen bekerja di node lokal, sesuai struktur proyek Anda:

## 1. Setup Server Stream Lokal

**Tujuan:** Menyiapkan server stream untuk menerima RTSP dari kamera dan menyediakan RTMP/HLS untuk analisis, live stream, dan logging.

### Langkah:

#### 1.1 Konfigurasi Server Stream:
- Siapkan konfigurasi RTMP di file `stream_server/nginx.conf` untuk menerima RTSP dan menyediakan RTMP/HLS.
- Tambahkan logging ke file `stream_server/nginx.conf` untuk mencatat status RTMP dan HLS.
- Simpan log di `/mnt/Data/Syslog/stream.log`.
- Pastikan port 1935 (RTMP) dan 8080 (HLS) sudah disiapkan di konfigurasi.

#### 1.2 Build Docker Image:
- Pastikan file `stream_server/Dockerfile` sudah sesuai untuk membangun image Docker server stream.

#### 1.3 Jalankan Server Stream:
- Jalankan server stream menggunakan docker-compose dan pastikan log dicatat di `/mnt/Data/Syslog/stream.log`.

#### 1.4 Uji Stream:
- Kirim RTSP dari kamera ke server stream.
- Pastikan stream dapat diakses melalui RTMP dan HLS secara lokal.

#### 1.5 Verifikasi Log Server Stream:
- Periksa file `/mnt/Data/Syslog/stream.log` untuk memastikan status stream tercatat.

## 2. Jalankan Backup Manager

**Tujuan:** Menyimpan video secara selektif berdasarkan analisis gerakan dan deteksi objek, sambil mencatat proses ke log.

### Langkah:

#### 2.1 Konfigurasi Backup Manager:
- Pastikan stream URL di `backup_manager.py` diatur ke RTMP server lokal.
- Gunakan pipeline Frame Differencing dan MobileNet di file `backup/scripts/frame_differencing.py` dan `backup/scripts/mobilenet.py`.
- Tambahkan logging di `backup_manager.py` untuk mencatat hasil analisis dan status backup ke `/mnt/Data/Syslog/backup.log`.

#### 2.2 Build Docker Image:
- Gunakan file `backup/Dockerfile` untuk membangun image Docker backup manager.

#### 2.3 Jalankan Backup Manager:
- Jalankan kontainer backup menggunakan docker-compose dan pastikan proses dicatat di `/mnt/Data/Syslog/backup.log`.

#### 2.4 Verifikasi Backup dan Log:
- Pastikan file backup tersimpan di direktori yang telah dikonfigurasi (misalnya, `/mnt/Data/Backup`).
- Periksa log di `/mnt/Data/Syslog/backup.log` untuk memastikan status backup tercatat.

## 3. Monitoring HDD Lokal

**Tujuan:** Memantau kapasitas disk, menghapus file lama jika hampir penuh, dan mencatat status kapasitas HDD ke log.

### Langkah:

#### 3.1 Konfigurasi HDD Monitor:
- Pastikan `hdd_monitor.py` sudah diatur untuk memantau disk lokal.
- Tentukan direktori untuk menyimpan log kapasitas HDD (misalnya, `/mnt/Data/Syslog`).
- Pastikan `hdd_monitor.py` sudah mencatat laporan kapasitas disk ke `/mnt/Data/Syslog/hdd.log`.

#### 3.2 Build Docker Image:
- Gunakan file `hdd/Dockerfile` untuk membangun image Docker monitoring HDD.

#### 3.3 Jalankan HDD Monitor:
- Jalankan kontainer HDD monitor menggunakan docker-compose dan pastikan log dicatat di `/mnt/Data/Syslog/hdd.log`.

#### 3.4 Verifikasi Laporan HDD:
- Periksa file `/mnt/Data/Syslog/hdd.log` untuk memastikan kapasitas disk tercatat.

## 4. Logging Status Kamera

**Tujuan:** Memantau status kamera (aktif atau mati) dan mencatat hasilnya ke log.

### Langkah:

#### 4.1 Tambahkan Validasi Kamera:
- Gunakan `validate_cctv.py` untuk memeriksa status kamera secara berkala.
- Simpan status kamera ke `/mnt/Data/Syslog/cctv_status.log`.

#### 4.2 Integrasikan ke Monitoring:
- Pastikan validasi kamera berjalan sebagai bagian dari pipeline backup manager atau sebagai proses terpisah.

#### 4.3 Verifikasi Log Kamera:
- Periksa file `/mnt/Data/Syslog/cctv_status.log` untuk memastikan status kamera tercatat.

## 5. Setup API Lokal

**Tujuan:** Menggabungkan laporan dari monitoring HDD, backup, status kamera, dan server stream ke dalam endpoint API lokal.

### Langkah:

#### 5.1 Konfigurasi Flask API:
- Tambahkan endpoint API `/status` di `api/app/` untuk menggabungkan data dari:
    - `/mnt/Data/Syslog/hdd.log`
    - `/mnt/Data/Syslog/backup.log`
    - `/mnt/Data/Syslog/cctv_status.log`
    - `/mnt/Data/Syslog/stream.log`

#### 5.2 Jalankan API Lokal:
- Jalankan API menggunakan Flask dan ekspos ke port lokal (misalnya, 5000).

#### 5.3 Verifikasi Endpoint API:
- Akses endpoint `/status` di browser atau curl untuk memastikan semua log tercantum dalam format JSON.

## Arsitektur Teknologi dengan Logging

| Komponen       | Fungsi                                               | Log File                        | Lokasi File                  | Teknologi                  |
|----------------|------------------------------------------------------|---------------------------------|------------------------------|----------------------------|
| Server Stream  | Menyediakan RTMP/HLS untuk live stream dan analisis backup. | `/mnt/Data/Syslog/stream.log`   | `stream_server/nginx.conf`   | Nginx RTMP, FFmpeg         |
| Backup Manager | Menganalisis gerakan dan objek untuk backup selektif. | `/mnt/Data/Syslog/backup.log`   | `backup/backup_manager.py`   | OpenCV, TensorFlow Lite    |
| HDD Monitor    | Memantau kapasitas disk dan menghapus file lama.     | `/mnt/Data/Syslog/hdd.log`      | `hdd/hdd_monitor.py`         | Psutil, Logrotate          |
| CCTV Status    | Memantau status kamera (aktif atau mati).            | `/mnt/Data/Syslog/cctv_status.log` | `backup/scripts/validate_cctv.py` | FFmpeg, Python             |
| Flask API      | Menggabungkan laporan HDD, backup, dan status kamera. | -                               | `api/app/`                   | Flask, Python              |

## Checklist Pengerjaan

| Langkah                              | Status |
|--------------------------------------|--------|
| 1. Konfigurasi server stream lokal   | ⬜      |
| 2. Build dan jalankan server stream  | ⬜      |
| 3. Test RTMP dan HLS                 | ⬜      |
| 4. Konfigurasi backup manager        | ⬜      |
| 5. Build dan jalankan backup manager | ⬜      |
| 6. Test backup selektif              | ⬜      |
| 7. Konfigurasi monitoring HDD        | ⬜      |
| 8. Build dan jalankan HDD monitor    | ⬜      |
| 9. Test laporan kapasitas HDD        | ⬜      |
| 10. Tambahkan logging status kamera  | ⬜      |
| 11. Verifikasi log kamera            | ⬜      |
| 12. Konfigurasi API lokal            | ⬜      |
| 13. Test endpoint API lokal          | ⬜      |

## Langkah Berikutnya

- Pastikan semua log dicatat ke `/mnt/Data/Syslog` untuk monitoring terpusat.
- Tambahkan dokumentasi detail untuk log format dan fungsionalitas di folder `doc/`.
- Uji integrasi penuh di lingkungan lokal sebelum dipindahkan ke server pusat.