from __future__ import annotations

import json
import uuid

from manager.app.database.models import ContainerRecord, Deployment
from manager.app.database.repository import get_machine, save_container
from manager.app.grpc.client import AgentClient
from manager.app.services.machine_service import resolve_machine


def agent_for(machine, token: str) -> AgentClient:
    return AgentClient(f"{machine.ip}:{machine.agent_port}", token)


def container_to_dict(row: ContainerRecord) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "machine_id": row.machine_id,
        "image": row.image,
        "status": row.status,
        "deployment_id": row.deployment_id,
    }


def deploy(db, token: str, machine_ref: str, image: str, replicas: int, name_prefix: str | None = None, env=None, ports=None, volumes=None, network=None):
    machine = resolve_machine(db, machine_ref)
    if machine.status not in {"healthy", "unknown"}:
        raise ValueError(f"Machine '{machine.name}' is not healthy")
    deployment_id = str(uuid.uuid4())
    prefix = name_prefix or image.split("/")[-1].split(":")[0].replace(".", "-")
    prefix = f"{prefix}-{deployment_id[:6]}"
    client = agent_for(machine, token)
    response = client.create_containers(image=image, replicas=replicas, name_prefix=prefix, env=env or [], ports=ports or {}, volumes=volumes or [], network=network)
    dep = Deployment(
        id=deployment_id,
        machine_id=machine.id,
        image=image,
        replicas=replicas,
        name_prefix=prefix,
        env_json=json.dumps(env or []),
        ports_json=json.dumps(ports or {}),
        volumes_json=json.dumps(volumes or []),
        network=network,
    )
    db.add(dep)
    for item in response.get("containers", []):
        save_container(db, {**item, "machine_id": machine.id}, deployment_id)
    return {"deployment_id": deployment_id, "machine": machine.name, "desired_replicas": replicas, "containers": response.get("containers", [])}
