"""Database operations tying together models, crypto, and the AWG manager."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import awg, crypto
from .models import Peer, Server
from .schemas import PeerCreate, ServerCreate, ServerUpdate


# --------------------------------------------------------------------------- #
#  Servers
# --------------------------------------------------------------------------- #
def list_servers(db: Session) -> list[Server]:
    return list(db.scalars(select(Server).order_by(Server.id)))


def get_server(db: Session, server_id: int) -> Server | None:
    return db.get(Server, server_id)


def get_server_by_name(db: Session, name: str) -> Server | None:
    return db.scalar(select(Server).where(Server.name == name))


def create_server(db: Session, data: ServerCreate) -> Server:
    priv, pub = crypto.generate_keypair()
    server = Server(
        name=data.name,
        description=data.description,
        private_key=priv,
        public_key=pub,
        address=data.address,
        listen_port=data.listen_port,
        dns=data.dns,
        mtu=data.mtu,
        endpoint_host=data.endpoint_host,
        wan_interface=data.wan_interface,
        jc=data.jc, jmin=data.jmin, jmax=data.jmax,
        s1=data.s1, s2=data.s2,
        h1=data.h1, h2=data.h2, h3=data.h3, h4=data.h4,
    )
    db.add(server)
    db.commit()
    db.refresh(server)
    awg.apply_server(server)
    return server


def update_server(db: Session, server: Server, data: ServerUpdate) -> Server:
    for field in (
        "description", "address", "listen_port", "dns", "mtu", "endpoint_host",
        "wan_interface", "jc", "jmin", "jmax", "s1", "s2", "h1", "h2", "h3", "h4",
        "enabled",
    ):
        setattr(server, field, getattr(data, field))
    db.commit()
    db.refresh(server)
    awg.apply_server(server)
    return server


def delete_server(db: Session, server: Server) -> None:
    awg.remove_server(server)
    db.delete(server)
    db.commit()


def toggle_server(db: Session, server: Server) -> Server:
    server.enabled = not server.enabled
    db.commit()
    db.refresh(server)
    if server.enabled:
        awg.apply_server(server)
    else:
        awg.down_server(server)
    return server


# --------------------------------------------------------------------------- #
#  Peers
# --------------------------------------------------------------------------- #
def get_peer(db: Session, peer_id: int) -> Peer | None:
    return db.get(Peer, peer_id)


def create_peer(db: Session, server: Server, data: PeerCreate) -> Peer:
    priv, pub = crypto.generate_keypair()
    psk = crypto.generate_preshared_key() if data.use_preshared_key else ""
    address = data.address.strip() or awg.next_free_ip(server)

    peer = Peer(
        server_id=server.id,
        name=data.name,
        private_key=priv,
        public_key=pub,
        preshared_key=psk,
        address=address,
        allowed_ips=data.allowed_ips,
        dns=data.dns,
        keepalive=data.keepalive,
    )
    db.add(peer)
    db.commit()
    db.refresh(server)
    awg.apply_server(server)
    db.refresh(peer)
    return peer


def delete_peer(db: Session, peer: Peer) -> None:
    server = peer.server
    db.delete(peer)
    db.commit()
    db.refresh(server)
    awg.apply_server(server)


def toggle_peer(db: Session, peer: Peer) -> Peer:
    peer.enabled = not peer.enabled
    db.commit()
    server = peer.server
    db.refresh(server)
    awg.apply_server(server)
    db.refresh(peer)
    return peer
