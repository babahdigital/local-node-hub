import os
import time
import subprocess

class BackupSession:
    """
    Satu sesi perekaman ffmpeg:
      - start_recording() => panggil ffmpeg (tanpa -t)
      - still_ok(max_dur) => cek durasi
      - stop_recording() => terminate ffmpeg
    """
    def __init__(self, rtsp_url, channel, stream_title="Untitled"):
        self.rtsp_url     = rtsp_url
        self.channel      = channel
        self.stream_title = stream_title
        self.proc         = None
        self.start_time   = None
        self.file_path    = None

    def start_recording(self):
        self.start_time = time.time()
        out_file = self._make_filename()
        self.file_path = out_file

        cmd = [
            "ffmpeg",
            "-hide_banner", 
            "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-i", self.rtsp_url,
            "-c", "copy",
            "-metadata", f"title={self.stream_title}",
            out_file
        ]
        self.proc = subprocess.Popen(cmd)
        return out_file

    def _make_filename(self):
        backup_root = "/mnt/Data/Backup"
        date_str    = time.strftime("%d-%m-%Y")
        time_str    = time.strftime("%H-%M-%S")
        ch_folder   = f"Channel-{self.channel}"
        final_dir   = os.path.join(backup_root, date_str, ch_folder)
        os.makedirs(final_dir, exist_ok=True)
        return os.path.join(final_dir, f"CH{self.channel}-{time_str}.mkv")

    def still_ok(self, max_dur=300):
        """
        True jika belum melewati max_dur detik perekaman.
        """
        if not self.proc:
            return False
        elapsed = time.time() - self.start_time
        return (elapsed < max_dur)

    def stop_recording(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except:
                pass
            self.proc = None