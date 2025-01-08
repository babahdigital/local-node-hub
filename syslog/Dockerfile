FROM alpine:3.21
# atau python:3.10-alpine jika script butuh Python bawaan

ENV APK_MIRROR=http://mirror.leaseweb.com/alpine/

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
       python3 \
       py3-pip  # jika perlu

WORKDIR /app/syslog

# Salin script python (main.py) ke container
COPY ./syslog/main.py /app/syslog/main.py

# Pastikan main.py bisa dieksekusi
RUN chmod +x /app/syslog/main.py

# Expose port syslog
EXPOSE 1514/tcp
EXPOSE 1514/udp

# Jalankan Python di foreground
ENTRYPOINT ["/app/syslog/main.py"]