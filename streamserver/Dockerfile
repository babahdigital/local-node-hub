# Gunakan base image python slim (bisa diganti versi lain)
FROM python:3.12-slim

# Pastikan kita bisa install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Buat folder /app/streamserver di dalam container
WORKDIR /app/streamserver

# (Opsional) Salin file requirements jika ingin install library tambahan
# COPY requirements.txt /app/streamserver/
# RUN pip install --no-cache-dir -r requirements.txt

# Salin semua file dari folder host "streamserver" ke container "/app/streamserver"
COPY ./streamserver /app/streamserver
COPY ./config/credentials.sh /app/config/credentials.sh

# Pastikan file credentials.sh bersifat executable (jika ingin di-run di container)
RUN chmod +x /app/config/credentials.sh || true

# Expose port 5000 (untuk Flask)
EXPOSE 5000

# Jalankan server
CMD ["/bin/bash", "-c", "source /app/config/credentials.sh && exec python main.py"]