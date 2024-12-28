# Konfigurasi Syslog-ng dengan Logrotate dan Zona Waktu Dinamis

Proyek ini mengatur Syslog-ng untuk pengumpulan log jaringan dan Logrotate untuk manajemen log di dalam container Docker, dengan dukungan konfigurasi zona waktu dinamis.

## Fitur
- **Syslog-ng** untuk pengumpulan log dari jaringan melalui UDP/TCP.
- **Logrotate** untuk rotasi log otomatis dengan threshold yang dapat disesuaikan.
- **Konfigurasi Zona Waktu Dinamis** menggunakan variabel `TIMEZONE` dan `TZ`.
- **Pesan Dinamis** melalui file konfigurasi `log_messages.json`.

## Cara Penggunaan

### Edit Environment Variables
Ubah `docker-compose.yml` untuk mengatur zona waktu:
```yaml
environment:
    TIMEZONE: Asia/Makassar
    TZ: Asia/Makassar
```

### Build dan Jalankan Container
```bash
docker-compose build
docker-compose up -d
```

### Verifikasi Waktu di Container
```bash
docker exec syslog-ng date
```

### Melihat Log Syslog-ng
```bash
docker logs syslog-ng
```

## Struktur Folder
```bash
.
├── docker-compose.yml         # Konfigurasi Docker Compose
├── Dockerfile                 # Dockerfile untuk Syslog-ng dan Logrotate
├── app/
│   ├── config/
│   │   ├── syslog-ng.conf     # Konfigurasi Syslog-ng
│   │   └── log_messages.json  # Pesan log dinamis
│   ├── logrotate/
│   │   └── syslog-ng          # Konfigurasi Logrotate
│   └── entrypoint.sh          # Script entrypoint untuk container
└── logs/                      # Folder untuk menyimpan log
```

## Catatan
- Pastikan `log_messages.json` berisi pesan statis yang sesuai.
- Rotasi log akan berjalan otomatis berdasarkan konfigurasi di `logrotate/syslog-ng`.
- Jika ada kendala atau pertanyaan, silakan buka issue di repositori ini.

## Verifikasi File Log yang Dihasilkan

### Lokasi Log Syslog-ng
Berdasarkan konfigurasi di file `syslog-ng.conf`, log disimpan di:
- Default log: `/mnt/Data/Syslog/default/default.log`

Untuk melihat log:
```bash
cat /mnt/Data/Syslog/default/default.log
```
Untuk memantau log secara real-time:
```bash
tail -f /mnt/Data/Syslog/default/default.log
```

### Log Rotasi
File log yang dirotasi akan berada di lokasi berikut:
```bash
/mnt/Data/Syslog/default/logrotate.status
```
Untuk memeriksa status rotasi:
```bash
cat /mnt/Data/Syslog/default/logrotate.status
```

## Verifikasi Layanan dan Status

### Cek Kesehatan Container
Gunakan perintah berikut untuk memeriksa kesehatan container:
```bash
docker ps
```
Cari kolom `STATUS` untuk memastikan container dalam status `healthy`.

### Cek Konfigurasi Logrotate
Jalankan logrotate secara manual untuk memverifikasi:
```bash
docker exec syslog-ng logrotate -d -s /mnt/Data/Syslog/default/logrotate.status /etc/logrotate.d/syslog-ng
```

### Cek Zona Waktu
Untuk memverifikasi zona waktu container:
```bash
docker exec syslog-ng date
```
Jika zona waktu tidak sesuai, pastikan variabel `TIMEZONE` disetel dengan benar di file `.env` atau `docker-compose.yml`.

## Langkah Tambahan
- Pastikan folder `/mnt/Data/Syslog` memiliki izin yang benar untuk akses tulis oleh container.
- Gunakan file `.env` untuk mengatur konfigurasi seperti `TIMEZONE` agar lebih mudah dikelola.
- Periksa konfigurasi jaringan container jika ada masalah konektivitas.

Jika Anda menghadapi masalah saat menjalankan perintah ini, beri tahu saya untuk analisis lebih lanjut.
