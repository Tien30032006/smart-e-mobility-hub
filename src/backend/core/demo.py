"""Demo helpers: wiring of persisted stores and the one-call reset. SHARED FILE (owner: TV5)."""
from __future__ import annotations

from .database import persistence
from .event_bus import bus
from .logger import get_logger
from .simulator import simulator
from .state_manager import network
from .stream import stream_hub

log = get_logger("demo")


def register_persisted_stores() -> None:
    """Tell the database which module-owned dicts must survive a restart."""
    from ..modules.reservation import payment_gateway, service, smart_lock
    from ..modules.operations import state as operations_state
    persistence.register_store("wallet.wallets", lambda: payment_gateway._wallets)
    persistence.register_store("wallet.orders", lambda: payment_gateway._orders)
    persistence.register_store("wallet.ledger", lambda: payment_gateway._ledger)
    persistence.register_store("reservation.trips", lambda: service._trips)
    persistence.register_store("reservation.issues", lambda: service._issues)
    persistence.register_store("reservation.locks", lambda: smart_lock._lock_states)
    for name in ("alerts", "incidents", "tickets", "relocation_orders", "charging_overrides"):
        persistence.register_store(f"operations.{name}", lambda name=name: getattr(operations_state, name))
    persistence.attach_bus(bus)


def reset_module_state() -> None:
    """Clear every module-owned store (each module exposes its own reset helper)."""
    from ..modules.reservation import payment_gateway, service, smart_lock
    payment_gateway.reset_ledger()
    from ..modules.operations import state as operations_state
    operations_state.reset()
    service.reset_module_state()
    smart_lock.reset_locks()
    try:
        from ..modules.charging.repository import repository
        repository._store = None
    except Exception:  # noqa: BLE001
        log.exception("charging store reset failed")


def reset_demo(seed: int | None = None) -> dict:
    """Back to the initial demo data: seed JSON -> memory -> database (operator only)."""
    from ..data.seed_data import seed_network
    with network.lock:
        reset_module_state()
        seed_network(fresh=True)
        try:
            from ..modules.operations.incident_handler import seed_demo_incidents
            from .config import settings
            if settings.demo_mode:
                seed_demo_incidents()
        except Exception:  # noqa: BLE001
            log.exception("demo incident seed failed")
        bus.history.clear()
        simulator.reseed(seed)
    if persistence.enabled:
        persistence.wipe()
        persistence.flush()
    stream_hub.publish("hub_updated", {"hub_id": None, "reason": "demo_reset"})
    log.info("demo data reset")
    return {"reset": True, "hubs": len(network.hubs), "vehicles": len(network.vehicles),
            "users": len(network.users), "seed": simulator.seed}
