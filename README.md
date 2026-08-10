# Simple Docker Cluster Orchestrator — Python MVP

This implementation follows the uploaded project specification, but uses Python instead of Go:

- Manager: FastAPI + gRPC + SQLite + SQLAlchemy
- Agent: Python gRPC server + Docker SDK + psutil
- CLI: Typer
- No SSH is used for orchestration.
- Only the Manager stores SQLite state.
- Agents automatically discover their own LAN IP during registration.
- The user supplies the Manager address only once when an Agent joins.

The original project asks for a centralized manager, agents on Docker hosts, registration, lifecycle control, heartbeats, persistent state, desired/actual state and basic self-healing.

## Architecture

```text
                         MANAGER PC
              +-----------------------------+
              | FastAPI :8000              |
              | gRPC    :9000              |
              | SQLite  orchestrator.db    |
              +-------------+---------------+
                            |
                         gRPC/network
             +--------------+--------------+
             |              |              |
             v              v              v
          Agent-1        Agent-2        Agent-N
           :9001          :9001          :9001
             |              |              |
          Docker         Docker         Docker
```

## Important networking rule

The Agent needs to know the Manager's address once. The Agent does **not** need its own IP passed on the command line. It discovers its local IP by opening a UDP socket toward the Manager and sends that IP in the registration request.

The Manager then stores:

```text
machine_id -> name -> IP -> agent_port
```

For this MVP, Manager and Agents should be on a network where the Manager can reach each Agent's TCP `9001` port and each Agent can reach the Manager's TCP `9000` port.

## Installation

### Manager PC

Install Docker only if you also want to run containers locally. The Manager itself does not need Docker.

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .venv\\Scripts\\Activate.ps1

pip install -r requirements.txt
pip install -e .
```

Set the cluster token. Use the same token on every Agent.

Linux/macOS:

```bash
export CLUSTER_TOKEN='change-me-strong-token'
```

PowerShell:

```powershell
$env:CLUSTER_TOKEN='change-me-strong-token'
```

Start Manager:

```bash
uvicorn manager.app.main:app --host 0.0.0.0 --port 8000
```

Manager ports:

- HTTP API: `8000`
- gRPC: `9000`
- SQLite: `./orchestrator.db`

### Agent PC

Install Docker Engine/Desktop and make sure the current user can access Docker.

Then:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Join once:

```bash
orchestrator-agent join \
  --manager 192.168.1.10:9000 \
  --name machine-2 \
  --token change-me-strong-token
```

Start:

```bash
orchestrator-agent start
```

The Agent will:

1. discover its own hostname/IP/CPU/RAM;
2. register with the Manager;
3. start listening on port `9001`;
4. send a heartbeat every 5 seconds;
5. receive Docker commands over gRPC.

## CLI

Set the Manager HTTP endpoint on the client machine if it is not local:

Linux/macOS:

```bash
export ORCHESTRATOR_MANAGER='http://192.168.1.10:8000'
```

PowerShell:

```powershell
$env:ORCHESTRATOR_MANAGER='http://192.168.1.10:8000'
```

List machines:

```bash
orchestrator machines
```

Deploy:

```bash
orchestrator run --machine machine-2 --replicas 4 --image nginx:latest
```

List containers:

```bash
orchestrator ps
orchestrator ps --machine machine-2
```

Lifecycle:

```bash
orchestrator start web-xxxxxx-1
orchestrator stop web-xxxxxx-1
orchestrator restart web-xxxxxx-1
orchestrator rm web-xxxxxx-1
```

Inspect/logs:

```bash
orchestrator inspect web-xxxxxx-1
orchestrator logs web-xxxxxx-1
```

Networking, volume and env:

```bash
orchestrator run \
  --machine machine-2 \
  --replicas 1 \
  --image nginx:latest \
  --publish 8080:80 \
  --volume mydata:/data \
  --env APP_ENV=dev
```

For multiple replicas on one machine, do not publish the same host port to every replica; Docker will reject the port collision.

## Project tree

```text
docker-cluster-orchestrator/
├── manager/
│   └── app/
│       ├── api/routes.py
│       ├── core/config.py
│       ├── database/{database.py,models.py,repository.py}
│       ├── grpc/{server.py,client.py}
│       ├── services/{machine_service.py,container_service.py}
│       ├── state/reconciler.py
│       └── main.py
├── agent/
│   ├── cli.py
│   └── app/
│       ├── core/config.py
│       ├── docker/{docker_client.py,container_manager.py}
│       ├── grpc/server.py
│       ├── heartbeat/heartbeat.py
│       ├── system/system_info.py
│       └── main.py
├── cli/orchestrator/main.py
├── common/rpc.py
├── proto/orchestrator.proto
├── requirements.txt
└── pyproject.toml
```

## Security note

The MVP uses a shared cluster token and insecure gRPC transport to keep the project easy to understand. Do not expose these ports directly to the public Internet. A production version should add TLS/mTLS, which is also listed as a future feature in the original specification.

## Troubleshooting

### Manager cannot connect to an Agent

Check:

```bash
ping <agent-ip>
```

and that TCP 9001 is allowed through the Agent machine's firewall.

### Agent cannot register

Check TCP 9000 from Agent to Manager and confirm the token is identical.

### Docker error on Agent

Run on the Agent PC:

```bash
docker ps
```

If that fails, fix Docker permissions/service status before starting the Agent.

### Windows Docker Desktop

The Python Docker SDK normally uses the local Docker Desktop named pipe when running on Windows. Keep Docker Desktop running.
