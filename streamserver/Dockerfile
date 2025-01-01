# Gunakan base image alfg/nginx-rtmp
FROM alfg/nginx-rtmp

# Install FFmpeg menggunakan apk (Alpine package manager)
RUN apk add --no-cache ffmpeg ffmpeg bash jq

# Set WORKDIR ke direktori aplikasi
WORKDIR /app/streamserver

# Buat direktori HLS
RUN mkdir -p /tmp/hls && chmod -R 777 /tmp/hls

# Salin konfigurasi nginx
COPY config/nginx.conf /etc/nginx/nginx.conf

# Jalankan nginx saat container dijalankan
CMD ["nginx", "-g", "daemon off;"]