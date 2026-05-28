import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from backend.data.maps_data import MAPS

for mid, m in MAPS.items():
    print(f"Map: {mid} ({m['name']}) {len(m['rows'])}x{len(m['rows'][0])}")
    for i, row in enumerate(m['rows'][:6]):
        print(f"  {row[:50]}")
    print()