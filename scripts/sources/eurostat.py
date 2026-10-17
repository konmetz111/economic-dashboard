"""Eurostat ueber die offene Verbreitungsschnittstelle (JSON-stat).

Gebraucht fuer Industrieproduktion und Einzelhandel im Euroraum. Die bis
Oktober 2026 genutzten EZB-Spiegel dieser Reihen (STS.M.I9.Y.PROD... und
STS.M.I9.Y.TOVV...) werden nicht mehr fortgeschrieben - sie liefern klaglos
Werte, die im September 2025 enden, und zwar unter jedem Gebietscode, den die
EZB fuehrt. Eurostat selbst ist aktuell.

Fallstrick bei den Filtercodes: In diesem Datensatz heisst der Indikator `PRD`
und nicht `PROD`, und der Einzelhandelsumsatz `VOL_SLS` und nicht `TOVV`. Ein
falscher Code fuehrt nicht zu einem Fehler, sondern zu einer Antwort mit
gueltiger Struktur und null Werten - genau die Art stiller Leere, die dieses
Projekt vermeiden soll. Deshalb prueft der Abruf unten ausdruecklich, dass
jede Filterdimension genau eine Kategorie trifft.
"""

from __future__ import annotations

from common import Reihe, hole, zahl

BASIS = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


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
    tabelle = args["tabelle"]
    filter_ = dict(args.get("filter") or {})

    nutzlast = hole(f"{BASIS}/{tabelle}",
                    params={"format": "JSON", "lang": "EN", **filter_},
                    timeout=120).json()

    dimensionen = nutzlast.get("id") or []
    kategorien = nutzlast.get("dimension") or {}

    # Jede gefilterte Dimension muss genau eine Kategorie treffen, sonst ist
    # entweder der Code falsch (null Kategorien) oder die Auswahl nicht
    # eindeutig (mehrere) - dann waere der flache Wertindex nicht mehr der
    # Zeitindex und die Reihe stillschweigend falsch zusammengesetzt.
    for name in dimensionen:
        if name == "time":
            continue
        anzahl = len((kategorien.get(name, {}).get("category", {}).get("index") or {}))
        if anzahl != 1:
            raise RuntimeError(
                f"Eurostat {tabelle}: Dimension '{name}' trifft {anzahl} Kategorien, "
                f"erwartet genau eine. Filter pruefen (uebergeben: {filter_})."
            )

    zeitindex = kategorien.get("time", {}).get("category", {}).get("index") or {}
    if not zeitindex:
        raise RuntimeError(f"Eurostat {tabelle}: keine Zeitdimension in der Antwort")
    rueck = {nummer: label for label, nummer in zeitindex.items()}

    reihe = Reihe(key=key, quelle=f"Eurostat {tabelle}")
    for schluessel, wert in (nutzlast.get("value") or {}).items():
        label = rueck.get(int(schluessel))
        tag = _tag(label) if label else None
        betrag = zahl(wert)
        if tag and betrag is not None:
            reihe.punkte.append((tag, betrag * float(args.get("faktor", 1.0))))

    if reihe.leer:
        raise RuntimeError(
            f"Eurostat {tabelle} lieferte keine Werte. Struktur war gueltig, also "
            f"sind die Filtercodes wahrscheinlich veraltet: {filter_}")
    return reihe
