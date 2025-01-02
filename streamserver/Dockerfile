# Gunakan base image alfg/nginx-rtmp
FROM alfg/nginx-rtmp

# Install FFmpeg, Bash, jq, dan Python
RUN apk add --no-cache ffmpeg bash jq python3 py3-pip

# Set WORKDIR ke direktori aplikasi
WORKDIR /app/streamserver

# Buat direktori HLS
RUN mkdir -p /app/streamserver/scripts /app/streamserver/config /tmp/hls && chmod -R 777 /tmp/hls

# Install dependensi Python jika diperlukan
RUN pip3 install --no-cache-dir python-dotenv

# Salin konfigurasi dari folder
COPY streamserver/config/nginx.conf /etc/nginx/nginx.conf
COPY streamserver/scripts/ /app/streamserver/scripts/
COPY streamserver/entrypoint.sh /app/streamserver/entrypoint.sh

# Salin konfigurasi dari root
COPY ../scripts/utils.py /app/streamserver/scripts/utils.py
COPY streamserver/ /app/streamserver

RUN chmod +x /app/streamserver/entrypoint.sh

# Jalankan nginx saat container dijalankan
CMD ["nginx", "-g", "daemon off;"]
