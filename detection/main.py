import os
import cv2
import json
import time
import threading
from datetime import datetime
from motion_detection import MotionDetector

file_write_lock = threading.Lock()

def save_motion_event(channel, bounding_boxes):
    event_data = {
        "timestamp": datetime.now().isoformat(),
        "channel": channel,
        "bounding_boxes": bounding_boxes
    }
    with file_write_lock:
        with open("detection_events.json", "a") as f:
            f.write(json.dumps(event_data) + "\n")

def detect_motion_in_channel(channel, host_ip, motion_detector):
    stream_url = f"http://{host_ip}/ch{channel}/"
    print(f"[THREAD-{channel}] Membuka stream: {stream_url}")

    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        print(f"[THREAD-{channel}] ERROR: Gagal membuka stream.")
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print(f"[THREAD-{channel}] Stream terputus/frame kosong.")
                break

            bboxes = motion_detector.detect(frame)
            if bboxes:
                print(f"[THREAD-{channel}] Gerakan terdeteksi: {bboxes}")
                save_motion_event(channel, bboxes)

            # Tambahkan jeda kecil agar CPU tidak 100%, opsional
            # time.sleep(0.01)

    except KeyboardInterrupt:
        print(f"[THREAD-{channel}] Dihentikan oleh user.")
    finally:
        cap.release()
        print(f"[THREAD-{channel}] Selesai.")

def load_channels_from_json(json_path="/mnt/Data/Syslog/resource/resource_monitor_state.json"):
    """
    Contoh fungsi untuk memuat channel dari file JSON. 
    Anda bisa menyesuaikan kunci JSON yang tepat, misalnya "channel_list".
    """
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        # Misal kita asumsikan "channel_list" di dalam "stream_config"
        stream_config = data.get("stream_config", {})
        channel_list = stream_config.get("channel_list", [])  
        # channel_list di JSON bisa berupa array int => [1,3,4]
        # Ubah jadi string => ["1", "3", "4"]
        channels = [str(ch) for ch in channel_list]
        return channels
    except (FileNotFoundError, json.JSONDecodeError):
        return []  # Jika file tidak ada atau rusak, kembalikan list kosong

def main():
    host_ip = os.getenv("HOST_IP", "127.0.0.1")
    motion_detector = MotionDetector()

    # Agar looping terus: setiap X detik cek apakah ada channel di JSON
    while True:
        channels = load_channels_from_json()
        if not channels:
            print("[MAIN] Tidak ada data channel. Tunggu 10 detik...")
            time.sleep(10)
            continue  # Kembali ke awal loop
        
        print(f"[MAIN] Ditemukan channel: {channels}")

        # Buat thread untuk setiap channel
        threads = []
        for ch in channels:
            t = threading.Thread(
                target=detect_motion_in_channel,
                args=(ch, host_ip, motion_detector),
                daemon=True
            )
            t.start()
            threads.append(t)

        # Tunggu sampai user menekan Ctrl+C, 
        # atau jika diinginkan, hentikan setelah sekian waktu
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[MAIN] Dihentikan oleh user.")
            break  # Keluar loop while True => program selesai

    print("[MAIN] Program selesai.")

if __name__ == "__main__":
    main()