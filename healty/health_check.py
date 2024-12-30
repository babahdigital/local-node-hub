from flask import Flask, jsonify
from dotenv import load_dotenv
from utils import load_log_messages, setup_logger
import requests
import os
import statistics

# Load environment variables
load_dotenv()

# Constants and configuration
DEFAULT_LOG_MESSAGES_FILE = "/app/config/log_messages.json"
DEFAULT_LIVESTREAM_URL = "http://127.0.0.1:8554/health"
INITIAL_TIMEOUT = 5  # Default timeout in seconds

# Force default values
LOG_MESSAGES_FILE = DEFAULT_LOG_MESSAGES_FILE
LIVESTREAM_URL = DEFAULT_LIVESTREAM_URL

# Load log messages
try:
    log_messages = load_log_messages(LOG_MESSAGES_FILE)
except RuntimeError as e:
    print(f"Gagal memuat pesan log: {e}")
    exit(1)

# Setup logger
logger = setup_logger("HealthCheck")

# Initialize Flask app
app = Flask(__name__)

# Dynamic timeout storage
timeout_history = []

def calculate_dynamic_timeout():
    """
    Calculate a dynamic timeout based on previous response times.
    Use default INITIAL_TIMEOUT if no history is available.
    """
    if timeout_history:
        avg_timeout = statistics.mean(timeout_history)
        return max(2, min(10, avg_timeout))  # Ensure timeout is between 2 and 10 seconds
    return INITIAL_TIMEOUT

def check_livestream_health():
    """
    Check the health of the livestream URL with dynamic timeout.
    """
    timeout = calculate_dynamic_timeout()
    logger.info(f"Memeriksa livestream dengan timeout dinamis: {timeout} detik.")
    try:
        response = requests.get(LIVESTREAM_URL, timeout=timeout)
        response_time = response.elapsed.total_seconds()
        timeout_history.append(response_time)  # Record response time for dynamic adjustment
        if response.status_code == 200:
            logger.info(log_messages["health_check"]["livestream_healthy"])
            return True
        else:
            logger.warning(log_messages["health_check"]["livestream_unhealthy"].format(status_code=response.status_code))
            return False
    except requests.exceptions.RequestException as e:
        logger.error(log_messages["health_check"]["livestream_error"].format(error=str(e)))
        return False

@app.route('/health', methods=['GET'])
def health_check():
    """
    Flask endpoint to check the health of the application.
    """
    logger.info(log_messages["health_check"]["endpoint_accessed"])
    livestream_healthy = check_livestream_health()
    if livestream_healthy:
        return jsonify({"status": "healthy"}), 200
    else:
        return jsonify({"status": "unhealthy"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)