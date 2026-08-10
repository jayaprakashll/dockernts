from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from manager.app.database.models import ContainerRecord, Deployment, Heartbeat, Machine


def utcnow():
    return datetime.now(timezone.utc)


def upsert_machine(db: Session, data: dict) -> Machine:
    machine = db.get(Machine, data["machine_id"])
    if machine is None:
        machine = Machine(id=data["machine_id"], name=data["name"], hostname=data["hostname"], ip=data["ip"], agent_port=data["agent_port"])
        db.add(machine)
    machine.name = data["name"]
    machine.hostname = data["hostname"]
    machine.ip = data["ip"]
    machine.agent_port = int(data.get("agent_port", 9001))
    machine.cpu_count = int(data.get("cpu_count", 0))
    machine.memory_mb = int(data.get("memory_mb", 0))
    machine.docker_version = str(data.get("docker_version", "unknown"))
    machine.status = "healthy"
    machine.last_heartbeat = utcnow()
    db.commit()
    db.refresh(machine)
    return machine


def get_machine(db: Session, machine_ref: str) -> Machine | None:
    machine = db.get(Machine, machine_ref)
    if machine:
        return machine
    return db.scalar(select(Machine).where(Machine.name == machine_ref))


def list_machines(db: Session) -> list[Machine]:
    return list(db.scalars(select(Machine).order_by(Machine.name)).all())


def delete_machine(db: Session, machine_ref: str) -> bool:
    machine = get_machine(db, machine_ref)
    if not machine:
        return False
    db.delete(machine)
    db.commit()
    return True


def save_heartbeat(db: Session, data: dict) -> None:
    machine = db.get(Machine, data["machine_id"])
    if not machine:
        return
    now = utcnow()
    machine.cpu_count = int(data.get("cpu_count", machine.cpu_count))
    machine.memory_mb = int(data.get("memory_mb", machine.memory_mb))
    machine.docker_version = str(data.get("docker_version", machine.docker_version))
    machine.status = str(data.get("health", "healthy"))
    machine.last_heartbeat = now
    db.add(Heartbeat(machine_id=machine.id, timestamp=now, cpu_percent=float(data.get("cpu_percent", 0)), memory_percent=float(data.get("memory_percent", 0)), running_containers=int(data.get("running_containers", 0)), health=machine.status))
    db.commit()


def save_container(db: Session, data: dict, deployment_id: str | None = None) -> None:
    existing = db.get(ContainerRecord, data["id"])
    if existing is None:
        existing = ContainerRecord(id=data["id"], name=data["name"], machine_id=data["machine_id"], image=data.get("image", "unknown"), status=data.get("status", "unknown"), deployment_id=deployment_id)
        db.add(existing)
    else:
        existing.name = data["name"]
        existing.machine_id = data["machine_id"]
        existing.image = data.get("image", existing.image)
        existing.status = data.get("status", existing.status)
        if deployment_id:
            existing.deployment_id = deployment_id
    db.commit()


def delete_container(db: Session, container_id: str) -> None:
    row = db.get(ContainerRecord, container_id)
    if row:
        db.delete(row)
        db.commit()


def list_deployments(db: Session, active_only: bool = True) -> list[Deployment]:
    stmt = select(Deployment)
    if active_only:
        stmt = stmt.where(Deployment.active.is_(True))
    return list(db.scalars(stmt.order_by(Deployment.created_at)).all())
