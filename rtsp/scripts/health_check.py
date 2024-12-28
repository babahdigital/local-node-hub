from flask import Flask, jsonify
import os
import logging
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Konfigurasi dari .env
HEALTH_CHECK_PORT = int(os.getenv("HEALTH_CHECK_PORT", 8080))
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", "/app/config/log_messages.json")
ENABLE_SYSLOG = os.getenv("ENABLE_SYSLOG", "true").lower() == "true"
SYSLOG_SERVER = os.getenv("SYSLOG_SERVER", "syslog-ng")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", "1514"))

# Load log messages
def load_log_messages(file_path):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Gagal memuat pesan log dari {file_path}: {e}")

# Validasi log messages
try:
    log_messages = load_log_messages(LOG_MESSAGES_FILE)
except RuntimeError as e:
    print(e)
    exit(1)

# Logging Setup
logger = logging.getLogger("HealthCheck")
logger.setLevel(logging.INFO)

if ENABLE_SYSLOG:
    from logging.handlers import SysLogHandler
    syslog_handler = SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))
    syslog_formatter = logging.Formatter('[HEALTH-CHECK] %(message)s')
    syslog_handler.setFormatter(syslog_formatter)
    logger.addHandler(syslog_handler)

# Endpoint untuk health check
@app.route('/health', methods=['GET'])
def health_check():
    """
    Endpoint untuk memeriksa kesehatan layanan.
    """
    try:
        logger.info(log_messages["health_check"]["endpoint_accessed"])
        # Contoh status layanan (dapat disesuaikan sesuai kebutuhan)
        status = {
            "livestream_status": "healthy",
            "backup_manager_status": "healthy",
            "disk_status": "healthy",
        }
        logger.info(log_messages["health_check"]["return_from_cache"])
        return jsonify({"status": log_messages["health_check"]["healthy"], "details": status}), 200
    except Exception as e:
        logger.error(log_messages["health_check"]["processing_error"].format(error=str(e)))
        return jsonify({"status": log_messages["health_check"]["unhealthy"], "error": str(e)}), 500

# Jalankan Health Check Server
if __name__ == "__main__":
    try:
        logger.info(log_messages["health_check"]["service_starting"].format(port=HEALTH_CHECK_PORT))
        app.run(host="0.0.0.0", port=HEALTH_CHECK_PORT)
    except Exception as e:
        logger.error(log_messages["health_check"]["service_failed"].format(error=str(e)))
