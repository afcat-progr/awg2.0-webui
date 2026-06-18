"""Server (AWG interface) routes."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import awg, crud
from ..auth import current_user
from ..database import get_db
from ..models import User
from ..schemas import ServerCreate, ServerUpdate
from ..templating import templates

router = APIRouter(dependencies=[Depends(current_user)])


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    servers = crud.list_servers(db)
    statuses = {s.id: awg.interface_status(s) for s in servers}
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"servers": servers, "statuses": statuses, "username": user.username},
    )


@router.get("/servers/new", response_class=HTMLResponse)
def new_server_form(request: Request, user: User = Depends(current_user)):
    return templates.TemplateResponse(
        request, "server_form.html", {"server": None, "errors": None, "username": user.username}
    )


def _parse_server_form(form) -> ServerCreate:
    return ServerCreate(
        name=form.get("name", "").strip(),
        description=form.get("description", "").strip(),
        address=form.get("address", "").strip(),
        listen_port=int(form.get("listen_port") or 51820),
        dns=form.get("dns", "").strip(),
        mtu=int(form.get("mtu") or 1420),
        endpoint_host=form.get("endpoint_host", "").strip(),
        wan_interface=form.get("wan_interface", "eth0").strip() or "eth0",
        jc=int(form.get("jc") or 4),
        jmin=int(form.get("jmin") or 40),
        jmax=int(form.get("jmax") or 70),
        s1=int(form.get("s1") or 0),
        s2=int(form.get("s2") or 0),
        h1=(form.get("h1") or "1148506570").strip(),
        h2=(form.get("h2") or "1820040150").strip(),
        h3=(form.get("h3") or "1377490607").strip(),
        h4=(form.get("h4") or "1973755675").strip(),
    )


@router.post("/servers", response_class=HTMLResponse)
async def create_server(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    form = await request.form()
    try:
        data = _parse_server_form(form)
    except Exception as exc:  # noqa: BLE001
        return templates.TemplateResponse(
            request,
            "server_form.html",
            {"server": None, "errors": str(exc), "username": user.username, "form": dict(form)},
            status_code=422,
        )
    if crud.get_server_by_name(db, data.name):
        return templates.TemplateResponse(
            request,
            "server_form.html",
            {"server": None, "errors": f"Интерфейс {data.name} уже существует", "username": user.username, "form": dict(form)},
            status_code=409,
        )
    server = crud.create_server(db, data)
    return RedirectResponse(f"/servers/{server.id}", status_code=303)


@router.get("/servers/{server_id}", response_class=HTMLResponse)
def server_detail(server_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    server = crud.get_server(db, server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    status = awg.interface_status(server)
    return templates.TemplateResponse(
        request,
        "server_detail.html",
        {"server": server, "status": status, "username": user.username},
    )


@router.get("/servers/{server_id}/edit", response_class=HTMLResponse)
def edit_server_form(server_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    server = crud.get_server(db, server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    return templates.TemplateResponse(
        request, "server_form.html", {"server": server, "errors": None, "username": user.username}
    )


@router.post("/servers/{server_id}/edit", response_class=HTMLResponse)
async def update_server(server_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    server = crud.get_server(db, server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    form = await request.form()
    try:
        base = _parse_server_form(form)
        data = ServerUpdate(**base.model_dump(), enabled=form.get("enabled") == "on")
        # name is immutable after creation (interface rename is messy); keep existing
        data.name = server.name
    except Exception as exc:  # noqa: BLE001
        return templates.TemplateResponse(
            request,
            "server_form.html",
            {"server": server, "errors": str(exc), "username": user.username},
            status_code=422,
        )
    crud.update_server(db, server, data)
    return RedirectResponse(f"/servers/{server.id}", status_code=303)


@router.post("/servers/{server_id}/toggle")
def toggle_server(server_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    server = crud.get_server(db, server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    crud.toggle_server(db, server)
    return RedirectResponse(f"/servers/{server.id}", status_code=303)


@router.post("/servers/{server_id}/delete")
def delete_server(server_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    server = crud.get_server(db, server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    crud.delete_server(db, server)
    return RedirectResponse("/", status_code=303)


@router.get("/servers/{server_id}/config", response_class=PlainTextResponse)
def server_config(server_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    server = crud.get_server(db, server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    return PlainTextResponse(
        awg.render_server_config(server),
        headers={"Content-Disposition": f'attachment; filename="{server.name}.conf"'},
    )
