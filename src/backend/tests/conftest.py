import os

# Tests never touch the real database file and never run the background simulator.
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["SIMULATOR_ENABLED"] = "false"
os.environ["DEMO_MODE"] = "true"
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-123"

import pytest
from fastapi.testclient import TestClient

from src.backend.app import app
from src.backend.core import auth as core_auth
from src.backend.core.event_bus import bus
from src.backend.core.simulator import simulator
from src.backend.core.state_manager import network
from src.backend.data.seed_data import seed_network


@pytest.fixture(autouse=True)
def fresh_state():
    """Every test starts from the same seeded network and an empty event bus."""
    bus.clear()
    seed_network(fresh=True)
    simulator.reseed(2026)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def auth(user_id: str) -> dict:
    """Authorization header carrying a real signed JWT for ``user_id``."""
    user = network.users.get(user_id)
    token = core_auth.issue_token(user) if user else "not-a-valid-token"
    return {"Authorization": f"Bearer {token}"}


STUDENT = auth("U-S01")
PRIVATE_EV_STUDENT = auth("U-S02")
OPERATOR = auth("U-OP1")
