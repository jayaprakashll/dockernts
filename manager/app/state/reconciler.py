from __future__ import annotations

import asyncio
import json
import logging

from manager.app.core.config import settings
from manager.app.database.database import SessionLocal
from manager.app.database.repository import list_deployments, get_machine, save_container, list_machines
from manager.app.grpc.client import AgentClient

LOG = logging.getLogger(__name__)


def mark_stale_machines() -> None:
    from datetime import datetime, timezone
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        for machine in list_machines(db):
            if machine.last_heartbeat is None:
                continue
            last = machine.last_heartbeat
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if (now - last).total_seconds() > 15:
                machine.status = "offline"
        db.commit()


async def reconcile_once() -> None:
    with SessionLocal() as db:
        deployments = list_deployments(db)
        for deployment in deployments:
            machine = get_machine(db, deployment.machine_id)
            if not machine or machine.status != "healthy":
                continue
            client = AgentClient(f"{machine.ip}:{machine.agent_port}", settings.cluster_token)
            try:
                response = await asyncio.to_thread(client.list_containers, True)
                containers = response.get("containers", [])
                managed = [c for c in containers if c.get("name", "").startswith(deployment.name_prefix + "-")]
                for item in managed:
                    save_container(db, {**item, "machine_id": machine.id}, deployment.id)
                if len(managed) < deployment.replicas:
                    missing = deployment.replicas - len(managed)
                    LOG.warning("self-healing deployment %s: missing %s replica(s)", deployment.id, missing)
                    response = await asyncio.to_thread(
                        client.create_containers,
                        image=deployment.image,
                        replicas=deployment.replicas,
                        name_prefix=deployment.name_prefix,
                        env=json.loads(deployment.env_json),
                        ports=json.loads(deployment.ports_json),
                        volumes=json.loads(deployment.volumes_json),
                        network=deployment.network,
                    )
                    for item in response.get("containers", []):
                        save_container(db, {**item, "machine_id": machine.id}, deployment.id)
            except Exception:
                LOG.exception("reconciliation failed for deployment %s", deployment.id)


async def reconciler_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(mark_stale_machines)
            await reconcile_once()
        except Exception:
            LOG.exception("reconciler error")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.reconcile_interval)
        except asyncio.TimeoutError:
            pass
