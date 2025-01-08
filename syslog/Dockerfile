FROM alpine:3.21

ENV APK_MIRROR=http://mirror.leaseweb.com/alpine/

# 1. Ganti mirror, install paket yang dibutuhkan
RUN sed -i "s|http://dl-cdn.alpinelinux.org/alpine/|${APK_MIRROR}|g" /etc/apk/repositories \
  && apk update \
  && apk add --no-cache \
     libcap \
     syslog-ng \
     syslog-ng-json \
     logrotate \
     jq \
     dcron \
     sudo \
     bash \
     procps \
     util-linux \
  && id -u abdullah &>/dev/null || adduser -D -s /bin/bash abdullah \
  && chmod 755 /usr/sbin/crond \
  && mkdir -p /run /app/syslog/var-run \
              /app/syslog/logrotate/crontabs \
  && chmod 755 /etc/logrotate.d

# 2. Buat folder kerja
WORKDIR /app/syslog

# 3. Salin semua file (script, config syslog-ng, dll.) 
#    + log_messages.json ke /app/config
COPY ./syslog /app/syslog

# 4. Pastikan skrip entrypoint dapat dieksekusi
RUN chmod +x /app/syslog/entrypoint.sh

# 5. Expose port 1514 (TCP/UDP)
EXPOSE 1514/tcp
EXPOSE 1514/udp

# 6. Jalankan skrip entrypoint terpusat (unified) 
ENTRYPOINT ["/app/syslog/entrypoint.sh"]