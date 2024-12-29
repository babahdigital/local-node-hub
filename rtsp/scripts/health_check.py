from flask import Flask, jsonify
from dotenv import load_dotenv
from utils import load_log_messages, setup_logger
import requests
import os

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
logger = setup_logger("HealthCheck")

app = Flask(__name__)

LIVESTREAM_URL = os.getenv("LIVESTREAM_URL", "http://127.0.0.1:8554/health")

def check_livestream_health():
    try:
        response = requests.get(LIVESTREAM_URL, timeout=5)
        if response.status_code == 200:
            return True
        else:
            logger.warning(log_messages["health_check"]["livestream_unhealthy"].format(status_code=response.status_code))
            return False
    except requests.exceptions.RequestException as e:
        logger.error(log_messages["health_check"]["livestream_error"].format(error=str(e)))
        return False

@app.route('/health', methods=['GET'])
def health_check():
    logger.info(log_messages["health_check"]["endpoint_accessed"])
    # Implementasi logika health check di sini
    livestream_healthy = check_livestream_health()
    if livestream_healthy:
        return jsonify({"status": "healthy"}), 200
    else:
        return jsonify({"status": "unhealthy"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)