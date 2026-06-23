"""Téléchargement résilient avec cache sur disque.

Les fichiers open data sont volumineux : on ne les télécharge qu'une seule fois
et on les conserve dans ``data/``. Tout passe par :func:`ensure_file`.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

CHUNK = 1 << 16  # 64 Ko
MAX_RETRIES = 3  # tentatives en cas de coupure réseau / timeout


def _human(n: float) -> str:
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024 or unit == "Go":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} Go"


def download(url: str, dest: Path, *, label: str | None = None, verbose: bool = True) -> Path:
    """Télécharge ``url`` vers ``dest`` (atomique via fichier temporaire).

    Réessaie automatiquement en cas de coupure réseau ou de timeout, et nettoie
    le fichier partiel entre deux tentatives.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    label = label or dest.name

    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length", 0))
                done = 0
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(CHUNK):
                        fh.write(chunk)
                        done += len(chunk)
                        if verbose and total:
                            pct = 100 * done / total
                            sys.stderr.write(
                                f"\r  ↓ {label} : {_human(done)} / {_human(total)} ({pct:4.1f}%)"
                            )
                            sys.stderr.flush()
            if verbose:
                sys.stderr.write(f"\r  ✓ {label} téléchargé ({_human(done)})\n")
                sys.stderr.flush()
            tmp.replace(dest)
            return dest
        except (requests.RequestException, OSError) as exc:
            last_exc = exc
            tmp.unlink(missing_ok=True)  # repart d'un fichier propre
            if verbose:
                sys.stderr.write(
                    f"\r  ⚠ {label} : échec (tentative {attempt}/{MAX_RETRIES}) — {exc}\n"
                )
                sys.stderr.flush()
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)  # back-off progressif

    raise RuntimeError(
        f"Échec du téléchargement de {url} après {MAX_RETRIES} tentatives."
    ) from last_exc


def ensure_file(url: str, dest: Path, *, label: str | None = None, verbose: bool = True) -> Path:
    """Renvoie ``dest`` en le téléchargeant seulement s'il est absent ou vide."""
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    return download(url, dest, label=label, verbose=verbose)
