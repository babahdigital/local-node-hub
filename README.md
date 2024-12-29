## [`README.md`](README.md )

# Sistem Backup dan Monitoring RTSP

Proyek ini dirancang untuk mengotomatisasi backup stream RTSP, memantau penggunaan disk, dan menyediakan layanan livestream. Ini mencakup beberapa komponen seperti manajer backup, monitor HDD, pemeriksaan kesehatan, dan server proxy untuk livestreaming. Sistem ini dibangun menggunakan Docker dan Docker Compose untuk memudahkan deployment dan manajemen.

## Daftar Isi

- [Ikhtisar](#ikhtisar)
- [Fitur](#fitur)
- [Arsitektur](#arsitektur)
- [Persiapan](#persiapan)
- [Penggunaan](#penggunaan)
- [Variabel Lingkungan](#variabel-lingkungan)
- [Logging](#logging)
- [Pemeriksaan Kesehatan](#pemeriksaan-kesehatan)
- [API](#api)
- [Kontribusi](#kontribusi)
- [Lisensi](#lisensi)

## Ikhtisar

Sistem Backup dan Monitoring RTSP adalah solusi komprehensif untuk mengelola stream RTSP. Ini mencakup komponen-komponen berikut:

- **Manajer Backup**: Secara otomatis melakukan backup stream RTSP.
- **Monitor HDD**: Memantau penggunaan disk dan merotasi file lama.
- **Pemeriksaan Kesehatan**: Menyediakan endpoint pemeriksaan kesehatan.
- **Server Livestream**: Menyediakan layanan livestream dengan autentikasi berbasis token.
- **Server Proxy**: Bertindak sebagai proxy untuk stream RTSP.

## Fitur

- **Skalabilitas Dinamis**: Menyesuaikan jumlah pekerja dan penundaan retry berdasarkan beban CPU.
- **Validasi Stream**: Memvalidasi stream RTSP sebelum backup.
- **Logging Komprehensif**: Mencatat log ke file dan syslog.
- **Pemeriksaan Kesehatan**: Memvalidasi kesehatan layanan sebelum memulai.
- **Konfigurasi melalui Variabel Lingkungan**: Konfigurasi fleksibel menggunakan variabel lingkungan.
- **Monitoring Penggunaan Disk**: Memantau penggunaan disk dan merotasi file lama untuk membebaskan ruang.
- **Layanan Livestream**: Menyediakan layanan livestream dengan autentikasi berbasis token.

## Arsitektur

Sistem ini terdiri dari beberapa kontainer Docker:

- **logrotate-setup**: Mengatur rotasi log untuk syslog.
- **syslog-ng**: Mengumpulkan dan mengelola log.
- **rtsp-backup**: Menangani backup stream RTSP.
- **proxy**: Bertindak sebagai proxy untuk stream RTSP.
- **backend**: Mengumpulkan data dan mengirimkannya ke kantor pusat melalui API.

## Persiapan

### Prasyarat

- Docker
- Docker Compose

### Instalasi

1. Clone repository:
    ```sh
    git clone https://github.com/yourusername/rtsp-backup-monitoring.git
    cd rtsp-backup-monitoring
    ```

2. Buat file [`.env`](.env) dengan variabel lingkungan yang diperlukan:
    ```env
    LOG_MESSAGES_FILE=/app/config/log_messages.json
    ENABLE_LIVESTREAM=true
    RTSP_USERNAME=your_rtsp_username
    RTSP_PASSWORD=your_rtsp_password
    RTSP_IP=your_rtsp_ip
    BACKUP_DIR=/mnt/Data/Backup
    HEALTH_CHECK_URL=http://127.0.0.1:8080/health
    BACKEND_ENDPOINT=http://your_backend_endpoint/api/report
    ```

3. Bangun dan jalankan kontainer:
    ```sh
    docker-compose up --build
    ```

## Penggunaan

### Menjalankan Backup

Sistem akan secara otomatis menjalankan backup stream RTSP sesuai dengan konfigurasi yang telah ditentukan.

### Memantau Penggunaan Disk

Monitor HDD akan memantau penggunaan disk dan merotasi file lama jika penggunaan disk melebihi batas yang ditentukan.

### Pemeriksaan Kesehatan

Endpoint pemeriksaan kesehatan dapat diakses di `http://127.0.0.1:8080/health` untuk memeriksa status kesehatan layanan.

## Variabel Lingkungan

| Variabel                 | Deskripsi                                                                          |
|--------------------------|--------------------------------------------------------------------------------------|
| `LOG_MESSAGES_FILE`      | Path file JSON yang berisi pesan-pesan log.                                         |
| `ENABLE_LIVESTREAM`      | `true/false`, apakah Livestream diaktifkan.                                         |
| `RTSP_USERNAME`          | Username untuk autentikasi RTSP.                                                    |
| `RTSP_PASSWORD`          | Password untuk autentikasi RTSP.                                                    |
| `RTSP_IP`                | IP address dari server RTSP.                                                        |
| `BACKUP_DIR`             | Direktori utama untuk penyimpanan backup.                                           |
| `HEALTH_CHECK_URL`       | URL endpoint layanan health check.                                                  |
| `BACKEND_ENDPOINT`       | Endpoint backend untuk melaporkan status sistem.                                    |

## Logging

Semua aktivitas monitoring, termasuk informasi penggunaan disk, penghapusan file, dan error dicatat dalam file log. Secara default di `/mnt/Data/Syslog/rtsp/`.

## Pemeriksaan Kesehatan

Sebelum memulai, skrip menunggu respons health check dari layanan terkait. Jika layanan sehat, monitoring akan berjalan. Jika tidak, skrip berhenti dengan pesan error ke log.

## API

### Endpoint Pemeriksaan Kesehatan

- **GET /health**: Mengembalikan status kesehatan layanan.

### Endpoint Backend

- **POST /api/report**: Mengirim laporan status sistem ke backend.

## Kontribusi

Kontribusi sangat diterima! Silakan fork repository ini dan buat pull request dengan perubahan Anda.

## Lisensi

Proyek ini dilisensikan di bawah lisensi MIT. Lihat file [LICENSE](LICENSE) untuk informasi lebih lanjut.

---

Dengan dokumentasi ini, Anda seharusnya dapat memahami dan mengoperasikan Sistem Backup dan Monitoring RTSP dengan mudah. Jika ada pertanyaan lebih lanjut, jangan ragu untuk menghubungi kami melalui issue di GitHub.
