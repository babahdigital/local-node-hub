import os
import time
import subprocess

class BackupSession:
    """
    Menangani 1 sesi backup => menulis ke file (dibuat di start).
    Mencatat kapan mulai, jika sudah 5 menit => tutup & spawn file baru.
    """
    def __init__(self, rtsp_url, channel):
        self.rtsp_url = rtsp_url
        self.channel = channel
        self.proc = None
        self.start_time = None
        self.file_path = None

    def start_recording(self):
        """
        Buka ffmpeg => menulis 1 file. 
        Tapi kita di script ini lebih suka 'fire and forget'?
        Untuk 'maksimal 5 menit' => kita perlu approach sedikit berbeda:
        """
        self.start_time = time.time()
        out_file = self._make_filename()
        self.file_path = out_file

        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-i", self.rtsp_url,
            "-c", "copy",
            # Tanpa -t, agar kita yang handle stop
            out_file
        ]
        self.proc = subprocess.Popen(cmd)
        return out_file

    def _make_filename(self):
        backup_root = "/mnt/Data/Backup"
        date_str = time.strftime("%d-%m-%Y")
        time_str = time.strftime("%H-%M-%S")
        channel_dir = f"channel{self.channel}"
        backup_dir = os.path.join(backup_root, date_str, channel_dir)
        os.makedirs(backup_dir, exist_ok=True)
        out_file = os.path.join(backup_dir, f"{time_str}.mkv")
        return out_file

    def still_ok(self, max_duration=300):
        """
        Cek apakah durasi < max_duration (5 menit=300s).
        If melebihi => False => kita tutup file & create baru.
        """
        if not self.proc:
            return False
        elapsed = time.time() - self.start_time
        return (elapsed < max_duration)

    def stop_recording(self):
        """
        Hentikan ffmpeg process.
        """
        if self.proc:
            self.proc.terminate()  # or send SIGINT
            self.proc.wait(timeout=5)
            self.proc = None

def backup_manager_test():
    """
    Contoh logic => 
    1) Start 
    2) while motion => check .still_ok(300)
    3) if !ok => stop & start new
    4) if no motion => stop
    """
    pass