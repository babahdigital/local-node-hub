# Tahap 1: Build (memasang dependensi dan library)
FROM python:3.9-alpine AS builder

RUN apk add --no-cache gcc musl-dev libffi-dev python3-dev py3-pip

WORKDIR /app/resource

COPY ./resource/ /app/resource
COPY ./scripts/utils.py /app/scripts/utils.py
COPY ./config/log_messages.json /app/config/log_messages.json

RUN pip install --no-cache-dir --prefix=/install psutil pytz python-dotenv

# Tahap 2: Runtime (image akhir yang kecil)
FROM python:3.9-alpine

# Tambahkan iputils agar 'ping' dipastikan ada, plus utilitas lain
RUN apk add --no-cache procps tzdata bash iputils

# Salin pustaka Python yang diinstal dari tahap build
COPY --from=builder /install /usr/local

WORKDIR /app/resource
COPY ./resource/ /app/resource
COPY ./scripts/utils.py /app/scripts/utils.py
COPY ./config/log_messages.json /app/config/log_messages.json

# Jalankan script resource_monitor.py
CMD ["python", "/app/resource/resource_monitor.py"]