"""Tests de normalisation de noms (sans accès réseau)."""

from frost_days.communes import normalize


def test_normalize_accents_and_case():
    assert normalize("Briançon") == "briancon"
    assert normalize("ÉVREUX") == "evreux"


def test_normalize_hyphens_and_apostrophes():
    assert normalize("Saint-Lucien") == "saint lucien"
    assert normalize("L'Oie") == "l oie"


def test_normalize_collapses_spaces():
    assert normalize("  Les   Hauts-Talican ") == "les hauts talican"


def test_normalize_none():
    assert normalize(None) == ""
