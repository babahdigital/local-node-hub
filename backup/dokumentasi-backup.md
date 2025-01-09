1. **RTSP_SUBTYPE (0, 1, dsb.)**
    - 0 biasanya menandakan main stream (resolusi lebih tinggi).
    - 1 sering menandakan sub stream (resolusi lebih rendah).

    **Tips:**
    - Jika server/kamera Anda menyediakan sub-stream (720p atau 480p), gunakan `RTSP_SUBTYPE=1` untuk menghemat CPU.
    - Jika Anda butuh rekaman resolusi tertinggi, pilih `0`.

2. **TEST_CHANNEL (off / “1,2”)**
    - `off` => script akan memproses channel 1..CHANNEL_COUNT.
    - Misalnya `TEST_CHANNEL="1,2"` => hanya channel 1 dan 2 yang diproses.

    **Tips:**
    - Gunakan `TEST_CHANNEL=off` jika Anda ingin semua channel.
    - Saat uji coba, Anda bisa set `TEST_CHANNEL="1"` untuk melihat hasil pipeline pada channel tertentu dulu.

3. **CHANNEL_COUNT (16, dsb.)**
    - Menentukan total channel yang akan diproses (jika `TEST_CHANNEL=off`).

    **Tips:**
    - Sesuaikan jumlah channel di NVR/kamera Anda.
    - Jika Anda punya 8 channel, isi 8; jika 16 channel, isi 16.

4. **CHUNK_DURATION (300, dsb.)**
    - Hanya berlaku untuk mode full.
    - Menentukan berapa detik sekali perekaman di-split menjadi segmen baru.

    **Tips:**
    - Umum dipakai nilai 300 s.d. 1800 detik (5–30 menit) per segmen.
    - Jika Anda ingin file rekaman tidak terlalu besar, gunakan interval 5–10 menit.

5. **FRAME_SKIP (5, 8, dsb.)**
    - Memproses hanya 1 dari N frame di pipeline motion.
    - Semakin besar, semakin ringan CPU, tapi gerakan singkat bisa terlewat.

    **Tips:**
    - 5–8 adalah rentang yang umum. Jika CPU masih terlalu tinggi, naikkan ke 10–12.
    - Jika Anda butuh sensitif terhadap gerakan singkat, turunkan ke 3–4.

6. **DOWNSCALE_RATIO (0.4, dsb.)**
    - Mengecilkan resolusi frame sebelum motion/object detection.
    - Semakin kecil angkanya, semakin ringan CPU, tapi detail berkurang.

    **Tips:**
    - 0.4–0.5 adalah kompromi yang bagus untuk CPU vs. akurasi.
    - Jika masih tinggi CPU usage, coba 0.3. Jika butuh detail lebih, naikkan ke 0.6 atau 0.7.

7. **MOTION_SLEEP (0.3, dsb.)**
    - Jeda (detik) antar loop analisis di pipeline motion/object.
    - Semakin besar, semakin sedikit “FPS analisis” => CPU lebih hemat.

    **Tips:**
    - 0.2–0.3 (5–3 FPS analisis) sudah cukup untuk CCTV biasa.
    - Jika gerakan sering terdeteksi telat, turunkan (misal 0.1).

8. **FREEZE_BLACK_INTERVAL (1800, dsb.)**
    - Mengatur seberapa sering cek freeze/black.
    - 0 => cek setiap putaran (bisa berat di CPU jika banyak channel).

    **Tips:**
    - 1800 detik (30 menit) untuk server dengan banyak channel => lebih efisien.
    - Jika jarang butuh cek freeze/black, Anda bisa naikkan ke 3600 (1 jam).

9. **BACKUP_MODE (full|motion|motion_obj)**
    - `full` => rekam terus.
    - `motion` => rekam saat ada gerakan.
    - `motion_obj` => gerakan + deteksi object tertentu (e.g., “person”).

    **Tips:**
    - `full` => Pemakaian storage besar. CPU relatif ringan (karena -c copy), tapi rekam nonstop.
    - `motion` => Hemat storage, CPU dipakai untuk motion detection.
    - `motion_obj` => Lebih selektif, tapi lebih berat CPU (karena object detection).

10. **MAX_RECORD (300, 600, dsb.)**
     - Durasi maksimal 1 segmen rekaman saat motion.
     - Jika tercapai durasi tersebut, script memulai segmen baru.

     **Tips:**
     - Nilai 300–900 (5–15 menit) umum dipakai agar file tidak terlalu besar.

