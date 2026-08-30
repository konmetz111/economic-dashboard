"""Stufe 1b: Kennzahlen rechnen und die Uebergabe an die Routine schreiben.

Dieses Skript rechnet - es formuliert nicht. Es erzeugt zwei Dateien:

  data/kennzahlen.json      Die Uebergabe an Stufe 2. Enthaelt je Graph alle
                            fertig gerechneten Groessen: Stand, Veraenderungen
                            ueber vier Zeitraeume, Perzentil, Spannweite und
                            Mittel der letzten zehn Jahre, dazu die
                            Erlaeuterung und die bekannte Schwaeche des
                            Indikators.

  docs/data/commentary.json Ein regelbasierter Grundtext, damit die Website nie
                            ohne Kommentar dasteht. Die Cloud-Routine
                            ueberschreibt diese Datei anschliessend mit ihrer
                            Fassung; bleibt sie aus, steht wenigstens die
                            nuechterne Variante da - erkennbar am Feld
                            "erzeugt_mit".

Die Trennung ist der Kern: Saemtliche Zahlen entstehen hier in Python. Das
Sprachmodell in Stufe 2 bekommt sie fertig und darf keine eigenen rechnen.
Damit kann im Kommentar keine Zahl stehen, die nicht vorher ausgerechnet wurde.

Aufruf:  python scripts/build_kennzahlen.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DATEN, WURZEL, jetzt_utc

WEBDATEN = WURZEL / "docs" / "data"
UEBERGABE = DATEN / "kennzahlen.json"


# --------------------------------------------------------------------------- #
# Kennzahlen                                                                   #
# --------------------------------------------------------------------------- #

def _vor_jahren(tag: str, jahre: int) -> str:
    d = date.fromisoformat(tag)
    try:
        return d.replace(year=d.year - jahre).isoformat()
    except ValueError:                       # 29. Februar
        return d.replace(year=d.year - jahre, day=28).isoformat()


def _wert_vor(punkte: list, tage: int) -> tuple[str, float] | None:
    if not punkte:
        return None
    ziel = (date.fromisoformat(punkte[-1][0]) - timedelta(days=tage)).isoformat()
    treffer = [p for p in punkte if p[0] <= ziel]
    return tuple(treffer[-1]) if treffer else None


def _perzentil(punkte: list, wert: float, jahre: int = 10) -> float | None:
    if not punkte:
        return None
    grenze = _vor_jahren(punkte[-1][0], jahre)
    fenster = [w for t, w in punkte if t >= grenze]
    if len(fenster) < 12:
        return None
    return round(sum(1 for w in fenster if w < wert) / len(fenster) * 100, 1)


def kennzahlen(reihe: dict) -> dict:
    """Alles, was Stufe 2 an Zahlen bekommt - und nur das."""
    punkte = reihe.get("punkte") or []
    grund = {"name": reihe["name"], "status": reihe["status"]}

    if reihe["status"] == "nicht_verfuegbar":
        grund["grund_der_nichtverfuegbarkeit"] = reihe.get("grund", "")
        return grund
    if not punkte:
        grund["hinweis"] = "Keine Datenpunkte vorhanden."
        return grund

    tag, jetzt = punkte[-1]
    grund |= {"stand": tag, "wert": round(jetzt, 3),
              "frequenz": reihe.get("frequenz", "unbekannt")}

    if reihe["status"] == "veraltet":
        grund["warnung"] = (
            f"Diese Reihe steht seit {tag} still. Der Abruf lief, aber die "
            f"Quelle hat nicht aktualisiert. Der Wert ist NICHT aktuell.")
    if reihe.get("fehler"):
        grund["warnung"] = (
            f"Der letzte Abruf ist gescheitert: {reihe['fehler']}. Gezeigt wird "
            f"der letzte erfolgreich geholte Stand vom {tag}.")

    for label, tage in (("woche", 7), ("monat", 30), ("quartal", 91), ("jahr", 365)):
        vorher = _wert_vor(punkte, tage)
        if vorher and vorher[0] != tag:
            grund[f"aenderung_{label}"] = round(jetzt - vorher[1], 3)

    grund["perzentil_10j"] = _perzentil(punkte, jetzt)
    fenster = [w for t, w in punkte if t >= _vor_jahren(tag, 10)]
    if fenster:
        grund |= {"min_10j": round(min(fenster), 3),
                  "max_10j": round(max(fenster), 3),
                  "mittel_10j": round(sum(fenster) / len(fenster), 3)}
    return grund


# --------------------------------------------------------------------------- #
# Regelbasierter Grundtext                                                     #
# --------------------------------------------------------------------------- #

def _richtung(delta: float) -> str:
    return "unveraendert" if abs(delta) < 1e-9 else ("gestiegen" if delta > 0 else "gefallen")


def _dt(wert: float) -> str:
    """Deutsche Zahlschreibweise - Komma als Dezimaltrennzeichen."""
    betrag = abs(wert)
    stellen = 0 if betrag >= 1000 else 1 if betrag >= 100 else 2
    return f"{wert:,.{stellen}f}".replace(",", " ").replace(".", ",")


# Welcher Vergleichszeitraum zu welcher Frequenz passt. Ohne diese Zuordnung
# stuende unter einer Quartalsreihe "gegenueber dem Vormonat", was schlicht
# falsch ist - der Vormonatswert existiert dort gar nicht.
VERGLEICH = {
    "taeglich": [("aenderung_woche", "gegenueber der Vorwoche"),
                 ("aenderung_monat", "gegenueber dem Vormonat")],
    "woechentlich": [("aenderung_monat", "gegenueber dem Vormonat"),
                     ("aenderung_quartal", "gegenueber dem Vorquartal")],
    "monatlich": [("aenderung_monat", "gegenueber dem Vormonat"),
                  ("aenderung_jahr", "gegenueber dem Vorjahr")],
    "quartalsweise": [("aenderung_quartal", "gegenueber dem Vorquartal"),
                      ("aenderung_jahr", "gegenueber dem Vorjahr")],
}


def regelbasiert(chart: dict, zahlen: list[dict]) -> str:
    einheit = chart.get("einheit", "")
    saetze = []

    for z in zahlen:
        if z["status"] == "nicht_verfuegbar":
            saetze.append(f"{z['name']}: nicht verfuegbar. "
                          f"{z.get('grund_der_nichtverfuegbarkeit', '')}".strip())
            continue
        if "wert" not in z:
            saetze.append(f"{z['name']}: keine Daten.")
            continue

        teil = f"{z['name']} steht bei {_dt(z['wert'])}"
        if einheit:
            teil += f" {einheit}"
        teil += f" (Stand {z['stand']})"

        for feld, bezeichnung in VERGLEICH.get(z.get("frequenz", ""), VERGLEICH["monatlich"]):
            if z.get(feld) is not None:
                teil += f", {bezeichnung} um {_dt(abs(z[feld]))} {_richtung(z[feld])}"
                break

        if z.get("perzentil_10j") is not None:
            teil += (f"; damit liegt der Wert ueber {_dt(z['perzentil_10j'])} Prozent "
                     f"aller Staende der vergangenen zehn Jahre")
        saetze.append(teil + ".")

        if z.get("warnung"):
            saetze.append(z["warnung"])

    zweiter = ("Die Einordnung der Folgen schreibt die Cloud-Routine; bis zu "
               "ihrem naechsten Lauf steht hier nur der Zahlenbefund. Was der "
               "Indikator misst, steht ueber dem Graphen"
               + (", seine bekannte Schwaeche darunter." if chart.get("schwaeche") else "."))
    return f"{' '.join(saetze)}\n\n{zweiter}"


# --------------------------------------------------------------------------- #

def main() -> int:
    meta = json.loads((WEBDATEN / "meta.json").read_text(encoding="utf-8"))

    charts, kommentare = [], {}
    for uebersicht in meta["charts"]:
        chart = json.loads(
            (WEBDATEN / f"chart-{uebersicht['id']}.json").read_text(encoding="utf-8"))
        zahlen = [kennzahlen(r) for r in chart["reihen"]]

        charts.append({
            "id": chart["id"],
            "titel": chart["titel"],
            "gruppe": chart["gruppe"],
            "einheit": chart.get("einheit", ""),
            "was_der_indikator_misst": chart.get("aussagekraft", ""),
            "bekannte_schwaeche": chart.get("schwaeche"),
            "schwellenwerte": chart.get("schwellen", []),
            "reihen": zahlen,
        })
        kommentare[chart["id"]] = {
            "text": regelbasiert(chart, zahlen),
            "erzeugt_mit": "regelbasiert",
        }

    UEBERGABE.parent.mkdir(parents=True, exist_ok=True)
    UEBERGABE.write_text(json.dumps({
        "erzeugt_utc": jetzt_utc(),
        "datenstand": meta["erzeugt"],
        "hinweis": ("Uebergabe von Stufe 1 an die Kommentar-Routine. Alle Zahlen "
                    "sind fertig gerechnet und duerfen nicht neu berechnet werden."),
        "charts": charts,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    (WEBDATEN / "commentary.json").write_text(json.dumps({
        "erzeugt": jetzt_utc(),
        "datenstand": meta["erzeugt"],
        "gesamtlage": None,
        "modell": "regelbasiert",
        "charts": kommentare,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"Kennzahlen fuer {len(charts)} Graphen geschrieben "
          f"({UEBERGABE.relative_to(WURZEL)}).")
    print("Regelbasierter Grundtext in docs/data/commentary.json - die "
          "Cloud-Routine ersetzt ihn beim naechsten Lauf.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
