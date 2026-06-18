#!/usr/bin/env bash
set -e

# Enable IPv4 forwarding (best-effort; requires the container to have the
# privilege. On the host you should also persist this in sysctl.conf).
if [ "${APPLY_TO_SYSTEM:-1}" = "1" ]; then
  sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
  sysctl -w net.ipv6.conf.all.forwarding=1 >/dev/null 2>&1 || true
fi

mkdir -p /data "${AWG_CONFIG_DIR:-/etc/amnezia/amneziawg}"

# If real awg / awg-quick were bind-mounted from the host, they shadow the
# image-built symlinks. Otherwise create fallback symlinks to plain wg.
if ! command -v awg &>/dev/null; then
  ln -sf /usr/bin/wg /usr/local/bin/awg 2>/dev/null || true
fi
if ! command -v awg-quick &>/dev/null; then
  ln -sf /usr/bin/wg-quick /usr/local/bin/awg-quick 2>/dev/null || true
fi

# Symlink /etc/wireguard -> config dir so awg-quick finds configs by name too.
ln -sfn "${AWG_CONFIG_DIR:-/etc/amnezia/amneziawg}" /etc/wireguard 2>/dev/null || true

echo "--- AWG WebUI starting ---"
echo "awg binary: $(which awg) -> $(readlink -f "$(which awg)" 2>/dev/null || echo 'native')"
echo "awg-quick:  $(which awg-quick) -> $(readlink -f "$(which awg-quick)" 2>/dev/null || echo 'native')"
echo "config dir: ${AWG_CONFIG_DIR:-/etc/amnezia/amneziawg}"
echo "--------------------------"

exec uvicorn app.main:app \
  --host "${HOST:-0.0.0.0}" \
  --port "${PORT:-8080}" \
  --proxy-headers \
  --forwarded-allow-ips '*'
