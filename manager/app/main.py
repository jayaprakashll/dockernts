from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from manager.app.api.routes import router
from manager.app.database.database import init_db
from manager.app.grpc.server import build_server
from manager.app.state.reconciler import reconciler_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
LOG = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    grpc_server = build_server()
    grpc_server.start()
    stop_event = asyncio.Event()
    task = asyncio.create_task(reconciler_loop(stop_event))
    LOG.info("manager gRPC server started")
    try:
        yield
    finally:
        stop_event.set()
        await task
        grpc_server.stop(3).wait()
        LOG.info("manager stopped")


app = FastAPI(title="Simple Docker Cluster Orchestrator Manager", version="1.0.0", lifespan=lifespan)
app.include_router(router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("manager.app.main:app", host="0.0.0.0", port=8000, reload=False)
