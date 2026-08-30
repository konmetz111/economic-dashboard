"""FRED - Federal Reserve Economic Data, St. Louis Fed.

Die Arbeitspferd-Quelle des Dashboards. Braucht einen kostenlosen API-Schluessel
(https://fredaccount.stlouisfed.org/apikeys), der als Secret FRED_API_KEY
hinterlegt wird.
"""

from __future__ import annotations

import re

from common import Reihe, hole, umgebung, zahl

BASIS = "https://api.stlouisfed.org/fred/series/observations"
START = "1960-01-01"


def _ohne_schluessel(text: str) -> str:
    """Den API-Schluessel aus einer Meldung entfernen.

    FRED erwartet den Schluessel als Abfrageparameter. Schlaegt ein Abruf fehl,
    schreibt requests die vollstaendige URL in die Ausnahme - samt Schluessel.
    Diese Meldung landet im Actions-Protokoll, in data/meta.json und damit auf
    der oeffentlichen Website. Deshalb wird sie hier abgefangen, bevor sie
    irgendwohin weitergereicht wird.
    """
    return re.sub(r"(api_key=)[^&\s]+", r"\1<entfernt>", text)


def abrufen(key: str, args: dict) -> Reihe:
    series_id = args["series_id"]
    faktor = float(args.get("faktor", 1.0))

    try:
        antwort = hole(BASIS, params={
            "series_id": series_id,
            "api_key": umgebung("FRED_API_KEY"),
            "file_type": "json",
            "observation_start": args.get("start", START),
        })
    except Exception as fehler:                        # noqa: BLE001
        raise RuntimeError(
            f"FRED-Abruf fuer '{series_id}' fehlgeschlagen: "
            f"{_ohne_schluessel(f'{type(fehler).__name__}: {fehler}')}"
        ) from None

    nutzlast = antwort.json()

    if "observations" not in nutzlast:
        raise RuntimeError(_ohne_schluessel(
            f"FRED lieferte keine Beobachtungen fuer '{series_id}': "
            f"{nutzlast.get('error_message', nutzlast)}"
        ))

    reihe = Reihe(key=key, quelle=f"FRED {series_id}")
    for beobachtung in nutzlast["observations"]:
        wert = zahl(beobachtung.get("value"))
        if wert is not None:
            reihe.punkte.append((beobachtung["date"], wert * faktor))
    return reihe
