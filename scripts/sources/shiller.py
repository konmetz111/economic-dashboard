"""Robert Shillers Datensatz zum S&P 500 (Yale), Datei ie_data.xls.

Liefert CAPE, nachlaufendes KGV und Gewinnrendite ab 1871. Die Datei ist eine
echte BIFF-.xls und braucht deshalb xlrd, nicht openpyxl.

Die Spaltenanordnung wird nicht hart verdrahtet, sondern anhand der
Kopfzeilen gesucht. Aendert Shiller das Layout, bricht der Abruf mit einer
klaren Meldung ab, statt stillschweigend die falsche Spalte zu lesen.
"""

from __future__ import annotations

import io
import re

import xlrd

from common import Reihe, hole

STARTSEITE = "https://shillerdata.com/"
NOTFALL = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"

# Die Datei wird pro Lauf dreimal gebraucht (CAPE, KGV, Gewinnrendite) und ist
# 1,6 MB gross. Einmal laden genuegt.
_blatt_zwischenspeicher = None


def _tag(zellwert) -> str | None:
    """Shillers Datumsformat 2026.07 bzw. 2026.1 in ein ISO-Datum wandeln.

    Achtung: Oktober steht als 2026.1 in der Datei, nicht als 2026.10 - die
    Nachkommastellen sind Hundertstel. Rechnen statt Text zerlegen.
    """
    try:
        wert = float(zellwert)
    except (TypeError, ValueError):
        return None
    jahr = int(wert)
    monat = int(round((wert - jahr) * 100))
    if not 1 <= monat <= 12:
        return None
    letzter = [31, 29 if jahr % 4 == 0 and (jahr % 100 != 0 or jahr % 400 == 0)
               else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][monat - 1]
    return f"{jahr:04d}-{monat:02d}-{letzter:02d}"


def _dateiadressen() -> list[str]:
    """Die aktuelle Adresse von ie_data.xls von Shillers Startseite lesen.

    Wichtig und nicht optional: Der Downloadpfad enthaelt eine Versionskennung,
    die sich mit jeder Aktualisierung aendert. Eine fest verdrahtete Adresse
    liefert weiterhin HTTP 200 - aber eine veraltete Fassung. Beim Test hier
    war das eine Datei, die zwei Jahre alt war, ohne dass irgendetwas
    fehlgeschlagen waere. Genau diese Art stiller Veralterung soll das Projekt
    nicht haben.
    """
    adressen = []
    try:
        seite = hole(STARTSEITE, timeout=60).text
        for treffer in re.findall(r'href="([^"]*ie_data[^"]*\.xls[^"]*)"', seite, re.I):
            adressen.append("https:" + treffer if treffer.startswith("//") else treffer)
    except Exception:                                  # noqa: BLE001
        pass
    adressen.append(NOTFALL)
    return adressen


def _blatt():
    global _blatt_zwischenspeicher
    if _blatt_zwischenspeicher is not None:
        return _blatt_zwischenspeicher

    letzter_fehler = None
    for url in _dateiadressen():
        try:
            rohdaten = hole(url, timeout=180).content
            mappe = xlrd.open_workbook(file_contents=rohdaten)
            blatt = next((mappe.sheet_by_name(n) for n in mappe.sheet_names()
                          if n.strip().lower().startswith("data")), None)
            _blatt_zwischenspeicher = blatt or mappe.sheet_by_index(0)
            return _blatt_zwischenspeicher
        except Exception as fehler:                   # noqa: BLE001
            letzter_fehler = fehler
    raise RuntimeError(f"Shiller-Datei nicht ladbar: {letzter_fehler}")


def _spalten(blatt) -> tuple[int, dict[str, int]]:
    """Kopfzeile finden und die gebrauchten Spalten identifizieren."""
    for zeile in range(min(20, blatt.nrows)):
        werte = [str(blatt.cell_value(zeile, s)).strip()
                 for s in range(blatt.ncols)]
        if werte and werte[0].lower() == "date":
            gefunden: dict[str, int] = {}
            for spalte, text in enumerate(werte):
                klein = text.lower()
                if klein == "p" and "preis" not in gefunden:
                    gefunden["preis"] = spalte
                elif klein == "e" and "gewinn" not in gefunden:
                    gefunden["gewinn"] = spalte
                elif "cape" in klein and "tr" not in klein and "cape" not in gefunden:
                    gefunden["cape"] = spalte
            # Die CAPE-Spalte traegt ihre Beschriftung manchmal eine Zeile
            # hoeher als "Date"; dann von oben nachschauen.
            if "cape" not in gefunden and zeile > 0:
                oben = [str(blatt.cell_value(zeile - 1, s))
                        for s in range(blatt.ncols)]
                for spalte, text in enumerate(oben):
                    if re.search(r"\bcape\b", text, re.I) and "tr" not in text.lower():
                        gefunden["cape"] = spalte
                        break
            if {"preis", "gewinn"} <= gefunden.keys():
                return zeile + 1, gefunden
    raise RuntimeError(
        "Kopfzeile in ie_data.xls nicht gefunden - Shiller hat das Layout "
        "geaendert. scripts/sources/shiller.py anpassen."
    )


def abrufen(key: str, args: dict) -> Reihe:
    feld = args["feld"]                # cape | pe_trailing | gewinnrendite
    blatt = _blatt()
    erste_zeile, spalten = _spalten(blatt)

    if feld == "cape" and "cape" not in spalten:
        raise RuntimeError("CAPE-Spalte in ie_data.xls nicht gefunden")

    reihe = Reihe(key=key, quelle="Robert Shiller, Yale (ie_data.xls)")
    for zeile in range(erste_zeile, blatt.nrows):
        tag = _tag(blatt.cell_value(zeile, 0))
        if tag is None:
            continue
        try:
            if feld == "cape":
                wert = float(blatt.cell_value(zeile, spalten["cape"]))
            else:
                preis = float(blatt.cell_value(zeile, spalten["preis"]))
                gewinn = float(blatt.cell_value(zeile, spalten["gewinn"]))
                if gewinn <= 0 or preis <= 0:
                    continue
                wert = (preis / gewinn) if feld == "pe_trailing" else (gewinn / preis * 100.0)
        except (TypeError, ValueError):
            continue
        if wert == wert and wert not in (float("inf"), float("-inf")):
            reihe.punkte.append((tag, wert))
    return reihe
