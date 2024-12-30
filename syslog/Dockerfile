# Tahap 1: Builder
FROM alpine:3.21 AS builder

# Set variabel lingkungan untuk APK mirror
ENV APK_MIRROR=http://mirror.leaseweb.com/alpine/

# Update APK mirror dan instal dependensi build
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
        bash

# Atur kemampuan untuk syslog-ng agar dapat mengikat port yang dilindungi
RUN setcap 'cap_net_bind_service=+ep' /usr/sbin/syslog-ng

# Buat direktori kerja
WORKDIR /app

RUN mkdir -p /app/config /app/logrotate /mnt/Data/Syslog/default/logrotate /mnt/Data/Syslog/var-run /etc/logrotate.d/backup

# Salin file konfigurasi dan skrip
COPY syslog/ /app
COPY config/log_messages.json /app/config/log_messages.json
COPY syslog/config/syslog-ng.conf /app/config/syslog-ng.conf
copy syslog/config/generate_rotate.sh /app/generate_rotate.sh
copy syslog/entrypoint.sh /app/entrypoint.sh

# Berikan izin eksekusi pada skrip
RUN chmod +x /app/entrypoint.sh /app/generate_rotate.sh

# Tahap 2: Final
FROM alpine:3.21

# Set variabel lingkungan untuk APK mirror
ENV APK_MIRROR=http://mirror.leaseweb.com/alpine/

# Update APK mirror dan instal dependensi runtime
RUN sed -i "s|http://dl-cdn.alpinelinux.org/alpine/|${APK_MIRROR}|g" /etc/apk/repositories \
    && apk update \
    && apk add --no-cache \
        syslog-ng \
        syslog-ng-json \
        libcap \
        logrotate \
        docker-cli \
        jq \
        dcron \
        bash

# Buat pengguna non-root bernama 'abdullah'
RUN adduser -D -s /bin/bash abdullah

# Buat direktori yang diperlukan
RUN mkdir -p /app/config /app/logrotate /mnt/Data/Syslog/default/logrotate /mnt/Data/Syslog/var-run /etc/logrotate.d/backup

# Salin file dan konfigurasi dari tahap builder
COPY --from=builder /usr/sbin/syslog-ng /usr/sbin/syslog-ng
COPY --from=builder /app /app

# Berikan izin eksekusi dan atur kepemilikan
RUN chmod +x /app/entrypoint.sh /app/generate_rotate.sh \
    && chown -R abdullah:abdullah /app /mnt/Data/Syslog /etc/logrotate.d

# Atur kemampuan untuk syslog-ng agar dapat mengikat port yang dilindungi
RUN setcap 'cap_net_bind_service=+ep' /usr/sbin/syslog-ng

# Buka port untuk syslog
EXPOSE 1514/udp 1514/tcp

# Gunakan pengguna non-root
USER abdullah

# Definisikan direktori kerja
WORKDIR /app

# Definisikan entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Tambahkan HEALTHCHECK
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD pgrep syslog-ng || exit 1