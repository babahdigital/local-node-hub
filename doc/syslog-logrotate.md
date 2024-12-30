# Sistem Pengelolaan Log dengan Syslog-ng dan Logrotate

## Pendahuluan
Dokumentasi ini berfokus pada fitur, kelebihan, dan kegunaan sistem pengelolaan log berbasis Docker yang dibangun menggunakan Syslog-ng untuk agregasi log dan Logrotate untuk rotasi log.

## Fitur Utama

| Fitur | Deskripsi | Kelebihan | Kegunaan |
|-------|-----------|-----------|----------|
| **Agregasi Log dengan Syslog-ng** | Mengumpulkan log dari berbagai sumber (UDP, TCP, file). Mendukung filter log berbasis level (debug, info, warn, error). Mendukung pencocokan pola log menggunakan regex. | Sistem terpusat untuk semua log aplikasi, firewall, dan sistem. Konfigurasi fleksibel untuk memisahkan log ke subdirektori. | Mengelola log dari banyak layanan dalam satu lokasi terpusat. Membantu analisis dan debugging dengan struktur log yang jelas. |
| **Rotasi Log Otomatis dengan Logrotate** | Rotasi log berdasarkan ukuran (misalnya, 5 MB) atau waktu (daily). Kompresi log lama untuk menghemat ruang disk. Pembersihan otomatis file log lama setelah jangka waktu tertentu. | Menjaga direktori log tetap rapi dan menghindari disk penuh. Mendukung reload otomatis layanan setelah rotasi. | Memastikan log lama tidak memenuhi kapasitas disk. Menyediakan file log yang relevan untuk audit atau debugging. |
| **Monitoring dan Notifikasi** | Skrip Python/Bash untuk memantau kapasitas disk. Notifikasi jika kapasitas disk hampir penuh (>90%). | Memberikan peringatan dini untuk mencegah masalah operasional. Dapat diintegrasikan dengan Telegram atau email. | Mempermudah manajemen kapasitas disk secara proaktif. Mengurangi risiko downtime akibat disk penuh. |
| **Dukungan Multi-Layanan** | Dukungan untuk log dari berbagai sumber seperti Nginx, RTSP, Firewall. Template konfigurasi logrotate yang dihasilkan otomatis berdasarkan direktori log. | Meminimalkan konfigurasi manual untuk layanan baru. Skalabilitas tinggi untuk lingkungan multi-layanan. | Meningkatkan efisiensi pengelolaan log di lingkungan multi-layanan. Memberikan visibilitas yang lebih baik atas kinerja setiap layanan. |

## Kelebihan Sistem

### Efisiensi Operasional
- Logrotate dan Syslog-ng berjalan di container terpisah untuk meningkatkan modularitas.
- Rotasi log otomatis menjaga performa sistem tanpa intervensi manual.

### Konsistensi dan Standarisasi
- Semua log disimpan dengan format yang konsisten.
- Penggunaan template logrotate memastikan standar rotasi di semua layanan.

### Keamanan
- Sistem berbasis Docker memungkinkan isolasi layanan.
- Hanya IP tertentu yang diizinkan mengirim log ke Syslog-ng.

### Kemudahan Pengelolaan
- Konfigurasi logrotate dihasilkan secara otomatis dengan skrip.
- Direktori log tetap rapi dengan struktur subdirektori yang terorganisir.

## Kegunaan Sistem

### Pengelolaan Log Terpusat
- Cocok untuk perusahaan yang memiliki banyak layanan atau aplikasi.
- Mempermudah troubleshooting dengan log terpusat.

### Pemantauan Operasional
- Membantu tim DevOps memantau kapasitas disk dan kesehatan sistem.
- Meningkatkan respons terhadap masalah log berlebih atau disk penuh.

### Kompatibilitas Multi-Layanan
- Mendukung berbagai jenis log seperti aplikasi web (Nginx), streaming video (RTSP), dan firewall.

## Studi Kasus

### Aplikasi di Lingkungan Perusahaan
- **Kebutuhan:** Log terpusat untuk semua aplikasi. Mengelola kapasitas disk untuk log besar.
- **Solusi:** Syslog-ng untuk mengumpulkan log dari semua layanan. Logrotate untuk rotasi otomatis log lama.
- **Hasil:** Penghematan disk 50% dengan kompresi log. Peningkatan efisiensi troubleshooting dengan log terorganisir.

### Monitoring Infrastruktur
- **Kebutuhan:** Peringatan dini jika kapasitas disk penuh.
- **Solusi:** Skrip monitoring disk dengan notifikasi Telegram.
- **Hasil:** Respon cepat terhadap kapasitas disk kritis.

## Kesimpulan
Sistem ini menawarkan solusi terintegrasi untuk pengelolaan log yang efektif. Dengan fitur seperti agregasi log terpusat, rotasi otomatis, dan notifikasi proaktif, sistem ini cocok untuk lingkungan multi-layanan yang kompleks.
