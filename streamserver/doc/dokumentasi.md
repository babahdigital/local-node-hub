# Dokumentasi Sistem CCTV Streaming & Validasi

Dokumentasi ini menjelaskan 3 skrip yang digunakan:

- **entrypoint.sh** – Skrip Shell yang menjadi Docker ENTRYPOINT.
- **validate_cctv.py** – Skrip Python untuk validasi RTSP stream (cek online/offline, black frames, freeze frames) dan menulis status ke log.
- **utils.py** – Skrip Python berisi fungsi utilitas (logging, decoding credentials, generate channels, dsb.).

## 1. Struktur File & Alur (High-Level Flow)

```bash
/home/abdullah
scripts
├── check_unhealthy.sh
├── utils.py
└── validate_model.py
streamserver
├── config
│   └── nginx.conf
├── doc
│   ├── dokumentasi.md
│   └── peta-logs.md
├── Dockerfile
├── entrypoint.sh
├── html
│   ├── error
│   │   ├── 404.html
│   │   └── 50x.html
│   └── index.html
└── scripts
    ├── motion_detect.py
    └── validate_cctv.py
config
├── credentials.sh
└── log_messages.json
```

### Alur Singkat:

1. Docker mengeksekusi `entrypoint.sh` saat kontainer dijalankan.
2. Di `entrypoint.sh`, dilakukan:
    - Decode credentials (Base64 RTSP_USER/PASSWORD).
    - Validasi environment (RTSP_IP, CHANNELS/TEST_CHANNEL, dsb.).
    - (Opsional) Memanggil `validate_cctv.py` untuk validasi RTSP (jika ENABLE_RTSP_VALIDATION=true).
    - Memulai streaming HLS via FFmpeg (tiap channel).
    - Menjalankan Nginx (`nginx -g 'daemon off;'`) agar kontainer tetap hidup.

### `validate_cctv.py` (jika dipanggil):

- Membaca environment (RTSP_IP, RTSP_USER_BASE64, RTSP_PASSWORD_BASE64, dsb.).
- Dekode credential (via `utils.decode_credentials()`).
- Loop channel → `ffprobe` untuk validasi, jika valid → cek black frames / freeze frames.
- Menulis status “Online/Offline” ke `cctv_status.log`. Bisa dijalankan sekali atau loop setiap X detik.

### `utils.py` menyediakan:

- Logger (dengan rotating file).
- `decode_credentials` (Base64).
- `generate_channels` (TEST_CHANNEL / CHANNELS).
- `get_local_time` (timestamp sesuai TIMEZONE).

## 2. Penjelasan Tiap Script

### 2.1. `entrypoint.sh`

**Fungsi Utama:**

- Menginisialisasi environment Docker.
- Mengecek dependencies (ffmpeg, python3, nginx).
- Decode credentials (RTSP_USER_BASE64 / RTSP_PASSWORD_BASE64).
- Validasi environment (RTSP_IP, CHANNELS, dsb.).
- Membuat folder log (Nginx, CCTV).
- (Opsional) Memanggil `validate_cctv.py`.
- Memulai FFmpeg streaming HLS.
- Menjalankan Nginx (`exec nginx -g 'daemon off;'`).

**Environment Variables penting di `entrypoint.sh`:**

- `RTSP_IP` – Alamat IP CCTV (DVR).
- `RTSP_USER_BASE64`, `RTSP_PASSWORD_BASE64` – Kredensial RTSP base64.
- `TEST_CHANNEL` / `CHANNELS` – Daftar channel (menentukan channel mana yang di‐stream).
- `ENABLE_RTSP_VALIDATION` – true => jalankan `validate_cctv.py`.
- `LOOP_ENABLE` – true => jalankan `validate_cctv.py` loop di background, false => single-run.
- `NGINX_LOG_PATH`, `CCTV_LOG_PATH`, `HLS_PATH` – Direktori log, dsb.

**Kelebihan:**

- Fleksibel: bisa single-run / loop untuk validasi (diatur lewat ENV).
- Memastikan Nginx tetap jadi proses utama, sehingga kontainer tidak exit.

### 2.2. `validate_cctv.py`

**Fungsi Utama:**

- Validasi RTSP stream menggunakan `ffprobe`.
- Cek black frames (dengan `blackdetect`) dan freeze frames (dengan `freezedetect`).
- Menulis “Online” / “Offline” ke `cctv_status.log`.

**Opsi:**

- `LOOP_ENABLE=true` => script akan loop setiap `CHECK_INTERVAL` detik (default 300).
- `LOOP_ENABLE=false` => script hanya dijalankan sekali, lalu selesai.

**Log Output:**

