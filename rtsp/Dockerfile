# Gunakan base image Python slim
FROM python:3.11-slim

# Metadata informasi
LABEL maintainer="Abdullah <babahdigital@gmail.com>"
LABEL version="1.4.0"
LABEL description="Dockerfile for RTSP Backup Manager with OpenRTSP and LIVE555"

# Set timezone untuk container
ENV TZ=Asia/Makassar

# Install dependensi sistem termasuk pkg-config
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    curl \
    procps \
    tzdata \
    bash \
    libssl-dev \
    pkg-config \
    gcc \
    g++ \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install LIVE555 dengan flag C++11
RUN wget http://www.live555.com/liveMedia/public/live555-latest.tar.gz && \
    tar -xzf live555-latest.tar.gz && \
    cd live && \
    ./genMakefiles linux && \
    sed -i 's/CXXFLAGS =/CXXFLAGS = -std=c++11/' config.linux && \
    sed -i 's/.test()/.test_and_set()/' BasicUsageEnvironment/BasicTaskScheduler.cpp && \
    make && \
    make install && \
    cd .. && rm -rf live live555-latest.tar.gz

# Upgrade pip untuk memastikan versi terbaru
RUN pip install --no-cache-dir --upgrade pip

# Tentukan direktori kerja
WORKDIR /app

# Tambahkan user non-root untuk keamanan
RUN useradd -ms /bin/bash abdullah

# Salin file requirements.txt terlebih dahulu untuk optimasi cache Docker
COPY requirements.txt /app/requirements.txt

# Install dependensi Python dari requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Salin semua script ke dalam direktori kerja
COPY scripts/ /app/scripts/

# Salin file konfigurasi lainnya
#COPY /home/abdullah/.env /app/.env

# Buat direktori untuk logs
RUN mkdir -p /mnt/Data/Syslog/rtsp /app/logs && chown -R abdullah:abdullah /mnt/Data/Syslog/rtsp /app/logs

# Salin entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Tetapkan timezone container
RUN ln -fs /usr/share/zoneinfo/$TZ /etc/localtime && dpkg-reconfigure -f noninteractive tzdata

# Ubah ownership direktori kerja ke user non-root
RUN chown -R abdullah:abdullah /app

# Switch ke user abdullah
USER abdullah

# Tetapkan entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]