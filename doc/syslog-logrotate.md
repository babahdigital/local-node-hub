# Sistem Pengelolaan Log dengan Syslog-ng dan Logrotate

## Pendahuluan
Dokumentasi ini menjelaskan fitur, kelebihan, fungsi utama, serta langkah uji coba sistem pengelolaan log berbasis Docker menggunakan Syslog-ng dan Logrotate. Sistem ini dirancang untuk mengelola log secara terpusat, efisien, dan otomatis, dengan dukungan waktu dinamis serta rotasi log berdasarkan ukuran atau waktu.

## Kelebihan Sistem
1. **Modularitas**
    - Logrotate dan Syslog-ng berjalan dalam container terpisah, memungkinkan manajemen layanan yang modular.
    - Penambahan layanan baru hanya membutuhkan konfigurasi minimal pada Syslog-ng atau Logrotate.

2. **Otomatisasi**
    - Cron job otomatis untuk menjalankan Logrotate memastikan rotasi log berjalan sesuai jadwal tanpa intervensi manual.
    - Skrip entrypoint memeriksa keberadaan cron job sebelum menambahkannya, menghindari duplikasi.

3. **Efisiensi Disk**
    - Rotasi log berdasarkan ukuran atau waktu, dengan kompresi otomatis pada log lama, menghemat kapasitas disk.
    - Pembersihan log lama dilakukan secara otomatis berdasarkan jangka waktu yang ditentukan (default 7 hari).

4. **Fleksibilitas**
    - Mendukung berbagai jenis log: aplikasi web (Nginx), layanan streaming (RTSP), firewall, dan sistem.
    - Log terorganisir dalam subdirektori sesuai jenis dan sumber log.

5. **Kemudahan Debugging**
    - Semua log disimpan dalam format terstruktur dengan pencocokan pola berbasis regex di Syslog-ng.
    - Log aktivitas sistem dan rotasi log dicatat secara terperinci untuk membantu debugging.

## Fungsi Utama
| Fungsi | Deskripsi | Contoh Penggunaan |
|--------|------------|-------------------|
| **Syslog-ng** | Mengumpulkan log dari berbagai sumber (UDP, TCP, file). | Log dari server aplikasi atau container lain dikirimkan ke Syslog-ng melalui protokol TCP/UDP. |
| **Logrotate** | Melakukan rotasi log berdasarkan ukuran (5 MB) atau waktu (daily). | Reload otomatis Syslog-ng setelah rotasi log. Kompresi log lama menggunakan gzip. |
| **Cron Integration** | Menjadwalkan Logrotate secara otomatis setiap jam. | Script entrypoint memeriksa keberadaan cron job sebelum menambahkannya, memastikan tidak ada duplikasi. |

## Simulasi Log
1. **Log Aktivitas dari Script Entrypoint**
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

2. **Log dari Syslog-ng**
    ```plaintext
    31-12-2024 03:10:25 INFO nginx[pid]: Klien terhubung dari 192.168.1.10
    31-12-2024 03:15:42 WARN rtsp[pid]: Waktu habis aliran terdeteksi pada Saluran 1
    31-12-2024 03:20:11 DEBUG firewall[pid]: Koneksi baru pada port 443
    ```

3. **Log Rotasi dari Logrotate**
    ```plaintext
    Memutar log /mnt/Data/Syslog/nginx/error.log, log->rotateCount adalah 7
    Mengompresi log dengan: /bin/gzip
    Mengganti nama /mnt/Data/Syslog/nginx/error.log.1.gz menjadi /mnt/Data/Syslog/nginx/error.log.2.gz
    Menyalin /mnt/Data/Syslog/nginx/error.log ke /mnt/Data/Syslog/nginx/error.log.1
    Memotong /mnt/Data/Syslog/nginx/error.log
    ```

## Kesimpulan
Sistem pengelolaan log berbasis Docker ini memberikan solusi efisien untuk:
- Mengelola log dari berbagai layanan secara terpusat.
- Memastikan kapasitas disk tetap optimal dengan rotasi dan kompresi log otomatis.
- Mempermudah debugging dan pemantauan aktivitas sistem.

Dengan kemampuan agregasi log, rotasi log otomatis, dan pemantauan kapasitas disk, sistem ini sangat cocok untuk lingkungan produksi yang kompleks.