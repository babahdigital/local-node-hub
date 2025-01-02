# Menggunakan base image Nginx (atau Alpine jika perlu)
FROM nginx:alpine

# Install FFmpeg, Bash, jq, Python, dan alat tambahan
RUN apk add --no-cache ffmpeg bash jq python3 py3-pip dos2unix

# Direktori kerja
WORKDIR /app/streamserver

# Buat folder sebelum runtime
RUN mkdir -p /app/streamserver/temp/client_body_temp \
    /app/streamserver/temp/proxy_temp \
    /app/streamserver/temp/fastcgi_temp \
    /app/streamserver/temp/scgi_temp \
    /app/streamserver/temp/uwsgi_temp \
    /app/streamserver/temp/stream \
    /app/streamserver/config \
    /app/streamserver/scripts

# Membuat virtual environment untuk Python
RUN python3 -m venv /app/streamserver/venv

# Aktifkan virtual environment dan install dependensi Python
RUN /app/streamserver/venv/bin/pip install --no-cache-dir python-dotenv

# Salin file lainnya (disesuaikan dengan kebutuhan)
COPY streamserver/scripts/validate_cctv.py /app/streamserver/scripts/validate_cctv.py
COPY streamserver/config /app/streamserver/config
COPY ../scripts/utils.py /app/streamserver/scripts/utils.py

# Salin skrip konfigurasi
COPY streamserver/entrypoint.sh /app/streamserver/entrypoint.sh
RUN dos2unix /app/streamserver/entrypoint.sh && \
    chmod +x /app/streamserver/entrypoint.sh

# Entry point
ENTRYPOINT ["/app/streamserver/entrypoint.sh"]