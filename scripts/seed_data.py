"""Print the seeded demo network (sanity check): python scripts/seed_data.py"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.backend.data.seed_data import seed_network

print(json.dumps(seed_network().get_network_status(), indent=2, ensure_ascii=False))
