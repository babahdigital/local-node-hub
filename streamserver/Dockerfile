# Gunakan base image alfg/nginx-rtmp
FROM alfg/nginx-rtmp

# Install ffmpeg using Alpine's package manager (apk)
RUN apk add --no-cache ffmpeg bash jq

# Set WORKDIR ke direktori aplikasi
WORKDIR /app/streamserver

# Salin konfigurasi nginx
COPY config/nginx.conf /etc/nginx/nginx.conf

CMD ["nginx", "-g", "daemon off;"]