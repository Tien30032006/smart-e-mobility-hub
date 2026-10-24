"""HTTP API of the simulation module.   OWNER: Member 4

Base path: /api/simulation   (operators only)
"""
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel

from ...core.auth import require_operator
from ...core.entities import Operator
from . import engine, recommender, report, scenarios

router = APIRouter(prefix="/api/simulation", tags=["What-if Simulation - Member 4"])

# results are kept in memory here; move to a store in engine.py if you prefer
RESULTS: dict = {}


class ScenarioIn(BaseModel):
    kind: str
    params: dict = {}
    description: str = ""
    template_id: Optional[str] = None


@router.get("/templates")                                   # UC2
def templates(op: Operator = Depends(require_operator)):
    return scenarios.list_templates()


@router.post("/scenarios")                                  # UC1 (+UC2 when template_id given)
def configure(body: ScenarioIn, op: Operator = Depends(require_operator)):
    if body.template_id:
        return scenarios.create_from_template(body.template_id, body.params)
    return scenarios.create_scenario(body.kind, body.params, body.description)


@router.post("/scenarios/{scenario_id}/run")                # UC3 (+UC4, UC5)
def run(scenario_id: str, op: Operator = Depends(require_operator)):
    result = engine.run(scenarios.get_scenario(scenario_id))
    RESULTS[result.result_id] = result
    return result


@router.get("/results/{result_id}")
def get_result(result_id: str, op: Operator = Depends(require_operator)):
    return RESULTS[result_id]


@router.get("/results/{result_id}/recommendations")         # UC6
def recommendations(result_id: str, op: Operator = Depends(require_operator)):
    return recommender.generate(RESULTS[result_id])


@router.get("/results/{result_id}/report")                  # UC7
def export(result_id: str, fmt: str = "xlsx", op: Operator = Depends(require_operator)):
    content, media_type, filename = report.export_report(RESULTS[result_id], fmt)
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
