### Dokumentasi Syslog dan Logrotate

## Syslog

### Deskripsi
Syslog adalah protokol standar untuk mengirim pesan log dalam jaringan IP. Syslog digunakan untuk mengumpulkan log dari berbagai perangkat dan aplikasi, mengirimkannya ke server log, dan menyimpannya atau memprosesnya lebih lanjut.

### Fitur dan Fungsi
1. **Pengumpulan Log Terpusat**:
    - Mengumpulkan log dari berbagai sumber seperti server, perangkat jaringan, dan aplikasi.
    - Mendukung berbagai protokol transportasi seperti UDP, TCP, dan TLS.

2. **Filter dan Kategori Log**:
    - Memungkinkan penyaringan log berdasarkan tingkat keparahan (debug, info, warning, error, critical).
    - Mendukung filter berbasis pola untuk mengkategorikan log.

3. **Format Log Kustom**:
    - Mendukung template untuk mengatur format log sesuai kebutuhan.
    - Dapat menambahkan informasi tambahan seperti timestamp, hostname, dan program.

4. **Penyimpanan dan Rotasi Log**:
    - Menyimpan log ke file dengan dukungan rotasi log otomatis.
    - Mendukung berbagai tujuan penyimpanan seperti file, database, dan remote server.

5. **Keamanan**:
    - Mendukung enkripsi log menggunakan TLS untuk keamanan data.
    - Mendukung otentikasi dan kontrol akses untuk mengamankan log.

### Kelebihan
- **Skalabilitas**: Dapat menangani volume log yang besar dari berbagai sumber.
- **Fleksibilitas**: Mendukung berbagai format log dan tujuan penyimpanan.
- **Keamanan**: Mendukung enkripsi dan otentikasi untuk melindungi data log.
- **Kompatibilitas**: Mendukung berbagai sistem operasi dan perangkat jaringan.

## Logrotate

### Deskripsi
Logrotate adalah utilitas untuk mengelola file log dengan cara merotasi, mengompresi, dan menghapus log lama secara otomatis. Logrotate membantu menjaga ukuran file log tetap terkendali dan memastikan log terbaru selalu tersedia.

### Fitur dan Fungsi
1. **Rotasi Log Otomatis**:
    - Merotasi log berdasarkan ukuran atau waktu (harian, mingguan, bulanan).
    - Mendukung rotasi log berbasis ukuran file.

2. **Kompresi Log**:
    - Mengompresi log lama untuk menghemat ruang penyimpanan.
    - Mendukung berbagai format kompresi seperti gzip dan bzip2.

3. **Penghapusan Log Lama**:
    - Menghapus log lama secara otomatis setelah sejumlah rotasi tertentu.
    - Mendukung penghapusan log berdasarkan usia file.

4. **Konfigurasi Fleksibel**:
    - Mendukung konfigurasi per-file atau per-direktori.
    - Mendukung skrip post-rotate untuk menjalankan perintah setelah rotasi.

5. **Notifikasi dan Logging**:
    - Mendukung notifikasi email setelah rotasi log.
    - Menyimpan log aktivitas rotasi untuk audit dan debugging.

### Kelebihan
- **Otomatisasi**: Mengelola log secara otomatis tanpa intervensi manual.
- **Penghematan Ruang**: Mengompresi log lama untuk menghemat ruang penyimpanan.
- **Fleksibilitas**: Mendukung berbagai skenario rotasi dan konfigurasi.
- **Keandalan**: Menjaga log tetap terkendali dan memastikan log terbaru selalu tersedia.

### Simulasi Hasil Log

#### Hasil Log dari `syslog-ng`

Setelah mengirim pesan log, berikut adalah contoh hasil log yang dihasilkan oleh `syslog-ng`:

**/mnt/Data/Syslog/test/test.log**
```
30-12-2024 12:34:56 127.0.0.1 logger: Test log message over UDP
```

**/mnt/Data/Syslog/rtsp/rtsp.log**
```
30-12-2024 12:34:57 127.0.0.1 logger: RTSP log message over TCP
```

**/mnt/Data/Syslog/debug/debug.log**
```
30-12-2024 12:34:58 127.0.0.1 logger: Debug log message over UDP
```

#### Hasil Log setelah `logrotate`

Setelah menjalankan `logrotate`, log akan dirotasi dan dikompresi jika memenuhi kondisi rotasi (misalnya ukuran file mencapai 10M). Berikut adalah contoh hasil setelah rotasi:

**/mnt/Data/Syslog/test/test.log.1.gz**
```
30-12-2024 12:34:56 127.0.0.1 logger: Test log message over UDP
```

**/mnt/Data/Syslog/rtsp/rtsp.log.1.gz**
```
30-12-2024 12:34:57 127.0.0.1 logger: RTSP log message over TCP
```

**/mnt/Data/Syslog/debug/debug.log.1.gz**
```
30-12-2024 12:34:58 127.0.0.1 logger: Debug log message over UDP
```

### Kesimpulan

Dengan konfigurasi `syslog-ng` dan `logrotate` yang tepat, kita dapat mengelola log secara efisien dengan format timestamp yang diinginkan dan memastikan log tetap terkendali melalui rotasi otomatis. Kombinasi ini memberikan solusi lengkap untuk manajemen log yang efisien dan andal.
