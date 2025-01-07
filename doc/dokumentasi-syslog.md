# Dokumentasi Syslog

## 1. Struktur Proyek (Directory & File)

Di bawah ini contoh struktur direktori yang memuat file-file penting:

```bash
.
├── docker-compose.yml
├── .env               # (Opsional) Menyimpan environment variable (jika diperlukan)
├── syslog/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── config/
│   │   ├── syslog-ng.conf         # Konfigurasi syslog-ng utama
│   │   └── log_messages.json      # Template pesan log
│   ├── logrotate/
│   │   ├── syslog-ng              # Template / config untuk logrotate (jika manual)
│   │   ├── crontabs/
│   │   │   └── root               # File crontab
│   │   └── generate_rotate.sh     # (Opsional, jika masih dipakai)
│   ├── var-run/
│   │   └── crond.pid             # PID file crond (runtime)
│   └── ...
└── ...
```

Catatan: Nama folder/file Anda bisa berbeda, ini hanya contoh paling umum.

### Tabel Penjelasan Singkat Setiap File Utama

| Nama File                     | Lokasi                  | Fungsi                                                                 |
|-------------------------------|-------------------------|------------------------------------------------------------------------|
| docker-compose.yml            | ./ (root project)       | Mendefinisikan service Docker (syslog, dsb.), port, volume, environment, dsb. |
| Dockerfile                    | ./syslog/               | Instruksi build image syslog-ng berbasis Alpine (instalasi paket syslog-ng, logrotate, dsb.). |
| entrypoint.sh                 | ./syslog/               | Skrip utama yang dijalankan saat container start: <ul><li>Membersihkan/menyiapkan folder log</li><li>Meng-generate config logrotate</li><li>Menjalankan cron</li><li>exec syslog-ng di foreground</li></ul> |
| syslog-ng.conf                | ./syslog/config/        | Konfigurasi utama syslog-ng (source, filter, destination, log path).    |
| log_messages.json             | ./syslog/config/        | File JSON berisi template pesan log, bisa dibaca oleh Python atau shell untuk menampilkan pesan spesifik. |
| syslog-ng (template logrotate) | ./syslog/logrotate/     | File template logrotate yang memuat definisi rotasi log (ukuran, rotasi, compress, postrotate). |
| crontabs/root                 | ./syslog/logrotate/     | File crontab yang berisi jadwal cron. Biasanya di-mount ke crond agar logrotate berjalan periodik. |
| generate_rotate.sh (opsional) | ./syslog/logrotate/     | Skrip pembuatan file syslog-ng (logrotate) secara otomatis, jika dibutuhkan (kini bisa tergantikan oleh entrypoint.sh). |
| var-run/                      | ./syslog/var-run/       | Folder runtime yang menyimpan crond.pid (PID file daemon cron).         |
| .env                          | ./ (root project)       | (Opsional) Menyimpan environment variable SYSLOG_SERVER, SYSLOG_PORT, CLEAN_ON_STARTUP, dsb. |

## 2. Penjelasan entrypoint.sh (Unified Syslog + Logrotate)

`entrypoint.sh` adalah skrip inti yang akan dieksekusi saat container berjalan. Fungsinya:

1. **Load Pesan Log**
    - Membaca `log_messages.json` jika ada, lalu menampilkan pesan per key via `jq`.
2. **Opsional: Membersihkan folder /mnt/Data/Syslog**
    - Tergantung `CLEAN_ON_STARTUP`.
3. **Membuat subfolder log yang dibutuhkan (debug, test, auth, dsb.).**
4. **Generate Konfigurasi logrotate (jika belum ada)**
    - Men-scan file `*.log` di `/mnt/Data/Syslog`.
    - Menulis definisi rotasi (misal size 5M, rotate 7, postrotate kill -HUP "…").
5. **Menyalakan crond**
    - Menggunakan file crontab yang di-touch/disiapkan di `/app/syslog/logrotate/crontabs/root`.
    - Mengarahkan log cron ke `/mnt/Data/Syslog/default/logrotate/cron.log`.
6. **Menjalankan logrotate manual pertama kali (-f) untuk memastikan config siap.**
7. **Menjalankan syslog-ng di foreground agar kontainer tidak exit.**

### Contoh Skrip Terbaru

