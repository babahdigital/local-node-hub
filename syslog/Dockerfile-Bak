# Gunakan base image Alpine (versi terbaru atau spesifik)
FROM alpine:latest

# Ganti mirror default ke Leaseweb (atau dl-cdn.alpinelinux.org)
RUN sed -i 's|http://dl-cdn.alpinelinux.org/alpine/|http://mirror.leaseweb.com/alpine/|g' /etc/apk/repositories

# Update & Install dependencies
RUN apk update && apk add --no-cache \
    bash \
    net-tools \
    iputils \
    syslog-ng \
    syslog-ng-json \
    libcap \
    logrotate \
    docker-cli \
    jq \
    util-linux \
    tzdata

# Set capabilities untuk binary syslog-ng agar bisa bind port < 1024
RUN setcap 'cap_net_bind_service=+ep' /usr/sbin/syslog-ng

# Tambahkan user 'abdullah' (non-root)
RUN adduser -D -s /bin/bash abdullah

# Buat direktori yang dibutuhkan, ubah owner
RUN mkdir -p /app/config /app/logrotate /mnt/Data/Syslog/default/logrotate /mnt/Data/Syslog/var-run /etc/logrotate.d/backup \
    && chown -R abdullah:abdullah /app /mnt/Data/Syslog /etc/logrotate.d

# Copy file konfigurasi & script
COPY config/syslog-ng.conf /app/config/syslog-ng.conf
COPY entrypoint.sh /app/entrypoint.sh
COPY logrotate/syslog-ng /app/logrotate/syslog-ng

# Beri izin eksekusi pada script entrypoint
RUN chmod +x /app/entrypoint.sh

# Set working directory
WORKDIR /app

# Expose port syslog
EXPOSE 1514/udp 1514/tcp

# Switch ke user non-root
USER abdullah

# Jalankan script entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]