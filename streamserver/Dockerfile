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
      --error-log-path=/app/streamserver/nginx/error.log \
      --http-log-path=/app/streamserver/nginx/access.log \
      --pid-path=/app/streamserver/nginx/nginx.pid \
      --lock-path=/app/streamserver/nginx/nginx.lock \
      --http-client-body-temp-path=/app/streamserver/nginx/client_temp \
      --http-proxy-temp-path=/app/streamserver/nginx/proxy_temp \
      --http-fastcgi-temp-path=/app/streamserver/nginx/fastcgi_temp \
      --http-uwsgi-temp-path=/app/streamserver/nginx/uwsgi_temp \
      --http-scgi-temp-path=/app/streamserver/nginx/scgi_temp \
      --with-http_ssl_module && \
    make && make install && \
    cd /tmp && rm -rf nginx-${NGINX_VERSION}*

# Buat direktori untuk cache, HLS, dan Nginx
RUN mkdir -p /app/streamserver/hls /app/streamserver/nginx && \
    chmod -R 777 /app/streamserver/hls /app/streamserver/nginx

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

# Hapus build dependencies untuk memperkecil ukuran image
RUN apt-get remove --purge -y \
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
    apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/*

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

# Salin aplikasi dari stage builder
COPY --from=builder /usr/sbin/nginx /usr/sbin/nginx
COPY --from=builder /etc/nginx /etc/nginx
COPY --from=builder /app/streamserver /app/streamserver

# Pastikan file memiliki izin eksekusi dan direktori dimiliki oleh abdullah
RUN chmod +x /app/streamserver/entrypoint.sh && \
    chown -R abdullah:abdullah /app/streamserver

# Atur user default ke 'abdullah'
USER abdullah

ENV PATH="/app/streamserver/venv/bin:$PATH"

WORKDIR /app/streamserver

ENTRYPOINT ["/app/streamserver/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;", "-c", "/etc/nginx/nginx.conf"]

EXPOSE 8080