```bash
#!/usr/bin/env bash
set -e

# --------------------------------
# Fungsi Logging (dengan Timezone)
# --------------------------------
log() { ... }

# --------------------------------
# Variabel & ENV
# --------------------------------
LOG_MESSAGES_FILE_PATH="${LOG_MESSAGES_FILE_PATH:-"/app/config/log_messages.json"}"
SYSLOG_CONFIG="/app/syslog/config/syslog-ng.conf"
CONFIG_SOURCE="/app/syslog/logrotate/syslog-ng"
CONFIG_TARGET="/etc/logrotate.d/syslog-ng"
LOGROTATE_STATE_FILE="/mnt/Data/Syslog/default/logrotate/logrotate.status"
LOGROTATE_LOG="/mnt/Data/Syslog/default/logrotate/logrotate.log"
CRON_FILE="/app/syslog/logrotate/crontabs/root"
CRON_JOB="0 * * * * logrotate -v -f -s /mnt/Data/Syslog/default/logrotate/logrotate.status /etc/logrotate.d/syslog-ng >> /mnt/Data/Syslog/default/logrotate/cron.log 2>&1"

USER_OWNER="abdullah"
GROUP_OWNER="abdullah"
CHMOD_DIR=755
CHMOD_FILE=644
LOG_BASE_DIR="/mnt/Data/Syslog"
CLEAN_ON_STARTUP="${CLEAN_ON_STARTUP:-true}"

# --------------------------------
# Fungsi-Fungsi
# --------------------------------
load_messages() { ... }
get_message()   { ... }
clean_logs()    { ... }
generate_logrotate_config() { ... }
setup_logrotate_and_cron()  { ... }

main() {
  load_messages
  clean_logs
  setup_logrotate_and_cron

  # Cek config syslog-ng
  if [[ ! -f "$SYSLOG_CONFIG" ]]; then
     log "WARNING: syslog-ng.conf tidak ditemukan."
     # cp /app/syslog/config/default.syslog-ng.conf "$SYSLOG_CONFIG" (jika perlu)
  fi

  log "Menjalankan syslog-ng..."
  exec syslog-ng --foreground -f "$SYSLOG_CONFIG"
}

main
```

## 3. Dockerfile

Sebuah contoh Dockerfile single-stage (tanpa gcc, musl-dev, dsb.):

```dockerfile
FROM alpine:3.21

ENV APK_MIRROR=http://mirror.leaseweb.com/alpine/
RUN sed -i "s|http://dl-cdn.alpinelinux.org/alpine/|${APK_MIRROR}|g" /etc/apk/repositories \
     && apk update \
     && apk add --no-cache \
         syslog-ng \
         syslog-ng-json \
         logrotate \
         jq \
         dcron \
         sudo \
         bash \
         procps \
         util-linux \
     && adduser -D -s /bin/bash abdullah \
     && mkdir -p /run /app/syslog/var-run \
     && chmod 755 /etc/logrotate.d

WORKDIR /app/syslog

# Copy file syslog + config
COPY ./syslog /app/syslog
# Copy config / log_messages
COPY ./config /app/config

# Pastikan entrypoint dapat dieksekusi
RUN chmod +x /app/syslog/entrypoint.sh

EXPOSE 1514/tcp
EXPOSE 1514/udp

ENTRYPOINT ["/app/syslog/entrypoint.sh"]
```

Catatan: Anda bisa menyesuaikan user, group, port, dsb.

## 4. Contoh docker-compose.yml

```yaml
version: '3.8'
services:
  syslog:
     build:
        context: .
        dockerfile: ./syslog/Dockerfile
     container_name: syslog-ng
     hostname: syslog-ng
     restart: unless-stopped
     ports:
        - "1514:1514/tcp"
        - "1514:1514/udp"
     volumes:
        - /mnt/Data/Syslog:/mnt/Data/Syslog
        - /etc/localtime:/etc/localtime:ro
        - /etc/timezone:/etc/timezone:ro
        # (Opsional) Bind mount log_messages.json kalau ingin update di host
        - ./config/log_messages.json:/app/config/log_messages.json
     environment:
        CLEAN_ON_STARTUP: "false"
        # Bisa juga set user via USER_OWNER/USER_GROUP dsb.
     healthcheck:
        test: ["CMD", "pgrep", "syslog-ng"]
        interval: 30s
        timeout: 10s
        retries: 3
     networks:
        babahdigital:

networks:
  babahdigital:
```

Penjelasan:
- Service syslog akan mem-build image dari `syslog/Dockerfile`.
- Volume `/mnt/Data/Syslog` di host dipetakan ke container untuk menyimpan log.
- `CLEAN_ON_STARTUP=false` agar log lama tidak dihapus saat restart.

## 5. Konfigurasi syslog-ng.conf (Contoh)

Berikut contoh minimal `syslog-ng.conf` yang menerima log di port 1514 (TCP+UDP) dan mem-filter beberapa kategori:

