import time
import requests
from utils import load_log_messages, setup_logger, validate_backend_url
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Path ke log_messages.json
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", "/app/config/log_messages.json")

# Load log messages
try:
    log_messages = load_log_messages(LOG_MESSAGES_FILE)
except RuntimeError as e:
    print(e)
    exit(1)

# Setup logger
logger = setup_logger("ReportManager")

BACKEND_ENDPOINT = os.getenv("BACKEND_ENDPOINT", "http://127.0.0.1:5001/api/report")

def send_report_to_backend(endpoint, payload):
    """
    Mengirim laporan ke backend.
    """
    try:
        response = requests.post(endpoint, json=payload)
        response.raise_for_status()
        logger.info(log_messages["report_manager"]["report_sent"].format(endpoint=endpoint))
        return True
    except requests.exceptions.RequestException as e:
        logger.error(log_messages["report_manager"]["report_failed"].format(endpoint=endpoint, error=str(e)))
        return False

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