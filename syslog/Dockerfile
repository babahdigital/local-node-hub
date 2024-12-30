# Stage 1: Build
FROM alpine:3.18 AS builder

# Ganti mirror default ke Leaseweb dan install dependencies build
RUN sed -i 's|http://dl-cdn.alpinelinux.org/alpine/|http://mirror.leaseweb.com/alpine/|g' /etc/apk/repositories \
    && apk update && apk add --no-cache \
        gcc \
        musl-dev \
        libcap \
        logrotate \
        docker-cli \
        jq \
        util-linux \
        tzdata \
        syslog-ng \
        syslog-ng-json \
        iputils \
        net-tools \
        bash \
    && setcap 'cap_net_bind_service=+ep' /usr/sbin/syslog-ng \
    && adduser -D -s /bin/bash abdullah \
    && mkdir -p /app/config /app/logrotate /mnt/Data/Syslog/default/logrotate /mnt/Data/Syslog/var-run /etc/logrotate.d/backup

# Salin file konfigurasi & script
COPY config/syslog-ng.conf /app/config/syslog-ng.conf
COPY entrypoint.sh /app/entrypoint.sh
COPY logrotate/syslog-ng /app/logrotate/syslog-ng

# Set izin eksekusi
RUN chmod +x /app/entrypoint.sh

# Stage 2: Final
FROM alpine:3.18

# Install dependencies runtime
RUN apk update && apk add --no-cache \
        syslog-ng \
        syslog-ng-json \
        libcap \
        logrotate \
        docker-cli \
        jq \
        util-linux \
        tzdata \
        iputils \
        net-tools \
        bash

# Ganti mirror default ke Leaseweb
RUN sed -i 's|http://dl-cdn.alpinelinux.org/alpine/|http://mirror.leaseweb.com/alpine/|g' /etc/apk/repositories

# Tambahkan user non-root
RUN adduser -D -s /bin/bash abdullah

# Buat direktori yang dibutuhkan
RUN mkdir -p /app/config /app/logrotate /mnt/Data/Syslog/default/logrotate /mnt/Data/Syslog/var-run /etc/logrotate.d/backup

# Copy dependencies dari stage builder
COPY --from=builder /usr/sbin/syslog-ng /usr/sbin/syslog-ng
COPY --from=builder /app/config/syslog-ng.conf /app/config/syslog-ng.conf
COPY --from=builder /app/entrypoint.sh /app/entrypoint.sh
COPY --from=builder /app/logrotate/syslog-ng /app/logrotate/syslog-ng

# Set izin eksekusi dan kepemilikan
RUN chmod +x /app/entrypoint.sh \
    && chown -R abdullah:abdullah /app /mnt/Data/Syslog /etc/logrotate.d

# Set working directory
WORKDIR /app

# Expose port syslog
EXPOSE 1514/udp 1514/tcp

# Switch ke user non-root
USER abdullah

# Jalankan script entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]