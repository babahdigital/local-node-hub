from flask import Flask, jsonify
from dotenv import load_dotenv
from utils import load_log_messages, setup_logger

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

@app.route('/health', methods=['GET'])
def health_check():
    logger.info(log_messages["health_check"]["start"])
    # Implementasi logika health check di sini
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)