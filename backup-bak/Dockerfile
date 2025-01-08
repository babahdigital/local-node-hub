FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
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

# Install LIVE555 with C++11 flag
RUN wget http://www.live555.com/liveMedia/public/live555-latest.tar.gz && \
    tar -xzf live555-latest.tar.gz && \
    cd live && \
    ./genMakefiles linux && \
    sed -i 's/CXXFLAGS =/CXXFLAGS = -std=c++11/' config.linux && \
    sed -i 's/.test()/.test_and_set()/' BasicUsageEnvironment/BasicTaskScheduler.cpp && \
    make && \
    make install && \
    cd .. && rm -rf live live555-latest.tar.gz

# Copy requirements file
COPY requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy all scripts to the working directory
COPY scripts/ /app/scripts/

# Copy configuration files
COPY config/log_messages.json /app/config/log_messages.json
COPY tool/credentials.sh /app/config/credentials.sh

# Create directories for logs
RUN mkdir -p /mnt/Data/Syslog/rtsp /app/logs && chown -R root:root /mnt/Data/Syslog/rtsp /app/logs

# Copy entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set timezone for the container
ENV TZ=Asia/Makassar
RUN ln -fs /usr/share/zoneinfo/$TZ /etc/localtime && dpkg-reconfigure -f noninteractive tzdata

# Change ownership of the working directory to a non-root user
RUN chown -R root:root /app

# Switch to non-root user
USER root

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]