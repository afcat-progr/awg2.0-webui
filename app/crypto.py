"""Curve25519 key generation for WireGuard / AmneziaWG.

Keys use the same wire format as `wg genkey` / `wg pubkey` / `wg genpsk`:
32 raw bytes, base64-encoded. We rely on the audited `cryptography` library for
the X25519 math instead of hand-rolling the Montgomery ladder.
"""
import base64
import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

_RAW = serialization.Encoding.Raw
_PUB = serialization.PublicFormat.Raw
_PRIV = serialization.PrivateFormat.Raw
_NOENC = serialization.NoEncryption()


def generate_private_key() -> str:
    """Return a base64-encoded X25519 private key (matches `wg genkey`)."""
    key = X25519PrivateKey.generate()
    raw = key.private_bytes(_RAW, _PRIV, _NOENC)
    return base64.b64encode(raw).decode()


def public_key_from_private(private_key_b64: str) -> str:
    """Derive the base64 public key from a base64 private key (matches `wg pubkey`)."""
    raw = base64.b64decode(private_key_b64)
    key = X25519PrivateKey.from_private_bytes(raw)
    pub = key.public_key().public_bytes(_RAW, _PUB)
    return base64.b64encode(pub).decode()


def generate_keypair() -> tuple[str, str]:
    """Return (private_key, public_key) base64-encoded."""
    priv = generate_private_key()
    return priv, public_key_from_private(priv)


def generate_preshared_key() -> str:
    """Return a base64-encoded 32-byte preshared key (matches `wg genpsk`)."""
    return base64.b64encode(os.urandom(32)).decode()
