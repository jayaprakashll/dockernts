# dockernts — Streamlit dashboard

A Python/Streamlit control panel for your `dockernts` Manager API. It talks
to the **real** FastAPI endpoints — no mock data — so what you see is
whatever `GET /api/machines` and `GET /api/containers` actually return.

## Run

```bash
pip install -r requirements.txt

# in one terminal: start your manager (adjust to your actual entrypoint)
cd dockernts
python -m manager.app.main          # serves on http://0.0.0.0:8000

# in another terminal: start the dashboard
streamlit run app.py
```

Then open the Streamlit URL it prints (usually `http://localhost:8501`) and
point the sidebar's **Manager API base URL** at your manager, e.g.
`http://127.0.0.1:8000/api`.

## What's wired up

| Tab | Endpoint(s) |
|---|---|
| Overview | `GET /machines`, `GET /containers` — aggregate metrics + charts |
| Machines | `GET /machines`, `DELETE /machines/{ref}` |
| Containers | `GET /containers`, `POST .../start`, `POST .../stop`, `POST .../restart`, `DELETE /containers/{ref}`, `GET .../logs`, `GET .../inspect` |
| Deploy | `POST /deployments` (mirrors the `RunRequest` schema exactly: image, machine, replicas, name_prefix, env, ports, volumes, network) |
| Session deploys | Local-only log of deploys you've made from this UI, since the manager doesn't expose a `GET /deployments` list route yet |

## Notes on honesty vs. the earlier HTML mockup

The manager's `/machines` response includes `cpu_count` and `memory_mb`
(capacity), not live CPU/RAM **usage** — that data lands in the
`heartbeats` table but isn't exposed over HTTP in this codebase yet. So
this dashboard doesn't fake usage bars; it shows what's real (status, last
heartbeat, core count, Docker version) and skips what isn't available.
If you add a `GET /machines/{id}/heartbeats` route later, wiring in live
CPU/mem sparklines here is a small addition — happy to build that once the
endpoint exists.

## Auto-refresh

Toggle **Auto-refresh** in the sidebar to poll on an interval (uses a
`time.sleep` + `st.rerun()` loop, since Streamlit has no built-in ticker).
Or just hit **Refresh now**.