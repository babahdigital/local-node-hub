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

## Tahapan Implementasi

Berdasarkan alur yang diusulkan, tahapannya adalah:

### 1. HDD Monitoring (Tahap Pertama)

**Fungsi Utama**: Memastikan kapasitas disk cukup untuk proses backup.

**Alur**:
- HDD Monitoring berjalan sebagai proses terpisah (atau container terpisah) untuk memantau kapasitas disk.
- Jika kapasitas disk melebihi ambang batas, HDD Monitoring:
    - Menghapus file lama berdasarkan aturan retensi atau kapasitas.
    - Melaporkan status kapasitas disk ke Syslog-ng dan Report Manager.
- Backup Manager memeriksa log HDD Monitoring sebelum memulai proses backup.

**Output**: Disk selalu memiliki ruang yang cukup untuk backup.

### 2. Validasi CCTV (Tahap Kedua)

**Fungsi Utama**: Memastikan stream RTSP valid sebelum data di-backup.

**Alur**:
- Backup Manager memanggil skrip Validasi CCTV (validate_rtsp_stream dan check_black_frames) untuk setiap channel RTSP.
- Jika validasi gagal:
    - Backup untuk channel tersebut dilewati.
    - Log kegagalan dikirim ke Report Manager.
- Jika validasi berhasil:
    - Channel ditambahkan ke daftar yang akan di-backup.

**Output**: Hanya stream yang valid yang diproses lebih lanjut.

### 3. Backup Manager (Tahap Ketiga)

**Fungsi Utama**: Melakukan backup stream RTSP yang sudah divalidasi ke disk.

**Alur**:
- Backup Manager memeriksa kapasitas disk sebelum memulai proses backup (dengan membaca log HDD Monitoring).
- Memproses backup hanya untuk channel yang lolos validasi.
- Jika backup berhasil:
    - File backup dicatat di log dan dilaporkan ke Report Manager.
- Jika backup gagal:
    - Log kegagalan dicatat dan dikirim ke Report Manager.

**Output**: Backup berjalan hanya untuk stream yang valid dan tersedia.

### Mengapa Tahapan Ini?

**HDD Monitoring Sebelum Validasi**:
- Jika disk penuh, validasi tidak diperlukan karena backup tidak dapat dilakukan.
- Ini menghemat waktu dan resource sistem.

**Validasi Sebelum Backup**:
- Memastikan hanya stream yang valid yang di-backup, menghindari pemborosan resource dan disk.

**Log yang Terkait**:
- Semua tahap menghasilkan log yang dapat dianalisis di Report Manager atau kantor pusat.

### Rekomendasi Implementasi

1. Siapkan container terpisah untuk HDD Monitoring dan pastikan berjalan terus-menerus.
2. Integrasikan validasi ke Backup Manager untuk dijalankan sebelum proses backup.
3. Optimalkan Backup Manager untuk memeriksa kapasitas disk dan memproses backup dalam batch kecil.

Jika setuju, saya dapat menyusun rencana lebih rinci atau langsung menyesuaikan script untuk setiap tahap.

### Langkah 1: HDD Monitoring

**Dockerize HDD Monitoring**:
- Menyiapkan Dockerfile untuk menjalankan skrip `hdd_monitor.py` dalam container terpisah.
- Memastikan script berjalan terus-menerus memantau kapasitas disk.

**Sinkronisasi Log**:
- Mengarahkan log dari HDD Monitoring ke Syslog-ng.
- Menyimpan log kapasitas disk di lokasi yang mudah diakses oleh Backup Manager.

**Menambahkan Endpoint (Opsional)**:
- Endpoint sederhana untuk melaporkan status kapasitas disk secara real-time.

### Langkah 2: Validasi CCTV

**Integrasi ke Backup Manager**:
- Memastikan fungsi `validate_rtsp_stream` dan `check_black_frames` dipanggil untuk setiap channel sebelum backup dimulai.
- Menambahkan log hasil validasi (berhasil/gagal) ke Syslog-ng dan Report Manager.

**Efisiensi Proses**:
- Memproses validasi dalam batch kecil untuk menghindari penggunaan resource berlebihan.

### Langkah 3: Backup Manager

**Integrasi dengan HDD Monitoring**:
- Backup Manager memeriksa log HDD Monitoring untuk memastikan kapasitas disk mencukupi sebelum backup dimulai.

**Optimasi Proses Backup**:
- Backup dilakukan hanya untuk channel yang telah divalidasi.
- Menangani batch backup paralel dengan jumlah thread yang disesuaikan dengan resource.

**Pelaporan Log**:
- Hasil backup dilaporkan ke Syslog-ng dan Report Manager, termasuk keberhasilan atau kegagalan backup.

### Langkah 4: Sinkronisasi Log

**Syslog-ng**:
- Semua komponen (HDD Monitoring, Validasi CCTV, dan Backup Manager) mencatat log ke Syslog-ng untuk monitoring terpusat.

**Report Manager**:
- Mengirimkan log yang relevan ke kantor pusat untuk analisis.

### Implementasi

**Dockerfile HDD Monitoring**:
- Membuat Dockerfile untuk `hdd_monitor.py`.

**Backup Manager**:
- Memodifikasi script agar hanya memproses backup jika validasi dan kapasitas disk memenuhi syarat.

**Sinkronisasi dengan Syslog-ng**:
- Mengintegrasikan logging untuk semua komponen ke Syslog-ng.

Jika setuju, saya akan mulai dari HDD Monitoring terlebih dahulu. Anda akan menerima script yang dimodifikasi, Dockerfile, dan konfigurasi terkait. Mari kita lanjutkan?