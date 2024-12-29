# Backup Manager

Backup Manager adalah sebuah skrip Python yang digunakan untuk melakukan backup stream RTSP secara otomatis. Skrip ini mendukung dynamic scaling berdasarkan beban CPU dan memiliki fitur logging yang lengkap.

## Deskripsi
Skrip `backup_manager.py` digunakan untuk melakukan backup stream RTSP dari beberapa channel secara paralel. Skrip ini menggunakan `ProcessPoolExecutor` untuk menjalankan proses backup secara paralel dan menyesuaikan parameter dinamis seperti jumlah pekerja, batas concurrency, dan jeda antar batch berdasarkan beban CPU.

## Fitur

1. **Dynamic Scaling**: Menentukan jumlah pekerja dan delay retry berdasarkan beban CPU.
2. **Validasi Stream RTSP**: Memvalidasi stream RTSP sebelum melakukan backup menggunakan `ffprobe`.
3. **Backup Stream RTSP**: Melakukan backup stream RTSP menggunakan `openRTSP`.
4. **Logging**: Mendukung logging ke file dan syslog dengan format yang terstruktur.
5. **Health Check**: Melakukan health check awal sebelum memulai proses backup.
6. **Konfigurasi Dinamis**: Menggunakan variabel lingkungan untuk konfigurasi yang fleksibel.

## Variabel Lingkungan
Skrip ini menggunakan variabel lingkungan yang dapat diatur melalui file `.env` atau langsung di lingkungan sistem. Berikut adalah variabel lingkungan yang digunakan:

| Variabel | Deskripsi |
| --- | --- |
| `LOG_MESSAGES_FILE` | Path ke file JSON yang berisi pesan log. |
| `RTSP_USERNAME` | Username untuk autentikasi RTSP. |
| `RTSP_PASSWORD` | Password untuk autentikasi RTSP. |
| `RTSP_IP` | Alamat IP kamera RTSP. |
| `RTSP_SUBTYPE` | Subtype stream RTSP (default: 1). |
| `VIDEO_DURATION` | Durasi video yang akan di-backup (dalam detik). |
| `CHANNELS` | Jumlah channel yang akan di-backup. |
| `BACKUP_DIR` | Direktori tempat menyimpan hasil backup. |
| `MAX_RETRIES` | Jumlah maksimal retry untuk backup. |
| `HEALTH_CHECK_URL` | URL untuk health check. |
| `HEALTH_CHECK_TIMEOUT` | Timeout untuk health check (dalam detik). |
| `SYSLOG_SERVER` | Alamat server syslog. |
| `SYSLOG_PORT` | Port server syslog. |
| `ENABLE_SYSLOG` | Mengaktifkan atau menonaktifkan syslog (true/false). |
| `BACKEND_ENDPOINT` | Endpoint backend untuk mengirim laporan. |

## Instalasi

1. Clone repository ini:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3. Buat file `.env` berdasarkan contoh `.env.example` dan sesuaikan dengan konfigurasi Anda.

## Penggunaan

Jalankan skrip `backup_manager.py`:
```bash
python backup_manager.py
```

## Fungsi

### `load_log_messages(file_path)`
Memuat pesan log dari file JSON.

**Parameter:**
- `file_path`: Path ke file JSON yang berisi pesan log.

**Mengembalikan:**
- Dictionary yang berisi pesan log.

### `get_dynamic_retry_delay()`
Menghitung jeda antar batch berdasarkan beban CPU.

**Mengembalikan:**
- Integer yang menunjukkan jeda dalam detik.

### `get_dynamic_concurrency_limit()`
Menghitung batas concurrency berdasarkan beban CPU.

**Mengembalikan:**
- Integer yang menunjukkan batas concurrency.

### `get_dynamic_max_workers()`
Menentukan jumlah pekerja untuk `ProcessPoolExecutor` berdasarkan beban CPU.

**Mengembalikan:**
- Integer yang menunjukkan jumlah pekerja.

