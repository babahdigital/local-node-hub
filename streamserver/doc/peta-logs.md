| Kategori Log     | Path Log                                      | Fungsi                                                      |
|------------------|-----------------------------------------------|-------------------------------------------------------------|
| Performance      | /mnt/Data/Syslog/rtsp/performance/performance.log | Mencatat metrik kinerja sistem seperti CPU/RAM.             |
| Backup           | /mnt/Data/Syslog/rtsp/backup/backup.log       | Melacak status proses backup (berhasil/gagal).              |
| Security         | /mnt/Data/Syslog/rtsp/security/security.log   | Log aktivitas keamanan seperti upaya login.                 |
| Alerts           | /mnt/Data/Syslog/rtsp/alerts/alerts.log       | Peringatan penting yang membutuhkan perhatian segera.       |
| Audit            | /mnt/Data/Syslog/rtsp/audit/audit.log         | Mencatat perubahan konfigurasi/pengguna.                    |
| Scheduler        | /mnt/Data/Syslog/rtsp/scheduler/scheduler.log | Log tugas terjadwal seperti rotasi log.                     |
| RTSP             | /mnt/Data/Syslog/rtsp/rtsp.log                | Log aktivitas RTSP seperti validasi streaming.              |
| Streaming-HLS    | /mnt/Data/Syslog/rtsp/streaming/hls.log       | Aktivitas HLS, termasuk penggunaan FFmpeg.                  |
| Network          | /mnt/Data/Syslog/rtsp/network/network.log     | Status koneksi jaringan (timeout, gagal).                   |
| HDD Monitoring   | /mnt/Data/Syslog/rtsp/hdd/hdd_monitor.log     | Kapasitas dan kesehatan hard disk.                          |
| Debug            | /mnt/Data/Syslog/rtsp/debug/debug.log         | Informasi debugging.                                        |
| Default          | /mnt/Data/Syslog/rtsp/stream/stream_service.log | Log fallback untuk aktivitas umum.                          |
| Validasi CCTV    | /mnt/Data/Syslog/rtsp/cctv/validation.log     | Log validasi RTSP stream.                                   |
| Status CCTV      | /mnt/Data/Syslog/rtsp/cctv/cctv_status.log    | Melacak status channel CCTV (Online/Offline).               |
| NGINX Error      | /mnt/Data/Syslog/rtsp/nginx_error.log         | Log kesalahan dari server NGINX.                            |
| NGINX Access     | /mnt/Data/Syslog/rtsp/nginx_access.log        | Log akses HTTP server NGINX.                                |
| HLS Output       | /app/hls/ch<channel_number>/live.m3u8         | Penyimpanan file HLS streaming untuk setiap channel.        |