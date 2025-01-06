# Tahap 1: Build (memasang dependensi dan library)
FROM python:3.9-alpine AS builder

# Instal alat dan pustaka yang diperlukan untuk kompilasi
RUN apk add --no-cache gcc musl-dev libffi-dev python3-dev py3-pip

# Direktori kerja
WORKDIR /app/resource

# Salin script dan dependensi
COPY ./resource/ /app/resource
COPY ./scripts/utils.py /app/scripts/utils.py

# Instal pustaka Python
RUN pip install --no-cache-dir --prefix=/install psutil pytz python-dotenv

# Tahap 2: Runtime (image akhir yang kecil)
FROM python:3.9-alpine

# Instal `pgrep`, timezone, dan dependensi runtime yang diperlukan
RUN apk add --no-cache procps tzdata

# Salin pustaka yang diinstal dari tahap build
COPY --from=builder /install /usr/local

# Salin script ke image runtime
WORKDIR /app/resource 
COPY ./resource/ /app/resource
COPY ./scripts/utils.py /app/scripts/utils.py

# Menetapkan entrypoint untuk script Python
CMD ["python", "/app/resource/resource_monitor.py"]