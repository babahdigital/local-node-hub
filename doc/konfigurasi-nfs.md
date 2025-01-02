# Langkah-Langkah Konfigurasi NFS di TrueNAS

## 1. Persiapan di TrueNAS

### a. Login ke TrueNAS
Gunakan terminal atau SSH untuk login ke TrueNAS sebagai pengguna root atau pengguna dengan akses administrator.

### b. Buat Direktori untuk NFS
Buat direktori yang akan diekspor melalui NFS:
```bash
sudo mkdir -p /mnt/Data/Backup
sudo mkdir -p /mnt/Data/Syslog
```

### c. Atur Izin Direktori
Atur izin direktori untuk akses yang sesuai:
```bash
sudo chmod -R 755 /mnt/Data/Backup /mnt/Data/Syslog
sudo chown -R abdullah:abdullah /mnt/Data/Backup /mnt/Data/Syslog
```

### d. Konfigurasi File `/etc/exports`
Tambahkan entri berikut ke file `/etc/exports` untuk menentukan akses subnet:
```plaintext
/mnt/Data/Backup 172.16.10.0/24(ro,sync,no_subtree_check)
/mnt/Data/Backup 172.16.30.0/28(rw,sync,no_subtree_check)
/mnt/Data/Syslog 172.16.30.0/28(rw,sync,no_subtree_check)
```
Penjelasan:
- `/mnt/Data/Backup`
    - Subnet 172.16.10.0/24: Akses read-only (tidak bisa menghapus atau mengubah file).
    - Subnet 172.16.30.0/28: Akses penuh (read-write).
- `/mnt/Data/Syslog`
    - Subnet 172.16.30.0/28: Akses penuh (read-write).
- `sync`: Data ditulis ke disk sebelum diakui.
- `no_subtree_check`: Menghindari overhead subtree checking.

### e. Reload Konfigurasi NFS
Terapkan perubahan konfigurasi:
```bash
sudo exportfs -rav
```

### f. Verifikasi Ekspor NFS
Gunakan perintah berikut untuk memverifikasi direktori yang diekspor:
```bash
sudo showmount -e
```
Output yang diharapkan:
```plaintext
Export list for 172.16.30.2:
/mnt/Data/Backup 172.16.10.0/24,172.16.30.0/28
/mnt/Data/Syslog 172.16.30.0/28
```

## 2. Konfigurasi Klien Linux (Server Docker)

### a. Instal Paket NFS
Instal paket NFS yang diperlukan:
```bash
sudo apt update
sudo apt install nfs-common
```

### b. Buat Direktori Mount Point
Buat direktori lokal untuk mount NFS:
```bash
sudo mkdir -p /mnt/Backup
sudo mkdir -p /mnt/Syslog
```

### c. Mount NFS
Mount direktori Backup:
```bash
sudo mount -t nfs4 172.16.30.2:/mnt/Data/Backup /mnt/Backup
```
Mount direktori Syslog:
```bash
sudo mount -t nfs4 172.16.30.2:/mnt/Data/Syslog /mnt/Syslog
```

### d. Otomatisasi Mount dengan `/etc/fstab`
Tambahkan entri berikut ke file `/etc/fstab` agar mount otomatis saat boot:
```plaintext
172.16.30.2:/mnt/Data/Backup /mnt/Backup nfs4 defaults,_netdev 0 0
172.16.30.2:/mnt/Data/Syslog /mnt/Syslog nfs4 defaults,_netdev 0 0
```
Jalankan perintah:
```bash
sudo mount -a
```

### e. Tes Akses
Tes baca dan tulis:
```bash
echo "Test Backup Write" > /mnt/Backup/testfile
cat /mnt/Backup/testfile

echo "Test Syslog Write" > /mnt/Syslog/testfile
cat /mnt/Syslog/testfile
```

## 3. Konfigurasi Klien Windows

### a. Aktifkan Client for NFS
Buka Control Panel > Programs > Turn Windows features on or off. Centang Client for NFS dan klik OK.

### b. Mount NFS
Mount Backup (Read-Only):
```cmd
mount -o anon \\172.16.30.2\mnt\Data\Backup Z:
```
Mount Syslog (Read-Write):
```cmd
mount -o anon \\172.16.30.2\mnt\Data\Syslog Y:
```

### c. Otomatisasi Mount
Buat file batch, misalnya `mount_nfs.bat`:
```cmd
mount -o anon \\172.16.30.2\mnt\Data\Backup Z:
mount -o anon \\172.16.30.2\mnt\Data\Syslog Y:
```
Jadwalkan file batch untuk dijalankan pada startup menggunakan Task Scheduler.

## 4. Troubleshooting

### a. Masalah Mount
Cek konektivitas:
```bash
ping 172.16.30.2
```
Periksa log NFS di server TrueNAS:
```bash
sudo tail -f /var/log/messages
```

### b. Masalah Izin
Pastikan UID/GID di klien cocok dengan server:
```bash
id
```
Atur ulang izin di server:
```bash
sudo chmod -R 755 /mnt/Data/Backup /mnt/Data/Syslog
sudo chown -R abdullah:abdullah /mnt/Data/Backup /mnt/Data/Syslog
```

Tutorial ini mencakup konfigurasi lengkap NFS di TrueNAS dengan akses untuk klien Linux dan Windows serta tips troubleshooting.