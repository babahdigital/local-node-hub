1. Logging dengan utils.py  
    Logging terpusat menggunakan utils.py tanpa perlu mengulang setup logger.  

2. Pemisahan Log Messages  
    Kelola pesan log dalam file JSON (misalnya log_messages.json) sehingga lebih modular.  

3. Konsistensi Timezone  
    Gunakan fungsi get_local_time untuk menjaga timestamp tetap konsisten.  

4. Fleksibilitas Logging  
    Manfaatkan rotating file handler agar log tidak memenuhi disk dan tambahkan opsi syslog jika diperlukan.
