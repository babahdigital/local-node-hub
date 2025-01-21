#!/bin/bash
# entrypoint.sh
# 1) source credentials jika ada
# 2) jalankan supervisord
# (supervisord.conf kita siapkan di /etc/supervisor/supervisord.conf atau di /app/config)

set -e

# Cek jika ada credentials
if [ -f /app/config/credentials.sh ]; then
  source /app/config/credentials.sh
fi

# Jalankan supervisord
exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf