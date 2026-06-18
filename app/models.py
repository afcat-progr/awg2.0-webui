"""Database models.

A *Server* maps to one AmneziaWG interface (awg0, awg1, ...).
A *Peer* is a client that connects to one server.
A *User* is a panel admin.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Server(Base):
    """One AmneziaWG interface on this host."""

    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Interface name, e.g. "awg0". Must be unique & valid for the OS.
    name: Mapped[str] = mapped_column(String(15), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255), default="")

    # Server keypair.
    private_key: Mapped[str] = mapped_column(String(64))
    public_key: Mapped[str] = mapped_column(String(64))

    # Networking.
    address: Mapped[str] = mapped_column(String(64))          # e.g. 10.8.0.1/24
    listen_port: Mapped[int] = mapped_column(Integer)         # UDP port
    dns: Mapped[str] = mapped_column(String(128), default="")
    mtu: Mapped[int] = mapped_column(Integer, default=1420)

    # Public endpoint advertised to peers (host part). Falls back to global setting.
    endpoint_host: Mapped[str] = mapped_column(String(255), default="")

    # NAT / firewall hooks (the wan interface used for masquerade).
    wan_interface: Mapped[str] = mapped_column(String(32), default="eth0")
    post_up: Mapped[str] = mapped_column(Text, default="")
    post_down: Mapped[str] = mapped_column(Text, default="")

    # ---- AmneziaWG 2.0 obfuscation parameters ----
    jc: Mapped[int] = mapped_column(Integer, default=4)       # junk packet count
    jmin: Mapped[int] = mapped_column(Integer, default=40)    # junk packet min size
    jmax: Mapped[int] = mapped_column(Integer, default=70)    # junk packet max size
    s1: Mapped[int] = mapped_column(Integer, default=0)       # init packet junk size
    s2: Mapped[int] = mapped_column(Integer, default=0)       # response packet junk size
    # H1-H4 are magic headers. AmneziaWG 2.0 accepts either a single uint32 value
    # ("1234") or a range ("123-456"). Stored as strings to support both. They
    # must be large, UNIQUE, non-overlapping; small/overlapping values break the
    # handshake (client hangs on "Connecting...").
    h1: Mapped[str] = mapped_column(String(32), default="1148506570")  # init message
    h2: Mapped[str] = mapped_column(String(32), default="1820040150")  # response message
    h3: Mapped[str] = mapped_column(String(32), default="1377490607")  # cookie message
    h4: Mapped[str] = mapped_column(String(32), default="1973755675")  # transport message

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    peers: Mapped[list["Peer"]] = relationship(
        back_populates="server",
        cascade="all, delete-orphan",
        order_by="Peer.id",
    )


class Peer(Base):
    """A client of a server."""

    __tablename__ = "peers"
    __table_args__ = (UniqueConstraint("server_id", "address", name="uq_peer_addr"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(64))
    private_key: Mapped[str] = mapped_column(String(64))
    public_key: Mapped[str] = mapped_column(String(64))
    preshared_key: Mapped[str] = mapped_column(String(64), default="")

    address: Mapped[str] = mapped_column(String(64))         # e.g. 10.8.0.2/32
    allowed_ips: Mapped[str] = mapped_column(String(255), default="0.0.0.0/0, ::/0")
    dns: Mapped[str] = mapped_column(String(128), default="")
    keepalive: Mapped[int] = mapped_column(Integer, default=25)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    server: Mapped["Server"] = relationship(back_populates="peers")
