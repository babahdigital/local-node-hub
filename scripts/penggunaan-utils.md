# Dokumentasi Penggunaan

## 1. Menambahkan Kategori Log Baru

1. Buka kamus `LOG_CATEGORIES`.
2. Tambahkan entry baru dengan kunci (nama kategori) dan nilai dictionary yang memuat path log.

Contoh:
```python
LOG_CATEGORIES["MY_NEW_CATEGORY"] = {
    "description": "Deskripsi singkat kategori baru.",
    "path": "/mnt/Data/Syslog/my_new_category/my_new_category.log"
}
```

3. Setelah itu, Anda dapat memanggil logger dengan:
```python
logger_new_cat = setup_category_logger("MY_NEW_CATEGORY")
logger_new_cat.info("Log dari kategori baru...")
```

## 2. Menggunakan Logger Berdasarkan Kategori

Gunakan `setup_category_logger("NAMA_KATEGORI")` untuk mendapatkan logger sesuai kategori.

Contoh:
```python
logger_performance = setup_category_logger("PERFORMANCE")
logger_performance.info("Pesan info untuk kategori performance.")
```

## 3. Fungsi Utility

### `decode_credentials()`

- Membaca environment variable `RTSP_USER_BASE64` dan `RTSP_PASSWORD_BASE64`, lalu mendekode Base64.
- Mengembalikan `(username, password)`.
- Jika tidak terdefinisi, melempar `RuntimeError`.

### `generate_channels()`

- Membuat daftar channel berdasarkan `TEST_CHANNEL` atau `CHANNELS`.
- `TEST_CHANNEL="1,2,3"` akan mengembalikan `[1,2,3]`.
- `CHANNELS=3` akan mengembalikan `[1,2,3]`.

### `get_local_time()`

- Mengembalikan waktu lokal berdasarkan ENV `TIMEZONE`.
- Default: "Asia/Makassar".
- Format: `DD-MM-YYYY HH:MM:SS TZ+Offset`.

### `get_log_message(key)`

- Mengambil pesan log dari file JSON yang sudah di-load ke `LOG_MESSAGES`.
- `key` berupa dot-notation. Jika `key` tidak ditemukan, melempar `RuntimeError`.

## 4. Poin Penting Lainnya

- `ENABLE_SYSLOG`: Jika diset `true` di environment, script akan mengirim log juga ke Syslog Server (`SYSLOG_SERVER` dan `SYSLOG_PORT`).
- `DEBUG_MODE`: Jika diset `true`, logger akan menampilkan level `DEBUG` (jika tidak, hanya `INFO` ke atas).
- Rotating File: Dibatasi `DEFAULT_LOG_SIZE` (10 MB), dengan `DEFAULT_BACKUP_COUNT` (5 file backup).

Dengan struktur di atas, penambahan kategori baru atau fungsi utility menjadi lebih mudah. Anda cukup memperbarui kamus `LOG_CATEGORIES` atau menambahkan fungsi baru di bagian FUNGSI UTILITY UMUM sesuai kebutuhan.