"""Interface en ligne de commande pour Frost Days.

Exemples :
    python -m frost_days.cli --commune Briançon --departement 05 \
        --start 2014-01-01 --end 2023-12-31
    python -m frost_days.cli -c Paris -d 75 -s 2014-01-01 -e 2023-12-31 --csv output
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config
from .frost import compute_frost_report


def _force_utf8() -> None:
    """Évite les UnicodeEncodeError sur les consoles Windows (cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="frost-days",
        description="Calcule le nombre de jours de gel (TN <= 0°C) pour une commune.",
    )
    p.add_argument("-c", "--commune", required=True, help="Nom de la commune")
    p.add_argument("-d", "--departement", required=True, help="Code ou nom du département")
    p.add_argument("-s", "--start", default="2014-01-01", help="Date de début (AAAA-MM-JJ)")
    p.add_argument("-e", "--end", default="2023-12-31", help="Date de fin (AAAA-MM-JJ)")
    p.add_argument(
        "--max-missing", type=float, default=config.MAX_MISSING_FRACTION,
        help="Seuil max de valeurs manquantes pour retenir une station (défaut 0.35)",
    )
    p.add_argument(
        "--method", choices=["haversine", "kdtree"], default="haversine",
        help="Méthode de recherche de la station la plus proche",
    )
    p.add_argument("--top", type=int, default=10, help="Nb de jours les plus gélifs à afficher")
    p.add_argument("--csv", metavar="DIR", help="Dossier où exporter les tables en CSV")
    p.add_argument("-q", "--quiet", action="store_true", help="Masque la progression du téléchargement")
    return p


def main(argv: list[str] | None = None) -> int:
    _force_utf8()
    args = build_parser().parse_args(argv)

    try:
        report = compute_frost_report(
            args.commune, args.departement, args.start, args.end,
            max_missing=args.max_missing, method=args.method, verbose=not args.quiet,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1

    print("\n" + "=" * 64)
    print(report.summary_text())
    print("=" * 64)

    # Jours de gel par année
    print("\nJours de gel par année :")
    for _, row in report.per_year.iterrows():
        print(f"  {int(row['year'])} : {int(row['n_frost']):>3} jours "
              f"({int(row['n_days_observed'])} jours observés)")

    # Jours calendaires les plus gélifs
    doy = report.day_of_year.sort_values(["freq_pct", "n_frost"], ascending=False)
    print(f"\nTop {args.top} des jours calendaires les plus gélifs :")
    for _, row in doy.head(args.top).iterrows():
        print(f"  {row['label']:<16} gel {int(row['n_frost'])}/{int(row['n_years'])} ans "
              f"({row['freq_pct']:.0f}%)")

    if args.csv:
        out = Path(args.csv)
        out.mkdir(parents=True, exist_ok=True)
        tag = f"{report.commune.nom}_{report.commune.dep_code}".replace(" ", "_")
        report.daily.to_csv(out / f"{tag}_quotidien.csv", index=False)
        report.per_year.to_csv(out / f"{tag}_par_annee.csv", index=False)
        report.day_of_year.to_csv(out / f"{tag}_par_jour_calendaire.csv", index=False)
        report.candidates.to_csv(out / f"{tag}_stations.csv", index=False)
        print(f"\nTables exportées dans {out.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
