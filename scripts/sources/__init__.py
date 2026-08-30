"""Registrierung der Abrufmodule.

Jedes Modul stellt eine Funktion `abrufen(key, args) -> Reihe` bereit. Wirft sie
eine Ausnahme, faengt `hole_reihe` sie ab und macht daraus eine Fehlerreihe -
so kann ein einzelner Quellenausfall den Gesamtlauf nicht abbrechen.
"""

from __future__ import annotations

import importlib
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import Reihe, fehlerreihe  # noqa: E402

MODULE = {
    "fred": "sources.fred",
    "ecb": "sources.ecb",
    "yahoo": "sources.yahoo",
    "lbma": "sources.lbma",
    "oecd": "sources.oecd",
    "shiller": "sources.shiller",
    "finra": "sources.finra",
    "sec_edgar": "sources.sec_edgar",
    "stoxx": "sources.stoxx",
}


_GEHEIM = re.compile(r"(?i)((?:api[_-]?key|token|secret|password)=)[^&\s\"']+")


def _entschaerfen(text: str) -> str:
    """Zugangsdaten aus Fehlermeldungen entfernen - letzte Instanz.

    Fehlertexte wandern in data/meta.json und damit auf die oeffentliche
    Website sowie ins Actions-Protokoll. Eine Bibliothek, die eine URL samt
    Abfrageparametern in ihre Ausnahme schreibt, wuerde einen Schluessel dort
    veroeffentlichen. Die Quellmodule saeubern ihre Meldungen bereits selbst;
    das hier greift auch fuer Module, die es kuenftig vergessen.
    """
    return _GEHEIM.sub(r"\1<entfernt>", text)


def hole_reihe(key: str, adapter: str, args: dict) -> Reihe:
    if adapter not in MODULE:
        return fehlerreihe(key, f"Unbekannter Adapter '{adapter}'")
    try:
        modul = importlib.import_module(MODULE[adapter])
        reihe = modul.abrufen(key, args or {})
    except Exception as fehler:                      # noqa: BLE001
        return fehlerreihe(key, _entschaerfen(f"{type(fehler).__name__}: {fehler}"))
    if reihe.leer and reihe.status == "ok":
        return fehlerreihe(key, "Quelle lieferte keine Datenpunkte")

    # Perioden werden auf ihr Ende datiert: Ein Quartalswert fuer Q3 2026 traegt
    # den 30.09.2026, ein Monatswert fuer August den 31.08. Solange die Periode
    # laeuft, liegt dieses Datum in der Zukunft. Auf der Zeitachse sieht das aus,
    # als reichten die Daten weiter, als sie es tun; deshalb auf heute begrenzen.
    heute = date.today().isoformat()
    reihe.punkte = [(t, w) if t <= heute else (heute, w) for t, w in reihe.punkte]
    return reihe.sortiert()
