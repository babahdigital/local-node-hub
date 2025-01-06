# Dokumentasi Sistem CCTV Streaming & Validasi

Di bawah ini adalah contoh dokumentasi lengkap untuk 3 script yang Anda gunakan:

- **entrypoint.sh** – (Shell script) yang berfungsi sebagai entrypoint Docker.
- **validate_cctv.py** – (Script Python) yang berfungsi untuk memvalidasi RTSP stream, mendeteksi frame hitam (black frames), freeze frames, dan menulis status ke log.
- **utils.py** – (Script Python) yang berisi berbagai fungsi utilitas (utility) untuk logging, decoding credentials, generating channel list, dsb.

Dokumentasi ini mencakup:

- Struktur File & Flow
- Penjelasan Tiap Script
- Environment Variables yang dipakai
- Cara Pengembangan & Tips

## 1. Struktur File dan Alur (High-Level Flow)

```bash
.
├─ entrypoint.sh                      # Script bash untuk Docker ENTRYPOINT
├─ streamserver/
│  ├─ scripts/
│  │  ├─ validate_cctv.py            # Validasi RTSP, black/freeze detection
│  │  └─ utils.py                    # Fungsi utilitas Python (logger, credential, dsb.)
│  └─ ... (mungkin file lain)
├─ Dockerfile
├─ .env (opsional, berisi environment)
└─ ...
```

Docker mengeksekusi `entrypoint.sh` saat kontainer dijalankan.

### Di entrypoint.sh:

- Melakukan decode_credentials (Base64 user/password).
- Melakukan validate_environment (cek RTSP_IP, user “abdullah” dsb.).
- (Opsional) Memanggil `validate_cctv.py` untuk memvalidasi RTSP (jika `ENABLE_RTSP_VALIDATION=true`).
- Menjalankan FFmpeg streaming HLS.
- Menjalankan `nginx -g 'daemon off;'` (atau proses lain) agar kontainer tetap hidup.

### validate_cctv.py:

- Membaca environment (RTSP_IP, RTSP_USER_BASE64, RTSP_PASSWORD_BASE64, dsb.).
- Dekode credential (melalui `utils.decode_credentials()`).
- Mengecek setiap channel (memakai `generate_channels()` dari utils).
- Memakai ffprobe untuk validasi RTSP. Jika valid, lanjut cek black frames (`check_black_frames`) dan freeze frames (`check_freeze_frames`).
- Menulis status channel (Online/Offline) ke file log (`cctv_status.log`).

### utils.py:

- Menyediakan `setup_logger` untuk menulis log ke file (rotating file, syslog, dsb. tergantung konfigurasi).
- Menyediakan `decode_credentials` untuk dekode Base64.
- Menyediakan `generate_channels` yang membaca TEST_CHANNEL atau CHANNELS.
- Fungsi `get_local_time` untuk menampilkan timestamp sesuai zona waktu.

## 2. Penjelasan Tiap Script

### 2.1 entrypoint.sh

**Fungsi Utama:** Menginisialisasi environment, men-decode credential, memvalidasi environment, dan men-start proses streaming HLS & Nginx. Sebagai Docker entrypoint, ia harus:

- Mengecek dependencies (opsional) – ffmpeg, python3, nginx, dsb.
- Decode RTSP credentials
- Validasi environment (RTSP_IP, CHANNELS, dsb.)
- Membuat folder log Nginx
- Membersihkan direktori HLS (opsional)
- (Opsional) Jalankan `validate_cctv.py` jika `ENABLE_RTSP_VALIDATION=true`.
- Memulai streaming dengan FFmpeg (tiap channel).
- Men-exec `nginx -g 'daemon off;'` (jika tidak ada argumen lain).

**Struktur (rangkuman):**

```bash
#!/bin/bash
set -Eeuo pipefail

# 1. Cek environment, decode credentials
# 2. Validasi environment
# 3. Setup log directory (Nginx, CCTV)
# 4. Cleanup HLS
# 5. Jalankan python validate_cctv.py (opsional)
# 6. start_hls_streams
# 7. exec nginx atau argumen lain
```

