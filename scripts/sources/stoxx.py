"""STOXX - VSTOXX, der Volatilitätsindex des EURO STOXX 50.

Zwei Fallstricke stecken in dieser Quelle, beide der Art "lädt anstandslos,
liefert aber Unbrauchbares".

Erstens die Datei: Bis Oktober 2026 wurde hier `h_vstoxx.txt` abgerufen. Diese
Datei existiert weiterhin, antwortet mit HTTP 200 und enthält 4357 saubere
Datenpunkte - nur endet sie am 12. Februar 2016. STOXX pflegt sie seit einem
Jahrzehnt nicht mehr. Aufgefallen ist das erst, als die Aktualitätsprüfung
3901 Tage Rückstand meldete. Die lebende Datei heißt `h_v2tx.txt` und hat ein
anderes Format: semikolongetrennt, mit einer Symbolspalte.

Zweitens die Zertifikatskette: www.stoxx.com sendet nur sein eigenes
Zertifikat und lässt das Zwischenzertifikat weg. Windows holt es selbsttätig
über die AIA-Adresse nach - darum funktioniert curl dort -, OpenSSL und damit
Python tun das nicht und brechen mit CERTIFICATE_VERIFY_FAILED ab, lokal wie
auf dem GitHub-Runner. Deshalb wird hier ein Prüfbündel aus den
certifi-Wurzeln plus dem fehlenden Zwischenzertifikat verwendet (siehe
scripts/certs/). Die Prüfung bleibt vollständig aktiv; abgeschaltet wird sie
nicht.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import certifi

from common import Reihe, hole, zahl

URL = "https://www.stoxx.com/document/Indices/Current/HistoricalData/h_v2tx.txt"
ZWISCHEN = Path(__file__).resolve().parent.parent / "certs" / "stoxx-zwischenzertifikat.pem"

_buendel: str | None = None


def _pruefbuendel() -> str:
    """certifi-Wurzeln plus das fehlende Zwischenzertifikat, einmal erzeugt."""
    global _buendel
    if _buendel is None:
        ziel = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "ca-stoxx.pem"
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(
            Path(certifi.where()).read_text(encoding="utf-8") + "\n"
            + ZWISCHEN.read_text(encoding="utf-8"), encoding="utf-8")
        _buendel = str(ziel)
    return _buendel


def abrufen(key: str, args: dict) -> Reihe:
    """Aufbau: Kopfzeile `Date;Symbol;Indexvalue`, danach je Zeile ein Tag
    im Format `16.10.2026;V2TX;17.219`."""
    symbol = args.get("symbol", "V2TX")
    zeilen = hole(URL, timeout=120, verify=_pruefbuendel()).text.splitlines()

    leser = csv.DictReader(io.StringIO("\n".join(zeilen)), delimiter=";")
    felder = {f.strip() for f in (leser.fieldnames or [])}
    if not {"Date", "Symbol", "Indexvalue"} <= felder:
        raise RuntimeError(f"Unerwarteter Aufbau von h_v2tx.txt. Spalten: {felder}")

    reihe = Reihe(key=key, quelle=f"STOXX {symbol}")
    for zeile in leser:
        if (zeile.get("Symbol") or "").strip() != symbol:
            continue
        roh = (zeile.get("Date") or "").strip()
        wert = zahl(zeile.get("Indexvalue"))
        if wert is None or len(roh) != 10 or "." not in roh:
            continue
        tag, monat, jahr = roh.split(".")
        reihe.punkte.append((f"{jahr}-{monat}-{tag}", wert))

    if reihe.leer:
        raise RuntimeError(f"h_v2tx.txt enthielt keine Zeile mit Symbol '{symbol}'")
    return reihe