- `validation.log` (log detail, mencatat semua info/command ffmpeg, ffprobe).
- `cctv_status.log` (ringkasan, menampilkan Online/Offline per channel).

### 2.3. `utils.py`

**Fungsi Utama:**

- `setup_logger(logger_name, log_path)` – Membuat logger Python (rotating file).
- `decode_credentials()` – Membaca & decode RTSP_USER_BASE64 / RTSP_PASSWORD_BASE64.
- `generate_channels()` – Membuat list channel (misal [1,2,3] dari TEST_CHANNEL atau CHANNELS).
- `get_local_time()` – Mengembalikan timestamp lokal sesuai TIMEZONE.

**Kelebihan:**

- Memisahkan logika umum, sehingga `validate_cctv.py` dan script lain dapat memakai fungsi yang sama.
- Mempermudah debugging (log rotating, syslog opsional).

## 3. Environment Variables Penting

### Common

- `RTSP_IP`, `RTSP_USER_BASE64`, `RTSP_PASSWORD_BASE64`.
- `CHANNELS`, `TEST_CHANNEL`.
- `ENABLE_RTSP_VALIDATION` (true/false).
- `SKIP_ABDULLAH_CHECK` (true/false).

### Loop & Interval

- `LOOP_ENABLE` (true/false) – Apakah `validate_cctv.py` loop atau sekali.
- `CHECK_INTERVAL` (detik) – Interval loop (misalnya 300 = 5 menit).

### Log & Path

- `NGINX_LOG_PATH`, `CCTV_LOG_PATH`, `HLS_PATH`.
- `LOG_PATH`, `ENABLE_SYSLOG`, dsb.

### NVR Mode (opsional)

- `NVR_ENABLE=true`, `NVR_SUBNET=192.168.1.0/24` => validasi beberapa IP.

## 4. Cara Pengembangan & Tips

### Testing di Luar Docker

- Jalankan `entrypoint.sh` langsung di host. Pastikan python3, ffmpeg, nginx tersedia.
- Jalankan `validate_cctv.py`: `python3 validate_cctv.py`. Cek log di `cctv_status.log` & `validation.log`.

### Perhatikan Timeout

- `ffprobe`/`ffmpeg` bisa lambat jika koneksi CCTV lambat. Sesuaikan parameter `timeout=10` → 15 or 20.

### Tangani Freeze Frames

- Freeze detection kadang false positive bila scene CCTV diam. Atur `freezedetect=n=-60dB:d=0.5` jadi 1.0 dsb.

### Pengaturan Loop

- `LOOP_ENABLE=true` + `CHECK_INTERVAL=300` => per 5 menit.
- Perpendek interval jika butuh status lebih sering, tetapi beban CPU/net akan naik.

### Integrasi Nginx

- Pastikan di akhir `entrypoint.sh`: `exec nginx -g 'daemon off;'`.
- Jika `validate_cctv.py` mode loop, jalankan di background: `python3 validate_cctv.py &`.

### Pengaturan Log Rotation

- `utils.py` menyediakan `RotatingFileHandler` (limit 10MB, 5 backup).
- Sesuaikan agar disk tidak penuh.

### Security

- Password di‐masking di log (*****).
- Pastikan credential `.env` tidak bocor di repo publik.

## 5. Ringkasan

### `entrypoint.sh`:

- Mengecek dependencies, decode credential, validasi environment.
- Opsi: Menjalankan `validate_cctv.py` (single-run / loop).
- Memulai FFmpeg HLS, Nginx di foreground.

### `validate_cctv.py`:

- Mem‐ffprobe tiap channel => cek online/offline.
- Deteksi black frames & freeze frames (opsional).
- Tulis status di `cctv_status.log`.
- Bisa loop terus (`LOOP_ENABLE=true`) atau sekali (`LOOP_ENABLE=false`).

### `utils.py`:

- `setup_logger` untuk rotating file log.
- `decode_credentials` (base64).
- `generate_channels`, `get_local_time`, dsb.

Dengan struktur ini, Anda dapat mengembangkan sistem CCTV streaming & validasi dengan:

- Modular & Mudah Dimaintain – Setiap script punya tanggung jawab jelas.
- Fleksibel (ENV `LOOP_ENABLE`, `CHECK_INTERVAL`, `ENABLE_RTSP_VALIDATION`).
- Aman (base64 credential, mask password di log).

Semoga dokumentasi sederhana ini dapat membantu Anda memahami alur kerja, menambah fitur (seperti motion detection, freeze sensitivitas, dsb.), serta menjaga sistem streaming CCTV Anda dengan lebih efisien dan mudah.

Selamat mengembangkan!