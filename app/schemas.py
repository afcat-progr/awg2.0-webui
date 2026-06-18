"""Pydantic schemas for form validation."""
import re

from pydantic import BaseModel, Field, field_validator

_IFACE_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,14}$")

# A magic header: either a single uint32 ("1234") or a range ("123-456").
_HEADER_RE = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+)\s*)?$")
_U32_MAX = 4294967295  # uint32 max (2^32-1)
# Types 1-4 are reserved by WireGuard, so headers must be >= 5. There is NO
# upper "must be large" requirement — small values like 2392 work fine
# (confirmed by real-world configs). We only enforce format, uint32 range,
# and that the four headers do not overlap each other.
_HEADER_MIN = 5


def _header_bounds(value: str) -> tuple[int, int]:
    """Validate a header value and return (low, high) inclusive bounds.

    Accepts "N" (single) or "A-B" (range). Raises ValueError on bad input.
    """
    m = _HEADER_RE.match(value or "")
    if not m:
        raise ValueError(f"Неверный формат заголовка «{value}». Используйте число (1234) или диапазон (123-456).")
    low = int(m.group(1))
    high = int(m.group(2)) if m.group(2) is not None else low
    if low > high:
        raise ValueError(f"В диапазоне «{value}» левая граница больше правой.")
    if low < _HEADER_MIN or high > _U32_MAX:
        raise ValueError(f"Значения H1–H4 должны быть в диапазоне {_HEADER_MIN}…{_U32_MAX} (получено «{value}»).")
    return low, high


class ServerCreate(BaseModel):
    name: str = Field(..., description="Interface name, e.g. awg0")
    description: str = ""
    address: str = Field("10.8.0.1/24")
    listen_port: int = Field(51820, ge=1, le=65535)
    dns: str = ""
    mtu: int = Field(1420, ge=576, le=9000)
    endpoint_host: str = ""
    wan_interface: str = "eth0"

    # AWG obfuscation. Defaults follow a known-good real-world config.
    jc: int = Field(11, ge=1, le=128)        # junk packet count
    jmin: int = Field(545, ge=0, le=1280)    # junk packet min size
    jmax: int = Field(896, ge=1, le=1280)    # junk packet max size
    s1: int = Field(90, ge=0, le=1280)       # padding of handshake init message
    s2: int = Field(70, ge=0, le=1280)       # padding of handshake response message
    s3: int = Field(50, ge=0, le=1280)       # padding of handshake cookie message
    s4: int = Field(15, ge=0, le=1280)       # padding of transport messages
    # H1-H4 are magic headers. AmneziaWG 2.0 accepts a single uint32 ("1234")
    # or a range ("123-456"). They must be UNIQUE and NON-OVERLAPPING; small
    # values are fine. They MUST be identical on client and server.
    h1: str = Field("2392")  # init message
    h2: str = Field("1324")  # response message
    h3: str = Field("4123")  # cookie message
    h4: str = Field("1232")  # transport message

    @field_validator("name")
    @classmethod
    def _valid_name(cls, v: str) -> str:
        if not _IFACE_RE.match(v):
            raise ValueError("Имя интерфейса должно начинаться с буквы, 1-15 символов (a-z, 0-9, _, -).")
        return v

    @field_validator("jmax")
    @classmethod
    def _jmax_gt_jmin(cls, v: int, info) -> int:
        jmin = info.data.get("jmin", 0)
        if v < jmin:
            raise ValueError("Jmax должен быть >= Jmin.")
        return v

    @field_validator("s2")
    @classmethod
    def _s1_plus_56_ne_s2(cls, v: int, info) -> int:
        # AmneziaWG hard rule: S1 + 56 must not equal S2.
        s1 = info.data.get("s1", 0)
        if s1 + 56 == v:
            raise ValueError("Недопустимо: S1 + 56 не должно равняться S2.")
        return v

    @field_validator("h1", "h2", "h3", "h4")
    @classmethod
    def _valid_header(cls, v: str) -> str:
        v = (v or "").strip()
        _header_bounds(v)  # raises on bad format/range
        return v

    @field_validator("h4")
    @classmethod
    def _headers_distinct(cls, v: str, info) -> str:
        # H1-H4 ranges must not overlap each other (and singles must differ).
        raw = [info.data.get("h1"), info.data.get("h2"), info.data.get("h3"), v]
        spans: list[tuple[int, int]] = []
        for h in raw:
            if h is None:
                return v  # an earlier header already failed; skip cross-check
            spans.append(_header_bounds(h))
        for i in range(len(spans)):
            for j in range(i + 1, len(spans)):
                a_lo, a_hi = spans[i]
                b_lo, b_hi = spans[j]
                if a_lo <= b_hi and b_lo <= a_hi:
                    raise ValueError("H1, H2, H3, H4 не должны пересекаться (значения/диапазоны должны быть разными).")
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
