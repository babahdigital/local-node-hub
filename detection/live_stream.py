import cv2

def run_live_stream(url="http://127.0.0.1/ch1/"):
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print(f"Gagal membuka stream: {url}")
        return

    print("Tekan 'q' untuk keluar.")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        cv2.imshow("Live Stream", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_live_stream()