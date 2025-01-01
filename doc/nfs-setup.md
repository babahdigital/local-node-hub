# Dokumentasi dan Tutorial: Skrip Konfigurasi Klien NFS

## Pendahuluan
Skrip ini dirancang untuk mempermudah konfigurasi klien Network File System (NFS) pada sistem berbasis Linux. Dengan menggunakan skrip ini, Anda dapat secara otomatis mengatur mount point untuk shares NFS yang disediakan oleh server TrueNAS, memastikan bahwa share tersebut selalu terhubung setiap kali sistem dinyalakan.

## Fitur Skrip
Skrip ini memiliki beberapa fitur utama yang memudahkan pengaturan dan pemeliharaan koneksi NFS antara server dan klien:

1. **Konfigurasi Parametrik**
    - `NFS_SERVER`: Alamat IP server NFS (contoh: 172.16.30.2).
    - `CLIENT_IP`: Alamat IP klien yang akan mengakses shares.
    - `SHARES`: Daftar direktori yang akan dibagikan dari server NFS.
    - `MOUNT_POINTS`: Lokasi di klien tempat shares NFS akan di-mount.
    - `FSTYPE`: Tipe filesystem yang digunakan, dalam hal ini nfs4.

2. **Pengecekan Hak Akses Root**
    - Skrip memastikan bahwa dijalankan dengan hak akses root untuk melakukan perubahan sistem yang diperlukan.

3. **Instalasi Paket nfs-common**
    - Memeriksa apakah paket nfs-common sudah terinstal. Jika belum, skrip akan menginstalnya secara otomatis menggunakan apt-get.

4. **Pembuatan Direktori Mount Point**
    - Skrip akan membuat direktori mount point yang diperlukan jika belum ada di sistem klien.

5. **Konfigurasi /etc/fstab**
    - Menambahkan entri ke file /etc/fstab untuk memastikan bahwa shares NFS ter-mount secara otomatis saat booting. Skrip memeriksa apakah entri sudah ada sebelum menambahkannya.

6. **Mounting Shares**
    - Melakukan proses mount semua shares yang telah dikonfigurasi dengan menjalankan mount -a.

7. **Verifikasi Mount Point**
    - Memeriksa apakah setiap mount point berhasil di-mount dan memberikan pesan status yang sesuai.

## Langkah-Langkah Penggunaan Skrip
Berikut adalah panduan langkah demi langkah untuk menggunakan skrip ini:

1. **Persiapan Awal**
    - Pastikan Akses Root: Skrip ini harus dijalankan dengan hak akses root. Anda dapat menggunakan sudo untuk menjalankannya.
      ```bash
      sudo bash ./tool/nfs-setup.sh
      ```
    - Edit Konfigurasi Skrip: Sesuaikan variabel konfigurasi di awal skrip sesuai dengan lingkungan Anda.
      ```bash
      NFS_SERVER="172.16.30.2" # IP server NFS (TrueNAS)
      CLIENT_IP="172.16.30.3"  # IP klien
      SHARES=( "/mnt/Data/Syslog" "/mnt/Data/Backup" ) # Daftar share di NFS server
      MOUNT_POINTS=( "/mnt/Data/Syslog" "/mnt/Data/Backup" ) # Lokasi mount di klien
      FSTYPE="nfs4" # Tipe filesystem NFS
      ```

2. **Menjalankan Skrip**
    - Pastikan skrip memiliki izin eksekusi. Jika belum, tambahkan izin eksekusi menggunakan chmod.
      ```bash
      chmod +x ./tool/nfs-setup.sh
      ```
    - Jalankan skrip sebagai root.
      ```bash
      sudo ./tool/nfs-setup.sh
      ```

3. **Verifikasi Hasil Mount**
    - Setelah skrip selesai dijalankan, Anda dapat memverifikasi mount point menggunakan perintah mount atau df -h.
      ```bash
      mount | grep nfs
      ```
      atau
      ```bash
      df -h | grep nfs
      ```

## Cara Melakukan Export dengan exportfs
Untuk memastikan bahwa server NFS (TrueNAS) telah meng-export direktori yang akan di-mount oleh klien, Anda perlu menggunakan perintah exportfs. Berikut adalah cara melakukannya:

