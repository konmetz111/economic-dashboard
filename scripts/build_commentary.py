"""Stufe 2: Kennzahlen rechnen und daraus die Kommentare erzeugen.

Zweistufig, und zwar aus einem inhaltlichen Grund: Python rechnet saemtliche
Zahlen - Stand, Veraenderungen, Perzentil, Schwellenlage - und uebergibt sie
fertig an das Sprachmodell. Das Modell formuliert nur noch. Damit kann im Text
keine Zahl stehen, die nicht vorher ausgerechnet wurde.

Faellt der Schluessel ANTHROPIC_API_KEY, entsteht trotzdem ein Kommentar: dann
rein regelbasiert, nuechterner formuliert, aber vollstaendig und korrekt.

Aufruf:  python scripts/build_commentary.py
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import WURZEL, jetzt_utc

WEBDATEN = WURZEL / "docs" / "data"
ARCHIV = WEBDATEN / "archiv"

MODELL = os.environ.get("BRIEFING_MODELL", "claude-opus-5")

SYSTEM = """Du schreibst die Kommentare eines volkswirtschaftlichen \
Wochenbriefings auf Deutsch.

Absolute Regeln:
- Verwende ausschliesslich die Zahlen, die dir im Abschnitt KENNZAHLEN \
uebergeben werden. Erfinde keine Zahl, keinen Termin, kein Zitat und kein \
Ereignis. Du hast keinen Zugang zu Nachrichten.
- Wenn eine Reihe als veraltet, fehlerhaft oder im Aufbau gekennzeichnet ist, \
schreibe das ausdruecklich dazu, statt den letzten Stand als aktuell zu deuten.
- Beruecksichtige die genannte Schwaeche des Indikators. Ein Indikator mit \
bekanntem Fehlalarm-Problem darf nicht als Beweis praesentiert werden.
- Keine Anlageberatung, keine Kauf- oder Verkaufsempfehlung.

