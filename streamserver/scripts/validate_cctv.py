import os
import subprocess
import ipaddress
from datetime import datetime
import sys

from utils import setup_logger, get_local_time, decode_credentials

# Pastikan folder scripts ada di PATH (jika utils.py ada di /app/scripts)
sys.path.append("/app/scripts")

# Konfigurasi log
LOG_PATH = os.getenv("LOG_PATH", "/mnt/Data/Syslog/rtsp/cctv/validation.log")
CCTV_LOG_PATH = os.getenv("CCTV_LOG_PATH", "/mnt/Data/Syslog/rtsp/cctv/cctv_status.log")
logger = setup_logger("RTSP-Validation", LOG_PATH)

def write_status_log(channel: int, status: str) -> None:
    """
    Menulis status kamera (Online/Offline) ke file log CCTV.
    """
    timestamp = get_local_time()
    try:
        with open(CCTV_LOG_PATH, "a") as f:
            f.write(f"{timestamp} - Channel {channel}: {status}\n")
    except IOError as e:
        logger.error(f"Gagal menulis ke {CCTV_LOG_PATH}: {e} (Channel {channel}, Status: {status})")

def check_black_frames(rtsp_url: str) -> bool:
    """
    Periksa apakah frame hitam terdeteksi pada RTSP URL.
    """
    try:
        cmd = [
            "ffmpeg",
            "-i", rtsp_url,
            "-vf", "blackdetect=d=0.1:pic_th=0.98",
            "-an",
            "-t", "5",
            "-f", "null",
            "-"
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        # Jika b"black_start" terdeteksi => frame hitam
        return b"black_start" not in result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout saat memeriksa frame hitam: {rtsp_url}")
        return False
    except Exception as e:
        logger.error(f"Kesalahan tidak terduga (blackdetect): {e}")
        return False

def parse_subnet(nvr_subnet: str):
    """
    Menghasilkan daftar IP dari subnet NVR jika NVR_ENABLE=true.
    """
    logger.info(f"Parsing subnet NVR: {nvr_subnet}")
    return list(ipaddress.ip_network(nvr_subnet, strict=False).hosts())

def validate_rtsp_stream(rtsp_url: str) -> bool:
    """
    Validasi RTSP stream menggunakan ffprobe.
    """
    try:
        logger.info(f"Memvalidasi RTSP URL: {rtsp_url}")
        cmd = ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name",
               "-of", "default=noprint_wrappers=1", rtsp_url]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)

        # Cek kembalian ffprobe
        if result.returncode == 0:
            logger.info("RTSP stream valid.")
            return True
        else:
            logger.error(f"RTSP stream tidak valid: {result.stderr.decode()}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("Timeout saat memvalidasi RTSP stream.")
        return False
    except Exception as e:
        logger.error(f"Kesalahan tidak terduga (ffprobe): {e}")
        return False

def generate_channels() -> list:
    """
    Menghasilkan daftar channel berdasarkan TEST_CHANNEL atau CHANNELS.
    """
    test_channel = os.getenv("TEST_CHANNEL", "off")
    channels = []

    if test_channel.lower() != "off":
        # Jika TEST_CHANNEL diatur, gunakan nilai ini
        try:
            channels = [int(ch.strip()) for ch in test_channel.split(",")]
            logger.info(f"TEST_CHANNEL diatur: {channels}")
        except ValueError:
            logger.error(f"TEST_CHANNEL tidak valid. Gunakan format '1' atau '1,2,3'.")
            sys.exit(1)
    else:
        try:
            total_channels = int(os.getenv("CHANNELS", "1"))
            channels = list(range(1, total_channels + 1))
            logger.info(f"CHANNELS diatur: {channels}")
        except ValueError:
            logger.error("CHANNELS tidak valid; gunakan integer.")
            sys.exit(1)

    return channels

def main() -> None:
    """
    Fungsi utama untuk memvalidasi RTSP stream.
    """
    try:
        # 1. Dekode kredensial RTSP
        rtsp_user, rtsp_password = decode_credentials()
    except RuntimeError as e:
        logger.error(f"Kesalahan saat mendekode kredensial: {e}")
        return

    # 2. Baca variabel lingkungan
    rtsp_ip = os.getenv("RTSP_IP")
    rtsp_subtype = os.getenv("RTSP_SUBTYPE", "1")
    nvr_enable = os.getenv("NVR_ENABLE", "false").lower() == "true"
    nvr_subnet = os.getenv("NVR_SUBNET", "")

    # 3. Tentukan daftar IP
    if nvr_enable:
        ips = parse_subnet(nvr_subnet)
        logger.info(f"Mode NVR aktif, Subnet: {nvr_subnet}, Total IP: {len(ips)}")
    else:
        ips = [rtsp_ip]
        logger.info(f"Mode DVR aktif, IP: {rtsp_ip}")

    # 4. Generate daftar channel
    channels_to_validate = generate_channels()

    # 5. Validasi tiap IP dan channel
    for ip in ips:
        for channel in channels_to_validate:
            rtsp_url = f"rtsp://{rtsp_user}:{rtsp_password}@{ip}:554/cam/realmonitor?channel={channel}&subtype={rtsp_subtype}"
            if validate_rtsp_stream(rtsp_url):
                logger.info(f"Channel {channel} valid.")
                write_status_log(channel, "Online")
                # Opsi: Periksa frame hitam
                if not check_black_frames(rtsp_url):
                    logger.warning(f"Channel {channel}: Frame hitam terdeteksi.")
                    write_status_log(channel, "Offline (Black Frames)")
            else:
                logger.error(f"Channel {channel} tidak valid.")
                write_status_log(channel, "Offline")

    logger.info("Validasi selesai untuk semua channel.")

if __name__ == "__main__":
    main()