11. **MOTION_TIMEOUT (10, dsb.) & POST_MOTION_DELAY (10, dsb.)**
     - `MOTION_TIMEOUT` => waktu idle tanpa gerakan sebelum perekaman berhenti.
     - `POST_MOTION_DELAY` => penambahan jeda lagi setelah gerakan hilang, mencegah rekaman “terpotong” terlalu cepat.

     **Tips:**
     - 5–10 detik untuk `MOTION_TIMEOUT`, +10 detik post-buffer = total 15–20 detik idle sebelum stop.
     - Naikkan jika Anda mau menangkap beberapa detik ekstra setelah gerakan.

12. **ENABLE_FREEZE_CHECK / ENABLE_BLACKOUT (true/false)**
     - Menentukan apakah script melakukan ffmpeg freeze/blackdetect di awal pipeline.

     **Tips:**
     - Jika CPU sering penuh, set false atau atur `FREEZE_BLACK_INTERVAL` lebih tinggi.
     - Jika Anda ingin memastikan video tidak freeze/black, set ke true.

13. **LOOP_ENABLE (true/false) & CHECK_INTERVAL (300)**
     - `LOOP_ENABLE=true` => script jalan terus, setiap `CHECK_INTERVAL` detik memulai loop lagi.
     - `LOOP_ENABLE=false` => hanya 1 putaran, lalu exit.
     - `CHECK_INTERVAL` => jeda (detik) sebelum loop berikutnya.

     **Tips:**
     - 300 detik (5 menit) adalah nilai umum. Sesuaikan dengan seberapa sering Anda ingin memeriksa channel.

14. **FREEZE_SENSITIVITY, FREEZE_RECHECK_TIMES, FREEZE_RECHECK_DELAY**
     - `FREEZE_SENSITIVITY` (6.0) => durasi frame tak berubah sebelum dianggap freeze.
     - `FREEZE_RECHECK_TIMES` => berapa kali recheck freeze.
     - `FREEZE_RECHECK_DELAY` => jeda antar recheck.

     **Tips:**
     - 6.0–10.0 detik sensitivitas adalah rentang umum untuk freeze-check.
     - Makin besar, makin lama menilai “freeze”, tapi mengurangi false positive.

15. **CONF_PERSON=0.7, CONF_CAR=0.5, CONF_MOTOR=0.5**
     - Threshold confidence object detection (person, car, motorbike).
     - Makin tinggi => makin ketat, makin sedikit false positive tapi lebih sering “ketinggalan” objek.

     **Tips:**
     - 0.6–0.7 untuk person cenderung pas.
     - 0.5 untuk mobil/motor cenderung cukup (karena mobil/motor lebih mudah terdeteksi).
     - Hindari nilai 1.0 karena hampir mustahil model mencapainya.

16. **MOTION_HISTORY, MOTION_VARTH, MOTION_SHADOWS, MOTION_AREA_THRESHOLD**
     - (Opsional, hanya jika Anda benar-benar mau menyesuaikan di motion_detection.py)

     - `MOTION_HISTORY` (default 500)
        - Jumlah frame yang disimpan background subtractor (MOG2).
        - Makin besar => latar belakang lebih stabil, tapi respons terhadap perubahan mendadak lebih lambat.
     - `MOTION_VARTH` (varThreshold, default 16)
        - Sensitivitas “perubahan latar belakang”. Makin kecil => makin sensitif.
     - `MOTION_SHADOWS` (true/false)
        - Deteksi bayangan. Kadang menimbulkan false alarm, tapi berguna jika area banyak bayangan.
     - `MOTION_AREA_THRESHOLD` (3000 default)
        - Batas minimal luas kontur gerakan (piksel) untuk dianggap “motion”.
        - Makin besar => gerakan kecil diabaikan.

**Kesimpulan Umum**
- Sesuaikan nilai setiap variabel dengan kondisi server, kapasitas CPU, tingkat detail yang diinginkan, dan storage yang tersedia.
- Jika CPU tinggi, Anda bisa perbesar `FRAME_SKIP`, kecilkan `DOWNSCALE_RATIO` (mis. 0.3), naikkan `MOTION_SLEEP` (0.3–0.5).
- Jika terlalu sering terlewat gerakan, kecilkan `FRAME_SKIP`, naikkan `DOWNSCALE_RATIO` ke 0.6, dsb.
- Untuk object detection, mulai dengan threshold 0.6–0.7 untuk person. Lebih tinggi => lebih ketat.
- Jangan ragu melakukan uji coba dan memantau log/CPU usage, lalu menyesuaikan lagi hingga sesuai kebutuhan.