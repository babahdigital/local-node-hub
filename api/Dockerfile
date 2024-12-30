# Gunakan base image Python slim
FROM python:3.11-slim

# Menetapkan environment variable untuk performa
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install dependensi sistem
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Buat direktori yang diperlukan
RUN mkdir -p /app/api/

# Salin file requirements terlebih dahulu
COPY api/requirements.txt /app/api/requirements.txt

# Install dependensi Python
RUN pip install --no-cache-dir -r /app/api/requirements.txt

# Salin seluruh aplikasi
COPY api/ /app/api/

# Buat direktori data
RUN mkdir -p /app/api/data

# Memberikan izin eksekusi
RUN chmod -R 755 /app/api/

# Jalankan Gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5001", "--timeout", "60", "backend_api:app"]