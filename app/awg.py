"""AmneziaWG system manager.

Responsible for:
  * rendering server interface config (`awg0.conf`)
  * rendering client config (and its QR code)
  * applying changes to the live system via `awg-quick` / `awg syncconf`
  * helpers for IP allocation and public-IP detection

When ``settings.apply_to_system`` is False everything except the actual system
calls still runs (config files are written), which is handy for development on a
machine without AmneziaWG installed.
"""
from __future__ import annotations

import ipaddress
import os
import subprocess
import urllib.request
from pathlib import Path

from .config import settings
from .models import Peer, Server


# --------------------------------------------------------------------------- #
#  IP allocation
# --------------------------------------------------------------------------- #
def server_network(server: Server) -> ipaddress.IPv4Network:
    """Return the IPv4 network the server's address belongs to."""
    iface = ipaddress.ip_interface(server.address.split(",")[0].strip())
    return ipaddress.ip_network(f"{iface.network.network_address}/{iface.network.prefixlen}", strict=False)


def next_free_ip(server: Server) -> str:
    """Pick the next free /32 host address inside the server's subnet."""
    net = server_network(server)
    used: set[str] = {ipaddress.ip_interface(server.address.split(",")[0].strip()).ip.compressed}
    for peer in server.peers:
        for part in peer.address.split(","):
            part = part.strip()
            if part:
                used.add(ipaddress.ip_interface(part).ip.compressed)

    for host in net.hosts():
        if host.compressed not in used:
            return f"{host.compressed}/32"
    raise RuntimeError("No free addresses left in the server subnet")


def detect_public_ip() -> str:
    """Best-effort public IP detection for the Endpoint advertised to clients."""
    if settings.public_endpoint:
        return settings.public_endpoint
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            with urllib.request.urlopen(url, timeout=4) as resp:
                ip = resp.read().decode().strip()
                if ip:
                    return ip
        except Exception:
            continue
    return "YOUR_SERVER_IP"


# --------------------------------------------------------------------------- #
#  Config rendering
# --------------------------------------------------------------------------- #
def default_post_up(wan: str) -> str:
    return (
        f"iptables -A FORWARD -i %i -j ACCEPT; "
        f"iptables -A FORWARD -o %i -j ACCEPT; "
        f"iptables -t nat -A POSTROUTING -o {wan} -j MASQUERADE"
    )


def default_post_down(wan: str) -> str:
    return (
        f"iptables -D FORWARD -i %i -j ACCEPT; "
        f"iptables -D FORWARD -o %i -j ACCEPT; "
        f"iptables -t nat -D POSTROUTING -o {wan} -j MASQUERADE"
    )


def render_server_config(server: Server) -> str:
    """Render the full interface config including [Peer] blocks."""
    post_up = server.post_up or default_post_up(server.wan_interface)
    post_down = server.post_down or default_post_down(server.wan_interface)

    lines = [
        "[Interface]",
        f"PrivateKey = {server.private_key}",
        f"Address = {server.address}",
        f"ListenPort = {server.listen_port}",
    ]
    if server.mtu:
        lines.append(f"MTU = {server.mtu}")
    lines += [
        f"PostUp = {post_up}",
        f"PostDown = {post_down}",
        "",
        "# ---- AmneziaWG 2.0 obfuscation ----",
        f"Jc = {server.jc}",
        f"Jmin = {server.jmin}",
        f"Jmax = {server.jmax}",
        f"S1 = {server.s1}",
        f"S2 = {server.s2}",
        f"H1 = {server.h1}",
        f"H2 = {server.h2}",
        f"H3 = {server.h3}",
        f"H4 = {server.h4}",
    ]

    for peer in server.peers:
        if not peer.enabled:
            continue
        lines += ["", f"# {peer.name}", "[Peer]", f"PublicKey = {peer.public_key}"]
        if peer.preshared_key:
            lines.append(f"PresharedKey = {peer.preshared_key}")
        lines.append(f"AllowedIPs = {peer.address}")

    return "\n".join(lines) + "\n"


def render_client_config(server: Server, peer: Peer) -> str:
    """Render a config that the *client* imports."""
    endpoint_host = peer.server.endpoint_host or server.endpoint_host or detect_public_ip()
    dns = peer.dns or server.dns or settings.default_dns

    lines = [
        "[Interface]",
        f"PrivateKey = {peer.private_key}",
        f"Address = {peer.address}",
    ]
    if dns:
        lines.append(f"DNS = {dns}")
    if server.mtu:
        lines.append(f"MTU = {server.mtu}")
    lines += [
        "",
        "# ---- AmneziaWG 2.0 obfuscation (must match server) ----",
        f"Jc = {server.jc}",
        f"Jmin = {server.jmin}",
        f"Jmax = {server.jmax}",
        f"S1 = {server.s1}",
        f"S2 = {server.s2}",
        f"H1 = {server.h1}",
        f"H2 = {server.h2}",
        f"H3 = {server.h3}",
        f"H4 = {server.h4}",
        "",
        "[Peer]",
        f"PublicKey = {server.public_key}",
    ]
    if peer.preshared_key:
        lines.append(f"PresharedKey = {peer.preshared_key}")
    lines += [
        f"AllowedIPs = {peer.allowed_ips}",
        f"Endpoint = {endpoint_host}:{server.listen_port}",
        f"PersistentKeepalive = {peer.keepalive}",
    ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
#  System application
# --------------------------------------------------------------------------- #
def config_path(server: Server) -> Path:
    return Path(settings.awg_config_dir) / f"{server.name}.conf"


def _run(cmd: list[str]) -> tuple[bool, str]:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        ok = out.returncode == 0
        return ok, (out.stdout + out.stderr).strip()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def write_config(server: Server) -> Path:
    """Write the interface config file to disk (chmod 600)."""
    path = config_path(server)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_server_config(server))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def apply_server(server: Server) -> tuple[bool, str]:
    """Write config and (re)start the interface."""
    write_config(server)
    if not settings.apply_to_system:
        return True, "Config written (apply_to_system disabled)."

    if not server.enabled:
        return down_server(server)

    # If already up, hot-reload with syncconf; otherwise bring it up.
    is_up, _ = _run([settings.wg_bin, "show", server.name])
    if is_up:
        ok, msg = _run([settings.wg_quick_bin, "strip", server.name])
        # strip prints a stripped config to stdout; feed it to syncconf via a temp file
        if ok:
            strip_path = config_path(server).with_suffix(".stripped")
            strip_path.write_text(msg + "\n")
            ok, sync = _run([settings.wg_bin, "syncconf", server.name, str(strip_path)])
            strip_path.unlink(missing_ok=True)
            return ok, sync or "synced"
        return ok, msg
    return _run([settings.wg_quick_bin, "up", server.name])


def down_server(server: Server) -> tuple[bool, str]:
    if not settings.apply_to_system:
        return True, "apply_to_system disabled."
    return _run([settings.wg_quick_bin, "down", server.name])


def remove_server(server: Server) -> None:
    if settings.apply_to_system:
        down_server(server)
    config_path(server).unlink(missing_ok=True)


def enable_on_boot(server: Server) -> tuple[bool, str]:
    if not settings.apply_to_system:
        return True, "apply_to_system disabled."
    return _run(["systemctl", "enable", f"awg-quick@{server.name}"])


def interface_status(server: Server) -> dict[str, str]:
    """Return raw `awg show` dump and an up/down flag."""
    if not settings.apply_to_system:
        return {"up": "unknown", "dump": "(apply_to_system disabled)"}
    is_up, dump = _run([settings.wg_bin, "show", server.name])
    return {"up": "up" if is_up else "down", "dump": dump}
