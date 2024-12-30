# Gunakan base image Python slim
FROM python:3.11-slim

# Install dependencies sistem
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Buat direktori kerja
WORKDIR /app

# Salin file requirements.txt
COPY requirements.txt /app/

# Install dependencies Python
RUN pip install --no-cache-dir -r requirements.txt

# Salin file script Python
COPY hdd_monitor.py /app/

# Pastikan direktori log tersedia
RUN mkdir -p /mnt/Data/Syslog/rtsp

# Gunakan Gunicorn untuk menjalankan Flask
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "hdd_monitor:app"]