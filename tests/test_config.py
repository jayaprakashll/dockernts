from pathlib import Path

from agent.app.core.config import AgentConfig


def test_agent_config_roundtrip(tmp_path: Path):
    path = tmp_path / "agent.yaml"
    cfg = AgentConfig.new("machine-1", "127.0.0.1:9000", "token")
    cfg.save(path)
    loaded = AgentConfig.load(path)
    assert loaded.machine_id == cfg.machine_id
    assert loaded.name == "machine-1"
    assert loaded.manager_address == "127.0.0.1:9000"