**Environment Variables yang sering dibaca di entrypoint.sh:**

- `RTSP_IP` – Alamat IP CCTV (mode DVR).
- `RTSP_USER_BASE64`, `RTSP_PASSWORD_BASE64` – Base64 username & password.
- `TEST_CHANNEL`, `CHANNELS` – Daftar channel.
- `ENABLE_RTSP_VALIDATION` – Jika true, jalankan `validate_cctv.py`.
- `NGINX_LOG_PATH`, `CCTV_LOG_PATH`, `HLS_PATH` – Jalur folder log, dsb.

### 2.2 validate_cctv.py

**Fungsi Utama:** Memvalidasi RTSP stream & menulis status. Secara garis besar:

- `decode_credentials()` – Dapat user & password RTSP.
- Baca environment – RTSP_IP, NVR_ENABLE, NVR_SUBNET, dsb.
- Tentukan IP list:
    - Jika `NVR_ENABLE=true`, parse subnet (NVR_SUBNET) => banyak IP.
    - Jika `NVR_ENABLE=false`, pakai RTSP_IP.
- Generate Channels (pakai `generate_channels()` dari utils).
- Loop setiap IP dan Channel:
    - Build RTSP URL (dengan kredensial asli).
    - Jalankan ffprobe => validasi.
    - Kalau valid => cek black frames, freeze frames (jika “DVR mode”).
    - Tulis status (Online/Offline) ke file `cctv_status.log`.

**Opsi Loop:**

Anda dapat menambahkan “loop” di script jika butuh pengecekan periodik (misalnya tiap 5 menit). Environment `LOOP_ENABLE=true` dan `CHECK_INTERVAL=300` akan membuat script jalan terus.

**Log Files:**

- Log detail: `validation.log` (LOG_PATH).
- Status ringkas: `cctv_status.log` (CCTV_LOG_PATH).

### 2.3 utils.py

**Fungsi Utama:** Kumpulan utility yang membantu script Python lain.

- `setup_logger(logger_name, log_path)`
    - Membuat logger dengan RotatingFileHandler agar file log tidak membengkak.
    - Opsional: menambahkan SysLogHandler jika `ENABLE_SYSLOG=true`.
- `decode_credentials()`
    - Membaca environment `RTSP_USER_BASE64`, `RTSP_PASSWORD_BASE64` => decode Base64 => kembalikan (user, pass).
- `generate_channels()`
    - Jika `TEST_CHANNEL != 'off'`, parse string jadi list int.
    - Jika `TEST_CHANNEL == 'off'`, buat range(1..CHANNELS).
- `get_local_time()`
    - Mengembalikan string waktu sesuai TIMEZONE (default: Asia/Makassar).
- (Opsional) `get_log_message(key)`
    - Jika ada `LOG_MESSAGES_FILE` (JSON berisi template pesan log), bisa mengambil pesan berdasarkan key.

## 3. Environment Variables Penting

### Common

- `RTSP_IP`
    - Alamat IP DVR. Contoh: 172.16.10.252.
- `RTSP_USER_BASE64` / `RTSP_PASSWORD_BASE64`
    - Base64 dari username & password RTSP. Contoh `echo -n "babahdigital" | base64`.
- `CHANNELS`
    - Jumlah channel. Contoh 8 => Channel 1..8.
- `TEST_CHANNEL`
    - Override channel list. Contoh `TEST_CHANNEL=1,3,4`.
- `ENABLE_RTSP_VALIDATION`
    - Jika true, jalankan `validate_cctv.py` di `entrypoint.sh`.
- `NVR_ENABLE`, `NVR_SUBNET`
    - Jika NVR mode, `NVR_ENABLE=true` dan `NVR_SUBNET=172.16.10.0/24` misalnya.

### Untuk Logging

