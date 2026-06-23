"""Pré-télécharge et met en cache les données d'un ou plusieurs départements.

Utile pour préparer une démo (le premier appel d'un département télécharge le
fichier Météo-France, ce qui peut prendre ~1 min).

Exemples :
    python scripts/prefetch.py 05 06 67
    python scripts/prefetch.py --all        # tous les départements métropolitains
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frost_days import meteo  # noqa: E402

METRO = [f"{i:02d}" for i in range(1, 96) if i != 20] + ["2A", "2B"]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Pré-cache des départements Météo-France.")
    p.add_argument("departements", nargs="*", help="Codes département (ex. 05 06 2A)")
    p.add_argument("--all", action="store_true", help="Tous les départements métropolitains")
    args = p.parse_args(argv)

    deps = METRO if args.all else args.departements
    if not deps:
        p.error("Indiquez au moins un département, ou utilisez --all.")

    for dep in deps:
        t0 = time.time()
        try:
            path = meteo.build_department_cache(dep)
            print(f"[OK] {dep} -> {path.name} ({time.time() - t0:.0f}s)")
        except Exception as exc:  # noqa: BLE001
            print(f"[ERREUR] {dep} : {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
