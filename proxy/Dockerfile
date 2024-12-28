# Gunakan base image Nginx
FROM nginx:alpine

# Install utilitas envsubst dan bash
RUN apk add --no-cache gettext bash

# Salin template nginx.conf
COPY config/nginx.conf.template /app/config/nginx.conf.template

# CMD untuk membaca credentials.sh dari volume dan generate nginx.conf
CMD ["/bin/sh", "-c", "source /app/config/credentials.sh && envsubst < /app/config/nginx.conf.template > /etc/nginx/nginx.conf && nginx -g 'daemon off;'"]

# Buat direktori untuk log
RUN mkdir -p /app/logs

# Expose port untuk RTSP
EXPOSE 8554