"""OECD Data Explorer ueber SDMX.

Gebraucht fuer den Composite Leading Indicator. Die FRED-Spiegel dieser Reihen
(USALOLITONOSTSAM, EA19LOLITONOSTSAM) werden nicht mehr fortgeschrieben - sie
liefern klaglos Werte, die im Januar 2024 bzw. November 2022 enden. Der Weg
ueber die OECD selbst ist der einzige, der aktuelle Staende bringt.

Der Reihenschluessel ist positionsabhaengig und wird in der Konfiguration als
`pfad` uebergeben, damit eine neue Reihe keinen Codeeingriff braucht.
"""

from __future__ import annotations

import csv
import io

from common import Reihe, hole, zahl

BASIS = "https://sdmx.oecd.org/public/rest/data"


def _tag(zeitraum: str) -> str | None:
    zeitraum = zeitraum.strip()
    if len(zeitraum) == 10:
        return zeitraum
    if len(zeitraum) == 7 and "-Q" in zeitraum:
        jahr, q = zeitraum.split("-Q")
        return f"{jahr}-{ {1: '03-31', 2: '06-30', 3: '09-30', 4: '12-31'}[int(q)] }"
    if len(zeitraum) == 7:
        return f"{zeitraum}-01"
    if len(zeitraum) == 4:
        return f"{zeitraum}-12-31"
    return None


def abrufen(key: str, args: dict) -> Reihe:
    dataflow = args["dataflow"]
    pfad = args["pfad"]

    antwort = hole(f"{BASIS}/{dataflow}/{pfad}",
                   params={"format": "csvfilewithlabels",
                           "startPeriod": args.get("start", "1990-01")},
                   timeout=120, headers={"Accept": "text/csv"})

    leser = csv.DictReader(io.StringIO(antwort.text))
    felder = leser.fieldnames or []
    if "TIME_PERIOD" not in felder or "OBS_VALUE" not in felder:
        raise RuntimeError(
            f"OECD-Antwort ohne TIME_PERIOD/OBS_VALUE. Spalten: {felder[:12]}")

    reihe = Reihe(key=key, quelle=f"OECD {dataflow} {pfad}")
    for zeile in leser:
        tag = _tag(zeile.get("TIME_PERIOD", ""))
        wert = zahl(zeile.get("OBS_VALUE"))
        if tag and wert is not None:
            reihe.punkte.append((tag, wert))

    if reihe.leer:
        raise RuntimeError(f"OECD lieferte keine Werte fuer {dataflow}/{pfad}")
    return reihe
