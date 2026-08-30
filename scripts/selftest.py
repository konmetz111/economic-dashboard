"""Selbsttest: Konfiguration pruefen und jede Quelle wirklich abrufen.

Warum das im Repository steht und nicht im Papierkorb: Der erste Durchlauf
dieses Tests hat 17 von 28 Quellen als kaputt entlarvt - darunter drei, die
klaglos Daten lieferten, nur eben veraltete oder falsch verdichtete. Genau
solche Fehler sieht man einem gruenen Lauf nicht an. Nach jeder Aenderung an
einem Quellmodul oder an einem Reihenschluessel gehoert dieser Test gelaufen.

    python scripts/selftest.py             # Konfiguration und alle Quellen
    python scripts/selftest.py --nur-konfig  # ohne Netz, in Sekunden
    python scripts/selftest.py --ohne-fred   # wenn kein Schluessel gesetzt ist
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml

from common import WURZEL
from sources import MODULE, hole_reihe

VERWEISE = ("basis", "minuend", "subtrahend", "zaehler", "nenner", "kurz", "lang")
FORMELN = {"differenz", "jahresrate", "qoq_annualisiert", "kreditimpuls", "zscore",
           "cape_aufbau", "quotient", "quotient_prozent", "quotient_indexiert",
           "forward_1j1j", "index_ab"}

# Ab wann eine Reihe auffaellig alt ist, nach erkannter Frequenz. Nur ein
# Hinweis im Test, kein Fehler - manche Statistiken erscheinen nun einmal spaet.
ALTERSGRENZE_TAGE = 200


def konfiguration() -> dict:
    return yaml.safe_load(
        (WURZEL / "config" / "indicators.yaml").read_text(encoding="utf-8"))


def konfig_pruefen(konf: dict) -> list[str]:
    fehler: list[str] = []
    gruppen = {g["id"] for g in konf["gruppen"]}
    roh = konf.get("rohreihen") or {}
    alle_keys = set(roh) | {r["key"] for c in konf["charts"] for r in c["reihen"]}

    gesehen_charts, gesehen_reihen = set(), set()
    for c in konf["charts"]:
        if c["id"] in gesehen_charts:
            fehler.append(f"Doppelte Chart-ID: {c['id']}")
        gesehen_charts.add(c["id"])
        if c["gruppe"] not in gruppen:
            fehler.append(f"{c['id']}: unbekannte Gruppe '{c['gruppe']}'")
        for pflicht in ("titel", "aussagekraft", "quelle", "einheit"):
            if not c.get(pflicht):
                fehler.append(f"{c['id']}: Feld '{pflicht}' fehlt")
        if any(r.get("achse") == "rechts" for r in c["reihen"]):
            fehler.append(f"{c['id']}: zweite Y-Achse ist nicht zulaessig")
        if c.get("band"):
            eigene = {r["key"] for r in c["reihen"]}
            for seite in ("von", "bis"):
                if c["band"][seite] not in eigene:
                    fehler.append(f"{c['id']}: Band zeigt auf '{c['band'][seite]}'")

        for r in c["reihen"]:
            if r["key"] in gesehen_reihen:
                fehler.append(f"Doppelter Reihen-Key: {r['key']}")
            gesehen_reihen.add(r["key"])
            if r.get("verfuegbar") is False:
                if not r.get("grund"):
                    fehler.append(f"{r['key']}: nicht verfuegbar, aber ohne Grund")
                continue
            if r["adapter"] == "berechnet":
                args = r.get("args", {})
                if args.get("formel") not in FORMELN:
                    fehler.append(f"{r['key']}: unbekannte Formel '{args.get('formel')}'")
                for feld in VERWEISE:
                    if feld in args and args[feld] not in alle_keys:
                        fehler.append(f"{r['key']}: Verweis '{feld}: {args[feld]}' "
                                      f"zeigt ins Leere")
            elif r["adapter"] not in MODULE:
                fehler.append(f"{r['key']}: unbekannter Adapter '{r['adapter']}'")

    for key, e in roh.items():
        if e["adapter"] not in MODULE:
            fehler.append(f"Rohreihe {key}: unbekannter Adapter '{e['adapter']}'")
    return fehler


def quellen_pruefen(konf: dict, ohne_fred: bool) -> int:
    auftraege: list[tuple[str, str, dict]] = []
    for key, e in (konf.get("rohreihen") or {}).items():
        auftraege.append((key, e["adapter"], e.get("args", {})))
    for c in konf["charts"]:
        for r in c["reihen"]:
            if r.get("verfuegbar") is False or r["adapter"] == "berechnet":
                continue
            auftraege.append((r["key"], r["adapter"], r.get("args", {})))
    if ohne_fred:
        auftraege = [a for a in auftraege if a[1] != "fred"]

    print(f"\n{len(auftraege)} Abrufe\n")
    print(f"{'Reihe':24} {'Adapter':10} {'Punkte':>7}  {'Stand':12}  Befund")
    print("-" * 96)

    gut = schlecht = alt = 0
    for key, adapter, args in auftraege:
        reihe = hole_reihe(key, adapter, args)
        if reihe.status != "ok":
            schlecht += 1
            print(f"{key:24} {adapter:10} {'-':>7}  {'-':12}  FEHLER: {reihe.fehler}")
            continue
        gut += 1
        tage = (date.today() - date.fromisoformat(reihe.letztes_datum)).days
        marke = f"  ALT ({tage} Tage)" if tage > ALTERSGRENZE_TAGE else ""
        if marke:
            alt += 1
        print(f"{key:24} {adapter:10} {len(reihe.punkte):>7}  "
              f"{reihe.letztes_datum:12}  {reihe.letzter_wert:,.3f}{marke}")

    print("-" * 96)
    print(f"{gut} erfolgreich, {schlecht} fehlgeschlagen"
          + (f", davon {alt} auffaellig alt" if alt else ""))
    return schlecht


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--nur-konfig", action="store_true")
    zerleger.add_argument("--ohne-fred", action="store_true")
    argumente = zerleger.parse_args()

    konf = konfiguration()
    print(f"{len(konf['gruppen'])} Gruppen, {len(konf['charts'])} Charts, "
          f"{len(konf.get('rohreihen') or {})} Rohreihen")

    fehler = konfig_pruefen(konf)
    if fehler:
        print(f"\n{len(fehler)} Beanstandungen in der Konfiguration:")
        for f in fehler:
            print(f"  - {f}")
        return 1
    print("Konfiguration: keine Beanstandungen.")

    if argumente.nur_konfig:
        return 0
    return 1 if quellen_pruefen(konf, argumente.ohne_fred) else 0


if __name__ == "__main__":
    raise SystemExit(main())
