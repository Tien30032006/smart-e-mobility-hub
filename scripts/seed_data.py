"""Print the seeded demo network, or wipe the SQLite file.

    python scripts/seed_data.py              # show the seed data
    python scripts/seed_data.py --reset-db   # delete data/hub.db (next start re-seeds)
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.backend.core.config import settings
from src.backend.data.seed_data import seed_network

if "--reset-db" in sys.argv:
    for suffix in ("", "-wal", "-shm"):
        f = Path(settings.database_path + suffix)
        if f.exists():
            f.unlink()
            print("deleted", f)
else:
    print(json.dumps(seed_network().get_network_status(), indent=2, ensure_ascii=False))
