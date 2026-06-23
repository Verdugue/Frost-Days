"""Frost Days — calcul des jours de gel par commune (données Météo-France)."""

from __future__ import annotations

from .frost import FrostReport, compute_frost_report

__all__ = ["FrostReport", "compute_frost_report", "__version__"]
__version__ = "0.1.0"
