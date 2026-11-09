"""Application entry point. SHARED FILE.

Run from the project root:
    uvicorn src.backend.app:app --reload --port 8000
Swagger UI: http://localhost:8000/docs      Frontend: http://localhost:8000/app/

Unfinished endpoints answer HTTP 501 with the owner + use case (see core/todo.py).

Startup (lifespan): connect SQLite -> restore the last saved state (or seed the demo data)
-> wire the event bus to SSE -> start the simulator and the periodic database flush.
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .core.api_shared import router as shared_router
from .core.config import settings
from .core.database import persistence
from .core.demo import register_persisted_stores
from .core.event_bus import bus
from .core.logger import get_logger
from .core.simulator import simulator
from .core.state_manager import HubNotFound, VehicleNotFound, network
from .core.stream import stream_hub
from .core.todo import NotImplementedYet
from .data.seed_data import seed_network
from .modules.charging.routes import router as charging_router
from .modules.operations.routes import router as operations_router
from .modules.reservation.routes import router as reservation_router
from .modules.simulation.routes import router as simulation_router

SRC_DIR = Path(__file__).resolve().parents[1]
log = get_logger("app")
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
PAYMENT_PATHS = ("/api/wallet", "/api/payments")
DOMAIN_PATHS = ("/api/reservation", "/api/charging", "/api/operator", "/api/operations", "/api/simulation")


def restore_or_seed() -> str:
    """Load the saved state from SQLite, or seed the demo data and save it. Returns 'restored'|'seeded'."""
    register_persisted_stores()
    if settings.persistence_enabled:
        persistence.connect(settings.database_path)
        if persistence.load():
            from .data.seed_data import sync_seed_catalog
            sync_seed_catalog()
            if settings.demo_mode:
                from .modules.operations.incident_handler import seed_demo_incidents
                seed_demo_incidents()
            persistence.flush()
            return "restored"
    seed_network()
    if settings.demo_mode:
        from .modules.operations.incident_handler import seed_demo_incidents
        seed_demo_incidents()
    persistence.flush()
    return "seeded"


def _wire_modules() -> None:
    """Hook module-owned handlers into the bus (each is optional until its owner finishes it)."""
    stream_hub.attach()
    try:
        from .modules.charging import telemetry
        telemetry.register_simulator_handlers()
    except Exception:  # noqa: BLE001
        log.exception("charging telemetry handlers not registered")
    try:
        from .modules.operations import service as ops_service
        ops_service.register_event_handlers()
    except NotImplementedYet:
        log.warning("operations event handlers are not ready")
    except Exception:  # noqa: BLE001
        log.exception("operations handlers not registered")


async def _flush_loop() -> None:
    while True:
        await asyncio.sleep(max(1.0, settings.persist_interval_seconds))
        try:
            await run_in_threadpool(persistence.flush)
        except Exception:  # noqa: BLE001
            log.exception("periodic database flush failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    stream_hub.bind_loop(asyncio.get_running_loop())
    mode = restore_or_seed()
    log.info("state %s (database=%s)", mode, settings.database_path if settings.persistence_enabled else "off")
    _wire_modules()
    flusher = asyncio.create_task(_flush_loop()) if persistence.enabled else None
    simulator.start()
    yield
    await simulator.stop()
    if flusher:
        flusher.cancel()
    if persistence.enabled:
        await run_in_threadpool(persistence.flush)
        persistence.close()


def create_app() -> FastAPI:
    seed_network()
    app = FastAPI(title="Smart E-Mobility Hub", version="0.2.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(NotImplementedYet)
    async def _todo_handler(_, exc: NotImplementedYet):
        return JSONResponse(status_code=501, content={
            "detail": "Not implemented yet", "owner": exc.owner,
            "use_case": exc.use_case, "hint": exc.hint})

    @app.exception_handler(HubNotFound)
    async def _hub_404(_, exc):
        return JSONResponse(status_code=404, content={"detail": f"Hub {exc} not found"})

    @app.exception_handler(VehicleNotFound)
    async def _vehicle_404(_, exc):
        return JSONResponse(status_code=404, content={"detail": f"Vehicle {exc} not found"})

    # ---- shared endpoints ---------------------------------------------------
    @app.get("/api/health", tags=["Shared"])
    def health():
        return {"status": "ok", "hubs": len(network.hubs), "vehicles": len(network.vehicles),
                "database": persistence.enabled, "demo_mode": settings.demo_mode,
                "simulator": simulator.enabled, "stream_clients": stream_hub.subscriber_count}

    @app.get("/api/hubs", tags=["Shared"])
    def hubs():
        return [network.get_hub_status(h) for h in network.hubs]

    @app.get("/api/hubs/{hub_id}", tags=["Shared"])
    def hub(hub_id: str):
        return network.get_hub_status(hub_id)

    @app.get("/api/network/status", tags=["Shared"])
    def network_status():
        return network.get_network_status()

    app.include_router(shared_router)
    app.include_router(reservation_router)
    app.include_router(charging_router)
    app.include_router(operations_router)
    app.include_router(simulation_router)

    @app.middleware("http")
    async def persist_and_notify(request: Request, call_next):
        """After every successful write: save to SQLite and tell SSE clients to refresh."""
        response = await call_next(request)
        path = request.url.path
        if request.method in MUTATING and response.status_code < 400 and path.startswith("/api/"):
            if persistence.enabled:
                try:
                    await run_in_threadpool(persistence.flush)
                except Exception:  # noqa: BLE001 - never fail a request because of the audit copy
                    log.exception("database flush failed")
            if path.startswith(PAYMENT_PATHS):
                stream_hub.publish("payment_updated", {"path": path})
            elif path.startswith(DOMAIN_PATHS):
                stream_hub.publish("hub_updated", {"hub_id": None, "reason": "http"})
        return response

    @app.middleware("http")
    async def no_cache_for_frontend(request: Request, call_next):
        """Dev convenience: browsers (incl. VS Code's built-in one) must never reuse stale HTML/CSS/JS."""
        response = await call_next(request)
        if request.url.path.startswith(("/app", "/shared")):
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @app.get("/", include_in_schema=False)
    async def frontend_home():
        return RedirectResponse(url="/app/", status_code=307)

    app.mount("/shared", StaticFiles(directory=SRC_DIR / "shared"), name="shared")
    app.mount("/app", StaticFiles(directory=SRC_DIR / "frontend", html=True), name="frontend")
    return app


app = create_app()
