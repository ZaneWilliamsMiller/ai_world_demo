import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.maps_data import MAPS


def main():
    m = MAPS["world"]
    print("name:", m["name"])
    print("rows:", len(m["rows"]), "cols:", len(m["rows"][0]) if m["rows"] else 0)
    for y in range(12, 18):
        print(f"{y:2d}: {m['rows'][y]}")
    print()
    for y in range(2, 11):
        row = m["rows"][y]
        if "=" in row or "~" in row:
            print(f"{y:2d}: {row}")
    for y in range(len(m["rows"])):
        row = m["rows"][y]
        if "!" in row or "@" in row:
            print(f"{y:2d}: {row}")


if __name__ == "__main__":
    main()
