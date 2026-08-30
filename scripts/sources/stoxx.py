"""STOXX - VSTOXX und seine Laufzeit-Subindizes.

Offizielle, frei zugaengliche Textdatei mit Historie ab 1999. Aufbau:
drei Kopfzeilen, danach kommagetrennte Werte mit deutschem Datumsformat.
"""

from __future__ import annotations

import csv
import io

from common import Reihe, hole, zahl

URL = "https://www.stoxx.com/document/Indices/Current/HistoricalData/h_vstoxx.txt"


def abrufen(key: str, args: dict) -> Reihe:
    spalte = args.get("spalte", "V2TX")
    zeilen = hole(URL, timeout=120).text.splitlines()

    # Kopfzeile ist die erste Zeile, die mit "Date" beginnt.
    start = next((i for i, z in enumerate(zeilen[:10])
                  if z.strip().lower().startswith("date")), None)
    if start is None:
        raise RuntimeError("Kopfzeile in h_vstoxx.txt nicht gefunden")

    leser = csv.DictReader(io.StringIO("\n".join(zeilen[start:])))
    if spalte not in (leser.fieldnames or []):
        raise RuntimeError(
            f"Spalte '{spalte}' fehlt in h_vstoxx.txt. Vorhanden: "
            f"{leser.fieldnames}"
        )

    reihe = Reihe(key=key, quelle=f"STOXX {spalte}")
    for zeile in leser:
        roh = (zeile.get("Date") or "").strip()
        wert = zahl(zeile.get(spalte))
        if wert is None or len(roh) != 10 or "." not in roh:
            continue
        tag, monat, jahr = roh.split(".")
        reihe.punkte.append((f"{jahr}-{monat}-{tag}", wert))
    return reihe
