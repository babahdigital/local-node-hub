# Dokumentasi: Fitur-Fitur HDD Monitor

## Deskripsi Umum
`hdd_monitor.py` adalah script Python yang dirancang untuk memantau penggunaan disk dan melakukan rotasi file lama secara otomatis ketika kapasitas penyimpanan mendekati batas maksimum. Script ini kompatibel dengan HDD fisik maupun penyimpanan dengan batasan quota seperti TrueNAS.

## Fitur Utama

| Fitur | Deskripsi |
|-------|-----------|
| Penjadwalan Interval Monitoring | Menggunakan variabel `MONITOR_INTERVAL` untuk mengatur frekuensi monitoring disk secara berkala. |
| Otomatisasi Batas Kapasitas Disk | `MAX_CAPACITY_PERCENT` dihitung secara otomatis berdasarkan ukuran disk atau quota dataset. |
| Kompatibilitas dengan Quota TrueNAS | Memanfaatkan `shutil.disk_usage()` untuk menghormati batas quota yang diterapkan pada dataset TrueNAS. |
| Deteksi Disk Penuh atau Quota Penuh | Menambahkan log untuk membedakan apakah disk penuh karena quota atau kapasitas fisik. |
| Rotasi File Lama | Menghapus file lama secara otomatis ketika penggunaan penyimpanan mencapai batas maksimum. |
| Rotasi Log Otomatis | Menggunakan `RotatingFileHandler` untuk memastikan log monitoring tidak memenuhi disk. |
| Logging Terperinci | Semua aktivitas monitoring, termasuk penggunaan disk dan tindakan rotasi, dicatat dalam file log. |
| Validasi Layanan Health Check | Memastikan layanan dalam kondisi sehat menggunakan fungsi `wait_for_health_check()` sebelum monitoring dimulai. |
| Ketahanan terhadap Error | Error pada satu iterasi monitoring tidak menghentikan proses keseluruhan. |

## Cara Kerja

### Penjadwalan Monitoring
Script berjalan dalam loop, memeriksa kapasitas disk pada interval yang ditentukan (`MONITOR_INTERVAL`).

### Perhitungan Kapasitas Maksimal
Jika `MAX_CAPACITY_PERCENT` tidak diatur di `.env`, script akan menghitung batas otomatis:
- HDD > 500GB: 95%
- HDD 100GB-500GB: 92%
- HDD < 100GB: 90%

### Deteksi Kapasitas Disk atau Quota
Menggunakan `shutil.disk_usage()` untuk memeriksa kapasitas total, penggunaan, dan sisa ruang. Log mencatat apakah penyimpanan penuh karena quota atau kapasitas fisik.

### Rotasi File Lama
Jika kapasitas penyimpanan melebihi batas, file lama dihapus berdasarkan urutan waktu modifikasi (file paling lama dihapus terlebih dahulu).

### Rotasi Log
File log dibatasi hingga 10MB per file dengan maksimum 5 file, memastikan log tidak memenuhi disk.

### Penanganan Error
Jika terjadi error selama iterasi monitoring, script akan mencatat log error dan melanjutkan iterasi berikutnya.

### Health Check
Script memvalidasi layanan terkait sebelum memulai monitoring.

## Variabel Lingkungan yang Digunakan

| Variabel | Deskripsi |
|----------|-----------|
| `BACKUP_DIR` | Direktori utama untuk penyimpanan backup. |
| `MONITOR_INTERVAL` | Interval waktu (detik) antara setiap iterasi monitoring. |
| `ROTATE_THRESHOLD` | Persentase pengurangan kapasitas setelah rotasi file lama selesai. |
| `SYSLOG_SERVER` | Host atau IP server Syslog untuk logging. |
| `SYSLOG_PORT` | Port server Syslog. |
| `ENABLE_SYSLOG` | `true/false`, apakah Syslog diaktifkan untuk logging. |
| `BACKEND_ENDPOINT` | URL endpoint backend untuk melaporkan status sistem. |
| `HEALTH_CHECK_URL` | URL endpoint layanan health check. |
| `HEALTH_CHECK_TIMEOUT` | Waktu maksimal (detik) untuk menunggu respons dari health check. |

## Log dan Debugging

### File Log
Semua aktivitas dicatat dalam file log di `/mnt/Data/Syslog/rtsp/hdd_monitor.log`. File log secara otomatis berotasi setelah mencapai ukuran 10MB.

### Error Handling
Error pada iterasi tertentu tidak menghentikan proses monitoring secara keseluruhan. Semua error dicatat dalam log.

## Kompatibilitas

### HDD Fisik
Memantau kapasitas fisik disk menggunakan `shutil.disk_usage`.

### TrueNAS dengan Quota
Quota dihormati secara otomatis karena `shutil.disk_usage` hanya melaporkan kapasitas dalam batas quota.