```ini
@version: 4.8

options {
  threaded(yes);
  flush-lines(0);
  keep-hostname(yes);
  chain-hostnames(no);
  stats(freq(600));
};

source s_net {
  network(ip("0.0.0.0") port(1514) transport("udp"));
  network(ip("0.0.0.0") port(1514) transport("tcp"));
};

# Template custom (tanggal) -> log ke file
template t_custom {
  template("${DAY}-${MONTH}-${YEAR} ${HOUR}:${MIN}:${SEC} ${HOST} ${PROGRAM}: ${MSG}\n");
  template_escape(no);
};

# Filter
filter f_debug {
  match("(?i)\\[Debug\\]" value("MESSAGE"));
};

destination d_debug {
  file("/mnt/Data/Syslog/debug/debug.log" create-dirs(yes) template(t_custom));
};

log {
  source(s_net);
  filter(f_debug);
  destination(d_debug);
};

# Destination default
destination d_default {
  file("/mnt/Data/Syslog/default/default.log" create-dirs(yes) template(t_custom));
};

log {
  source(s_net);
  destination(d_default);
};
```

Anda bisa menambahkan filter dan destination untuk kategori lain (RTSP, NETWORK, BACKUP, dsb.) sesuai kebutuhan.

## 6. Bagaimana Proses Berjalan

### Docker Build

Jalankan `docker build -t syslog-ng .` (atau lewat `docker-compose build`) untuk membangun image.

### Docker Run / Docker Compose Up

```bash
docker-compose up -d syslog
```

Kontainer syslog berjalan. `entrypoint.sh` dieksekusi:
- Membaca `log_messages.json` (jika ada).
- (Opsional) Menghapus isi `/mnt/Data/Syslog` bila `CLEAN_ON_STARTUP=true`.
- Membuat subfolder log, generate config logrotate, menyalakan cron.
- Menjalankan `syslog-ng --foreground`.

### Syslog Siap Menerima Log di Port 1514

Aplikasi lain (dalam container berbeda atau di luar) bisa mengirim log via UDP/TCP ke `hostname:1514`.
Logrotate akan berjalan setiap jam (sesuai `CRON_JOB="0 * * * * ..."`) untuk memeriksa ukuran log, lalu memutar (rotate) jika sudah >5MB.

### Memverifikasi

- `docker logs syslog-ng` menampilkan output dari `entrypoint.sh`.
- Cek folder `/mnt/Data/Syslog/` di host untuk melihat file `default.log`, `debug.log`, dsb.
- Lihat `cron.log`, `logrotate.log`, dll. untuk memantau rotasi log.

## 7. FAQ & Tips

### Mengapa “No logs were rotated”?

Artinya, logrotate mendapati file belum melebihi size 5M atau masih kosong, sehingga tidak perlu dirotasi saat itu. Postrotate script pun tidak dipanggil.

### Apakah Perlu docker-cli / docker compose di Dalam Container?

Tidak, karena kita sudah pakai `kill -HUP "$(pgrep syslog-ng)"` untuk reload syslog-ng setelah rotasi, bukan `docker exec`.

### Ingin Agar Log Lama Tidak Terhapus Saat Restart?

- Set `CLEAN_ON_STARTUP=false`.
- Pastikan volume `/mnt/Data/Syslog` di-mount ke host, sehingga data persisten.

### Filter Syslog Lain?

Anda dapat menambahkan filter di `syslog-ng.conf`, misalnya `match("(?i)\\[RTSP\\]" value("MESSAGE"))`, lalu diarahkan ke `rtsp.log`, dsb.

### Kenapa Muncul Rotasi untuk /var/log/auth.log?

Alpine punya config default di `/etc/logrotate.conf` atau `/etc/logrotate.d/alpine.conf`.
Bisa dibiarkan (jika file kosong, tidak mengganggu), atau hapus konfig bawaan jika tidak diinginkan.

## 8. Rangkuman

Dengan satu kontainer saja, Anda telah:

- Menangani Syslog-ng (menerima log via UDP/TCP 1514).
- Menangani Logrotate (melalui cron) agar file log di `/mnt/Data/Syslog` tidak membengkak.
- Menggunakan satu entrypoint yang men-setup folder, memulai cron, dan menjalankan syslog-ng.

### File-file Kunci:

- `entrypoint.sh`: Orkestrasi persiapan log + logrotate + syslog-ng.
- `syslog-ng.conf`: Aturan filter/destinasi syslog.
- `logrotate/syslog-ng (template)`: Aturan rotasi log + postrotate HUP.
- `docker-compose.yml`: Mendefinisikan service “syslog” beserta volume, environment, dsb.
- `Dockerfile`: Memasang paket (syslog-ng, logrotate, cron, jq, dsb.) dan menyalin skrip.

Hasilnya: Solusi siap pakai untuk logging dengan syslog-ng dan rotasi log otomatis dalam satu container.