### Logrotate Configuration
The logrotate configuration for Syslog-ng is located at:
```bash
/syslog/logrotate/syslog-ng
```

Konfigurasi Logrotate, copy ke `/etc/logrotate.d/` di sistem anda:

```bash
cp syslog/logrotate/syslog-ng /etc/logrotate.d/syslog-ng
```

Uji Konfigurasi dengan ini
```bash
logrotate -d /etc/logrotate.d/syslog-ng
```

Jalankan dengan ini
```bash
logrotate -f /etc/logrotate.d/syslog-ng
```

Pastikan logrotate.timer diaktifkan:
```bash
systemctl enable logrotate.timer
systemctl start logrotate.timer
```

```bash
systemctl list-timers --all | grep logrotate
```

Hasilnya akan seperti ini:
```bash
Thu 2024-12-26 00:00:00 WITA  5h 41min left Wed 2024-12-25 00:00:04 WITA  18h ago   logrotate.timer logrotate.service
```