"""HTTP API of the operations module.   OWNER: Member 3

Base path: /api/operator   (operators only)
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...core.auth import require_operator
from ...core.entities import Operator
from . import charging_oversight, incident_handler, redistribution, service

router = APIRouter(prefix="/api/operator", tags=["Operations - Member 3"])


class RelocationPlanIn(BaseModel):
    from_hub: str
    to_hub: str
    vehicle_ids: list[str]
    reason: str = ""


class OverrideIn(BaseModel):
    hub_id: str
    session_id: str
    reason: str


@router.get("/dashboard")                                          # UC01
def dashboard(op: Operator = Depends(require_operator)):
    return service.get_dashboard()


@router.get("/hubs/{hub_id}")                                      # UC01 drill-down
def hub_detail(hub_id: str, op: Operator = Depends(require_operator)):
    return service.get_hub_detail(hub_id)


@router.get("/alerts")                                             # UC02
def alerts(status: Optional[str] = None, op: Operator = Depends(require_operator)):
    return service.list_alerts(status)


@router.post("/alerts/{alert_id}/acknowledge")                     # UC02
def ack_alert(alert_id: str, op: Operator = Depends(require_operator)):
    return service.acknowledge_alert(alert_id, op.user_id)


@router.get("/redistribution/proposals")                           # UC03
def proposals(op: Operator = Depends(require_operator)):
    return redistribution.propose_redistribution()


@router.post("/redistribution/orders")                             # UC03 + UC-OP04
def create_order(plan: RelocationPlanIn, op: Operator = Depends(require_operator)):
    return redistribution.create_relocation_order(plan.model_dump(), op.user_id)


@router.get("/redistribution/orders")                              # UC-OP04
def orders(op: Operator = Depends(require_operator)):
    return redistribution.list_orders()


@router.get("/incidents")                                          # UC05
def incidents(status: Optional[str] = None, op: Operator = Depends(require_operator)):
    return incident_handler.list_incidents(status)


@router.post("/incidents/{incident_id}/handle")                    # UC05 (+UC-OP06, UC-OP07)
def handle(incident_id: str, op: Operator = Depends(require_operator)):
    return {"handled": incident_handler.handle_incident(incident_id, op.user_id)}


@router.get("/charging/{hub_id}")                                  # UC-OP08
def charging_view(hub_id: str, op: Operator = Depends(require_operator)):
    return charging_oversight.view_charging_allocation(hub_id)


@router.post("/charging/{hub_id}/run")                             # UC-OP08
def charging_run(hub_id: str, op: Operator = Depends(require_operator)):
    return charging_oversight.run_allocation(hub_id, op.user_id)


@router.post("/charging/override")                                 # UC-OP09
def charging_override(body: OverrideIn, op: Operator = Depends(require_operator)):
    return charging_oversight.override_priority(body.hub_id, body.session_id, op.user_id, body.reason)
