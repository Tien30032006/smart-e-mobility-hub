"""UC7 Export Simulation Report.   OWNER: Member 4

CSV/Excel (openpyxl) or PDF (reportlab) are both fine; pick ONE first, add the other if time allows.
Add the library to requirements.txt when you choose it.
"""
from __future__ import annotations

from ...core.todo import todo
from .models import SimulationResult

OWNER = "Member 4"


def export_report(result: SimulationResult, fmt: str = "xlsx") -> tuple[bytes, str, str]:
    """Return (content_bytes, media_type, filename): scenario, impact table, recommendations."""
    todo(OWNER, "UC7", "build report file from result")
