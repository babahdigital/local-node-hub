# Stage 1: Build
FROM python:3.11-alpine AS builder

# Install dependencies build
RUN apk update && apk add --no-cache \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev \
    openssl-dev \
    build-base

WORKDIR /app

# Salin dan install dependencies Python
COPY hdd/requirements.txt /app/hdd/
COPY config/log_messages.json /app/hdd/config/
RUN pip install --prefix=/install --no-cache-dir -r hdd/requirements.txt

# Salin script Python
COPY hdd/hdd_monitor.py /app/hdd/
COPY hdd/entrypoint.sh /app/hdd/

# Stage 2: Final
FROM python:3.11-alpine

WORKDIR /app

# Copy dependencies yang diinstall dari stage builder
COPY --from=builder /install /usr/local

# Salin script Python dari stage builder
COPY hdd/hdd_monitor.py /app/hdd/
COPY config/log_messages.json /app/hdd/config/
COPY hdd/entrypoint.sh /app/hdd/entrypoint.sh

RUN chmod +x /app/hdd/entrypoint.sh

# Expose port Flask
EXPOSE 5000

ENTRYPOINT ["/app/hdd/entrypoint.sh"]

# Jalankan aplikasi dengan Gunicorn
#CMD ["gunicorn", "--bind", "0.0.0.0:5000", "hdd_monitor:app"]