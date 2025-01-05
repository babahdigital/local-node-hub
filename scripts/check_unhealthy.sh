#!/usr/bin/env bash

CONTAINER_NAME="stream-server"
LOGFILE="/mnt/Data/Syslog/default/check_unhealthy.log"
touch "$LOGFILE"

STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null)

if [ "$STATUS" == "unhealthy" ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') - Container $CONTAINER_NAME is unhealthy. Restarting..." >> "$LOGFILE"
  docker restart "$CONTAINER_NAME" >> "$LOGFILE" 2>&1
fi
