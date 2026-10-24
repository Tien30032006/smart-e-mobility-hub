"""Application entry point. SHARED FILE.

Run from the project root:
    uvicorn src.backend.app:app --reload --port 8000
Swagger UI: http://localhost:8000/docs      Frontend: http://localhost:8000/app/

Unfinished endpoints answer HTTP 501 with the owner + use case (see core/todo.py).
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .core import auth
from .core.state_manager import HubNotFound, VehicleNotFound, network
from .core.todo import NotImplementedYet
from .data.seed_data import seed_network
from .modules.charging.routes import router as charging_router
from .modules.operations.routes import router as operations_router
from .modules.reservation.routes import router as reservation_router
from .modules.simulation.routes import router as simulation_router

SRC_DIR = Path(__file__).resolve().parents[1]


class LoginIn(BaseModel):
    email: str


def create_app() -> FastAPI:
    seed_network()
    app = FastAPI(title="Smart E-Mobility Hub", version="0.1.0")
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
        return {"status": "ok", "hubs": len(network.hubs), "vehicles": len(network.vehicles)}

    @app.post("/api/auth/login", tags=["Shared"])
    def login(body: LoginIn):
        user = auth.login(body.email)
        if user is None:
            raise HTTPException(status_code=401, detail="Unknown e-mail")
        return {"token": user.user_id, "user_id": user.user_id, "full_name": user.full_name,
                "role": user.user_role.value}

    @app.get("/api/hubs", tags=["Shared"])
    def hubs():
        return [network.get_hub_status(h) for h in network.hubs]

    @app.get("/api/hubs/{hub_id}", tags=["Shared"])
    def hub(hub_id: str):
        return network.get_hub_status(hub_id)

    @app.get("/api/network/status", tags=["Shared"])
    def network_status():
        return network.get_network_status()

    app.include_router(reservation_router)
    app.include_router(charging_router)
    app.include_router(operations_router)
    app.include_router(simulation_router)

    app.mount("/shared", StaticFiles(directory=SRC_DIR / "shared"), name="shared")
    app.mount("/app", StaticFiles(directory=SRC_DIR / "frontend", html=True), name="frontend")
    return app


app = create_app()
