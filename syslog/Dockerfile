# Tahap 1: Builder
FROM alpine:3.21 AS builder

# Set variabel lingkungan untuk APK mirror
ENV APK_MIRROR=http://mirror.leaseweb.com/alpine/

# Ganti repositori APK default dengan mirror Leaseweb dan update
RUN sed -i "s|http://dl-cdn.alpinelinux.org/alpine/|${APK_MIRROR}|g" /etc/apk/repositories \
    && apk update

# Instal dependensi build dan paket-paket yang diperlukan
# gcc: Kompilator C, diperlukan jika Anda mengkompilasi dari sumber
# musl-dev: Header dan library untuk musl, diperlukan untuk kompilasi
# libcap: Library untuk mengatur kemampuan (capabilities) pada executable
# syslog-ng: Daemon syslog untuk pengelolaan log
# syslog-ng-json: Modul JSON untuk syslog-ng
# logrotate: Alat untuk mengelola rotasi log
# docker-cli: CLI Docker untuk interaksi dengan Docker daemon
# jq: Alat untuk memproses JSON di baris perintah
# bash: Shell Bash
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libcap \
    syslog-ng \
    syslog-ng-json \
    logrotate \
    docker-cli \
    jq \
    bash

# Atur kemampuan untuk syslog-ng agar dapat mengikat port yang dilindungi
RUN setcap 'cap_net_bind_service=+ep' /usr/sbin/syslog-ng

# Buat pengguna non-root bernama 'abdullah'
RUN adduser -D -s /bin/bash abdullah

# Buat direktori yang diperlukan dengan izin yang sesuai
RUN mkdir -p \
    /app/config \
    /app/logrotate \
    /mnt/Data/Syslog/default/logrotate \
    /mnt/Data/Syslog/var-run \
    /etc/logrotate.d/backup \
    && chown -R abdullah:abdullah /app /mnt/Data/Syslog /etc/logrotate.d

# Salin file konfigurasi dan skrip
COPY config/syslog-ng.conf /app/config/syslog-ng.conf
COPY entrypoint.sh /app/entrypoint.sh
COPY logrotate/syslog-ng /app/logrotate/syslog-ng
COPY generate_logrotate.sh /app/generate_logrotate.sh  # Pastikan skrip ini ada

# Berikan izin eksekusi untuk skrip dan entrypoint
RUN chmod +x /app/entrypoint.sh /app/generate_logrotate.sh

# Tahap 2: Final
FROM alpine:3.21

# Set variabel lingkungan untuk APK mirror
ENV APK_MIRROR=http://mirror.leaseweb.com/alpine/

# Ganti repositori APK default dengan mirror Leaseweb dan update
RUN sed -i "s|http://dl-cdn.alpinelinux.org/alpine/|${APK_MIRROR}|g" /etc/apk/repositories \
    && apk update

# Instal dependensi runtime
# syslog-ng: Daemon syslog untuk pengelolaan log
# syslog-ng-json: Modul JSON untuk syslog-ng
# libcap: Library untuk mengatur kemampuan (capabilities) pada executable
# logrotate: Alat untuk mengelola rotasi log
# docker-cli: CLI Docker untuk interaksi dengan Docker daemon
# jq: Alat untuk memproses JSON di baris perintah
# bash: Shell Bash
RUN apk add --no-cache \
    syslog-ng \
    syslog-ng-json \
    libcap \
    logrotate \
    docker-cli \
    jq \
    bash

# Buat pengguna non-root bernama 'abdullah'
RUN adduser -D -s /bin/bash abdullah

# Buat direktori yang diperlukan
RUN mkdir -p \
    /app/config \
    /app/logrotate \
    /mnt/Data/Syslog/default/logrotate \
    /mnt/Data/Syslog/var-run \
    /etc/logrotate.d/backup

# Salin binary syslog-ng dan konfigurasi dari tahap builder
COPY --from=builder /usr/sbin/syslog-ng /usr/sbin/syslog-ng
COPY --from=builder /app/config/syslog-ng.conf /app/config/syslog-ng.conf
COPY --from=builder /app/entrypoint.sh /app/entrypoint.sh
COPY --from=builder /app/logrotate/syslog-ng /app/logrotate/syslog-ng
COPY --from=builder /app/generate_logrotate.sh /app/generate_logrotate.sh  # Salin skrip generate_logrotate.sh

# Berikan izin eksekusi dan atur kepemilikan
RUN chmod +x /app/entrypoint.sh /app/generate_logrotate.sh \
    && chown -R abdullah:abdullah /app /mnt/Data/Syslog /etc/logrotate.d

# Atur kemampuan untuk syslog-ng agar dapat mengikat port yang dilindungi
RUN setcap 'cap_net_bind_service=+ep' /usr/sbin/syslog-ng

# Set direktori kerja
WORKDIR /app

# Buka port untuk syslog
EXPOSE 1514/udp 1514/tcp

# Gunakan pengguna non-root
USER abdullah

# Definisikan entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Tambahkan HEALTHCHECK
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD pgrep syslog-ng || exit 1