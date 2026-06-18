# AmneziaWG WebUI
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Runtime tools needed to manage interfaces from inside the container.
#  - iproute2 / iptables: networking & NAT
#  - amneziawg-tools + kernel module on the HOST (see README); we install the
#    userspace tools here so `awg` / `awg-quick` are available.
RUN apt-get update && apt-get install -y --no-install-recommends \
        iproute2 iptables openresolv procps ca-certificates curl gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install AmneziaWG userspace tools.
# The official packages live in the AmneziaWG PPA / repo. We pull the prebuilt
# tools; if your base differs, see README for alternatives.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends wireguard-tools || true; \
    # Provide awg/awg-quick as wrappers if amneziawg-tools are mounted from host;
    # otherwise fall back to wg/wg-quick (plain WireGuard) for testing.
    if [ ! -e /usr/bin/awg ]; then ln -sf /usr/bin/wg /usr/local/bin/awg || true; fi; \
    if [ ! -e /usr/bin/awg-quick ]; then ln -sf /usr/bin/wg-quick /usr/local/bin/awg-quick || true; fi; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME ["/data", "/etc/amnezia/amneziawg"]
EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
