# Step-by-Step Implementation untuk Node Lokal

Berikut adalah langkah-langkah detail untuk memastikan semua komponen bekerja di node lokal, sesuai struktur proyek Anda:

## 1. Setup Server Stream Lokal

**Tujuan:** Menyiapkan server stream untuk menerima RTSP dari kamera dan menyediakan RTMP/HLS untuk analisis dan live stream.

### Langkah:

#### 1.1 Konfigurasi Server Stream:
- Siapkan konfigurasi RTMP di file `stream_server/nginx.conf` untuk menerima RTSP dan menyediakan RTMP/HLS.
- Pastikan port 1935 (RTMP) dan 8080 (HLS) sudah disiapkan di konfigurasi.

#### 1.2 Build Docker Image:
- Gunakan file `stream_server/Dockerfile` untuk membangun image Docker server stream.

#### 1.3 Jalankan Server Stream:
- Pastikan server stream berjalan menggunakan docker-compose dengan memeriksa port yang di-ekspos.

#### 1.4 Uji Stream:
- Kirim RTSP dari kamera ke server stream.
- Pastikan stream dapat diakses melalui RTMP dan HLS secara lokal.

## 2. Jalankan Backup Manager

**Tujuan:** Menyimpan video secara selektif berdasarkan analisis gerakan dan deteksi objek.

### Langkah:

#### 2.1 Konfigurasi Backup Manager:
- Pastikan stream URL di `backup_manager.py` diatur ke RTMP server lokal.
- Gunakan pipeline Frame Differencing dan MobileNet di file `backup/scripts/frame_differencing.py` dan `backup/scripts/mobilenet.py`.

#### 2.2 Build Docker Image:
- Gunakan file `backup/Dockerfile` untuk membangun image Docker backup manager.

#### 2.3 Jalankan Backup Manager:
- Jalankan kontainer backup menggunakan docker-compose.

#### 2.4 Verifikasi Backup:
- Pastikan file backup tersimpan di direktori lokal yang telah dikonfigurasi (misalnya, `/mnt/Data/Backup`).

## 3. Monitoring HDD Lokal

**Tujuan:** Memantau kapasitas disk dan menghapus file lama jika hampir penuh.

### Langkah:

#### 3.1 Konfigurasi HDD Monitor:
- Pastikan `hdd_monitor.py` sudah diatur untuk memantau disk lokal.
- Tentukan direktori untuk menyimpan log kapasitas HDD (misalnya, `/mnt/Data/Syslog`).

#### 3.2 Build Docker Image:
- Gunakan file `hdd/Dockerfile` untuk membangun image Docker monitoring HDD.

#### 3.3 Jalankan HDD Monitor:
- Jalankan kontainer HDD monitor menggunakan docker-compose.

#### 3.4 Verifikasi Laporan HDD:
- Periksa log kapasitas disk yang dihasilkan di lokasi yang ditentukan.

## 4. Setup API Lokal

**Tujuan:** Menggabungkan laporan dari monitoring HDD dan backup menjadi endpoint API lokal.

### Langkah:

#### 4.1 Konfigurasi Flask API:
- Tambahkan endpoint API `/status` di `api/app/` untuk menggabungkan data dari monitoring HDD dan backup manager.

#### 4.2 Jalankan API Lokal:
- Jalankan API lokal menggunakan Flask dan ekspos ke port lokal (misalnya, 5000).

#### 4.3 Verifikasi Endpoint API:
- Akses endpoint `/status` di browser atau curl untuk memastikan data HDD dan backup dikembalikan dalam format JSON.

## Arsitektur Teknologi

| Komponen       | Fungsi                                               | Lokasi File                  | Teknologi                  |
|----------------|------------------------------------------------------|------------------------------|----------------------------|
| Server Stream  | Menyediakan RTMP/HLS untuk live stream dan analisis backup. | `stream_server/nginx.conf`   | Nginx RTMP, FFmpeg         |
| Backup Manager | Menganalisis gerakan dan objek untuk backup selektif. | `backup/backup_manager.py`   | OpenCV, TensorFlow Lite    |
| HDD Monitor    | Memantau kapasitas disk dan menghapus file lama.     | `hdd/hdd_monitor.py`         | Psutil, Logrotate          |
| Flask API      | Menggabungkan laporan HDD dan backup dalam satu endpoint. | `api/app/`                   | Flask, Python              |

## File dan Folder yang Dibutuhkan

| Folder/ File                  | Deskripsi                                                   |
|-------------------------------|-------------------------------------------------------------|
| `stream_server/nginx.conf`    | Konfigurasi Nginx RTMP untuk menerima RTSP dan menyediakan RTMP/HLS. |
| `backup/scripts/`             | Pipeline analisis gerakan dan deteksi objek.                |
| `backup_manager.py`           | Orkestrasi proses backup.                                   |
| `hdd/hdd_monitor.py`          | Monitoring kapasitas HDD dan pengelolaan file lama.         |
| `api/app/`                    | API untuk menggabungkan laporan HDD dan backup.             |

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
| 10. Konfigurasi API lokal            | ⬜      |
| 11. Test endpoint API lokal          | ⬜      |

## Langkah Berikutnya

- Uji integrasi penuh: pastikan semua komponen berjalan dan saling terhubung.
- Dokumentasikan hasil uji dalam folder `doc/`.
- Siapkan deployment untuk server pusat jika node lokal telah stabil.

Beri tahu saya jika Anda membutuhkan detail tambahan untuk salah satu langkah!