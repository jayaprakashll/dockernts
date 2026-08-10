# Start Here

This is the complete Python MVP requested from the project specification.

## The simplest real setup

Use 2+ PCs on the same LAN:

- PC-1: Manager + SQLite
- PC-2: Docker + Agent
- PC-3+: Docker + Agent (optional)

### PC-1 Manager

```bash
cd docker-cluster-orchestrator
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
export CLUSTER_TOKEN='my-secret-token'
uvicorn manager.app.main:app --host 0.0.0.0 --port 8000
```

Find PC-1's LAN IP, for example `192.168.1.10`.

### PC-2 Agent

Install Docker first and verify `docker ps` works.

```bash
cd docker-cluster-orchestrator
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
orchestrator-agent join --manager 192.168.1.10:9000 --name machine-2 --token my-secret-token
orchestrator-agent start
```

The Agent discovers its own IP. Do not pass `--ip`.

### PC-1 CLI

In another terminal:

```bash
export ORCHESTRATOR_MANAGER='http://127.0.0.1:8000'
orchestrator machines
orchestrator run --machine machine-2 --replicas 4 --image nginx:latest
orchestrator ps --machine machine-2
```

You should see the four containers on PC-2.

## Windows

Use PowerShell equivalents:

```powershell
$env:CLUSTER_TOKEN='my-secret-token'
$env:ORCHESTRATOR_MANAGER='http://192.168.1.10:8000'
```

The rest of the commands are the same.

## Firewall

Allow TCP:

- Manager PC: `9000` from Agent PCs
- Manager HTTP API: `8000` from the CLI PC if remote CLI is used
- Agent PCs: `9001` from the Manager PC

## Important

This MVP uses a shared token and insecure gRPC. Keep it on a trusted LAN/VPN. Do not expose ports 8000/9000/9001 directly to the public Internet.
