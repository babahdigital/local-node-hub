# Local-Node-Hub

Local-Node-Hub adalah solusi sistem terpusat untuk manajemen dan backup data CCTV di tingkat cabang, yang berfungsi sebagai pengelola log, backup video, dan relay data ke sistem pusat.

## Fitur

- **Syslog-ng**: Pengumpulan log dari jaringan melalui UDP/TTCP.
- **Logrotate**: Rotasi log otomatis dengan threshold yang dapat disesuaikan.
- **Konfigurasi Zona Waktu Dinamis**: Menggunakan variabel `TIMEZONE` dan `TZ`.
- **Pesan Dinamis**: Melalui file konfigurasi `log_messages.json`.
- **Backup Video**: Backup video CCTV secara otomatis.
- **Relay Data**: Relay data ke sistem pusat.

## Prasyarat

- Docker
- Docker Compose

## Cara Penggunaan

### 1. Clone Repository

```bash
git clone https://github.com/babahdigital/Local-Node-Hub.git
cd Local-Node-Hub
```

### 2. Edit Environment Variables

Ubah file `.env` untuk mengatur konfigurasi yang diperlukan:

```properties
RTSP_USERNAME=username
RTSP_PASSWORD=password
RTSP_IP=192.168.100.1
RTSP_SUBTYPE=1
VIDEO_DURATION=10
CHANNELS=1

# ===========================
# KONFIGURASI SYSLOG
# ===========================
SYSLOG_SERVER=syslog-ng
SYSLOG_PORT=1514
SYSLOG_HOST=0.0.0.0
SYSLOG_DATA_DIR=/mnt/Data/Syslog
SYSLOG_CONFIG_FILE=/app/config/syslog-ng.conf
SYSLOG_USER=abdullah
SYSLOG_HOSTNAME=syslog-ng
ENABLE_SYSLOG=true

# ===========================
# DIREKTORI & PATH
# ===========================
RTSP_OUTPUT_DIR=/data
BACKUP_DIR=/mnt/Data/Backup
NAS_MOUNT_POINT=/mnt/Data/Backup
LOG_MESSAGES_FILE=/app/config/log_messages.json

# ===========================
# KONFIGURASI RETRY DAN MONITORING
```

### 3. Build dan Jalankan Container

```bash
docker-compose build
docker-compose up -d
```

### 4. Verifikasi Waktu di Container

```bash
docker exec syslog-ng date
```

### 5. Melihat Log Syslog-ng

```bash
docker logs syslog-ng
```

### 6. Uji Coba Pengiriman Log

Kirim log uji ke `syslog-ng` untuk memastikan bahwa log diterima dan disimpan di lokasi yang benar:

#### 6.1. Kirim Log Melalui UDP

```bash
logger -n 127.0.0.1 -P 1514 --udp "Test log message over UDP"
```

#### 6.2. Kirim Log Melalui TCP

```bash
logger -n 127.0.0.1 -P 1514 --tcp "Test log message over TCP"
```

### 7. Verifikasi File Log

Periksa apakah file log telah dibuat dan berisi data yang diharapkan:

#### 7.1. Periksa Log Test

```bash
docker exec -it syslog-ng cat /mnt/Data/Syslog/test/test.log
```

#### 7.2. Periksa Log Default

```bash
docker exec -it syslog-ng cat /mnt/Data/Syslog/default/default.log
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
├── logs/                      # Folder untuk menyimpan log
├── data/                      # Folder untuk menyimpan data backup video
├── .env                       # File konfigurasi environment variables
└── README.md                  # Dokumentasi proyek
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
