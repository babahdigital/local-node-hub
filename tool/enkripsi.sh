# credentials.sh

# Informasi kredensial RTSP terenkripsi (Base64)
DVR_IP_BASE64=$(echo -n "172.16.10.252" | base64)
RTSP_IP=$(echo -n "10.10.19.3" | base64)
RTSP_USER_BASE64=$(echo -n "babahdigital" | base64)
RTSP_PASSWORD_BASE64=$(echo -n "Admin123@" | base64)