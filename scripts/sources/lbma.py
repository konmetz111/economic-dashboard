"""LBMA - offizielle Edelmetall-Referenzpreise fuer Gold und Silber.

Die London Bullion Market Association veroeffentlicht ihre taeglichen
Auktionspreise frei als JSON, mit Historie ab 1968. Das ist die
Referenzquelle, an der sich der physische Markt orientiert - besser als jeder
Terminkurs-Anbieter und ohne Schluessel.

Aufbau: [{"d": "2026-08-28", "v": [USD, GBP, EUR]}, ...]
"""

from __future__ import annotations

from common import Reihe, hole, zahl

URLS = {
    "gold": "https://prices.lbma.org.uk/json/gold_pm.json",
    "gold_am": "https://prices.lbma.org.uk/json/gold_am.json",
    "silber": "https://prices.lbma.org.uk/json/silver.json",
}

WAEHRUNGEN = {"USD": 0, "GBP": 1, "EUR": 2}


def abrufen(key: str, args: dict) -> Reihe:
    metall = args["metall"]
    spalte = WAEHRUNGEN[args.get("waehrung", "USD")]

    if metall not in URLS:
        raise RuntimeError(f"Unbekanntes Metall '{metall}' (bekannt: {sorted(URLS)})")

    nutzlast = hole(URLS[metall], timeout=90).json()
    if not isinstance(nutzlast, list):
        raise RuntimeError(f"LBMA lieferte kein Array fuer '{metall}'")

    reihe = Reihe(key=key, quelle=f"LBMA {metall}")
    for eintrag in nutzlast:
        tag = eintrag.get("d")
        werte = eintrag.get("v") or []
        if not tag or spalte >= len(werte):
            continue
        # Auktionsausfaelle stehen als 0 oder null in der Datei; sie waeren als
        # Preis von null grob irrefuehrend.
        wert = zahl(werte[spalte])
        if wert:
            reihe.punkte.append((tag, wert))
    return reihe
