"""HTTP API of the operations module.   OWNER: Member 3

Base path: /api/operator   (operators only)
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

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


class HandleIn(BaseModel):
    note: str = Field(default="", max_length=500)
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    confirm_cancel: bool = False        # UC05 alt 5a: Operator confirmed cancelling the reservation


class StaffIn(BaseModel):
    staff_id: str = "field-staff"
    reason: str = ""


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


@router.post("/alerts/{alert_id}/resolve")                         # UC02 (RESOLVED)
def resolve_alert(alert_id: str, op: Operator = Depends(require_operator)):
    return service.resolve_alert(alert_id, op.user_id)


@router.get("/redistribution/proposals")                           # UC03
def proposals(op: Operator = Depends(require_operator)):
    return redistribution.propose_redistribution()


@router.get("/redistribution/candidates")                          # UC03 step 3
def candidates(from_hub: str, to_hub: str, op: Operator = Depends(require_operator)):
    return redistribution.get_candidates(from_hub, to_hub)


@router.post("/redistribution/orders")                             # UC03 + UC-OP04
def create_order(plan: RelocationPlanIn, op: Operator = Depends(require_operator)):
    return redistribution.create_relocation_order(plan.model_dump(), op.user_id)


@router.get("/redistribution/orders")                              # UC-OP04
def orders(op: Operator = Depends(require_operator)):
    return redistribution.list_orders()


@router.post("/redistribution/orders/{order_id}/assign")           # field staff accepts (mock)
def assign_order(order_id: str, body: StaffIn = StaffIn(), op: Operator = Depends(require_operator)):
    return redistribution.assign_relocation_order(order_id, body.staff_id)


@router.post("/redistribution/orders/{order_id}/reject")           # field staff rejects (mock)
def reject_order(order_id: str, body: StaffIn = StaffIn(), op: Operator = Depends(require_operator)):
    return redistribution.reject_relocation_order(order_id, body.staff_id, body.reason)


@router.post("/redistribution/orders/{order_id}/complete")         # vehicles arrive
def complete_order(order_id: str, op: Operator = Depends(require_operator)):
    return redistribution.complete_relocation_order(order_id)


@router.post("/redistribution/orders/{order_id}/cancel")
def cancel_order(order_id: str, op: Operator = Depends(require_operator)):
    return redistribution.cancel_relocation_order(order_id, op.user_id)


@router.get("/incidents")                                          # UC05
def incidents(status: Optional[str] = None, op: Operator = Depends(require_operator)):
    return incident_handler.list_incidents(status)


@router.get("/incidents/{incident_id}/impact")                     # UC05 alt 5a (warning before confirming)
def incident_impact(incident_id: str, op: Operator = Depends(require_operator)):
    return incident_handler.get_incident_impact(incident_id)


@router.post("/incidents/{incident_id}/handle")                    # UC05 (+UC-OP06, UC-OP07)
def handle(incident_id: str, body: HandleIn = HandleIn(), op: Operator = Depends(require_operator)):
    return incident_handler.handle_incident_detailed(incident_id, op.user_id, body.note, body.priority,
                                                     body.confirm_cancel)


@router.post("/incidents/{incident_id}/resolve")                   # repair finished
def resolve_incident(incident_id: str, op: Operator = Depends(require_operator)):
    return incident_handler.resolve_incident(incident_id, op.user_id)


@router.get("/tickets")                                            # UC-OP06
def tickets(op: Operator = Depends(require_operator)):
    return incident_handler.list_tickets()


@router.get("/charging/audit")                                     # UC-OP09 audit trail
def charging_audit(hub_id: Optional[str] = None, op: Operator = Depends(require_operator)):
    return charging_oversight.list_override_audit(hub_id)


@router.get("/charging/{hub_id}")                                  # UC-OP08
def charging_view(hub_id: str, op: Operator = Depends(require_operator)):
    return charging_oversight.view_charging_allocation(hub_id)


@router.post("/charging/{hub_id}/run")                             # UC-OP08
def charging_run(hub_id: str, op: Operator = Depends(require_operator)):
    return charging_oversight.run_allocation(hub_id, op.user_id)


@router.post("/charging/override")                                 # UC-OP09
def charging_override(body: OverrideIn, op: Operator = Depends(require_operator)):
    return charging_oversight.override_priority(body.hub_id, body.session_id, op.user_id, body.reason)
