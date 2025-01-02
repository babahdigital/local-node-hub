# Tahap 1: Builder
FROM alpine:3.21 AS builder

ENV APK_MIRROR=http://mirror.leaseweb.com/alpine/

RUN sed -i "s|http://dl-cdn.alpinelinux.org/alpine/|${APK_MIRROR}|g" /etc/apk/repositories \
    && apk update \
    && apk add --no-cache \
        gcc \
        musl-dev \
        libcap \
        syslog-ng \
        syslog-ng-json \
        logrotate \
        docker-cli \
        jq \
        dcron \
        sudo \
        bash

# Ijinkan syslog-ng bind port <1024
RUN setcap 'cap_net_bind_service=+ep' /usr/sbin/syslog-ng

WORKDIR /app/syslog

# Buat struktur direktori untuk aplikasi
RUN mkdir -p config logrotate crontabs var-run \
           /app/syslog/var-run \
           /app/syslog/config \
           /etc/logrotate.d/backup \
           /mnt/Data/Syslog/default \
           /mnt/Data/Syslog/test \
           /mnt/Data/Syslog/debug

COPY . /app/syslog
RUN chmod +x /app/syslog/entrypoint.sh /app/syslog/config/generate_rotate.sh

# Tahap 2: Final
FROM alpine:3.21
ENV APK_MIRROR=http://mirror.leaseweb.com/alpine/

RUN sed -i "s|http://dl-cdn.alpinelinux.org/alpine/|${APK_MIRROR}|g" /etc/apk/repositories \
    && apk update \
    && apk add --no-cache \
        gcc \
        musl-dev \
        libcap \
        syslog-ng \
        syslog-ng-json \
        logrotate \
        docker-cli \
        jq \
        dcron \
        sudo \
        bash

# Pastikan user abdullah ada (buat hanya jika belum ada)
RUN id -u abdullah &>/dev/null || adduser -D -s /bin/bash abdullah

# Pastikan crond dapat dieksekusi user biasa
RUN chmod 755 /usr/sbin/crond

# Tambahkan folder /run dan var-run agar user abdullah dapat menulis
RUN mkdir -p /run /app/syslog/var-run \
 && chown -R abdullah:abdullah /app/syslog/var-run \
 && chmod 755 /etc/logrotate.d

# Pindahkan konfigurasi tetap di /app/syslog/config
RUN mkdir -p /app/syslog/config \
 && chown -R abdullah:abdullah /app/syslog/config

# Salin aplikasi dari builder
COPY --from=builder /app/syslog /app/syslog
RUN chown -R abdullah:abdullah /app/syslog

WORKDIR /app/syslog

# Pastikan entrypoint dijalankan
ENTRYPOINT ["/app/syslog/entrypoint.sh"]y