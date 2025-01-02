# Ringkasan Proyek

## Tujuan
Membangun stream server yang mendukung:
- Streaming dari RTSP ke RTMP/HLS.
- Validasi RTSP dan pencatatan status kamera.
- Logging terpusat untuk semua komponen.

## Komponen Utama
- **Stream Server**: Mengelola RTMP dan HLS.
- **Validasi RTSP**: Menyediakan status kamera (online/offline).
- **Logging**: Mengintegrasikan log ke dalam sistem terpusat.

# Struktur Proyek
```bash
/home/abdullah/
├── config/
│   ├── credentials.sh           # Kredensial RTSP (Base64 terenkripsi)
│   ├── log_messages.json        # Pesan log terpusat
├── script/
│   ├── utils.py                 # Library untuk logging dan utilitas
│   ├── validate_cctv.py         # Skrip validasi kamera
├── streamserver/
│   ├── Dockerfile               # Dockerfile untuk stream server
│   ├── entrypoint.sh            # Entrypoint untuk menjalankan stream dan validasi
│   └── scripts/
│   │   ├── validate.py          # Skrip validasi
│   │   └── livestream.py        # Skrip untuk livestream
│   └── config/
│       └── nginx.conf           # Konfigurasi Nginx
└── docker-compose.yml           # Konfigurasi Docker Compose
```

# Konfigurasi Utama

## File `credentials.sh`
```bash
RTSP_IP=MTcyLjE2LjMwLjM=  # Base64 dari 172.16.30.3
RTSP_USER_BASE64=YmFiYWhkaWdpdGFs  # Base64 dari babahdigital
RTSP_PASSWORD_BASE64=QWRtaW4xMjNA  # Base64 dari Admin123@
```

## File `nginx.conf`
```nginx
worker_processes auto;
events {
    worker_connections 1024;
}

rtmp {
    server {
        listen 1935;
        chunk_size 4096;

        application live {
            live on;
            record off;

            hls on;
            hls_path /tmp/hls;
            hls_fragment 3;
            hls_playlist_length 10;
        }
    }
}

http {
    server {
        listen 8080;

        location /hls {
            types {
                application/vnd.apple.mpegurl m3u8;
                video/mp2t ts;
            }
            root /tmp;
            add_header Cache-Control no-cache;
        }
    }
}
```

## File `validate_cctv.py`
```python
import os
from utils import setup_logger

logger = setup_logger("CCTV-Validation", "/mnt/Data/Syslog/cctv/cctv_status.log")

def validate_rtsp_stream(rtsp_url):
    try:
        # Validasi menggunakan ffprobe
        result = subprocess.run(
            ["ffprobe", "-i", rtsp_url, "-show_streams", "-loglevel", "quiet"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.error(f"RTSP validation timeout for {rtsp_url}")
        return False
```

## File `utils.py`
```python
import logging
from logging.handlers import SysLogHandler, RotatingFileHandler

def setup_logger(name, log_path):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # File logging
    file_handler = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=5)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
```

## File `Dockerfile`
```dockerfile
FROM alfg/nginx-rtmp

RUN apk add --no-cache ffmpeg bash python3 py3-pip
RUN mkdir -p /app/streamserver/scripts /tmp/hls && chmod -R 777 /tmp/hls

COPY config/nginx.conf /etc/nginx/nginx.conf
COPY script/validate_cctv.py /app/streamserver/scripts/validate_cctv.py
COPY script/utils.py /app/streamserver/scripts/utils.py

CMD ["nginx", "-g", "daemon off;"]
```

## File `docker-compose.yml`
```yaml
version: "3.8"
services:
  stream:
    build:
      context: .
      dockerfile: streamserver/Dockerfile
    image: streamserver:babah
    container_name: stream-server
    volumes:
      - ./config/nginx.conf:/etc/nginx/nginx.conf
      - /mnt/Data/Syslog/stream:/var/log/nginx
      - ./config/log_messages.json:/app/config/log_messages.json:ro
      - ./config/credentials.sh:/app/config/credentials.sh:ro
    ports:
      - "1935:1935"
      - "8080:8080"
```

# Proses Operasional

## Jalankan Docker Compose
```bash
docker-compose up -d
```

## Jalankan RTSP ke RTMP
```bash
docker exec -it stream-server bash
ffmpeg -i "rtsp://babahdigital:Admin123@@10.10.19.3:554/cam/realmonitor?channel=1&subtype=1" \
-c:v copy -c:a copy -f flv rtmp://localhost:1935/live/stream1
```

## Tes Stream
- **RTMP**: `rtmp://<host_ip>:1935/live/stream1`
- **HLS**: `http://<host_ip>:8080/hls/stream1.m3u8`

# Troubleshooting

## Periksa Log Nginx
```bash
docker exec -it stream-server tail -f /var/log/nginx/error.log
```

## Cek File HLS
```bash
ls -l /tmp/hls
```

## Periksa Akses Jaringan
```bash
nc -zv 172.16.30.3 1935
nc -zv 172.16.30.3 8080
```

# Kesimpulan
Proyek ini berhasil mengimplementasikan:
- Streaming RTSP ke RTMP/HLS.
- Validasi kamera dengan logging terpusat.
- Infrastruktur fleksibel dengan Docker Compose.