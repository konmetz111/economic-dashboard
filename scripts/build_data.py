"""Stufe 1: Alle Reihen abrufen, ableiten und fuer die Website buendeln.

Ablauf:
  1. Rohreihen und Chartreihen abrufen (parallel, weil fast alles Netzwartezeit ist)
  2. Reihen mit ANHAENGEND-Adapter um einen Punkt verlaengern statt zu ersetzen
  3. Berechnete Reihen aus den Rohreihen ableiten
  4. Aktualitaet pruefen und je Reihe einen Status setzen
  5. data/series/*.json (Bestand) und docs/data/chart-*.json (Website) schreiben

Aufruf:  python scripts/build_data.py [--nur chart-id[,chart-id]]
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml

import common
from common import (DATEN, REIHEN, WURZEL, Reihe, cape_aufbau, differenz,
                    fehlerreihe, indexiert, jahresrate, jetzt_utc,
                    kreditimpuls, mit_bestand_verschmelzen, forward_1j1j,
                    qoq_annualisiert, quotient, reihe_laden, reihe_speichern,
                    zscore)
from sources import MODULE, hole_reihe

WEBDATEN = WURZEL / "docs" / "data"
KONFIG = WURZEL / "config" / "indicators.yaml"

# Ab wann eine Reihe als veraltet gilt, je erkannter Frequenz.
#
# Grosszuegig bemessen, und das aus zwei Gruenden. Erstens haben Statistikaemter
# Feiertage und Revisionstermine. Zweitens - und das ist der eigentliche Grund
# fuer die hohen Werte - datieren FRED und die EZB eine Periode auf ihren
# Beginn: Der Wert fuer das erste Quartal 2026 traegt den 1. Januar, obwohl er
# erst im Juni erscheint. Eine Frist von 210 Tagen haette diese voellig
# aktuelle Reihe als veraltet gemeldet. Ein Fehlalarm bei jedem Lauf macht die
# Warnung wertlos, also lieber spaet warnen als falsch.
FRIST_TAGE = {"taeglich": 12, "woechentlich": 24, "monatlich": 100, "quartalsweise": 340}


# --------------------------------------------------------------------------- #
# Konfiguration                                                                #
# --------------------------------------------------------------------------- #

def konfiguration() -> dict:
    return yaml.safe_load(KONFIG.read_text(encoding="utf-8"))


# Felder in `args`, die auf eine andere Reihe zeigen statt einen Wert zu setzen.
VERWEISE = ("basis", "minuend", "subtrahend", "zaehler", "nenner", "kurz", "lang")


def abzurufende(konf: dict, nur: set[str] | None) -> dict[str, dict]:
    """Alle Reihen sammeln, die tatsaechlich ueber das Netz geholt werden.

    Bei `--nur` genuegt es nicht, die Reihen der gewaehlten Charts zu holen:
    Eine berechnete Reihe kann auf eine Reihe zeigen, die in einem ganz anderen
    Chart steht - das Kupfer/Gold-Verhaeltnis etwa braucht die Kupfer- und die
    Goldreihe, die je einen eigenen Graphen haben. Deshalb werden die Verweise
    aufgeloest und die Zielreihen mitgeholt.
    """
    quellen: dict[str, dict] = {}
    for chart in konf["charts"]:
        for reihe in chart["reihen"]:
            if reihe.get("verfuegbar") is False or reihe.get("adapter") == "berechnet":
                continue
            quellen[reihe["key"]] = {"adapter": reihe["adapter"],
                                     "args": reihe.get("args", {})}

    auftraege: dict[str, dict] = {}
    for key, eintrag in (konf.get("rohreihen") or {}).items():
        auftraege[key] = {"adapter": eintrag["adapter"], "args": eintrag.get("args", {})}

    gewaehlt = [c for c in konf["charts"] if not nur or c["id"] in nur]
    benoetigt: set[str] = set()
    for chart in gewaehlt:
        for reihe in chart["reihen"]:
            if reihe.get("verfuegbar") is False:
                continue
            if reihe.get("adapter") == "berechnet":
                args = reihe.get("args", {})
                benoetigt.update(args[f] for f in VERWEISE if f in args)
            else:
                benoetigt.add(reihe["key"])

    for key in benoetigt:
        if key in quellen and key not in auftraege:
            auftraege[key] = quellen[key]
    return auftraege


# --------------------------------------------------------------------------- #
# Abruf                                                                        #
# --------------------------------------------------------------------------- #

def _anhaengend(adapter: str) -> bool:
    """Liefert der Adapter nur den aktuellen Wert statt einer Historie?"""
    if adapter not in MODULE:
        return False
    modul = importlib.import_module(MODULE[adapter])
    return bool(getattr(modul, "ANHAENGEND", False))


def _verlaengern(neu: Reihe) -> Reihe:
    """Einen frisch geholten Einzelwert an den Bestand anhaengen.

    Ohne diesen Schritt haetten die aus Produktseiten gelesenen Kennzahlen
    dauerhaft genau einen Datenpunkt. Ein bereits vorhandenes Datum wird
    ueberschrieben, damit ein zweiter Lauf am selben Tag keine Dublette erzeugt.
    """
    bestand = reihe_laden(neu.key)
    if bestand is None or bestand.leer:
        return neu
    ohne_heute = [p for p in bestand.punkte if p[0] not in {t for t, _ in neu.punkte}]
    neu.punkte = sorted(ohne_heute + neu.punkte)
    return neu


def alle_abrufen(auftraege: dict[str, dict]) -> dict[str, Reihe]:
    def einer(paar):
        key, auftrag = paar
        reihe = hole_reihe(key, auftrag["adapter"], auftrag["args"])
        if reihe.status == "ok" and _anhaengend(auftrag["adapter"]):
            reihe = _verlaengern(reihe)
        return key, mit_bestand_verschmelzen(reihe)

    # Acht gleichzeitige Abrufe: genug, um die Laufzeit von Minuten auf
    # Sekunden zu druecken, und wenig genug, dass keine Quelle uns drosselt.
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(pool.map(einer, auftraege.items()))


# --------------------------------------------------------------------------- #
# Ableitungen                                                                  #
# --------------------------------------------------------------------------- #

def berechnen(key: str, args: dict, vorrat: dict[str, Reihe]) -> Reihe:
    formel = args["formel"]

    def hol(name: str) -> Reihe | None:
        reihe = vorrat.get(args[name] if name in args else name)
        return reihe if reihe and not reihe.leer else None

    if formel == "differenz":
        a, b = hol("minuend"), hol("subtrahend")
        if not a or not b:
            return fehlerreihe(key, "Eingangsreihe fehlt oder ist leer")
        return differenz(a, b, key)

    if formel == "jahresrate":
        basis = hol("basis")
        return jahresrate(basis, key) if basis else fehlerreihe(key, "Basisreihe fehlt")

    if formel == "qoq_annualisiert":
        basis = hol("basis")
        return qoq_annualisiert(basis, key) if basis else fehlerreihe(key, "Basisreihe fehlt")

    if formel == "kreditimpuls":
        basis = hol("basis")
        return kreditimpuls(basis, key) if basis else fehlerreihe(key, "Basisreihe fehlt")

    if formel == "cape_aufbau":
        basis = hol("basis")
        return cape_aufbau(basis, key) if basis else fehlerreihe(key, "Basisreihe fehlt")

    if formel == "zscore":
        basis = hol("basis")
        return zscore(basis, key) if basis else fehlerreihe(key, "Basisreihe fehlt")

    if formel in ("quotient", "quotient_prozent", "quotient_indexiert"):
        z, n = hol("zaehler"), hol("nenner")
        if not z or not n:
            return fehlerreihe(key, "Eingangsreihe fehlt oder ist leer")
        faktor = 100.0 if formel == "quotient_prozent" else 1.0
        ergebnis = quotient(z, n, key, faktor)
        return indexiert(ergebnis, key) if formel == "quotient_indexiert" else ergebnis

    if formel == "forward_1j1j":
        kurz, lang = hol("kurz"), hol("lang")
        if not kurz or not lang:
            return fehlerreihe(key, "Eingangsreihe fehlt oder ist leer")
        return forward_1j1j(kurz, lang, key)

    return fehlerreihe(key, f"Unbekannte Formel '{formel}'")


def ableitungen_ergaenzen(konf: dict, vorrat: dict[str, Reihe]) -> None:
    """Berechnete Reihen aufloesen - zweimal, weil sie aufeinander aufbauen koennen.

    Beispiel: kern_cpi_us ist selbst eine Jahresrate und zugleich Eingang des
    Realzinses. Ein zweiter Durchlauf genuegt fuer die vorhandene Verschachtelung.

    Bewusst ueber alle Charts, auch bei `--nur`: Rechnen kostet nichts, und eine
    ausgewaehlte Reihe kann auf eine berechnete Reihe aus einem anderen Chart
    zeigen. Fehlt deren Eingang, entsteht schlicht eine leere Reihe.
    """
    # Reihenfolge der Bedingungen: Als nicht verfuegbar gekennzeichnete Reihen
    # haben gar kein Feld "adapter", ein Zugriff darauf wirft.
    offen = [(chart, reihe) for chart in konf["charts"]
             for reihe in chart["reihen"]
             if reihe.get("verfuegbar") is not False
             and reihe.get("adapter") == "berechnet"]

    for _ in range(2):
        for _chart, reihe in offen:
            key = reihe["key"]
            if key in vorrat and vorrat[key].status == "ok" and not vorrat[key].leer:
                continue
            vorrat[key] = berechnen(key, reihe["args"], vorrat).sortiert()


# --------------------------------------------------------------------------- #
# Aktualitaet                                                                  #
# --------------------------------------------------------------------------- #

def frequenz(reihe: Reihe) -> str:
    if len(reihe.punkte) < 4:
        return "unbekannt"
    letzte = [date.fromisoformat(t) for t, _ in reihe.punkte[-13:]]
    abstaende = sorted((letzte[i] - letzte[i - 1]).days for i in range(1, len(letzte)))
    mitte = abstaende[len(abstaende) // 2]
    if mitte <= 4:
        return "taeglich"
    if mitte <= 10:
        return "woechentlich"
    if mitte <= 45:
        return "monatlich"
    return "quartalsweise"


def aktualitaet_pruefen(reihe: Reihe) -> tuple[str, str]:
    """(status, frequenz) - kennzeichnet Reihen, die stehengeblieben sind."""
    freq = frequenz(reihe)
    if reihe.status == "fehler" or reihe.leer:
        return reihe.status, freq
    frist = FRIST_TAGE.get(freq)
    if frist is None:
        return "ok", freq
    alter = (date.today() - date.fromisoformat(reihe.letztes_datum)).days
    return ("veraltet" if alter > frist else "ok"), freq


# --------------------------------------------------------------------------- #
# Ausgabe                                                                      #
# --------------------------------------------------------------------------- #

AUSDUENNEN_AB_JAHREN = 12


def _ausgeduennt(punkte: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Tageswerte, die aelter als zwoelf Jahre sind, auf Wochenwerte reduzieren.

    Der Grund ist nicht Sparsamkeit um ihrer selbst willen. Der Goldpreis reicht
    bis 1968, die Treasury-Renditen bis 1962 - zusammen sind das ueber elf
    Megabyte, die woechentlich neu committet wuerden. Auf einem Graphen von
    wenigen hundert Pixeln Breite sind Tageswerte von 1975 ohnehin nicht
    darstellbar: In der Max-Ansicht liegen dort Hunderte Punkte auf einer
    Bildschirmspalte.

    Die letzten zwoelf Jahre bleiben unangetastet - sie decken das
    Standardfenster von zehn Jahren mit Reserve ab, also jede Ansicht, in der
    die Tagesaufloesung tatsaechlich sichtbar wird. Die vollstaendige Reihe
    bleibt in data/series/ erhalten.
    """
    if len(punkte) < 400:
        return punkte
    grenze = date.today().replace(year=date.today().year - AUSDUENNEN_AB_JAHREN).isoformat()
    alt = [p for p in punkte if p[0] < grenze]
    neu = [p for p in punkte if p[0] >= grenze]
    if len(alt) < 400:
        return punkte

    # Je Kalenderwoche den letzten Wert behalten.
    je_woche: dict[tuple[int, int], tuple[str, float]] = {}
    for tag, wert in alt:
        jahr, woche, _ = date.fromisoformat(tag).isocalendar()
        je_woche[(jahr, woche)] = (tag, wert)
    return sorted(je_woche.values()) + neu


