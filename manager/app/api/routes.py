from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from manager.app.core.config import settings
from manager.app.database.database import get_db
from manager.app.database.repository import get_machine, list_machines
from manager.app.grpc.client import AgentClient
from manager.app.services.container_service import agent_for, deploy
from manager.app.services.machine_service import all_machines, machine_to_dict, remove_machine, resolve_machine

router = APIRouter()


class RunRequest(BaseModel):
    machine: str | None = None
    replicas: int = Field(default=1, ge=1, le=100)
    image: str
    name_prefix: str | None = None
    env: list[str] = Field(default_factory=list)
    ports: dict[str, int | str] = Field(default_factory=dict)
    volumes: list[str] = Field(default_factory=list)
    network: str | None = None


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/machines")
def machines(db: Session = Depends(get_db)):
    return {"machines": all_machines(db)}


@router.delete("/machines/{machine_ref}")
def delete_machine(machine_ref: str, db: Session = Depends(get_db)):
    try:
        remove_machine(db, machine_ref)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/deployments")
def run(req: RunRequest, db: Session = Depends(get_db)):
    if not req.machine:
        raise HTTPException(400, "MVP requires --machine. Automatic scheduling can be added later.")
    try:
        return deploy(db, settings.cluster_token, req.machine, req.image, req.replicas, req.name_prefix, req.env, req.ports, req.volumes, req.network)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(502, f"Agent operation failed: {exc}")


@router.get("/containers")
def containers(machine: str | None = Query(default=None), db: Session = Depends(get_db)):
    targets = []
    if machine:
        try:
            targets = [resolve_machine(db, machine)]
        except ValueError as exc:
            raise HTTPException(404, str(exc))
    else:
        targets = list_machines(db)

    result = []
    for m in targets:
        try:
            response = agent_for(m, settings.cluster_token).list_containers(True)
            for c in response.get("containers", []):
                c["machine_id"] = m.id
                c["machine"] = m.name
                result.append(c)
        except Exception as exc:
            result.append({"machine": m.name, "machine_id": m.id, "error": str(exc)})
    return {"containers": result}


def _find_container(db: Session, ref: str):
    for machine in list_machines(db):
        try:
            response = agent_for(machine, settings.cluster_token).list_containers(True)
            for c in response.get("containers", []):
                if c.get("id") == ref or c.get("short_id") == ref or c.get("name") == ref:
                    return machine, c
        except Exception:
            continue
    raise HTTPException(404, f"Container '{ref}' not found")


@router.post("/containers/{ref}/start")
def start_container(ref: str, db: Session = Depends(get_db)):
    m, c = _find_container(db, ref)
    return agent_for(m, settings.cluster_token).start_container(c["id"])


@router.post("/containers/{ref}/stop")
def stop_container(ref: str, db: Session = Depends(get_db)):
    m, c = _find_container(db, ref)
    return agent_for(m, settings.cluster_token).stop_container(c["id"])


@router.post("/containers/{ref}/restart")
def restart_container(ref: str, db: Session = Depends(get_db)):
    m, c = _find_container(db, ref)
    return agent_for(m, settings.cluster_token).restart_container(c["id"])


@router.delete("/containers/{ref}")
def remove_container(ref: str, force: bool = False, db: Session = Depends(get_db)):
    m, c = _find_container(db, ref)
    return agent_for(m, settings.cluster_token).remove_container(c["id"], force)


@router.get("/containers/{ref}/inspect")
def inspect_container(ref: str, db: Session = Depends(get_db)):
    m, c = _find_container(db, ref)
    return agent_for(m, settings.cluster_token).inspect_container(c["id"])


@router.get("/containers/{ref}/logs")
def logs(ref: str, tail: int = 200, db: Session = Depends(get_db)):
    m, c = _find_container(db, ref)
    return agent_for(m, settings.cluster_token).logs(c["id"], tail)