- `LOG_PATH`
    - Default "/mnt/Data/Syslog/rtsp/cctv/validation.log" – tempat menulis log detail `validate_cctv.py`.
- `CCTV_LOG_PATH`
    - Default "/mnt/Data/Syslog/rtsp/cctv/cctv_status.log" – tempat menulis ringkasan status Online/Offline.
- `ENABLE_SYSLOG` / `SYSLOG_SERVER` / `SYSLOG_PORT`
    - Jika `ENABLE_SYSLOG=true`, kirim log juga ke server Syslog di (`SYSLOG_SERVER`, `SYSLOG_PORT`).

### Opsi Loop

- `LOOP_ENABLE`
    - true => `validate_cctv.py` jalan terus (per interval). false => hanya sekali.
- `CHECK_INTERVAL`
    - Interval (detik) antar loop, misalnya 300 detik = 5 menit.

## 4. Cara Pengembangan & Tips Kesempurnaan

### Testing di Luar Docker

- Jalankan `entrypoint.sh` langsung di host (dengan environment seolah-olah). Pastikan path python3 dan ffmpeg sudah ada.
- Jalankan `validate_cctv.py` di host: `python3 validate_cctv.py`. Lihat hasil di `cctv_status.log` dan `validation.log`.

### Perhatikan Timeout

- ffprobe dan ffmpeg bisa memakan waktu jika jaringan lambat. Anda bisa menyesuaikan `timeout=10` jadi 15 atau 20 agar tidak terlalu sering “Timeout”.

### Tangani Freeze Frames

- Freeze frames (terdeteksi oleh freezedetect) bisa false positive jika scene kamera sedang diam/statis.
- Anda bisa menurunkan sensitivitas dengan mengubah `freezedetect=n=-60dB:d=0.5` => `freezedetect=n=-60dB:d=1.0`.

### Pengaturan Loop

- Jika beban CPU tinggi, perpanjang `CHECK_INTERVAL`.
- Jika Anda butuh status “real-time”, Anda bisa perpendek interval, tapi CPU usage akan naik.

### Integrasi dengan Nginx

- Pastikan `exec nginx -g 'daemon off;'` di bagian akhir `entrypoint.sh` agar kontainer tidak mati.
- Jika `validate_cctv.py` di mode loop, dan Anda masih ingin Nginx jalan, jalankan Python script di background atau gunakan supervisor (misalnya supervisord).

### Pengaturan Log Rotation

- `utils.py` sudah menyiapkan RotatingFileHandler (10MB max, 5 backup). Pastikan disk cukup.
- Anda bisa menyesuaikan `DEFAULT_LOG_SIZE` atau `DEFAULT_BACKUP_COUNT` di `utils.py`.

### Security

- Di log, password di-masking (*****).
- Pastikan credential `.env` atau environment variable tidak muncul di history atau Git repo publik.

## 5. Ringkasan

- **entrypoint.sh:** Script shell yang men-setup environment di Docker, men-decode credential, validasi environment, memanggil `validate_cctv.py` (opsional), kemudian memulai proses FFmpeg & Nginx.
- **validate_cctv.py:** Script Python khusus untuk memvalidasi RTSP (apakah Online, ada black frames, freeze frames, dsb.), lalu menulis hasilnya ke log. Bisa dijalankan sekali atau loop.
- **utils.py:** Kumpulan fungsi Python (logging, decoding, dsb.) yang dipakai di `validate_cctv.py`.

Dengan struktur ini, pengembangan menjadi modular: jika Anda perlu menambah deteksi lain (misal “motion detection” atau “watermark detection”), Anda cukup menambahkan fungsi di `validate_cctv.py` atau `utils.py`. Jika Anda perlu menambah environment variable baru (misal `FREEZE_SENSITIVITY`), cukup tambahkan di `.env` dan baca di `validate_cctv.py`.

Semoga dokumentasi ini membantu Anda memahami, menjaga, dan mengembangkan sistem CCTV streaming & validasi dengan lebih mudah. Terima kasih!