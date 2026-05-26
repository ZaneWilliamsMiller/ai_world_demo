import sys
sys.path.insert(0, r'C:\Users\AAWZV\.qclaw\workspace-ua58rsb93veqtxl7\living-paper')
from backend.data.maps_data import MAPS

for mid, m in MAPS.items():
    print(f"Map: {mid} ({m['name']}) {len(m['rows'])}x{len(m['rows'][0])}")
    for i, row in enumerate(m['rows'][:6]):
        print(f"  {row[:50]}")
    print()