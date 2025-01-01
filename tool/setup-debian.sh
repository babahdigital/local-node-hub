#!/bin/bash

# Pastikan script dijalankan sebagai root
if [ "$(id -u)" -ne 0 ]; then
    echo "Script ini harus dijalankan sebagai root!"
    exit 1
fi

# Update dan install tools networking dasar
echo "Memperbarui repositori dan menginstal alat dasar..."
apt update && apt upgrade -y
apt update && apt install -y \
    curl tcpdump docker.io jq net-tools openssh-server telnet netcat traceroute nmap dnsutils iputils-ping mtr whois iftop ethtool iperf3 \
    htop iotop sysstat git build-essential vim tmux python3 python3-pip strace lsof gdb ncdu zip unzip tree


# Konfigurasi Docker daemon.json
echo "Mengkonfigurasi Docker daemon.json..."
mkdir -p /etc/docker
cat <<EOF > /etc/docker/daemon.json
{
  "dns": [
    "8.8.8.8",
    "1.1.1.1"
  ],
  "default-address-pools": [
    {
      "base": "172.16.30.0/16",
      "size": 28
    }
  ],
  "features": {
    "buildkit": true
  }
}
EOF

# Restart Docker
echo "Restarting Docker service..."
systemctl restart docker

# Konfigurasi jaringan host
echo "Mengonfigurasi jaringan host..."
cat <<EOF > /etc/network/interfaces
# The loopback network interface
auto lo
iface lo inet loopback

# The primary network interface
allow-hotplug ens3
iface ens3 inet static
      address 172.16.30.3/28
      gateway 172.16.30.1
      dns-nameservers 8.8.8.8 1.1.1.1
      dns-search docker

# Macvlan network interface
auto macvlan0
iface macvlan0 inet static
      address 172.16.30.14/28
      pre-up ip link add macvlan0 link ens3 type macvlan mode bridge
      post-down ip link del macvlan0
EOF

# Aktifkan IP forwarding
echo "Mengaktifkan IP forwarding..."
echo "net.ipv4.ip_forward=1" | tee -a /etc/sysctl.conf
sysctl -p

# Restart networking service
echo "Restarting networking service..."
systemctl restart networking

# Konfigurasi SSH
echo "Mengonfigurasi SSH untuk login dengan password dan port 1983..."
sed -i 's/^#\?Port .*/Port 1983/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Restart SSH service
echo "Restarting SSH service..."
systemctl restart sshd

# Konfigurasi iptables
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
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv6.conf.all.forwarding=1

echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
echo "net.ipv6.conf.all.forwarding=1" >> /etc/sysctl.conf
sysctl -p

echo "===> Menginstal iptables-persistent..."
apt-get install -y iptables iptables-persistent

echo "===> Menyimpan aturan iptables..."
iptables-save > /etc/iptables/rules.v4
ip6tables-save > /etc/iptables/rules.v6

echo "===> Memastikan iptables-persistent aktif saat boot..."
systemctl enable netfilter-persistent

echo "===> Verifikasi konfigurasi iptables..."
iptables -L -n -v
ip6tables -L -n -v

# Reboot otomatis
echo "Konfigurasi selesai. Sistem akan reboot dalam 5 detik..."
sleep 5
reboot