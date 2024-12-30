### Sistem Pengelolaan Log dengan Syslog-ng dan Logrotate

## Pendahuluan
Dokumentasi ini menjelaskan fitur, kelebihan, fungsi utama, serta langkah uji coba sistem pengelolaan log berbasis Docker menggunakan Syslog-ng dan Logrotate. Sistem ini dirancang untuk mengelola log secara terpusat, efisien, dan otomatis, dengan dukungan waktu dinamis serta rotasi log berdasarkan ukuran atau waktu.

## Kelebihan Sistem
1. **Modularitas**
    - Sistem berjalan dalam container terpisah untuk Syslog-ng dan Logrotate, sehingga mempermudah manajemen.
    - Layanan baru dapat ditambahkan tanpa memengaruhi layanan yang sudah ada.
2. **Otomatisasi**
    - Cron job otomatis menjalankan Logrotate untuk rotasi log secara berkala (default setiap jam).
    - Skrip entrypoint memastikan cron job tidak ditambahkan lebih dari satu kali.
3. **Efisiensi Penggunaan Disk**
    - Rotasi log dilakukan berdasarkan ukuran log (default 5 MB) atau waktu (harian, mingguan, bulanan).
    - Log lama dikompresi otomatis menggunakan gzip untuk menghemat ruang disk.
    - Pembersihan log lama dilakukan otomatis (default menyimpan log selama 7 hari).
4. **Fleksibilitas**
    - Mendukung berbagai jenis log dari layanan seperti Nginx, RTSP, dan Firewall.
    - Log dikelompokkan dalam subdirektori berdasarkan jenisnya untuk mempermudah analisis.
5. **Waktu Dinamis**
    - Sistem menampilkan waktu sesuai zona waktu lokal (WIB, WITA, atau WIT), yang disesuaikan secara otomatis berdasarkan konfigurasi zona waktu pada host.
6. **Kemudahan Debugging**
    - Log terpusat dengan format terstruktur.
    - Pencatatan aktivitas sistem mempermudah debugging.

## Fungsi Utama
1. **Syslog-ng**
    - **Fungsi:** Mengumpulkan log dari berbagai sumber seperti protokol TCP, UDP, dan file.
    - **Konfigurasi:** Menyimpan log ke direktori yang sesuai berdasarkan sumber log. Mendukung pencocokan pola menggunakan regex untuk memfilter log.
2. **Logrotate**
    - **Fungsi:** Melakukan rotasi log berdasarkan ukuran atau waktu.
    - **Fitur Tambahan:** Reload otomatis layanan Syslog-ng setelah rotasi log. Kompresi log lama dengan gzip.
3. **Integrasi Cron**
    - **Fungsi:** Menjadwalkan Logrotate secara otomatis menggunakan cron.
    - **Penanganan Duplikasi:** Skrip entrypoint memeriksa keberadaan cron job sebelum menambahkannya.

## Langkah Uji Coba
1. **Kirim Log Menggunakan Logger**
    - Gunakan perintah berikut untuk mengirim pesan log ke Syslog-ng melalui TCP:
      ```bash
      logger -n 127.0.0.1 -P 1514 --tcp "Pesan log uji coba melalui TCP"
      ```
2. **Periksa Log yang Diterima**
    - Cek log yang disimpan oleh Syslog-ng. Misalnya, log dari protokol TCP disimpan di direktori `/mnt/Data/Syslog/default/default.log`:
      ```bash
      tail -f /mnt/Data/Syslog/default/default.log
      ```
3. **Simulasi Hasil Log**
    - Berikut adalah contoh log yang dihasilkan:
      ```plaintext
      31-12-2024 03:45:10 WITA 127.0.0.1: Pesan log uji coba melalui TCP
      ```

## Waktu Dinamis
Sistem secara otomatis mendeteksi zona waktu lokal berdasarkan konfigurasi host. Berikut adalah aturan penyesuaian zona waktu:
- +7: WIB (Waktu Indonesia Barat)
- +8: WITA (Waktu Indonesia Tengah)
- +9: WIT (Waktu Indonesia Timur)
Waktu ditampilkan secara dinamis dalam log dan output aktivitas sistem.

## Log Aktivitas Sistem
1. **Log dari Skrip Entrypoint**
    - Contoh log aktivitas sistem saat inisialisasi:
      ```plaintext
      2024-12-31 03:00:01 WITA - Pesan log_messages.json berhasil diload.
      2024-12-31 03:00:01 WITA - Memastikan direktori backup ada.
      2024-12-31 03:00:01 WITA - Direktori backup dibuat.
      2024-12-31 03:00:01 WITA - Memeriksa keberadaan cron job...
      2024-12-31 03:00:01 WITA - Cron job sudah ada, melewati penambahan.
      2024-12-31 03:00:01 WITA - Memulai layanan cron...
      2024-12-31 03:00:01 WITA - Menjalankan logrotate manual untuk verifikasi...
      2024-12-31 03:00:01 WITA - Logrotate selesai.
      2024-12-31 03:00:01 WITA - Memulai syslog-ng...
      ```
2. **Log dari Logrotate**
    - Log hasil rotasi logrotate:
      ```plaintext
      Rotating log /mnt/Data/Syslog/nginx/error.log, log->rotateCount is 7
      Compressing log with: /bin/gzip
      Renaming /mnt/Data/Syslog/nginx/error.log.1.gz to /mnt/Data/Syslog/nginx/error.log.2.gz
      Copying /mnt/Data/Syslog/nginx/error.log to /mnt/Data/Syslog/nginx/error.log.1
      Truncating /mnt/Data/Syslog/nginx/error.log
      ```

## Kesimpulan
Sistem ini memberikan solusi pengelolaan log yang efisien, fleksibel, dan otomatis. Dengan kemampuan agregasi log, rotasi log otomatis, dan pemantauan kapasitas disk, sistem ini sangat cocok untuk lingkungan produksi yang kompleks.

**Manfaat Utama:**
- Mengelola log dari berbagai sumber dalam satu lokasi terpusat.
- Memastikan kapasitas disk tetap terjaga dengan pembersihan log lama.
- Mempermudah troubleshooting dengan log yang terstruktur.
