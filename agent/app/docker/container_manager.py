from __future__ import annotations

import json
from typing import Any

from docker.errors import APIError, NotFound


class ContainerManager:
    def __init__(self, docker_client):
        self.client = docker_client

    @staticmethod
    def _normalize_env(env: list[str] | None) -> list[str]:
        return env or []

    @staticmethod
    def _normalize_volumes(volumes: list[str] | None) -> dict[str, dict[str, str]]:
        result: dict[str, dict[str, str]] = {}
        for volume in volumes or []:
            parts = volume.split(":")
            if len(parts) == 2:
                source, target = parts
                result[source] = {"bind": target, "mode": "rw"}
            elif len(parts) == 3:
                source, target, mode = parts
                result[source] = {"bind": target, "mode": mode}
            else:
                raise ValueError(f"Invalid volume '{volume}'. Use source:target[:ro]")
        return result

    @staticmethod
    def _normalize_ports(ports: dict[str, Any] | None) -> dict[str, Any]:
        # Example: {"80/tcp": 8080} or {"80/tcp": "8080:80"}
        result = {}
        for container_port, host_port in (ports or {}).items():
            if isinstance(host_port, str) and ":" in host_port:
                host_ip, host = host_port.rsplit(":", 1)
                result[container_port] = (host_ip, int(host))
            else:
                result[container_port] = int(host_port)
        return result

    def create_containers(
        self,
        image: str,
        replicas: int,
        name_prefix: str,
        env: list[str] | None = None,
        ports: dict[str, Any] | None = None,
        volumes: list[str] | None = None,
        network: str | None = None,
    ) -> list[dict]:
        if replicas < 1:
            raise ValueError("replicas must be >= 1")
        self.client.images.pull(image)
        created = []
        for index in range(1, replicas + 1):
            name = f"{name_prefix}-{index}"
            try:
                container = self.client.containers.get(name)
                if container.status != "running":
                    container.start()
            except NotFound:
                container = self.client.containers.create(
                    image=image,
                    name=name,
                    environment=self._normalize_env(env),
                    ports=self._normalize_ports(ports),
                    volumes=self._normalize_volumes(volumes),
                    network=network,
                    detach=True,
                )
                container.start()
            container.reload()
            created.append(self.serialize(container))
        return created

    def list_containers(self, all_containers: bool = True) -> list[dict]:
        return [self.serialize(c) for c in self.client.containers.list(all=all_containers)]

    def get(self, container_id: str):
        try:
            return self.client.containers.get(container_id)
        except NotFound as exc:
            raise ValueError(f"Container '{container_id}' not found") from exc

    def start(self, container_id: str) -> dict:
        c = self.get(container_id)
        c.start()
        c.reload()
        return self.serialize(c)

    def stop(self, container_id: str) -> dict:
        c = self.get(container_id)
        c.stop()
        c.reload()
        return self.serialize(c)

    def restart(self, container_id: str) -> dict:
        c = self.get(container_id)
        c.restart()
        c.reload()
        return self.serialize(c)

    def remove(self, container_id: str, force: bool = False) -> dict:
        c = self.get(container_id)
        info = self.serialize(c)
        c.remove(force=force)
        return info

    def inspect(self, container_id: str) -> dict:
        c = self.get(container_id)
        return c.attrs

    def logs(self, container_id: str, tail: int = 200) -> str:
        c = self.get(container_id)
        return c.logs(tail=tail).decode("utf-8", errors="replace")

    @staticmethod
    def serialize(container) -> dict:
        image = getattr(container.image, "tags", [None])[0] if container.image else None
        return {
            "id": container.id,
            "short_id": container.short_id,
            "name": container.name,
            "image": image or container.image.id if container.image else "unknown",
            "status": container.status,
            "labels": dict(container.labels or {}),
            "ports": container.ports,
        }
