import requests
import json
import time
import logging

# Logging Setup
logger = logging.getLogger("ReportManager")
logger.setLevel(logging.INFO)

# Konfigurasi dari variabel lingkungan
BACKEND_ENDPOINT = os.getenv("BACKEND_ENDPOINT", "http://127.0.0.1:5001/api/report")
MAX_RETRIES = int(os.getenv("BACKEND_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "10"))
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", "/app/config/log_messages.json")

# Load log messages dari JSON
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

def send_report_to_backend(endpoint, payload):
    """
    Mengirimkan laporan ke backend dengan mekanisme retry.
    """
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            logger.info(log_messages["report_manager"]["report_success"].format(payload=json.dumps(payload)))
            response = requests.post(endpoint, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info(log_messages["report_manager"]["report_success"].format(payload=payload))
                return True
            else:
                logger.warning(log_messages["report_manager"]["report_failed_attempt"].format(
                    attempt=attempt + 1,
                    retries=MAX_RETRIES,
                    status_code=response.status_code,
                    response_text=response.text
                ))
        except requests.RequestException as e:
            logger.error(log_messages["report_manager"]["request_exception"].format(
                attempt=attempt + 1,
                retries=MAX_RETRIES,
                error=str(e)
            ))
        
        attempt += 1
        logger.info(log_messages["report_manager"]["wait_before_retry"].format(delay=RETRY_DELAY))
        time.sleep(RETRY_DELAY)

    logger.error(log_messages["report_manager"]["report_failed"].format(
        retries=MAX_RETRIES,
        payload=json.dumps(payload)
    ))
    return False

def validate_backend_url(endpoint):
    """
    Memvalidasi apakah URL backend valid sebelum digunakan.
    """
    if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
        logger.error(log_messages["report_manager"]["invalid_url"].format(endpoint=endpoint))
        return False
    return True

if __name__ == "__main__":
    # Contoh penggunaan
    test_payload = {
        "type": "test_report",
        "status": "success",
        "message": "Laporan test berhasil dikirim",
        "timestamp": time.time()
    }

    if validate_backend_url(BACKEND_ENDPOINT):
        send_report_to_backend(BACKEND_ENDPOINT, test_payload)