### `get_dynamic_max_retries()`
Menghitung jumlah maksimal retry berdasarkan kondisi tertentu.

**Mengembalikan:**
- Integer yang menunjukkan jumlah maksimal retry.

### `get_rtsp_url(channel)`
Menghasilkan URL RTSP untuk channel tertentu.

**Parameter:**
- `channel`: Nomor channel.

**Mengembalikan:**
- String yang berisi URL RTSP.

### `validate_rtsp_stream(rtsp_url)`
Memvalidasi stream RTSP menggunakan `ffprobe`.

**Parameter:**
- `rtsp_url`: URL RTSP yang akan divalidasi.

**Mengembalikan:**
- Boolean yang menunjukkan apakah stream valid atau tidak.

### `backup_channel(channel)`
Melakukan backup channel menggunakan `openRTSP`.

**Parameter:**
- `channel`: Nomor channel yang akan di-backup.

## Logging

Skrip ini mendukung logging ke file dan syslog. Log file disimpan di `/mnt/Data/Syslog/rtsp/backup_manager.log` dengan rotasi otomatis.

## Alur Kerja Utama

1. **Memuat Variabel Lingkungan**:
   Menggunakan `load_dotenv()` untuk memuat variabel lingkungan dari file `.env`.

2. **Memuat Pesan Log**:
   Memanggil `load_log_messages(LOG_MESSAGES_FILE)` untuk memuat pesan log dari file JSON.

3. **Setup Logger**:
   Mengatur logger untuk mencatat pesan log ke file dan Syslog (jika diaktifkan).

4. **Health Check**:
   Memvalidasi URL health check menggunakan `validate_rtsp_stream(HEALTH_CHECK_URL)`.

5. **Mengambil Nilai Dinamis**:
   Mengambil nilai dinamis untuk `max_workers`, `concurrency_limit`, dan `retry_delay` menggunakan fungsi `get_dynamic_max_workers()`, `get_dynamic_concurrency_limit()`, dan `get_dynamic_retry_delay()`.

6. **Proses Backup**:
   Menggunakan `ProcessPoolExecutor` untuk menjalankan proses backup secara paralel. Setiap batch channel diproses secara paralel dengan jeda antar batch untuk menekan lonjakan resource.

7. **Penanganan Kesalahan**:
   Menangani kesalahan yang mungkin terjadi selama proses backup dan mencatatnya ke log.

8. **Mengakhiri Proses**:
   Mencatat pesan log ketika proses backup dihentikan atau selesai.

## Kontribusi

Silakan buat pull request atau buka issue untuk kontribusi atau pelaporan bug.

## Lisensi

Proyek ini dilisensikan di bawah lisensi MIT. Lihat file `LICENSE` untuk informasi lebih lanjut.

## Contoh Penggunaan

### Menjalankan Skrip

1. Buat file `.env` dengan variabel lingkungan yang diperlukan:
   ```env
   LOG_MESSAGES_FILE=/path/to/log_messages.json
   RTSP_USERNAME=your_username
   RTSP_PASSWORD=your_password
   RTSP_IP=192.168.1.100
   RTSP_SUBTYPE=1
   VIDEO_DURATION=10
   CHANNELS=4
   BACKUP_DIR=/mnt/Data/Backup
   HEALTH_CHECK_URL=http://127.0.0.1:8080/health
   HEALTH_CHECK_TIMEOUT=50
   SYSLOG_SERVER=syslog-ng
   SYSLOG_PORT=1514
   ENABLE_SYSLOG=true
   BACKEND_ENDPOINT=http://127.0.0.1:5001/api/report
   ```

2. Jalankan skrip `backup_manager.py`:
   ```sh
   python backup_manager.py
   ```

Dengan dokumentasi ini, Anda dapat memahami dan menggunakan skrip `backup_manager.py` dengan lebih baik. Jika ada pertanyaan lebih lanjut atau kebutuhan untuk penyesuaian, jangan ragu untuk menghubungi saya.