Form:
- Genau zwei Absaetze, getrennt durch eine Leerzeile.
- Absatz 1 - Bedeutung: Was sagen die juengsten Zahlen? Nenne den Stand und \
die relevanteste Veraenderung, ordne sie historisch ein.
- Absatz 2 - Folgen: Was folgt daraus plausibel fuer Konjunktur, Zinsen oder \
Maerkte? Formuliere als begruendete Erwartung mit Unsicherheit, nicht als \
Vorhersage. Nenne, was die Erwartung widerlegen wuerde.
- Je Absatz zwei bis vier Saetze. Nuechtern, praezise, ohne Werbesprache und \
ohne Floskeln wie "es bleibt spannend"."""


# --------------------------------------------------------------------------- #
# Kennzahlen                                                                   #
# --------------------------------------------------------------------------- #

def _wert_vor(punkte: list, tage: int) -> tuple[str, float] | None:
    if not punkte:
        return None
    ziel = (date.fromisoformat(punkte[-1][0]) - timedelta(days=tage)).isoformat()
    treffer = [p for p in punkte if p[0] <= ziel]
    return tuple(treffer[-1]) if treffer else None


def _perzentil(punkte: list, wert: float, jahre: int = 10) -> float | None:
    if not punkte:
        return None
    grenze = (date.fromisoformat(punkte[-1][0]).replace(
        year=date.fromisoformat(punkte[-1][0]).year - jahre)).isoformat()
    fenster = [w for t, w in punkte if t >= grenze]
    if len(fenster) < 12:
        return None
    kleiner = sum(1 for w in fenster if w < wert)
    return round(kleiner / len(fenster) * 100, 1)


def kennzahlen(reihe: dict) -> dict:
    """Alles, was das Sprachmodell an Zahlen bekommt - und nur das."""
    punkte = reihe.get("punkte") or []
    grund = {
        "name": reihe["name"],
        "status": reihe["status"],
        "aufbauend": reihe.get("aufbauend", False),
    }
    if reihe["status"] == "nicht_verfuegbar":
        grund["grund"] = reihe.get("grund", "")
        return grund
    if not punkte:
        grund["hinweis"] = "Keine Datenpunkte vorhanden."
        return grund

    tag, jetzt = punkte[-1]
    grund |= {"stand": tag, "wert": round(jetzt, 3),
              "frequenz": reihe.get("frequenz", "unbekannt")}
    if reihe["status"] == "veraltet":
        grund["warnung"] = (f"Reihe steht seit {tag} still - der Abruf lief, "
                            f"aber die Quelle hat nicht aktualisiert.")
    if reihe.get("fehler"):
        grund["warnung"] = f"Letzter Abruf fehlgeschlagen: {reihe['fehler']}"

    for label, tage in (("woche", 7), ("monat", 30), ("quartal", 91), ("jahr", 365)):
        vorher = _wert_vor(punkte, tage)
        if vorher and vorher[0] != tag:
            grund[f"aenderung_{label}"] = round(jetzt - vorher[1], 3)

    grund["perzentil_10j"] = _perzentil(punkte, jetzt)
    fenster = [w for t, w in punkte if t >= _vor_jahren(tag, 10)]
    if fenster:
        grund["min_10j"] = round(min(fenster), 3)
        grund["max_10j"] = round(max(fenster), 3)
        grund["mittel_10j"] = round(sum(fenster) / len(fenster), 3)
    return grund


def _vor_jahren(tag: str, jahre: int) -> str:
    d = date.fromisoformat(tag)
    try:
        return d.replace(year=d.year - jahre).isoformat()
    except ValueError:                       # 29. Februar
        return d.replace(year=d.year - jahre, day=28).isoformat()


# --------------------------------------------------------------------------- #
# Regelbasierter Text                                                          #
# --------------------------------------------------------------------------- #

def _richtung(delta: float) -> str:
    if abs(delta) < 1e-9:
        return "unveraendert"
    return "gestiegen" if delta > 0 else "gefallen"


def _dt(wert: float) -> str:
    """Deutsche Zahlschreibweise - Komma als Dezimaltrennzeichen."""
    betrag = abs(wert)
    stellen = 0 if betrag >= 1000 else 1 if betrag >= 100 else 2
    return f"{wert:,.{stellen}f}".replace(",", " ").replace(".", ",")


# Welcher Vergleichszeitraum zu welcher Frequenz passt. Ohne diese Zuordnung
# stuende unter einer Quartalsreihe "im Vergleich zum Vormonat", was schlicht
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
    """Vollstaendiger Kommentar ohne Sprachmodell - der Rueckfallweg."""
    einheit = chart.get("einheit", "")
    saetze = []

    for z in zahlen:
        if z["status"] == "nicht_verfuegbar":
            saetze.append(f"{z['name']}: nicht verfuegbar. {z.get('grund', '')}".strip())
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
                teil += (f", {bezeichnung} um {_dt(abs(z[feld]))} "
                         f"{_richtung(z[feld])}")
                break

        if z.get("perzentil_10j") is not None:
            teil += (f"; damit liegt der Wert ueber {_dt(z['perzentil_10j'])} Prozent "
                     f"aller Staende der vergangenen zehn Jahre")
        saetze.append(teil + ".")

        if z.get("warnung"):
            saetze.append(z["warnung"])

    zweiter = ("Eine Einordnung der Folgen entsteht nur mit Sprachmodell; ohne "
               "hinterlegten Schluessel bleibt es bei den Zahlen. Was der "
               "Indikator misst, steht ueber dem Graphen"
               + (", seine bekannte Schwaeche darunter." if chart.get("schwaeche") else "."))
    return f"{' '.join(saetze)}\n\n{zweiter}"


# --------------------------------------------------------------------------- #
# Sprachmodell                                                                 #
# --------------------------------------------------------------------------- #

def _klient():
    schluessel = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not schluessel:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    return anthropic.Anthropic(api_key=schluessel)


def _anfrage(klient, chart: dict, zahlen: list[dict]) -> str | None:
    inhalt = {
        "indikator": chart["titel"],
        "einheit": chart.get("einheit", ""),
        "was_er_misst": chart.get("aussagekraft", ""),
        "bekannte_schwaeche": chart.get("schwaeche"),
        "schwellenwerte": chart.get("schwellen", []),
        "KENNZAHLEN": zahlen,
    }
    try:
        antwort = klient.messages.create(
            model=MODELL,
            max_tokens=700,
            system=SYSTEM,
            messages=[{"role": "user", "content":
                       json.dumps(inhalt, ensure_ascii=False, indent=2)}],
        )
        return "".join(b.text for b in antwort.content if b.type == "text").strip()
    except Exception as fehler:                        # noqa: BLE001
        print(f"  Sprachmodell fuer '{chart['id']}' fehlgeschlagen: {fehler}",
              file=sys.stderr)
        return None


def _gesamtlage(klient, alle: list[dict]) -> str | None:
    if klient is None:
        return None
    verdichtet = [{"indikator": c["titel"], "kennzahlen": c["zahlen"]} for c in alle]
    try:
        antwort = klient.messages.create(
            model=MODELL,
            max_tokens=900,
            system=(SYSTEM + "\n\nAbweichend hier: Schreibe drei bis vier Absaetze, "
                    "die die Gesamtlage ueber alle Indikatoren hinweg zusammenfassen. "
                    "Achte auf Konfluenz - mehrere unabhaengige Gruppen, die in "
                    "dieselbe Richtung zeigen, sind aussagekraeftiger als ein "
                    "einzelner Ausschlag. Nenne ausdruecklich, wo sich Indikatoren "
                    "widersprechen."),
            messages=[{"role": "user", "content":
                       json.dumps(verdichtet, ensure_ascii=False)}],
        )
        return "".join(b.text for b in antwort.content if b.type == "text").strip()
    except Exception as fehler:                        # noqa: BLE001
        print(f"  Gesamtlage fehlgeschlagen: {fehler}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #

def main() -> int:
    meta = json.loads((WEBDATEN / "meta.json").read_text(encoding="utf-8"))
    klient = _klient()
    if klient is None:
        print("Kein ANTHROPIC_API_KEY - Kommentare werden regelbasiert erzeugt.")

    charts = []
    for uebersicht in meta["charts"]:
        pfad = WEBDATEN / f"chart-{uebersicht['id']}.json"
        chart = json.loads(pfad.read_text(encoding="utf-8"))
        chart["zahlen"] = [kennzahlen(r) for r in chart["reihen"]]
        charts.append(chart)

    def einer(chart: dict) -> tuple[str, dict]:
        text = _anfrage(klient, chart, chart["zahlen"]) if klient else None
        return chart["id"], {
            "text": text or regelbasiert(chart, chart["zahlen"]),
            "erzeugt_mit": MODELL if text else "regelbasiert",
            "kennzahlen": chart["zahlen"],
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        kommentare = dict(pool.map(einer, charts))

    gesamt = _gesamtlage(klient, charts)

    ausgabe = {
        "erzeugt": jetzt_utc(),
        "datenstand": meta["erzeugt"],
        "gesamtlage": gesamt,
        "modell": MODELL if klient else "regelbasiert",
        "charts": kommentare,
    }
    (WEBDATEN / "commentary.json").write_text(
        json.dumps(ausgabe, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # Wochenarchiv: Die Kommentare eines Laufs sind nach dem naechsten Lauf
    # sonst unwiederbringlich weg. Das Archiv macht Entwicklungen der Einschaetzung
    # nachlesbar - und den Autor dieser Einschaetzungen ueberpruefbar.
    ARCHIV.mkdir(parents=True, exist_ok=True)
    (ARCHIV / f"{date.today().isoformat()}.json").write_text(
        json.dumps(ausgabe, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    verzeichnis = sorted((p.stem for p in ARCHIV.glob("*.json")), reverse=True)
    (ARCHIV / "index.json").write_text(json.dumps(verzeichnis), encoding="utf-8")

    mit_modell = sum(1 for k in kommentare.values() if k["erzeugt_mit"] != "regelbasiert")
    print(f"{len(kommentare)} Kommentare erzeugt "
          f"({mit_modell} mit Sprachmodell, {len(kommentare) - mit_modell} regelbasiert).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
