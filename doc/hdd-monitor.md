# Dokumentasi: Fitur-Fitur HDD Monitor

## Deskripsi Umum
`hdd_monitor.py` adalah skrip Python yang dirancang untuk memantau penggunaan disk dan melakukan rotasi file lama secara otomatis ketika kapasitas penyimpanan mendekati batas maksimum. Skrip ini cocok untuk HDD fisik maupun penyimpanan dengan batasan quota seperti TrueNAS.

## Fitur Utama

| Fitur                           | Deskripsi                                                                                                                                                                               |
|---------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Penjadwalan Interval Monitoring | Menggunakan variabel `MONITOR_INTERVAL` untuk mengatur frekuensi pengecekan disk secara berkala.                                                                                       |
| Otomatisasi Batas Kapasitas Disk| Jika `MAX_CAPACITY_PERCENT` tidak diatur, skrip otomatis menghitung batas kapasitas disk berdasarkan ukuran disk atau quota (dinamis).                                                 |
| Kompatibilitas Quota TrueNAS    | Memanfaatkan `shutil.disk_usage()` untuk menghormati batas quota yang diterapkan pada dataset TrueNAS.                                                                                 |
| Deteksi Disk/Quota Penuh        | Membedakan apakah disk penuh karena quota atau kapasitas fisik, dan mencatat log jika penggunaan sudah mencapai 100%.                                                                  |
| Retensi Berbasis Umur File      | Menghapus file yang lebih tua dari `FILE_RETENTION_DAYS` hari. Secara default diaktifkan dengan logika: `(now_ts - os.path.getmtime(file)) > retention_seconds`.                       |
| Rotasi File Lama Berdasarkan Waktu Modifikasi | File lama dihapus secara berurutan (tertua lebih dulu) saat penggunaan disk melewati batas yang ditentukan (`MAX_CAPACITY_PERCENT`).                                 |
| Batas Penghapusan per Siklus    | `MAX_DELETE_PER_CYCLE` membatasi jumlah file yang dihapus dalam satu iterasi (default 500).                                                                                           |
| Penghapusan Folder Kosong       | Menghapus folder kosong setelah rotasi file, agar struktur direktori tetap bersih dan rapi.                                                                                           |
| Rotasi Log Otomatis             | Menggunakan `RotatingFileHandler` untuk memastikan file log tidak menghabiskan ruang disk.                                                                                             |
| Logging Terperinci              | Semua aktivitas termasuk penggunaan disk, tahap rotasi, dan error dicatat dalam file log maupun Syslog (jika diaktifkan).                                                             |
| Validasi Layanan Health Check   | Memvalidasi layanan lain dengan fungsi `wait_for_health_check()` sebelum skrip monitoring dimulai.                                                                                    |
| Ketahanan terhadap Error        | Error pada satu iterasi monitoring tidak menghentikan keseluruhan proses; skrip terus berjalan dan melaporkan error di log.                                                            |

## Nilai Rekomendasi Batasan

| Tipe Disk      | Batasan Minimum | Batasan Maksimum |
|----------------|-----------------|------------------|
| HDD Fisik      | 90% (disk size) | 95% (disk size)  |
| Quota TrueNAS  | 90% (quota)     | 95% (quota)      |

## Cara Kerja

1. **Penjadwalan Monitoring**  
    Skrip berjalan dalam loop, memeriksa kapasitas disk setiap interval `MONITOR_INTERVAL`.  

2. **Penghitungan Kapasitas Maksimal (Dinamis)**  
    Jika variabel `MAX_CAPACITY_PERCENT` tidak disetel, skrip menentukan batas penggunaan disk secara otomatis:
    - Jika total disk > 500GB: 95%
    - Jika total disk > 100GB: 92%
    - Jika total disk ≤ 100GB: 90%

3. **Retensi Berbasis Umur File**  
    Menghapus file lebih tua dari `FILE_RETENTION_DAYS` hari, menggunakan nilai default 7 hari. Aktif dengan logika: `(now_ts - os.path.getmtime(file)) > retention_seconds`.

4. **Rotasi File Lama**  
    Jika penggunaan disk (`usage_percent`) melebihi `MAX_CAPACITY_PERCENT`, skrip mengurutkan file berdasarkan waktu modifikasi tertua dan mulai menghapus file lama hingga kapasitas disk turun di bawah ambang batas.

5. **Batas Penghapusan per Siklus**  
    Maksimal `MAX_DELETE_PER_CYCLE` file yang dihapus pada setiap iterasi. Jika batas ini tercapai dan disk masih penuh, penghapusan dilanjutkan pada iterasi selanjutnya.

6. **Penghapusan Folder Kosong**  
    Setelah rotasi file, skrip menghapus folder kosong agar struktur direktori tetap rapi.

7. **Rotasi Log Otomatis**  
    Menggunakan `RotatingFileHandler` untuk file log dengan ukuran maksimum 10MB per file dan cadangan 5 file.

