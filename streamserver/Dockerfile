# Gunakan base image alpine dengan versi yang stabil
FROM alpine:3.18

# Tambahkan repositori edge dan instalasi paket yang diperlukan
RUN echo "http://dl-cdn.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories && \
    echo "http://dl-cdn.alpinelinux.org/alpine/edge/main" >> /etc/apk/repositories && \
    apk update && apk add --no-cache \
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
    wget && \
    rm -rf /var/cache/apk/*

# Download source code Nginx dan modul RTMP
WORKDIR /tmp
RUN wget https://nginx.org/download/nginx-1.27.3.tar.gz && \
    tar -xzvf nginx-1.27.3.tar.gz && \
    git clone https://github.com/arut/nginx-rtmp-module.git

# Build Nginx dengan modul RTMP
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
                --add-module=/tmp/nginx-rtmp-module \
                --with-http_ssl_module && \
    make && \
    make install

# Bersihkan file sementara
RUN apk del gcc libc-dev make && \
    rm -rf /tmp/nginx-1.27.3 /tmp/nginx-rtmp-module /tmp/nginx-1.27.3.tar.gz

# Buat direktori cache Nginx
RUN mkdir -p /var/cache/nginx && \
    chmod -R 777 /var/cache/nginx

# Salin file konfigurasi Nginx
COPY ./streamserver/config/nginx.conf /etc/nginx/nginx.conf

# Direktori kerja
WORKDIR /app/streamserver

# Salin file dan folder aplikasi
COPY ./scripts /app/scripts
COPY ./config /app/config
COPY ./streamserver /app/streamserver

# Konversi line-ending dan set izin untuk entrypoint
RUN dos2unix /app/streamserver/entrypoint.sh && \
    chmod +x /app/streamserver/entrypoint.sh

# Buat virtual environment dan install dependensi Python
RUN python3 -m venv /app/streamserver/venv && \
    /app/streamserver/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /app/streamserver/venv/bin/pip install --no-cache-dir python-dotenv pytz

# Set ENTRYPOINT untuk menjalankan inisialisasi aplikasi
ENTRYPOINT ["/app/streamserver/entrypoint.sh"]

# Jalankan Nginx sebagai perintah default
CMD ["nginx", "-g", "daemon off;"]

# Expose RTMP dan HTTP ports
EXPOSE 1935 8080