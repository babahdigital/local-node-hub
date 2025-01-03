FROM nginx:stable-alpine

RUN apk add --no-cache \
    ffmpeg \
    bash \
    jq \
    python3 \
    py3-pip \
    dos2unix

# Direktori kerja
WORKDIR /app/streamserver

# Salin hanya isi folder 'streamserver' (yang memuat Dockerfile, entrypoint, dsb.)
COPY . /app/streamserver
COPY . /app/streamserver

# Convert line-ending & set permission
RUN dos2unix entrypoint.sh && \
    chmod +x entrypoint.sh

# (Opsional) Buat virtual environment
RUN python3 -m venv venv && \
    /app/streamserver/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /app/streamserver/venv/bin/pip install --no-cache-dir python-dotenv

EXPOSE 1935 8080

ENTRYPOINT ["/app/streamserver/entrypoint.sh"]