def _gerundet(punkte: list[tuple[str, float]]) -> list[list]:
    """Ausduennen und runden - vier Nachkommastellen genuegen ueberall."""
    return [[t, round(w, 4)] for t, w in _ausgeduennt(punkte)]


def schreiben(konf: dict, vorrat: dict[str, Reihe], nur: set[str] | None) -> dict:
    WEBDATEN.mkdir(parents=True, exist_ok=True)
    REIHEN.mkdir(parents=True, exist_ok=True)

    for reihe in vorrat.values():
        if not reihe.leer:
            reihe_speichern(reihe)

    uebersicht, probleme = [], []

    for chart in konf["charts"]:
        # Nicht gewaehlte Charts bleiben unangetastet, gehen aber mit ihrem
        # zuletzt geschriebenen Stand in die Uebersicht ein. Ohne das wuerde ein
        # Lauf mit --nur die meta.json auf die gewaehlten Graphen zusammen-
        # streichen und den Rest der Website verschwinden lassen.
        if nur and chart["id"] not in nur:
            pfad = WEBDATEN / f"chart-{chart['id']}.json"
            if pfad.exists():
                alt = json.loads(pfad.read_text(encoding="utf-8"))
                uebersicht.append({
                    "id": alt["id"], "gruppe": alt["gruppe"], "titel": alt["titel"],
                    "einheit": alt.get("einheit", ""),
                    "reihen": [{"key": r["key"], "name": r["name"], "status": r["status"]}
                               for r in alt["reihen"]],
                })
            continue

        gebuendelt = {
            "id": chart["id"],
            "gruppe": chart["gruppe"],
            "titel": chart["titel"],
            "einheit": chart.get("einheit", ""),
            "aussagekraft": chart.get("aussagekraft", ""),
            "schwaeche": chart.get("schwaeche"),
            "hinweis": chart.get("hinweis"),
            "quelle": chart.get("quelle", ""),
            "frequenz": chart.get("frequenz"),
            "nulllinie": bool(chart.get("nulllinie")),
            "schwellen": chart.get("schwellen", []),
            "band": chart.get("band"),
            "reihen": [],
        }

        for beschreibung in chart["reihen"]:
            key = beschreibung["key"]
            eintrag = {
                "key": key,
                "name": beschreibung["name"],
                "achse": beschreibung.get("achse", "links"),
                "hinweis": beschreibung.get("hinweis"),
                "aufbauend": bool(beschreibung.get("aufbauend")),
            }

            if beschreibung.get("verfuegbar") is False:
                eintrag |= {"status": "nicht_verfuegbar",
                            "grund": beschreibung.get("grund", ""),
                            "punkte": []}
                gebuendelt["reihen"].append(eintrag)
                continue

            reihe = vorrat.get(key) or fehlerreihe(key, "Reihe wurde nicht abgerufen")
            status, freq = aktualitaet_pruefen(reihe)
            eintrag |= {
                "status": status,
                "fehler": reihe.fehler,
                "quelle": reihe.quelle,
                "frequenz": freq,
                "letztes_datum": reihe.letztes_datum,
                "punkte": _gerundet(reihe.punkte),
            }
            gebuendelt["reihen"].append(eintrag)

            if status != "ok":
                probleme.append({"chart": chart["id"], "reihe": key,
                                 "status": status, "grund": reihe.fehler,
                                 "letztes_datum": reihe.letztes_datum})

        (WEBDATEN / f"chart-{chart['id']}.json").write_text(
            json.dumps(gebuendelt, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")

        uebersicht.append({
            "id": chart["id"], "gruppe": chart["gruppe"], "titel": chart["titel"],
            "einheit": chart.get("einheit", ""),
            "reihen": [{"key": r["key"], "name": r["name"], "status": r["status"]}
                       for r in gebuendelt["reihen"]],
        })

    meta = {
        "erzeugt": jetzt_utc(),
        "titel": konf["meta"]["titel"],
        "untertitel": konf["meta"]["untertitel"],
        "standard_fenster": konf["meta"]["standard_fenster"],
        "fenster": konf["meta"]["fenster"],
        "gruppen": konf["gruppen"],
        "charts": uebersicht,
        "probleme": probleme,
    }
    (WEBDATEN / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return meta


# --------------------------------------------------------------------------- #

def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--nur", help="Kommaliste von Chart-IDs")
    argumente = zerleger.parse_args()
    nur = set(argumente.nur.split(",")) if argumente.nur else None

    konf = konfiguration()
    auftraege = abzurufende(konf, nur)
    print(f"Rufe {len(auftraege)} Reihen ab ...", flush=True)

    vorrat = alle_abrufen(auftraege)
    ableitungen_ergaenzen(konf, vorrat)
    meta = schreiben(konf, vorrat, nur)

    gesamt = sum(len(c["reihen"]) for c in meta["charts"])
    print(f"\n{len(meta['charts'])} Charts, {gesamt} Reihen geschrieben.")

    if meta["probleme"]:
        print(f"\n{len(meta['probleme'])} Reihen mit Befund:")
        for p in meta["probleme"]:
            print(f"  [{p['status']:14}] {p['chart']}/{p['reihe']}"
                  f"{' - ' + p['grund'] if p['grund'] else ''}"
                  f"{'  (Stand ' + p['letztes_datum'] + ')' if p['letztes_datum'] else ''}")

    # Totalausfall bricht ab, damit nichts committet wird. Einzelne Ausfaelle
    # sind normal und duerfen den Lauf nicht stoppen - sie stehen sichtbar in
    # den Daten und auf der Website.
    fehlerhaft = sum(1 for p in meta["probleme"] if p["status"] == "fehler")
    if gesamt and fehlerhaft > gesamt * 0.5:
        print(f"\nAbbruch: {fehlerhaft} von {gesamt} Reihen fehlgeschlagen. "
              f"Das sieht nach einem Netz- oder Schluesselproblem aus, "
              f"nicht nach einzelnen Quellenausfaellen.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
