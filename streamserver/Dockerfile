# Gunakan base image alpine versi stabil (contoh: 3.18)
FROM alpine:3.21

# Tambahkan repositori main dan community Alpine 3.21 (tanpa edge)
RUN echo "https://dl-cdn.alpinelinux.org/alpine/v3.21/main" > /etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/v3.21/community" >> /etc/apk/repositories && \
    apk update && \
    apk add --no-cache \
    git \
    gcc \
    libc-dev \
    make \
    openssl-dev \
    pcre-dev \
    zlib-dev \
    bash \
    jq \
    python3 \
    py3-pip \
    dos2unix \
    net-tools \
    ffmpeg \
    wget  \
    curl && \
    rm -rf /var/cache/apk/*

# Download source code Nginx
WORKDIR /tmp
RUN wget https://nginx.org/download/nginx-1.27.3.tar.gz && \
    tar -xzvf nginx-1.27.3.tar.gz

# Build Nginx tanpa modul RTMP
WORKDIR /tmp/nginx-1.27.3
RUN ./configure --prefix=/etc/nginx \
                --sbin-path=/usr/sbin/nginx \
                --modules-path=/usr/lib/nginx/modules \
                --conf-path=/etc/nginx/nginx.conf \
                --error-log-path=/var/log/nginx/error.log \
                --http-log-path=/var/log/nginx/access.log \
                --pid-path=/var/run/nginx.pid \
                --lock-path=/var/run/nginx.lock \
                --http-client-body-temp-path=/var/cache/nginx/client_temp \
                --http-proxy-temp-path=/var/cache/nginx/proxy_temp \
                --http-fastcgi-temp-path=/var/cache/nginx/fastcgi_temp \
                --http-uwsgi-temp-path=/var/cache/nginx/uwsgi_temp \
                --http-scgi-temp-path=/var/cache/nginx/scgi_temp \
                --with-http_ssl_module && \
    make && \
    make install

# Bersihkan file _build_ sementara
RUN apk del gcc libc-dev make && \
    rm -rf /tmp/nginx-1.27.3 /tmp/nginx-1.27.3.tar.gz

# Siapkan folder HLS agar Nginx dapat menulis segmen di sini
RUN mkdir -p /app/streamserver/hls && \
    chmod 777 /app/streamserver/hls

# Buat direktori cache Nginx
RUN mkdir -p /var/cache/nginx && \
    chmod -R 777 /var/cache/nginx

# Salin file konfigurasi Nginx
COPY ./streamserver/config/nginx.conf /etc/nginx/nginx.conf

# Set direktori kerja
WORKDIR /app/streamserver

# Salin file dan folder aplikasi
COPY ./scripts /app/scripts
COPY ./config /app/config
COPY ./streamserver /app/streamserver

# Konversi _line-ending_ dan set izin untuk entrypoint
RUN dos2unix /app/streamserver/entrypoint.sh && \
    dos2unix /app/streamserver/config/nginx.conf && \
    chmod +x /app/streamserver/entrypoint.sh

# Buat virtual environment Python dan install dependensi
RUN python3 -m venv /app/streamserver/venv && \
    /app/streamserver/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /app/streamserver/venv/bin/pip install --no-cache-dir python-dotenv pytz

# Set ENTRYPOINT untuk menjalankan skrip inisialisasi
ENTRYPOINT ["/app/streamserver/entrypoint.sh"]

# Jalankan Nginx sebagai perintah default
CMD ["nginx", "-g", "daemon off;", "-c", "/etc/nginx/nginx.conf"]

# Expose port HTTP (8080) untuk HLS
EXPOSE 8080