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
import math
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DATEN, WURZEL, jetzt_utc

WEBDATEN = WURZEL / "docs" / "data"
UEBERGABE = DATEN / "kennzahlen.json"
ARCHIV = WEBDATEN / "archiv"


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


def _rund(wert: float) -> float:
    """Auf sechs signifikante Stellen runden, nicht auf feste Nachkommastellen.

    Der Unterschied ist nicht kosmetisch: round(wert, 3) macht aus dem
    Kupfer/Gold-Verhaeltnis von 0,0014434 eine 0,001 - ein Fehler von dreissig
    Prozent, der so in die Uebergabedatei und damit in den Kommentar wandert.
    """
    return float(f"{wert:.6g}")


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
    grund |= {"stand": tag, "wert": _rund(jetzt),
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
            grund[f"aenderung_{label}"] = _rund(jetzt - vorher[1])

    grund["perzentil_10j"] = _perzentil(punkte, jetzt)
    fenster = [w for t, w in punkte if t >= _vor_jahren(tag, 10)]
    if fenster:
        grund |= {"min_10j": _rund(min(fenster)),
                  "max_10j": _rund(max(fenster)),
                  "mittel_10j": _rund(sum(fenster) / len(fenster))}
    return grund


# --------------------------------------------------------------------------- #
# Regelbasierter Grundtext                                                     #
# --------------------------------------------------------------------------- #

def _dt(wert: float) -> str:
    """Deutsche Zahlschreibweise mit sinnvoll vielen Nachkommastellen.

    Die Zahl der Stellen richtet sich nach der Groessenordnung, nicht nach einer
    festen Regel. Zwei Nachkommastellen pauschal haetten das
    Kupfer/Gold-Verhaeltnis - Werte um 0,0015 - als "0,00" ausgegeben.
    """
    betrag = abs(wert)
    if betrag >= 1000:
        stellen = 0
    elif betrag >= 100:
        stellen = 1
    elif betrag >= 0.1 or betrag == 0:
        stellen = 2
    else:
        stellen = min(8, 2 - math.floor(math.log10(betrag)))
    return f"{wert:,.{stellen}f}".replace(",", " ").replace(".", ",")




def regelbasiert(chart: dict, zahlen: list[dict]) -> str:
    """Grundtext ohne Sprachmodell - bewusst karg.

    Dieser Text erscheint nur, wenn die Kommentar-Routine seit dem Datenabruf
    nicht gelaufen ist. Er zaehlt deshalb nicht die Zahlen auf, die ohnehin
    neben dem Graphen stehen, sondern sagt, dass die Einschaetzung noch fehlt -
    und nennt nur, was man an der Kurve nicht ablesen kann: einen Stillstand
    der Quelle oder eine fehlende Reihe.
    """
    hinweise = []
    for z in zahlen:
        if z["status"] == "nicht_verfuegbar":
            hinweise.append(f"{z['name']}: nicht verfügbar. "
                            f"{z.get('grund_der_nichtverfuegbarkeit', '')}".strip())
        elif z.get("warnung"):
            hinweise.append(z["warnung"])
        elif "wert" not in z:
            hinweise.append(f"{z['name']}: keine Daten.")

    kern = ("Die Einordnung für diese Woche steht noch aus – sie entsteht im "
            "zweiten Lauf, der nach dem Datenabruf stattfindet.")
    return kern + ("\n\n" + " ".join(hinweise) if hinweise else "")


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
        }

    UEBERGABE.parent.mkdir(parents=True, exist_ok=True)
    UEBERGABE.write_text(json.dumps({
        "erzeugt_utc": jetzt_utc(),
        "datenstand": meta["erzeugt"],
        "hinweis": ("Uebergabe von Stufe 1 an die Kommentar-Routine. Alle Zahlen "
                    "sind fertig gerechnet und duerfen nicht neu berechnet werden."),
        "charts": charts,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    # Die Kommentare der Vorwoche archivieren, bevor der Grundtext sie
    # ueberschreibt. Sonst waere die Einschaetzung jeder Woche nach dem
    # naechsten Lauf unwiederbringlich weg - und damit auch die Moeglichkeit
    # nachzulesen, was vorige Woche erwartet wurde und was daraus geworden ist.
    bisher = WEBDATEN / "commentary.json"
    if bisher.exists():
        try:
            alt_inhalt = json.loads(bisher.read_text(encoding="utf-8"))
            stand = (alt_inhalt.get("datenstand") or alt_inhalt.get("erzeugt") or "")[:10]
            # Nur archivieren, was die Routine geschrieben hat - der eigene
            # Grundtext ist nichts, was man nachlesen will.
            if stand and any(k.get("text") for k in (alt_inhalt.get("charts") or {}).values())                     and alt_inhalt.get("gesamtlage"):
                ARCHIV.mkdir(parents=True, exist_ok=True)
                (ARCHIV / f"{stand}.json").write_text(
                    json.dumps(alt_inhalt, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")
        except (json.JSONDecodeError, OSError):
            pass

    (WEBDATEN / "commentary.json").write_text(json.dumps({
        "erzeugt": jetzt_utc(),
        "datenstand": meta["erzeugt"],
        "gesamtlage": None,
        "charts": kommentare,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    if ARCHIV.exists():
        verzeichnis = sorted((p.stem for p in ARCHIV.glob("*.json")
                              if p.stem != "index"), reverse=True)
        (ARCHIV / "index.json").write_text(json.dumps(verzeichnis), encoding="utf-8")

    print(f"Kennzahlen fuer {len(charts)} Graphen geschrieben "
          f"({UEBERGABE.relative_to(WURZEL)}).")
    print("Regelbasierter Grundtext in docs/data/commentary.json - die "
          "Cloud-Routine ersetzt ihn beim naechsten Lauf.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
