# Gunakan base image python:3.12-slim atau Debian-based minimal
FROM python:3.12-slim

# Pastikan apt-get update & install dependencies untuk build
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    gnupg \
    build-essential \
    pkg-config \
    cmake \
    libssl-dev \
    libffi-dev \
    yasm \
    nasm \
    libx264-dev \
    libx265-dev \
    libnuma-dev \
    # ... library lain jika butuh
    && rm -rf /var/lib/apt/lists/*

# Versi FFmpeg yang diinginkan
ENV FFmpeg_VERSION="n6.0"

# Download & compile FFmpeg source
RUN mkdir -p /tmp/ffmpeg-build && \
    cd /tmp/ffmpeg-build && \
    wget https://github.com/FFmpeg/FFmpeg/archive/refs/tags/${FFmpeg_VERSION}.tar.gz -O ffmpeg.tar.gz && \
    tar xzf ffmpeg.tar.gz && \
    cd FFmpeg-${FFmpeg_VERSION} && \
    ./configure \
        --prefix=/usr \
        --disable-debug \
        --disable-doc \
        --disable-static \
        --enable-shared \
        --enable-gpl \
        --enable-libx264 \
        --enable-libx265 \
        --enable-nonfree \
        # tambahkan opsi lain jika butuh
    && make -j$(nproc) && make install && \
    ldconfig && \
    cd / && rm -rf /tmp/ffmpeg-build

# Sekarang ffmpeg & ffprobe versi terbaru terpasang di /usr/bin

# Buat folder /app/streamserver
WORKDIR /app/streamserver

# Salin file requirements & install dependencies python
COPY ./streamserver/requirements.txt /app/streamserver
RUN pip install --no-cache-dir -r requirements.txt

# Salin semua file project
COPY ./streamserver /app/streamserver

# Folder HLS
RUN mkdir -p /app/streamserver/hls

# Salin credentials.sh
COPY ./config/credentials.sh /app/config/credentials.sh
RUN chmod +x /app/config/credentials.sh || true

# Expose port 8080
EXPOSE 8080

# CMD: source credentials & jalankan Gunicorn 1 worker
CMD ["/bin/bash", "-c", "source /app/config/credentials.sh && \
     exec gunicorn --bind 0.0.0.0:8080 main:app --workers 1"]