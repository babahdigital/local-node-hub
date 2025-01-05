# Tahap 1: Builder
FROM alpine:3.21 AS builder

# Gunakan mirror tercepat untuk paket APK
ENV APK_MIRROR=http://mirror.leaseweb.com/alpine/

RUN sed -i "s|http://dl-cdn.alpinelinux.org/alpine/|${APK_MIRROR}|g" /etc/apk/repositories && \
    apk update && \
    apk add --no-cache \
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
        bash \
        procps \
        util-linux

WORKDIR /app/syslog

# Buat struktur direktori dan salin file
RUN mkdir -p config logrotate var-run && \
    chmod 755 /app/syslog

COPY ./syslog /app/syslog
COPY ./config/log_messages.json /app/config/log_messages.json
RUN chmod +x /app/syslog/entrypoint.sh /app/syslog/logrotate/entrypoint-logrotate.sh /app/syslog/logrotate/generate_rotate.sh

# Tahap 2: Final
FROM alpine:3.21

ENV APK_MIRROR=http://mirror.leaseweb.com/alpine/

RUN sed -i "s|http://dl-cdn.alpinelinux.org/alpine/|${APK_MIRROR}|g" /etc/apk/repositories && \
    apk update && \
    apk add --no-cache \
        libcap \
        syslog-ng \
        syslog-ng-json \
        logrotate \
        docker-cli \
        jq \
        dcron \
        sudo \
        bash \
        procps \
        util-linux && \
    id -u abdullah &>/dev/null || adduser -D -s /bin/bash abdullah && \
    chmod 755 /usr/sbin/crond && \
    mkdir -p /run /app/syslog/var-run && \
    chmod 755 /etc/logrotate.d

WORKDIR /app/syslog

# Salin aplikasi dari builder
COPY --from=builder /app/syslog /app/syslog
COPY --from=builder /app/config /app/config

ENTRYPOINT ["/app/syslog/entrypoint.sh"]
EXPOSE 1514