8. **Logging Terperinci**  
    Menggunakan modul `logging` untuk mencatat setiap aktivitas, error, dan informasi kapasitas disk. Jika `ENABLE_SYSLOG` bernilai `true`, log juga dikirim ke server Syslog.

9. **Validasi Health Check**  
    Sebelum mulai, skrip menunggu respons health check dari layanan terkait (URL disetel di `HEALTH_CHECK_URL`). Jika layanan sehat, monitoring akan berjalan. Jika tidak, skrip berhenti dengan pesan error ke log.

10. **Penggunaan dan Quota TrueNAS**  
     Memanfaatkan `shutil.disk_usage()` sehingga jika dataset memiliki quota, skrip akan menyesuaikan nilai total disk dengan quota yang diterapkan.

## Variabel Lingkungan yang Digunakan

| Variabel                 | Deskripsi                                                                          |
|--------------------------|--------------------------------------------------------------------------------------|
| `BACKUP_DIR`            | Direktori utama untuk penyimpanan backup.                                           |
| `MONITOR_INTERVAL`       | Interval waktu (detik) antara iterasi monitoring.                                   |
| `MAX_CAPACITY_PERCENT`   | Persentase pemakaian disk sebelum skrip mulai menghapus file lama.                  |
| `ROTATE_THRESHOLD`       | Persentase tambahan untuk mencegah naik-turun rotasi terus-menerus.                 |
| `MAX_DELETE_PER_CYCLE`   | Batas jumlah file yang dihapus dalam satu siklus rotasi.                            |
| `FILE_RETENTION_DAYS`    | Jumlah hari file disimpan sebelum dihapus selama rotasi (default 7).               |
| `SYSLOG_SERVER`          | Host atau IP server Syslog untuk logging.                                           |
| `SYSLOG_PORT`            | Port server Syslog.                                                                 |
| `ENABLE_SYSLOG`          | `true/false`, apakah Syslog diaktifkan.                                             |
| `BACKEND_ENDPOINT`       | Endpoint backend untuk melaporkan status sistem.                                    |
| `HEALTH_CHECK_URL`       | URL endpoint layanan health check (digunakan `wait_for_health_check`).             |
| `HEALTH_CHECK_TIMEOUT`   | Waktu maksimal (detik) untuk menunggu respons health check.                         |
| `LOG_MESSAGES_FILE`      | Path file JSON yang berisi pesan-pesan log.                                         |
| `LOG_FILE`               | Path file log utama.                                                                |

## Log dan Debugging

- **File Log**: Semua aktivitas monitoring, termasuk informasi penggunaan disk, penghapusan file, dan error dicatat dalam file log. Secara default di `/mnt/Data/Syslog/rtsp/hdd_monitor.log`.  
- **Rotasi Log**: Secara otomatis berotasi setelah mencapai 10MB, dengan maksimal 5 berkas cadangan.  
- **Error Handling**: Jika terjadi error pada suatu iterasi, error akan dicatat di log dan proses dilanjutkan pada iterasi berikutnya.

## Kompatibilitas

- **HDD Fisik**: Memantau total kapasitas disk fisik melalui `shutil.disk_usage(BACKUP_DIR)`.
- **TrueNAS dengan Quota**: Jika Quota diterapkan, `shutil.disk_usage()` hanya melaporkan ukuran/disk usage dalam lingkup quota.

## Cara Menggunakan

1. Pastikan semua variabel lingkungan yang diperlukan sudah disetel (di file `.env` atau setara).  
```bash
# Jalankan skrip
python3 hdd_monitor.py
```

## Contoh Log

```plaintext
05-12-2023 10:23:14 [INFO] Monitoring disk berjalan.
05-12-2023 10:23:14 [INFO] Penggunaan disk: 78.52%. Total: 49.80 GiB, Terpakai: 39.06 GiB, Tersisa: 10.69 GiB.
05-12-2023 10:24:14 [INFO] Penggunaan disk: 91.03%. Total: 49.80 GiB, Terpakai: 45.32 GiB, Tersisa: 4.49 GiB.
05-12-2023 10:24:14 [INFO] Rotasi dimulai. Penggunaan disk 91.03% melebihi 90%.
05-12-2023 10:24:15 [INFO] File dihapus: 2023/12/05/some_old_file.mp4
05-12-2023 10:24:16 [INFO] Rotasi selesai. Penggunaan disk saat ini 89.94%.
05-12-2023 10:24:16 [WARNING] Penggunaan disk masih tinggi: 89.94%. Mungkin perlu rotasi tambahan.
05-12-2023 10:24:16 [INFO] Folder kosong dihapus: /mnt/Data/Backup/2023/12/05
05-12-2023 10:24:16 [ERROR] Terjadi kesalahan saat monitoring disk: [error message]
05-12-2023 10:24:16 [INFO] Monitoring disk dihentikan oleh pengguna.
```