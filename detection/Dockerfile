FROM python:3.9-slim

# 1. Install native libraries untuk OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Atur direktori kerja
WORKDIR /app/detection

# 3. Copy folder detection ke /app/detection
COPY ./detection /app/detection

# 4. Install dependencies Python (OpenCV, dsb.)
RUN pip install --no-cache-dir -r requirements.txt

# 5. Validasi model (MobileNet SSD, dsb.)
RUN python validate_model.py

# 6. Jalankan main.py secara default
CMD ["python", "main.py"]