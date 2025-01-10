# Gunakan base image python slim (bisa diganti versi lain)
FROM python:3.12-slim

# Pastikan kita bisa install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Buat folder /app/streamserver di dalam container
WORKDIR /app/streamserver

# Salin file requirements dan install dependencies
COPY ./streamserver/requirements.txt /app/streamserver
RUN pip install --no-cache-dir -r requirements.txt

# Salin semua file dari folder host "streamserver" ke container "/app/streamserver"
COPY ./streamserver /app/streamserver

# Salin credentials.sh ke /app/config
COPY ./config/credentials.sh /app/config/credentials.sh
RUN chmod +x /app/config/credentials.sh || true

# Expose port 5000 (untuk Gunicorn)
EXPOSE 5000

# Jalankan Gunicorn
# - Di sini kita source credentials.sh agar RTSP_USER_BASE64 dsb. di-export ke environment
# - Kemudian jalankan gunicorn dengan bind 0.0.0.0:5000
# - Asumsikan main.py punya "app = Flask(__name__)"
CMD ["/bin/bash", "-c", "source /app/config/credentials.sh && exec gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout ${GUNICORN_WORKER_TIMEOUT:-60} main:app"]
#CMD ["/bin/bash", "-c", "source /app/config/credentials.sh && exec gunicorn --bind 0.0.0.0:5000 main:app"]
