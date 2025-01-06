# =========================================
# STAGE 1: BUILD NGINX + LINGKUNGAN PYTHON
# =========================================
FROM python:3.12-slim AS builder

# --- ARG & ENV
ARG NGINX_VERSION=1.27.3
ENV DEBIAN_FRONTEND=noninteractive

# 1) Install dependencies untuk build
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
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
      python3-wheel \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

# 2) Download dan build Nginx
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
      --pid-path=/run/nginx/nginx.pid \
      --lock-path=/run/nginx/nginx.lock \
      --http-client-body-temp-path=/var/cache/nginx/client_temp \
      --http-proxy-temp-path=/var/cache/nginx/proxy_temp \
      --http-fastcgi-temp-path=/var/cache/nginx/fastcgi_temp \
      --http-uwsgi-temp-path=/var/cache/nginx/uwsgi_temp \
      --http-scgi-temp-path=/var/cache/nginx/scgi_temp \
      --with-http_ssl_module \
      --with-http_v2_module && \
    make -j"$(nproc)" && \
    make install && \
    cd /tmp && rm -rf nginx-${NGINX_VERSION}*

# 3) Buat direktori tambahan (cache Nginx)
RUN mkdir -p /var/cache/nginx/client_temp \
             /var/cache/nginx/proxy_temp \
             /var/cache/nginx/fastcgi_temp \
             /var/cache/nginx/uwsgi_temp \
             /var/cache/nginx/scgi_temp && \
    chmod -R 775 /var/cache/nginx

WORKDIR /app/streamserver

# 4) Copy aplikasi dan konfigurasi
COPY ./scripts/utils.py           /app/scripts/utils.py
COPY ./scripts/validate_model.py  /app/scripts/validate_model.py
COPY ./config/log_messages.json   /app/config/log_messages.json
COPY ./config/credentials.sh      /app/config/credentials.sh
COPY ./streamserver               /app/streamserver
COPY ./streamserver/html/error/404.html  /app/streamserver/html/error/404.html
COPY ./streamserver/html/error/50x.html  /app/streamserver/html/error/50x.html
COPY ./streamserver/html/index.html      /app/streamserver/html/index.html
COPY ./models/mobilenet_ssd       /app/models/mobilenet_ssd
COPY ./streamserver/config/nginx.conf /etc/nginx/nginx.conf
COPY ./streamserver/entrypoint.sh /app/streamserver/entrypoint.sh

# 5) Install Python dependencies ke venv
RUN pip install --no-cache-dir --upgrade pip && \
    python -m venv /app/streamserver/venv && \
    /app/streamserver/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /app/streamserver/venv/bin/pip install --no-cache-dir \
        python-dotenv \
        pytz \
        opencv-python-headless \
    && rm -rf /root/.cache/pip

# =========================================
# STAGE 2: FINAL (RUNTIME) IMAGE
# =========================================
FROM python:3.12-slim AS final

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/app/streamserver/venv/bin:$PATH"

# 1) Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      bash \
      nano \
      curl \
      procps \
      libpcre3 \
      libssl3 \
      zlib1g \
      ffmpeg \
      net-tools \
      libjpeg62-turbo-dev \
      libpng16-16 \
      libtiff6 \
      libwebp7 \
      libopenblas0 \
    && rm -rf /var/lib/apt/lists/*

# 2) Tambah user abdullah (UID 1000)
RUN adduser --disabled-password --gecos "" --uid 1000 abdullah

# 3) Salin hasil build (Nginx + app) dari STAGE builder
COPY --from=builder /usr/sbin/nginx        /usr/sbin/nginx
COPY --from=builder /etc/nginx             /etc/nginx
COPY --from=builder /var/cache/nginx       /var/cache/nginx
COPY --from=builder /app/scripts           /app/scripts
COPY --from=builder /app/config            /app/config
COPY --from=builder /app/streamserver      /app/streamserver

# 4) Buat folder pendukung Nginx + /run/nginx
RUN mkdir -p /app/hls \
             /run/nginx && \
    chmod -R 775 /app/hls /run/nginx

# 5) Buat folder /mnt/Data/Syslog/rtsp/nginx dan /mnt/Data/Syslog/rtsp/cctv 
#    di dalam image (untuk jaga-jaga jika TIDAK bind mount).
RUN mkdir -p /mnt/Data/Syslog/rtsp/nginx \
             /mnt/Data/Syslog/rtsp/cctv && \
    chmod -R 775 /mnt/Data/Syslog/rtsp && \
    chown -R abdullah:abdullah \
        /mnt/Data/Syslog/rtsp \
        /var/cache/nginx \
        /run/nginx \
        /app/hls

# 6) Pastikan entrypoint.sh bisa dieksekusi
RUN chmod +x /app/streamserver/entrypoint.sh && \
    chmod 0644 /app/config/credentials.sh

# 7) Pindah user abdullah
USER abdullah

WORKDIR /app/streamserver

# 8) Entry + CMD
ENTRYPOINT ["/app/streamserver/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;", "-c", "/etc/nginx/nginx.conf"]

# 9) Healthcheck (opsional)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD pgrep nginx || exit 1