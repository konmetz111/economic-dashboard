"""SEC EDGAR XBRL - Bilanzkennzahlen aus den Pflichtveroeffentlichungen.

Genutzt fuer Berkshire Hathaway (CIK 0001067983). Offizielle, kostenlose
Schnittstelle; die SEC verlangt einen identifizierenden User-Agent, der in
common.py gesetzt ist.

Die Kassequote wird bewusst aus 10-Q und 10-K gelesen und nicht aus den
13F-Formularen: 13F enthaelt die Wertpapierpositionen, nicht die Liquiditaet.
"""

from __future__ import annotations

from common import Reihe, hole, zahl

BASIS = "https://data.sec.gov/api/xbrl/companyconcept"

# Die SEC-WAF ist beim User-Agent eigen: Ohne Mozilla-Praefix antwortet sie mit
# HTTP 403, und eine URL im Agent-String loest ebenfalls eine Sperre aus. Diese
# Fassung ist die getestete Form, die durchgeht und das Projekt trotzdem
# benennt. Nicht ohne erneuten Test veraendern.
KOPFZEILEN = {
    "User-Agent": "Mozilla/5.0 (compatible; economic-dashboard/1.0)",
    "Accept": "application/json",
}

# Die frueher naheliegenden Bezeichnungen CashAndCashEquivalentsAtCarryingValue
# und ShortTermInvestments enden bei Berkshire 2017 - seither wird nach ASU
# 2016-18 unter dem langen Namen unten getaggt. Wer die alten Namen stehen
# laesst, bekommt eine Reihe, die neun Jahre zu frueh aufhoert, ohne dass ein
# Abruf fehlschlaegt.
#
# Wichtige Einschraenkung: Die kurzlaufenden US-Staatsanleihen, die den
# Grossteil der bekannten Berkshire-Barreserve ausmachen, tragen in den
# XBRL-Daten kein eigenes Konzept - sie stecken in dimensionierten Fakten, die
# die companyfacts-Schnittstelle nicht einzeln ausgibt. Diese Reihe ist deshalb
# die eng gefasste Liquiditaet, nicht der oft zitierte Gesamtbestand.
KONZEPTE = {
    "cash_und_kurzfrist": [
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "assets": ["Assets"],
}


_letzter_fehler: str | None = None


def _konzept(cik: str, name: str) -> dict[str, float]:
    """Endedatum -> Wert, jeweils die zuletzt eingereichte Fassung."""
    global _letzter_fehler
    url = f"{BASIS}/CIK{cik}/us-gaap/{name}.json"
    try:
        nutzlast = hole(url, timeout=60, headers=KOPFZEILEN).json()
    except Exception as fehler:                        # noqa: BLE001
        # Einzelne Konzeptbezeichnungen existieren fuer ein Unternehmen nicht -
        # das ist normal und wird von der Kandidatenliste aufgefangen. Der Grund
        # wird aber gemerkt, damit eine Sperre nicht als "Konzept unbekannt"
        # missverstanden wird, wenn am Ende alle Kandidaten leer sind.
        _letzter_fehler = f"{type(fehler).__name__}: {fehler}"
        return {}

    werte: dict[str, tuple[str, float]] = {}
    for eintrag in nutzlast.get("units", {}).get("USD", []):
        if eintrag.get("form") not in ("10-Q", "10-K"):
            continue
        ende = eintrag.get("end")
        wert = zahl(eintrag.get("val"))
        eingereicht = eintrag.get("filed", "")
        if not ende or wert is None:
            continue
        # Spaetere Einreichung ersetzt frueheren Stand (Restatements).
        if ende not in werte or eingereicht > werte[ende][0]:
            werte[ende] = (eingereicht, wert)
    return {ende: wert for ende, (_, wert) in werte.items()}


def abrufen(key: str, args: dict) -> Reihe:
    cik = args["cik"]
    gruppe = args["konzept"]
    skala = float(args.get("skala", 1.0))

    namen = KONZEPTE.get(gruppe)
    if not namen:
        raise RuntimeError(f"Unbekannte Konzeptgruppe '{gruppe}'")

    summe: dict[str, float] = {}
    for name in namen:
        for ende, wert in _konzept(cik, name).items():
            summe[ende] = summe.get(ende, 0.0) + wert

    if not summe:
        raise RuntimeError(
            f"SEC EDGAR lieferte keine Werte fuer CIK {cik}, Gruppe '{gruppe}'. "
            f"Geprueft: {', '.join(namen)}. "
            f"Letzter Abruffehler: {_letzter_fehler or 'keiner - Konzepte leer'}"
        )

    reihe = Reihe(key=key, quelle=f"SEC EDGAR XBRL, CIK {cik}")
    reihe.punkte = [(ende, wert / skala) for ende, wert in sorted(summe.items())]
    return reihe
