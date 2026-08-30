"""EZB Data Portal ueber die SDMX-2.1-Schnittstelle.

Kein Schluessel noetig. Der Reihenschluessel ist punktgetrennt und
positionsabhaengig; er laesst sich auf data.ecb.europa.eu an jeder Reihe
ablesen. Angefordert wird das CSV-Format, weil die SDMX-JSON-Struktur fuer
diesen Zweck unnoetig verschachtelt ist.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from common import Reihe, hole, zahl

BASIS = "https://data-api.ecb.europa.eu/service/data"


def _tag(zeitraum: str) -> str | None:
    """SDMX-Perioden auf ein ISO-Datum normalisieren.

    Die EZB mischt vier Frequenzen im selben Format: '2026-07-15' (taeglich),
    '2026-W34' (woechentlich, ISO-Kalenderwoche), '2026-07' (monatlich) und
    '2026-Q2' (quartalsweise). Quartale und Wochen werden auf das Ende des
    Zeitraums gelegt, weil die Zahl den abgelaufenen Zeitraum beschreibt.
    """
    zeitraum = zeitraum.strip()
    if len(zeitraum) == 10 and zeitraum[4] == "-" and zeitraum[7] == "-":
        return zeitraum
    if "-W" in zeitraum:
        jahr, woche = zeitraum.split("-W")
        try:
            return date.fromisocalendar(int(jahr), int(woche), 7).isoformat()
        except ValueError:
            return None
    if "-Q" in zeitraum:
        jahr, quartal = zeitraum.split("-Q")
        return f"{jahr}-{quartal_ende(int(quartal))}"
    if len(zeitraum) == 7:
        return f"{zeitraum}-01"
    if len(zeitraum) == 4:
        return f"{zeitraum}-12-31"
    return None


def quartal_ende(quartal: int) -> str:
    return {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}[quartal]


def abrufen(key: str, args: dict) -> Reihe:
    flow, schluessel = args["flow"], args["key"]
    url = f"{BASIS}/{flow}/{schluessel}"

    # Ohne 'detail'-Parameter. Mit detail=dataonly liefert die Schnittstelle je
    # nach Datenfluss andere Spaltennamen oder antwortet mit HTTP 400 - das hat
    # hier vier Reihen stillgelegt, bis der Test es aufgedeckt hat.
    antwort = hole(url, params={"format": "csvdata"},
                   headers={"Accept": "text/csv"})
    leser = csv.DictReader(io.StringIO(antwort.text))

    reihe = Reihe(key=key, quelle=f"EZB {flow}/{schluessel}")
    for zeile in leser:
        tag = _tag(zeile.get("TIME_PERIOD", ""))
        wert = zahl(zeile.get("OBS_VALUE"))
        if tag and wert is not None:
            reihe.punkte.append((tag, wert * float(args.get("faktor", 1.0))))

    if reihe.leer:
        raise RuntimeError(
            f"EZB lieferte keine Werte fuer {flow}/{schluessel}. "
            f"Reihenschluessel auf data.ecb.europa.eu pruefen."
        )
    return reihe
