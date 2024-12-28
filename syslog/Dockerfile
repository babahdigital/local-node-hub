# Gunakan base image Alpine
FROM alpine:latest

# Gunakan mirror alternatif untuk repository Alpine
RUN sed -i 's|http://dl-cdn.alpinelinux.org/alpine/|http://mirror.leaseweb.com/alpine/|g' /etc/apk/repositories

# Install dependencies dan syslog-ng
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
    tzdata

# Set capabilities untuk binary syslog-ng
RUN setcap 'cap_net_bind_service=+ep' /usr/sbin/syslog-ng

# Add non-root user 'abdullah' untuk keamanan
RUN adduser -D -s /bin/bash abdullah

# Create necessary directories dan set permissions
RUN mkdir -p /app/config /app/logrotate /mnt/Data/Syslog /etc/logrotate.d/backup \
    && chown -R abdullah:abdullah /app /mnt/Data/Syslog /etc/logrotate.d

# Copy konfigurasi syslog-ng dan script entrypoint
COPY config/syslog-ng.conf /app/config/syslog-ng.conf
COPY entrypoint.sh /app/entrypoint.sh
COPY logrotate/syslog-ng /app/logrotate/syslog-ng

# Beri izin eksekusi pada script
RUN chmod +x /app/entrypoint.sh

# Set working directory
WORKDIR /app

# Expose ports untuk syslog-ng
EXPOSE 1514/udp 1514/tcp

# Switch ke non-root user
USER abdullah

# Gunakan entrypoint untuk menjalankan script logrotate dan syslog-ng
ENTRYPOINT ["/app/entrypoint.sh"]