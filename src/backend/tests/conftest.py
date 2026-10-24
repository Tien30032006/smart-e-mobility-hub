import pytest
from fastapi.testclient import TestClient

from src.backend.app import app
from src.backend.core.event_bus import bus
from src.backend.data.seed_data import seed_network


@pytest.fixture(autouse=True)
def fresh_state():
    """Every test starts from the same seeded network and an empty event bus."""
    bus.clear()
    seed_network(fresh=True)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def auth(user_id: str) -> dict:
    return {"Authorization": f"Bearer {user_id}"}


STUDENT = auth("U-S01")
PRIVATE_EV_STUDENT = auth("U-S02")
OPERATOR = auth("U-OP1")
