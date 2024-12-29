FROM nginx:alpine

LABEL maintainer="babahdigital"
LABEL version="1.0"
LABEL description="Proxy berbasis Nginx dengan konfigurasi dinamis."

# Buat pengguna dan grup abdullah
RUN addgroup -S abdullah && adduser -S abdullah -G abdullah

RUN apk add --no-cache bash jq && mkdir -p /app/logs

COPY config/nginx.conf.template /app/config/
COPY entrypoint.sh /app/

RUN chmod +x /app/entrypoint.sh

EXPOSE 8554

ENTRYPOINT ["/app/entrypoint.sh"]