"""Yahoo-Kursdaten ueber die Chart-Schnittstelle.

Warum ueberhaupt Yahoo: Fuer Kupfer, Weizen, den Dollar-Index und die beiden
S&P-500-ETFs gibt es keine freie Alternative mit taeglicher Historie. Stooq
waere die erste Wahl gewesen und war es im ersten Entwurf auch - dort steht
inzwischen eine JavaScript-Bot-Sperre, die jeden automatischen Abruf mit einer
HTML-Seite statt der CSV-Datei beantwortet.

Bekanntes Risiko: Yahoo drosselt Zugriffe aus Rechenzentren. Auf einem
GitHub-Actions-Runner kann dieser Abruf deshalb scheitern, waehrend er vom
Wohnanschluss aus funktioniert - dieselbe Fehlerklasse wie bei der
YouTube-Quelle im Schwesterprojekt news-briefing. Der Ausfall ist dann laut und
auf der Website sichtbar. Die betroffenen Reihen sind Kupfer, Weizen, DXY und
die Marktbreite; Gold und Silber haengen bewusst an der LBMA, Brent an FRED.

Die aeltere Kursabfrage /v7/finance/quote verlangt inzwischen ein Sitzungs-
Token und ist damit nicht mehr brauchbar; /v8/finance/chart antwortet weiterhin
ohne Anmeldung.
"""

from __future__ import annotations

from datetime import datetime, timezone

from common import Reihe, hole

BASIS = "https://query1.finance.yahoo.com/v8/finance/chart"


def abrufen(key: str, args: dict) -> Reihe:
    symbol = args["symbol"]

    # Bewusst period1/period2 statt range=max: Bei range=max verdichtet Yahoo
    # stillschweigend auf Monatswerte, obwohl interval=1d angefordert wurde.
    # Fuer den S&P-500-ETF waren das 404 statt 8453 Punkte - eine grob falsche
    # Aufloesung, die man der Antwort nicht ansieht. Mit einem expliziten
    # Zeitfenster ab 1970 liefert dieselbe Schnittstelle die Tagesdaten.
    antwort = hole(f"{BASIS}/{symbol}",
                   params={"period1": "0", "period2": "9999999999",
                           "interval": args.get("intervall", "1d")},
                   timeout=90)
    nutzlast = antwort.json().get("chart") or {}

    if nutzlast.get("error"):
        raise RuntimeError(f"Yahoo meldet fuer '{symbol}': {nutzlast['error']}")
    ergebnisse = nutzlast.get("result") or []
    if not ergebnisse:
        raise RuntimeError(f"Yahoo lieferte kein Ergebnis fuer '{symbol}'")

    block = ergebnisse[0]
    zeiten = block.get("timestamp") or []
    kurse = ((block.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []

    reihe = Reihe(key=key, quelle=f"Yahoo {symbol}")
    for zeit, kurs in zip(zeiten, kurse):
        # Der jeweils letzte Balken ist bei laufender Sitzung oft noch leer.
        if kurs is None:
            continue
        tag = datetime.fromtimestamp(zeit, tz=timezone.utc).date().isoformat()
        reihe.punkte.append((tag, float(kurs)))

    if not reihe.punkte:
        raise RuntimeError(f"Yahoo lieferte fuer '{symbol}' nur leere Kurse")
    return reihe
