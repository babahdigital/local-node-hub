# Stage 1: ffmpeg-builder
FROM debian:bookworm-slim AS ffmpeg-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    autoconf \
    automake \
    build-essential \
    cmake \
    libass-dev \
    libfreetype-dev \
    libgnutls28-dev \
    libmp3lame-dev \
    libnuma-dev \
    libopus-dev \
    libssl-dev \
    libtheora-dev \
    libtool \
    libvorbis-dev \
    libvpx-dev \
    libx264-dev \
    libx265-dev \
    pkg-config \
    wget \
    yasm \
    nasm \
 && rm -rf /var/lib/apt/lists/*

RUN update-ca-certificates

ARG FFMPEG_VERSION=n6.0
RUN mkdir /ffmpeg && \
    cd /ffmpeg && \
    wget https://github.com/FFmpeg/FFmpeg/archive/refs/tags/${FFMPEG_VERSION}.tar.gz -O ffmpeg.tar.gz && \
    tar xzf ffmpeg.tar.gz && \
    cd FFmpeg-${FFMPEG_VERSION} && \
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
    && make -j"$(nproc)" \
    && make install \
    && ldconfig

# Stage 2: final
FROM python:3.12-slim AS final

# (Install supervisor & library minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    # plus library2 runtime basic (e.g. libass, libfreetype, dsb.)
 && rm -rf /var/lib/apt/lists/*

# Copy ffmpeg & ffprobe
COPY --from=ffmpeg-builder /usr/bin/ffmpeg  /usr/bin/
COPY --from=ffmpeg-builder /usr/bin/ffprobe /usr/bin/

# Copy all .so from /usr/lib (like libavcodec.so.60, libavdevice.so.60, etc.)
COPY --from=ffmpeg-builder /usr/lib /usr/lib

# (Jika 'make install' menaruh library di /usr/local/lib, maka salin /usr/local/lib)
# COPY --from=ffmpeg-builder /usr/local/lib /usr/local/lib

# Lanjutkan instal requirements, salin project, dsb.
WORKDIR /app/streamserver
COPY ./streamserver/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./streamserver /app/streamserver
RUN mkdir -p /app/streamserver/hls
RUN mkdir -p /app/streamserver/html/snapshots

# Salin supervisord.conf, entrypoint, dsb.
COPY ./streamserver/config/supervisord.conf /etc/supervisor/supervisord.conf
COPY ./config/credentials.sh /app/config/credentials.sh
COPY ./streamserver/entrypoint.sh /app/streamserver/entrypoint.sh
RUN chmod +x /app/streamserver/entrypoint.sh

EXPOSE 8080
CMD ["/app/streamserver/entrypoint.sh"]