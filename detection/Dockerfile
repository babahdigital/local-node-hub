# Menggunakan base image python:3.9-slim yang minimal
FROM python:3.9-slim

# Supaya log Python langsung dicetak ke stdout (tanpa buffering)
ENV PYTHONUNBUFFERED=1

# 1. Install native libraries yg diperlukan OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Tetapkan direktori kerja
WORKDIR /app/detection

# 3. Copy dahulu file requirements.txt agar caching layer efektif
COPY ./detection/requirements.txt /app/detection/requirements.txt

# 4. Install dependencies Python (OpenCV, dsb.)
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy sisa source code (main.py, motion_detection.py, dsb.)
COPY ./detection /app/detection

# (Opsional) 6. Jika Anda masih pakai validate_model.py:
# RUN python validate_model.py

# 7. Jalankan main.py secara default (headless deteksi gerakan, dsb.)
CMD ["python", "main.py"]