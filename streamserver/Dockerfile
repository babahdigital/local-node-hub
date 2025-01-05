# =========================================
# STAGE 1: BUILD NGINX + LINGKUNGAN PYTHON
# =========================================
FROM python:3.12-slim AS builder

ARG NGINX_VERSION=1.27.3
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies untuk build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpcre3-dev \
    zlib1g-dev \
    libssl-dev \
    wget \
    cmake \
    libjpeg-dev \
    libpng-dev \
    libwebp-dev \
    libtiff-dev \
    libopenblas-dev \
    gfortran \
    python3-dev \
    python3-setuptools \
    python3-wheel && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

# Download dan build Nginx
RUN wget https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz && \
    tar -xzvf nginx-${NGINX_VERSION}.tar.gz && \
    cd nginx-${NGINX_VERSION} && \
    ./configure \
      --prefix=/etc/nginx \
      --sbin-path=/usr/sbin/nginx \
      --modules-path=/usr/lib/nginx/modules \
      --conf-path=/etc/nginx/nginx.conf \
      --error-log-path=/mnt/Data/Syslog/rtsp/nginx/error.log \
      --http-log-path=/mnt/Data/Syslog/rtsp/nginx/access.log \
      --pid-path=/run/nginx.pid \
      --lock-path=/var/lock/nginx.lock \
      --http-client-body-temp-path=/var/cache/nginx/client_temp \
      --http-proxy-temp-path=/var/cache/nginx/proxy_temp \
      --http-fastcgi-temp-path=/var/cache/nginx/fastcgi_temp \
      --http-uwsgi-temp-path=/var/cache/nginx/uwsgi_temp \
      --http-scgi-temp-path=/var/cache/nginx/scgi_temp \
      --with-http_ssl_module && \
    make && make install && \
    cd /tmp && rm -rf nginx-${NGINX_VERSION}*

# Buat direktori tambahan di STAGE 1
RUN mkdir -p /var/cache/nginx/client_temp \
             /var/cache/nginx/proxy_temp \
             /var/cache/nginx/fastcgi_temp \
             /var/cache/nginx/uwsgi_temp \
             /var/cache/nginx/scgi_temp && \
    chmod -R 775 /var/cache/nginx

WORKDIR /app/streamserver

# Copy aplikasi dan konfigurasi
COPY ./scripts /app/scripts
COPY ./config /app/config
COPY ./streamserver /app/streamserver
COPY ./models/mobilenet_ssd /app/models/mobilenet_ssd
COPY ./streamserver/config/nginx.conf /etc/nginx/nginx.conf
COPY ./streamserver/entrypoint.sh /app/streamserver/entrypoint.sh

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    python -m venv /app/streamserver/venv && \
    /app/streamserver/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /app/streamserver/venv/bin/pip install --no-cache-dir \
        python-dotenv \
        pytz \
        opencv-python-headless

# =========================================
# STAGE 2: FINAL (RUNTIME) IMAGE
# =========================================
FROM python:3.12-slim AS final

ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    libpcre3 \
    libssl3 \
    zlib1g \
    ffmpeg \
    net-tools \
    libjpeg62-turbo-dev \
    libpng16-16 \
    libtiff6 \
    libwebp7 \
    libopenblas0 && \
    adduser --disabled-password --gecos "" --uid 1000 abdullah && \
    rm -rf /var/lib/apt/lists/*

# Salin aplikasi dan konfigurasi dari stage builder
COPY --from=builder /usr/sbin/nginx /usr/sbin/nginx
COPY --from=builder /etc/nginx /etc/nginx
COPY --from=builder /app/streamserver /app/streamserver
COPY --from=builder /mnt/Data/Syslog/rtsp/nginx /mnt/Data/Syslog/rtsp/nginx

# Pastikan file log dimiliki oleh user abdullah
RUN mkdir -p /mnt/Data/Syslog/rtsp/nginx && \
    chmod -R 775 /mnt/Data/Syslog/rtsp/nginx && \
    chown -R abdullah:abdullah /mnt/Data/Syslog/rtsp/nginx

# Buat direktori tambahan di STAGE 2 untuk runtime
RUN mkdir -p /app/streamserver/hls /var/cache/nginx/client_temp && \
    chmod -R 775 /app/streamserver/hls /var/cache/nginx

# Buat direktori error dan file HTML default
RUN mkdir -p /app/streamserver/error && \
    echo "<!DOCTYPE html><html><head><title>404 Not Found</title></head><body><h1>404 Not Found</h1></body></html>" > /app/streamserver/error/404.html && \
    echo "<!DOCTYPE html><html><head><title>500 Internal Server Error</title></head><body><h1>500 Internal Server Error</h1></body></html>" > /app/streamserver/error/50x.html && \
    chmod -R 755 /app/streamserver/error

# Pastikan file memiliki izin eksekusi
RUN chmod +x /app/streamserver/entrypoint.sh

# Tetap gunakan root untuk Nginx
USER root

ENV PATH="/app/streamserver/venv/bin:$PATH"

WORKDIR /app/streamserver

ENTRYPOINT ["/app/streamserver/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;", "-c", "/etc/nginx/nginx.conf"]