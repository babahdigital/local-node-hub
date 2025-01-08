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
DEFAULT_MAX_RETRIES = int(os.getenv("DEFAULT_MAX_RETRIES", "5"))
INITIAL_BACKOFF = int(os.getenv("INITIAL_BACKOFF", "1"))  # in seconds

def get_dynamic_max_retries():
    # Implementasi logika dinamis untuk menentukan MAX_RETRIES
    # Misalnya, berdasarkan stabilitas jaringan atau jumlah kegagalan sebelumnya
    # Untuk contoh ini, kita akan menggunakan nilai default
    return DEFAULT_MAX_RETRIES

def get_dynamic_backoff_time(retries):
    # Implementasi logika dinamis untuk menentukan backoff_time
    # Misalnya, berdasarkan jumlah retry yang telah dilakukan
    return INITIAL_BACKOFF * (2 ** (retries - 1))

def send_report_to_backend(endpoint, payload):
    """
    Mengirim laporan ke backend dengan retry logic menggunakan exponential backoff.
    """
    retries = 0
    max_retries = get_dynamic_max_retries()
    while retries < max_retries:
        try:
            response = requests.post(endpoint, json=payload)
            response.raise_for_status()
            logger.info(log_messages["report_manager"]["report_success"].format(endpoint=endpoint))
            return True
        except requests.exceptions.RequestException as e:
            retries += 1
            backoff_time = get_dynamic_backoff_time(retries)
            logger.error(log_messages["report_manager"]["report_failed_attempt"].format(
                attempt=retries, retries=max_retries, status_code=response.status_code if response else "N/A", response_text=str(e)))
            if retries < max_retries:
                logger.info(log_messages["report_manager"]["wait_before_retry"].format(delay=backoff_time))
                time.sleep(backoff_time)
            else:
                logger.error(log_messages["report_manager"]["report_failed"].format(retries=max_retries, payload=payload))
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