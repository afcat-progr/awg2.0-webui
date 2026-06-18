"""Pydantic schemas for form validation."""
import re

from pydantic import BaseModel, Field, field_validator

_IFACE_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,14}$")


class ServerCreate(BaseModel):
    name: str = Field(..., description="Interface name, e.g. awg0")
    description: str = ""
    address: str = Field("10.8.0.1/24")
    listen_port: int = Field(51820, ge=1, le=65535)
    dns: str = ""
    mtu: int = Field(1420, ge=576, le=9000)
    endpoint_host: str = ""
    wan_interface: str = "eth0"

    # AWG obfuscation.
    # H1-H4 must be large UNIQUE 32-bit values (>= 5). awg-quick silently
    # mangles small values, which breaks the handshake. Defaults below match
    # AmneziaWG-style random magic headers; they should differ per server but
    # MUST be identical on client and server.
    jc: int = Field(4, ge=1, le=128)
    jmin: int = Field(40, ge=0, le=1280)
    jmax: int = Field(70, ge=1, le=1280)
    s1: int = Field(0, ge=0, le=1132)
    s2: int = Field(0, ge=0, le=1188)
    h1: int = Field(1148506570, ge=5, le=2147483647)
    h2: int = Field(1820040150, ge=5, le=2147483647)
    h3: int = Field(1377490607, ge=5, le=2147483647)
    h4: int = Field(1973755675, ge=5, le=2147483647)

    @field_validator("name")
    @classmethod
    def _valid_name(cls, v: str) -> str:
        if not _IFACE_RE.match(v):
            raise ValueError("Interface name must start with a letter and be 1-15 chars (a-z, 0-9, _, -).")
        return v

    @field_validator("jmax")
    @classmethod
    def _jmax_gt_jmin(cls, v: int, info) -> int:
        jmin = info.data.get("jmin", 0)
        if v < jmin:
            raise ValueError("Jmax must be >= Jmin.")
        return v

    @field_validator("s2")
    @classmethod
    def _s1_plus_56_ne_s2(cls, v: int, info) -> int:
        # AmneziaWG hard rule: S1 + 56 must not equal S2.
        s1 = info.data.get("s1", 0)
        if s1 + 56 == v:
            raise ValueError("Недопустимо: S1 + 56 не должно равняться S2.")
        return v

    @field_validator("h4")
    @classmethod
    def _headers_unique(cls, v: int, info) -> int:
        # H1-H4 must all be distinct, otherwise the handshake fails.
        hs = [info.data.get("h1"), info.data.get("h2"), info.data.get("h3"), v]
        hs = [h for h in hs if h is not None]
        if len(set(hs)) != len(hs):
            raise ValueError("H1, H2, H3, H4 должны быть уникальными (все разные).")
        return v


class ServerUpdate(ServerCreate):
    enabled: bool = True


class PeerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    address: str = ""  # empty -> auto allocate
    allowed_ips: str = "0.0.0.0/0, ::/0"
    dns: str = ""
    keepalive: int = Field(25, ge=0, le=600)
    use_preshared_key: bool = True
