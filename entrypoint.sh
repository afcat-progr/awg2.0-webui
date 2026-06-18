#!/usr/bin/env bash
set -e

# Enable IPv4 forwarding (best-effort; requires the container to have the
# privilege. On the host you should also persist this in sysctl.conf).
if [ "${APPLY_TO_SYSTEM:-1}" = "1" ]; then
  sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
  sysctl -w net.ipv6.conf.all.forwarding=1 >/dev/null 2>&1 || true
fi

mkdir -p /data "${AWG_CONFIG_DIR:-/etc/amnezia/amneziawg}"

exec uvicorn app.main:app \
  --host "${HOST:-0.0.0.0}" \
  --port "${PORT:-8080}" \
  --proxy-headers \
  --forwarded-allow-ips '*'
