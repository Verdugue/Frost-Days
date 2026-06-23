"""Compare les résultats du programme à un export de référence (vérification).

Le professeur fournit des exports partiels (période 2013-2023, plusieurs
communes). Ce script recalcule les jours de gel pour chaque ligne de l'export
et compare au nombre attendu.

L'export attendu est un CSV avec au minimum les colonnes :
    commune, departement, date_debut, date_fin, jours_gel_attendus

Les noms de colonnes peuvent être adaptés via les options.

Exemple :
    python scripts/verify_against_export.py exports/reference.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frost_days.frost import compute_frost_report  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Vérifie le code contre un export de référence.")
    p.add_argument("export", help="Fichier CSV de référence")
    p.add_argument("--col-commune", default="commune")
    p.add_argument("--col-dep", default="departement")
    p.add_argument("--col-start", default="date_debut")
    p.add_argument("--col-end", default="date_fin")
    p.add_argument("--col-expected", default="jours_gel_attendus")
    p.add_argument("--tol", type=int, default=2, help="Écart toléré (en jours)")
    args = p.parse_args(argv)

    ref = pd.read_csv(args.export)
    results = []
    for _, row in ref.iterrows():
        commune = row[args.col_commune]
        dep = str(row[args.col_dep])
        start, end = row[args.col_start], row[args.col_end]
        expected = row.get(args.col_expected)
        try:
            rep = compute_frost_report(commune, dep, start, end, verbose=False)
            got = rep.total_frost_days
            diff = None if pd.isna(expected) else got - int(expected)
            ok = diff is None or abs(diff) <= args.tol
            results.append(
                {"commune": commune, "dep": dep, "attendu": expected,
                 "calcule": got, "ecart": diff, "ok": ok,
                 "station": rep.station_name, "distance_km": round(rep.station_distance_km, 1)}
            )
        except Exception as exc:  # noqa: BLE001
            results.append({"commune": commune, "dep": dep, "erreur": str(exc), "ok": False})

    out = pd.DataFrame(results)
    pd.set_option("display.max_columns", 20, "display.width", 160)
    print(out.to_string(index=False))

    if "ok" in out:
        n_ok = int(out["ok"].sum())
        print(f"\n{n_ok}/{len(out)} lignes dans la tolérance de ±{args.tol} jours.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
