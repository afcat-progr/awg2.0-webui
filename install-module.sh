#!/usr/bin/env bash
#
# install-module.sh — build & install the AmneziaWG kernel module on the HOST.
#
# Why this exists:
#   The AmneziaWG Ubuntu/Debian PPA sometimes ships a kernel module (dkms) that
#   is OLDER than the userspace tools (awg / awg-quick). When the module and the
#   tools disagree on the obfuscation wire-format (junk packets, S1-S4 padding,
#   H1-H4 magic headers), the handshake silently fails — the client connects but
#   no traffic flows ("Connecting..." / no internet). Building the module from
#   the matching GitHub source against the running kernel fixes this.
#
# Run this ON THE VPS HOST (not inside the container), as root:
#   sudo bash install-module.sh
#
# It is safe to re-run (e.g. after a kernel upgrade).

set -euo pipefail

REPO="https://github.com/amnezia-vpn/amneziawg-linux-kernel-module.git"
SRC_DIR="/opt/amneziawg-linux-kernel-module"
KVER="$(uname -r)"

echo "==> AmneziaWG kernel module installer"
echo "    kernel: ${KVER}"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run as root (sudo bash install-module.sh)"
  exit 1
fi

echo "==> Installing build prerequisites"
apt-get update -qq
apt-get install -y --no-install-recommends \
  git build-essential dkms "linux-headers-${KVER}" || {
    echo "WARN: linux-headers-${KVER} not found, trying generic linux-headers-amd64"
    apt-get install -y --no-install-recommends linux-headers-amd64
  }

if [ ! -d "/lib/modules/${KVER}/build" ]; then
  echo "ERROR: kernel headers for ${KVER} are missing (/lib/modules/${KVER}/build)."
  echo "       Install the matching linux-headers package and re-run."
  exit 1
fi

echo "==> Fetching source"
if [ -d "${SRC_DIR}/.git" ]; then
  git -C "${SRC_DIR}" pull --ff-only
else
  rm -rf "${SRC_DIR}"
  git clone --depth 1 "${REPO}" "${SRC_DIR}"
fi

echo "==> Building module"
make -C "${SRC_DIR}/src" -j"$(nproc)"

echo "==> Removing the stale PPA/DKMS module (if present)"
# Drop the dkms-managed module so it doesn't shadow our freshly built one.
if command -v dkms >/dev/null 2>&1; then
  dkms remove amneziawg/1.0.0 --all >/dev/null 2>&1 || true
fi
rm -f "/lib/modules/${KVER}/updates/dkms/amneziawg.ko"* 2>/dev/null || true

echo "==> Installing freshly built module"
make -C "${SRC_DIR}/src" install
depmod -a "${KVER}"

echo "==> Reloading module"
# Bring any awg interfaces down first so the module can be unloaded.
for cfg in /etc/amnezia/amneziawg/*.conf; do
  [ -e "$cfg" ] || continue
  awg-quick down "$cfg" >/dev/null 2>&1 || true
done
modprobe -r amneziawg 2>/dev/null || true
modprobe amneziawg

echo "==> Pinning dkms package so apt won't restore the old module"
apt-mark hold amneziawg-dkms >/dev/null 2>&1 || true

echo
echo "==> Done. Loaded module:"
modinfo amneziawg | grep -E "^filename|^version|^srcversion" || true
echo
echo "Now (re)start the panel container so it brings interfaces up on the new module:"
echo "    docker compose restart awg-webui"
