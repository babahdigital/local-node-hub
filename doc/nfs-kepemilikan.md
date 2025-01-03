# Dokumentasi Lengkap: Konfigurasi NFS Persistent dengan TrueNAS

Dokumentasi ini menjelaskan cara mengatur NFS pada TrueNAS untuk mendukung persistent storage dengan user tertentu (misalnya `abdullah`).

---

## **1. Konfigurasi di Server TrueNAS**

### **1.1. Atur Direktori yang Akan Diekspor**
Pastikan direktori yang akan diekspor memiliki struktur yang jelas dan dimiliki oleh user yang diinginkan.

- **Cek Kepemilikan Direktori**:
    ```bash
    ls -l /mnt/Data/
    ```

- **Ubah Kepemilikan Direktori** (jika diperlukan):
    ```bash
    chown -R abdullah:abdullah /mnt/Data/Backup
    chown -R abdullah:abdullah /mnt/Data/Syslog
    chmod -R u+rwx /mnt/Data/Backup
    chmod -R u+rwx /mnt/Data/Syslog
    ```

### **1.2. Konfigurasi File Ekspor NFS**
Edit file `/etc/exports` di TrueNAS:

```plaintext
"/mnt/Data/Backup"\
                172.16.30.0/28(sec=sys,rw,anonuid=1000,anongid=1000,insecure,no_subtree_check)\
                172.16.10.0/24(sec=sys,rw,anonuid=1000,anongid=1000,insecure,no_subtree_check)
"/mnt/Data/Syslog"\
                172.16.30.0/28(sec=sys,rw,anonuid=1000,anongid=1000,insecure,no_subtree_check)
```

#### **Penjelasan Opsi**:
- **`sec=sys`**: Menggunakan autentikasi berbasis UID/GID.
- **`rw`**: Mengizinkan akses baca/tulis.
- **`anonuid=1000, anongid=1000`**: Memetakan user anonim ke UID/GID user `abdullah`.
- **`insecure`**: Mengizinkan koneksi dari port non-privileged.
- **`no_subtree_check`**: Meningkatkan performa dan menghindari konflik subtree.

### **1.3. Restart Layanan NFS**
Setelah mengedit file ekspor, restart layanan NFS:

```bash
service nfsd restart
```

---

## **2. Konfigurasi Klien NFS**

### **2.1. Instal Paket yang Diperlukan**
Pastikan klien memiliki paket NFS yang diperlukan:

#### **Debian/Ubuntu**:
```bash
sudo apt update
sudo apt install nfs-common
```

#### **CentOS/RHEL**:
```bash
sudo yum install nfs-utils
```

### **2.2. Edit File `/etc/idmapd.conf`**
Pastikan domain di klien sesuai dengan domain di server TrueNAS:

```plaintext
[General]
Verbosity = 0
Domain = babahdigital.local
```

Restart layanan idmapd di klien:

```bash
sudo systemctl restart nfs-client.target
```

### **2.3. Tambahkan Entri di `/etc/hosts`** (Jika DNS Tidak Tersedia)
Jika nama domain server tidak bisa diresolusikan, tambahkan entri ke file `/etc/hosts`:

```plaintext
192.168.1.10 server.babahdigital.local server
```

### **2.4. Mount Direktori NFS**
Gunakan perintah berikut untuk mount direktori dari server TrueNAS:

```bash
mount -t nfs4 -o rw,sync server.babahdigital.local:/mnt/Data/Backup /mnt/Data/Backup
mount -t nfs4 -o rw,sync server.babahdigital.local:/mnt/Data/Syslog /mnt/Data/Syslog
```

#### **Verifikasi Mount**:
Cek status mount dengan:

```bash
mount | grep nfs
```

Output yang diharapkan:
```plaintext
server.babahdigital.local:/mnt/Data/Backup on /mnt/Data/Backup type nfs4 (rw,sync,...)
server.babahdigital.local:/mnt/Data/Syslog on /mnt/Data/Syslog type nfs4 (rw,sync,...)
```

---

## **3. Uji Akses dan Hak Kepemilikan**

### **3.1. Periksa Hak Akses di Klien**
Periksa hak akses:

```bash
ls -l /mnt/Data/Backup
ls -l /mnt/Data/Syslog
```

File dan direktori baru yang dibuat harus dimiliki oleh `abdullah`.

### **3.2. Tes Membuat File**
Sebagai user `abdullah`, buat file baru:

```bash
su - abdullah
cd /mnt/Data/Backup
touch testfile_backup
cd /mnt/Data/Syslog
touch testfile_syslog
```

File yang dibuat akan dimiliki oleh user `abdullah` jika konfigurasi benar.

---

## **4. Troubleshooting**

### **4.1. Periksa Log di Klien**
```bash
dmesg | grep nfs
```

### **4.2. Periksa Log di Server**
```bash
tail -f /var/log/messages | grep nfs
```

### **4.3. Sinkronisasi UID/GID**
Pastikan UID/GID user `abdullah` sama di server dan klien:

```bash
id -u abdullah
id -g abdullah
```

Jika tidak sama, sesuaikan UID/GID di klien atau server.

---

## **5. Catatan Tambahan**

- Pastikan jaringan antara server dan klien stabil.
- Gunakan DNS server lokal jika memungkinkan.
- Hindari opsi `insecure` jika tidak diperlukan.

---

Dengan langkah-langkah ini, NFS di TrueNAS Anda kini mendukung persistent storage dengan user `abdullah` sebagai pemilik default file dan direktori baru.
