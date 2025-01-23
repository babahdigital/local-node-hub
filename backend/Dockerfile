# ---------------------------------------------------------
# STAGE 1: BUILDER
# ---------------------------------------------------------
    FROM python:3.11-slim AS builder

    # Menonaktifkan bytecode dan buffer
    ENV PYTHONDONTWRITEBYTECODE=1
    ENV PYTHONUNBUFFERED=1
    
    # Install paket build-essential, gcc, libffi-dev dsb. jika dibutuhkan
    RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc libffi-dev curl \
        && rm -rf /var/lib/apt/lists/*
    
    # Set direktori kerja
    WORKDIR /app/backend
    
    # Salin file requirements
    COPY ./backend/requirements.txt .
    
    # Upgrade pip dan siapkan wheels
    RUN pip install --no-cache-dir --upgrade pip wheel
    RUN pip wheel --no-cache-dir -r requirements.txt -w /app/wheels
    
    # ---------------------------------------------------------
    # STAGE 2: FINAL (RUNTIME)
    # ---------------------------------------------------------
    FROM python:3.11-slim AS final
    
    ENV PYTHONDONTWRITEBYTECODE=1
    ENV PYTHONUNBUFFERED=1
    
    # Install paket minimal runtime (termasuk supervisor jika dibutuhkan)
    RUN apt-get update && apt-get install -y --no-install-recommends \
        curl supervisor \
        && rm -rf /var/lib/apt/lists/*
    
    # Direktori kerja di container
    WORKDIR /app/backend
    
    # Salin wheels dari stage builder
    COPY --from=builder /app/wheels /app/wheels
    
    # Install dependency dari wheels (paket python Anda)
    RUN pip install --no-cache-dir /app/wheels/*
    
    # Salin keseluruhan source code backend
    COPY ./backend /app/backend
    
    # Buat direktori data/log (opsional), atur permission
    RUN mkdir -p /app/backend/data \
        && chmod -R 755 /app/backend/
    
    # Expose port 5001 (opsional, dokumentasi)
    EXPOSE 5001
    
    # Salin file supervisor.conf ke dalam container
    COPY ./backend/config/supervisor.conf /etc/supervisor/conf.d/supervisor.conf
    
    # Menjalankan Supervisor (yang memanggil Gunicorn)
    CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisor.conf"]
    
    # Jika Anda tidak ingin Supervisor,
    # pakai perintah CMD Gunicorn langsung, misal:
    # CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5001", "--timeout", "60", "backend_api:app"]    