#!/bin/sh
set -e

# Wait for SRS and resolve its IP
for i in $(seq 1 15); do
  SRS_IP=$(getent hosts srs | awk '{print $1}' | head -1)
  [ -n "$SRS_IP" ] && break
  echo "Waiting for SRS DNS... ($i)"
  sleep 2
done

[ -z "$SRS_IP" ] && SRS_IP="srs"
echo "SRS resolved to: $SRS_IP"

sed "s/SRS_PLACEHOLDER/$SRS_IP/g" /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
exec nginx -g 'daemon off;'
