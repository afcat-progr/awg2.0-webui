"""Pydantic schemas for form validation."""
import re

from pydantic import BaseModel, Field, field_validator

_IFACE_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,14}$")

# A magic header: either a single uint32 ("1234") or a range ("123-456").
_HEADER_RE = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+)\s*)?$")
_U32_MAX = 2147483647  # AmneziaWG uses values up to 2^31-1
_HEADER_MIN = 5        # values below this are silently mangled / break handshake


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
        raise ValueError(f"Значения заголовка должны быть в диапазоне {_HEADER_MIN}…{_U32_MAX} (получено «{value}»).")
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

    # AWG obfuscation.
    jc: int = Field(4, ge=1, le=128)
    jmin: int = Field(40, ge=0, le=1280)
    jmax: int = Field(70, ge=1, le=1280)
    s1: int = Field(0, ge=0, le=1132)
    s2: int = Field(0, ge=0, le=1188)
    # H1-H4 are magic headers. AmneziaWG 2.0 accepts a single uint32 ("1234")
    # or a range ("123-456"). They must be large, UNIQUE and NON-OVERLAPPING;
    # otherwise the handshake fails (client hangs on "Connecting...").
    h1: str = Field("1148506570")  # init message
    h2: str = Field("1820040150")  # response message
    h3: str = Field("1377490607")  # cookie message
    h4: str = Field("1973755675")  # transport message

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
