"""Peer (client) routes."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import awg, crud, qr
from ..auth import current_user
from ..database import get_db
from ..models import User
from ..schemas import PeerCreate
from ..templating import templates

router = APIRouter(dependencies=[Depends(current_user)])


@router.post("/servers/{server_id}/peers", response_class=HTMLResponse)
async def create_peer(server_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    server = crud.get_server(db, server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    form = await request.form()
    try:
        data = PeerCreate(
            name=form.get("name", "").strip(),
            address=form.get("address", "").strip(),
            allowed_ips=form.get("allowed_ips", "0.0.0.0/0, ::/0").strip() or "0.0.0.0/0, ::/0",
            dns=form.get("dns", "").strip(),
            keepalive=int(form.get("keepalive") or 25),
            use_preshared_key=form.get("use_preshared_key", "on") == "on",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, str(exc))
    crud.create_peer(db, server, data)
    return RedirectResponse(f"/servers/{server.id}", status_code=303)


@router.get("/peers/{peer_id}", response_class=HTMLResponse)
def peer_detail(peer_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    peer = crud.get_peer(db, peer_id)
    if not peer:
        raise HTTPException(404, "Peer not found")
    config = awg.render_client_config(peer.server, peer)
    return templates.TemplateResponse(
        request,
        "peer_detail.html",
        {"peer": peer, "config": config, "qr": qr.qr_data_uri(config), "username": user.username},
    )


@router.get("/peers/{peer_id}/config", response_class=PlainTextResponse)
def peer_config(peer_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    peer = crud.get_peer(db, peer_id)
    if not peer:
        raise HTTPException(404, "Peer not found")
    config = awg.render_client_config(peer.server, peer)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in peer.name)
    return PlainTextResponse(
        config, headers={"Content-Disposition": f'attachment; filename="{safe}.conf"'}
    )


@router.post("/peers/{peer_id}/toggle")
def toggle_peer(peer_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    peer = crud.get_peer(db, peer_id)
    if not peer:
        raise HTTPException(404, "Peer not found")
    crud.toggle_peer(db, peer)
    return RedirectResponse(f"/servers/{peer.server_id}", status_code=303)


@router.post("/peers/{peer_id}/delete")
def delete_peer(peer_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    peer = crud.get_peer(db, peer_id)
    if not peer:
        raise HTTPException(404, "Peer not found")
    server_id = peer.server_id
    crud.delete_peer(db, peer)
    return RedirectResponse(f"/servers/{server_id}", status_code=303)
