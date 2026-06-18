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

    # AWG obfuscation
    jc: int = Field(4, ge=0, le=128)
    jmin: int = Field(40, ge=0, le=1280)
    jmax: int = Field(70, ge=0, le=1280)
    s1: int = Field(0, ge=0, le=1280)
    s2: int = Field(0, ge=0, le=1280)
    h1: int = Field(1, ge=0)
    h2: int = Field(2, ge=0)
    h3: int = Field(3, ge=0)
    h4: int = Field(4, ge=0)

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


class ServerUpdate(ServerCreate):
    enabled: bool = True


class PeerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    address: str = ""  # empty -> auto allocate
    allowed_ips: str = "0.0.0.0/0, ::/0"
    dns: str = ""
    keepalive: int = Field(25, ge=0, le=600)
    use_preshared_key: bool = True
