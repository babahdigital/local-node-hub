# Rencana Implementasi dan Prioritas Pengerjaan

Untuk sistem dengan komponen berikut:

1. **Backup Manager**: Melakukan backup data dari RTSP ke penyimpanan.
2. **HDD Monitoring**: Memantau kapasitas disk dan melakukan penghapusan file lama jika penuh.
3. **Report Manager**: Mengirimkan laporan status ke kantor pusat.
4. **Livestream**: Memberikan akses livestream RTSP secara real-time.
5. **Validasi CCTV**: Memastikan kualitas dan ketersediaan stream RTSP.
6. **Syslog-ng**: Mencatat log dari semua layanan (sudah berfungsi).
7. **API**: Mengumpulkan informasi dari seluruh sistem dan meneruskannya ke kantor pusat.
8. **Health Check**: Memantau status kesehatan semua layanan.

Berikut adalah rencana prioritas pengerjaan berdasarkan dependensi dan integrasi:

## Langkah 1: Backup Manager

**Deskripsi**: Komponen utama yang melakukan backup stream RTSP ke penyimpanan lokal.

**Prioritas**: Tinggi, karena menjadi inti dari seluruh sistem.

**Langkah Implementasi**:
- Pastikan script backup RTSP (`backup_manager.py`) mendukung paralel untuk banyak channel.
- Optimalkan pengelolaan file dan penamaan berdasarkan tanggal/channel.
- Integrasikan logging dengan Syslog-ng untuk melaporkan aktivitas backup.
- Dockerize script agar mudah di-deploy.

**Output**: Backup berjalan stabil untuk 8-32 channel.

## Langkah 2: HDD Monitoring

**Deskripsi**: Memantau kapasitas disk untuk menghindari kegagalan akibat disk penuh.

**Prioritas**: Tinggi, karena penyimpanan penuh dapat menyebabkan backup gagal.

**Langkah Implementasi**:
- Gunakan library seperti `psutil` untuk memantau penggunaan disk.
- Implementasikan penghapusan otomatis file lama berdasarkan kapasitas disk.
- Tambahkan logging untuk setiap tindakan (pencatatan kapasitas, penghapusan file).
- Dockerize monitoring script agar dapat berjalan independen.

**Output**: Disk tetap tersedia untuk penyimpanan backup secara otomatis.

## Langkah 3: Validasi CCTV

**Deskripsi**: Memastikan RTSP stream valid sebelum backup, mendeteksi masalah seperti frame hitam.

**Prioritas**: Tinggi, mendukung kualitas data yang di-backup.

**Langkah Implementasi**:
- Gunakan script validasi (`validate_cctv.py`) untuk mengecek kualitas stream.
- Jalankan validasi paralel untuk banyak channel.
- Integrasikan hasil validasi ke Report Manager.
- Dockerize script untuk operasi yang terisolasi.

**Output**: Stream RTSP divalidasi dan hanya data berkualitas tinggi yang di-backup.

## Langkah 4: Report Manager

**Deskripsi**: Mengirim laporan status (backup, validasi, penggunaan disk) ke kantor pusat.

**Prioritas**: Sedang, mendukung pengawasan pusat.

**Langkah Implementasi**:
- Bangun API untuk menerima data dari komponen lain (Backup Manager, Validasi CCTV, HDD Monitoring).
- Integrasikan pengiriman laporan ke server pusat melalui HTTP/REST.
- Dockerize agar mudah di-deploy.

**Output**: Informasi status dikirim ke kantor pusat secara real-time.

## Langkah 5: Livestream

**Deskripsi**: Memberikan akses langsung ke RTSP stream melalui server proxy.

**Prioritas**: Sedang, mendukung kebutuhan monitoring real-time.

**Langkah Implementasi**:
- Gunakan RTSP server seperti `rtsp-simple-server` atau `FFmpeg`.
- Integrasikan server Flask untuk mengelola endpoint akses livestream.
- Dockerize agar dapat berjalan secara independen.

**Output**: Stream RTSP dapat diakses melalui endpoint HTTP/RTSP.

## Langkah 6: Health Check

**Deskripsi**: Memantau kesehatan semua layanan.

**Prioritas**: Rendah, mendukung stabilitas sistem.

**Langkah Implementasi**:
- Tambahkan endpoint Flask untuk melaporkan kesehatan setiap layanan.
- Pastikan monitoring mencakup Backup Manager, HDD Monitoring, Validasi CCTV, dan lainnya.
- Dockerize health check untuk mempermudah integrasi dengan sistem monitoring.

**Output**: Sistem dapat dipantau secara keseluruhan melalui satu endpoint.

## Langkah 7: API untuk Pengumpulan Informasi

**Deskripsi**: Menerima data dari seluruh layanan dan meneruskannya ke kantor pusat.

**Prioritas**: Rendah, mendukung integrasi sistem pusat.

**Langkah Implementasi**:
- Kembangkan API berbasis Flask atau FastAPI untuk menerima data dari layanan lokal.
- Format data ke JSON dan kirim ke server pusat.
- Dockerize agar dapat di-deploy secara fleksibel.

**Output**: Semua data terkumpul di kantor pusat untuk analisis lebih lanjut.

## Urutan Pengerjaan

1. **Backup Manager** → Pondasi utama untuk sistem.
2. **HDD Monitoring** → Mencegah kegagalan backup.
3. **Validasi CCTV** → Memastikan data yang di-backup berkualitas.
4. **Report Manager** → Melaporkan status ke pusat.
5. **Livestream** → Mendukung akses real-time.
6. **Health Check** → Memantau kesehatan layanan.
7. **API** → Mengintegrasikan seluruh sistem dengan kantor pusat.

Jika Anda setuju, saya dapat mulai membuat kerangka untuk Backup Manager dan HDD Monitoring terlebih dahulu.