1. **Menambahkan Export di Server NFS**
    - Edit file /etc/exports di server NFS dan tambahkan direktori yang ingin di-share beserta izin aksesnya.
      ```bash
      /mnt/Data/Syslog 172.16.30.3(rw,sync,no_subtree_check)
      /mnt/Data/Backup 172.16.30.3(rw,sync,no_subtree_check)
      ```

2. **Mengaplikasikan Perubahan dengan exportfs**
    - Menambahkan Semua Export yang Dikonfigurasi
      ```bash
      exportfs -a
      ```
    - Mereload Export Table
      ```bash
      exportfs -r
      ```

3. **Verifikasi Export**
    - Pastikan direktori telah di-export dengan benar menggunakan:
      ```bash
      exportfs -v
      ```

## Tataletak Dokumentasi dan Tutorial
Untuk memudahkan pemahaman dan penggunaan skrip ini, dokumentasi dan tutorial dapat disusun dengan struktur berikut:

1. **Judul dan Pendahuluan**
    - Penjelasan singkat tentang tujuan skrip dan manfaat penggunaannya.

2. **Prasyarat**
    - Sistem operasi yang didukung.
    - Hak akses yang diperlukan.
    - Paket yang harus terinstal sebelumnya (jika ada).

3. **Deskripsi Skrip**
    - Penjelasan setiap bagian skrip, termasuk variabel konfigurasi dan fungsinya.

4. **Panduan Penggunaan**
    - Langkah-langkah detail mulai dari pengaturan konfigurasi hingga menjalankan skrip.
    - Contoh penggunaan dan output yang diharapkan.

5. **Pengelolaan Export di Server NFS**
    - Cara menambahkan direktori ke /etc/exports.
    - Penggunaan perintah exportfs untuk mengelola export.

6. **Troubleshooting**
    - Masalah umum yang mungkin terjadi dan solusinya.
    - Cara memeriksa status mount point dan export.

7. **Referensi**
    - Link ke dokumentasi resmi NFS.
    - Sumber tambahan untuk pembelajaran lebih lanjut.

8. **Lampiran**
    - Skrip lengkap.
    - Contoh konfigurasi /etc/exports.

## Contoh Dokumentasi
Berikut adalah contoh bagaimana bagian tertentu dari dokumentasi dapat ditulis:

### Contoh Konfigurasi Skrip
```bash
# Konfigurasi
NFS_SERVER="172.16.30.2" # IP server NFS (TrueNAS)
CLIENT_IP="172.16.30.3"  # IP klien
SHARES=( "/mnt/Data/Syslog" "/mnt/Data/Backup" ) # Daftar share di NFS server
MOUNT_POINTS=( "/mnt/Data/Syslog" "/mnt/Data/Backup" ) # Lokasi mount di klien
FSTYPE="nfs4" # Tipe filesystem NFS
```
Penjelasan:
- `NFS_SERVER`: Ganti dengan alamat IP server NFS Anda.
- `CLIENT_IP`: Alamat IP dari klien yang akan mengakses shares.
- `SHARES`: Daftar direktori di server yang akan dibagikan.
- `MOUNT_POINTS`: Lokasi di klien tempat shares akan di-mount.
- `FSTYPE`: Jenis filesystem yang digunakan untuk mounting.

### Langkah Menggunakan Skrip
1. **Edit Skrip**: Sesuaikan variabel konfigurasi sesuai kebutuhan.
2. **Beri Izin Eksekusi**: `chmod +x ./tool/nfs-setup.sh`
3. **Jalankan Skrip**: `sudo ./tool/nfs-setup.sh`
4. **Verifikasi**: Pastikan shares ter-mount dengan benar menggunakan `mount` atau `df -h`.

## Penutup
Dengan menggunakan skrip ini, proses konfigurasi klien NFS menjadi lebih efisien dan mengurangi kemungkinan kesalahan konfigurasi manual. Dokumentasi ini diharapkan dapat membantu Anda memahami dan memanfaatkan skrip dengan optimal.
