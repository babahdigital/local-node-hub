# Menggunakan base image python:3.9-slim yang minimal
FROM python:3.9-slim

# Supaya log Python langsung dicetak ke stdout (tanpa buffering)
ENV PYTHONUNBUFFERED=1

# 1. Install native libraries yang diperlukan OpenCV + FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    ffmpeg \
    jq \
    sudo \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# 2. Tetapkan direktori kerja
WORKDIR /app/backup

# 3. Copy dahulu file requirements.txt agar caching layer efektif
COPY ./backup/requirements.txt /app/backup/requirements.txt
COPY ./config/credentials.sh /app/config/credentials.sh

# 4. Install dependencies Python (OpenCV, dsb.)
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy sisa source code (main.py, motion_detection.py, dsb.)
COPY ./backup /app/backup

# 6. Credentials:
RUN chmod +x /app/config/credentials.sh
RUN chmod +x /app/backup/entrypoint.sh

# 7. Jalankan main.py secara default
#ENTRYPOINT ["/app/backup/entrypoint.sh"]
CMD ["/bin/bash", "-c", "source /app/config/credentials.sh && exec python main.py"]