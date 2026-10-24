"""JSON config loading helpers. SHARED FILE."""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = PROJECT_ROOT / "configs"


def load_json(name: str):
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return json.load(f)
