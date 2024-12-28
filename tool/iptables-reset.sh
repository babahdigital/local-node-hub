#!/bin/bash

# Pastikan script dijalankan sebagai root
if [ "$(id -u)" -ne 0 ]; then
    echo "Script ini harus dijalankan sebagai root!"
    exit 1
fi

echo "===> Menghapus semua aturan iptables..."
iptables -F
iptables -t nat -F
iptables -t mangle -F
iptables -X

ip6tables -F
ip6tables -t nat -F
ip6tables -t mangle -F
ip6tables -X

echo "===> Mengatur kebijakan default ke ACCEPT..."
iptables -P INPUT ACCEPT
iptables -P FORWARD ACCEPT
iptables -P OUTPUT ACCEPT

ip6tables -P INPUT ACCEPT
ip6tables -P FORWARD ACCEPT
ip6tables -P OUTPUT ACCEPT

echo "===> Mengaktifkan IP forwarding..."
# Enable forwarding secara runtime
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv6.conf.all.forwarding=1

# Simpan perubahan untuk persisten
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
echo "net.ipv6.conf.all.forwarding=1" >> /etc/sysctl.conf
sysctl -p

echo "===> Menambahkan /usr/sbin ke PATH (jika belum ada)..."
if [[ ":$PATH:" != *":/usr/sbin:"* ]]; then
    echo 'export PATH=$PATH:/usr/sbin' >> ~/.bashrc
    source ~/.bashrc
fi

echo "===> Menginstal iptables-persistent..."
apt-get update
apt-get install -y iptables iptables-persistent

echo "===> Menyimpan aturan iptables..."
iptables-save > /etc/iptables/rules.v4
ip6tables-save > /etc/iptables/rules.v6

echo "===> Memastikan iptables-persistent aktif saat boot..."
systemctl enable netfilter-persistent

echo "===> Verifikasi konfigurasi..."
iptables -L -n -v
ip6tables -L -n -v

echo "Proses selesai. Semua aturan telah dihapus, forwarding diaktifkan, dan iptables disimpan untuk persisten."