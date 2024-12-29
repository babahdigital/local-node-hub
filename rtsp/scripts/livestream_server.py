from flask import Flask, jsonify, request
import os
import jwt  # Install PyJWT untuk membuat token
import datetime
import subprocess
import logging
from dotenv import load_dotenv
from utils import load_log_messages, setup_logger

# Load konfigurasi dari .env
load_dotenv()

app = Flask(__name__)

# Konfigurasi
SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")
DDNS_DOMAIN = os.getenv("DDNS_DOMAIN", "your-ddns.mikrotik.com")
RTSP_PORT = int(os.getenv("RTSP_PORT", 554))
RTSP_SUBTYPE = os.getenv("RTSP_SUBTYPE", "0")
RTSP_USERNAME = os.getenv("RTSP_USERNAME", "admin")
RTSP_PASSWORD = os.getenv("RTSP_PASSWORD", "password")
LIVESTREAM_PORT = int(os.getenv("LIVESTREAM_PORT", 5005))
RTSP_TIMEOUT = int(os.getenv("RTSP_TIMEOUT", 10))  # Timeout untuk validasi stream
RTSP_SERVER_URL = os.getenv("RTSP_SERVER_URL", "rtsp://127.0.0.1:8554")

# Path ke log_messages.json
LOG_MESSAGES_FILE = os.getenv("LOG_MESSAGES_FILE", "/app/config/log_messages.json")

# Load log messages
try:
    log_messages = load_log_messages(LOG_MESSAGES_FILE)
except RuntimeError as e:
    print(e)
    exit(1)

# Setup logger
logger = setup_logger("Livestream")

# Fungsi untuk menghasilkan URL RTSP
def get_rtsp_url(channel):
    return f"{RTSP_SERVER_URL}/proxy/{channel}"

# Fungsi untuk memvalidasi stream RTSP
def validate_rtsp_stream(rtsp_url):
    try:
        result = subprocess.run(
            ["openRTSP", "-t", "5", "-V", rtsp_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=RTSP_TIMEOUT
        )
        if result.returncode == 0:
            logger.info(log_messages["livestream"]["url"]["valid_stream"].format(url=rtsp_url))
            return True
        else:
            logger.warning(log_messages["livestream"]["url"]["invalid_stream"].format(url=rtsp_url))
            return False
    except subprocess.TimeoutExpired:
        logger.error(log_messages["livestream"]["url"]["timeout"].format(url=rtsp_url))
        return False
    except Exception as e:
        logger.error(log_messages["livestream"]["url"]["unexpected_error"].format(error=str(e)))
        return False

@app.route('/generate-token/<int:channel>', methods=['GET'])
def generate_token(channel):
    if not (1 <= channel <= 16):
        logger.warning(log_messages["livestream"]["token"]["invalid_channel"].format(channel=channel))
        return jsonify({"error": "Channel harus berada dalam rentang 1-16"}), 400

    rtsp_url = get_rtsp_url(channel)

    if not validate_rtsp_stream(rtsp_url):
        return jsonify({"error": "Stream tidak tersedia untuk channel ini."}), 400

    expiration = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    payload = {
        "channel": channel,
        "exp": expiration,
        "username": RTSP_USERNAME,
        "password": RTSP_PASSWORD
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    logger.info(log_messages["livestream"]["token"]["create_success"].format(channel=channel))
    return jsonify({"token": token})

@app.route('/livestream', methods=['GET'])
def get_livestream_url():
    token = request.args.get("token")
    if not token:
        logger.warning(log_messages["livestream"]["url"]["missing_token"])
        return jsonify({"error": "Token tidak ditemukan"}), 400

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        channel = payload["channel"]

        rtsp_url = get_rtsp_url(channel)

        if not validate_rtsp_stream(rtsp_url):
            return jsonify({"error": "Stream tidak tersedia untuk channel ini."}), 400

        logger.info(log_messages["livestream"]["url"]["generate_success"].format(channel=channel))
        return jsonify({"livestream_url": rtsp_url})
    except jwt.ExpiredSignatureError:
        logger.error(log_messages["livestream"]["url"]["expired_token"])
        return jsonify({"error": "Token telah kedaluwarsa"}), 401
    except jwt.InvalidTokenError:
        logger.error(log_messages["livestream"]["url"]["invalid_token"])
        return jsonify({"error": "Token tidak valid"}), 400

@app.route('/health', methods=['GET'])
def health_check():
    logger.info(log_messages["livestream"]["health"]["accessed"])
    return jsonify({"status": "healthy", "message": "Livestream server is running!"})

if __name__ == "__main__":
    logger.info(log_messages["general"]["server_start"].format(port=LIVESTREAM_PORT))
    app.run(host="0.0.0.0", port=LIVESTREAM_PORT)