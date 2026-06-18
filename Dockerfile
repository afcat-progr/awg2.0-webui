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

# Install plain wireguard-tools as a build-time fallback for wg-quick.
# The real awg / awg-quick binaries are bind-mounted from the host at runtime
# (see docker-compose.yml). The fallback symlinks are only created if the
# real binaries are absent (development / testing without AmneziaWG).
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends wireguard-tools || true; \
    rm -rf /var/lib/apt/lists/*

# awg-quick looks for configs in /etc/wireguard/ by default, but we store them
# in /etc/amnezia/amneziawg/. Symlink so both paths work.
RUN mkdir -p /etc/amnezia/amneziawg \
    && ln -sf /etc/amnezia/amneziawg /etc/wireguard

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME ["/data", "/etc/amnezia/amneziawg"]
EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
