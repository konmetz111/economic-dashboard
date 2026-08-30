"""Gemeinsame Bausteine fuer Abruf, Speicherung und Umrechnung von Zeitreihen.

Zentrale Entwurfsentscheidung: Eine Reihe ist immer ein `Reihe`-Objekt mit einem
Status. Faellt eine Quelle aus, wird das Objekt mit status="fehler" und einer
Begruendung zurueckgegeben, statt eine Ausnahme nach oben durchzureichen. Der
Aufrufer entscheidet dann, ob er die zuletzt versionierten Werte behaelt. Damit
kann ein einzelner Quellenausfall nie den ganzen Lauf kippen - aber er bleibt
sichtbar, weil der Status bis in die Website durchgereicht wird.
"""

from __future__ import annotations

import json
import os
import time
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import requests

WURZEL = Path(__file__).resolve().parent.parent
DATEN = WURZEL / "data"
ROH = DATEN / "raw"
REIHEN = DATEN / "series"

# Ein aussagekraeftiger User-Agent ist bei SEC und FINRA Pflicht bzw. dringend
# empfohlen; anonyme Abrufe werden dort gedrosselt oder mit 403 abgewiesen.
UA = "economic-dashboard/1.0 (+https://github.com/konmetz111/economic-dashboard)"

_session: requests.Session | None = None


def sitzung() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    return _session


def hole(url: str, *, params: dict | None = None, versuche: int = 3,
         timeout: int = 60, headers: dict | None = None) -> requests.Response:
    """HTTP-GET mit Wiederholung bei Netz- und 5xx-Fehlern.

    4xx wird nicht wiederholt: Ein 404 auf eine Reihen-ID wird beim zweiten
    Versuch auch nicht besser, und ein 403 bedeutet fast immer eine Sperre, die
    durch schnelles Nachfassen nur bestaetigt wird.
    """
    letzter = None
    for versuch in range(versuche):
        try:
            antwort = sitzung().get(url, params=params, timeout=timeout,
                                    headers=headers or {})
            if antwort.status_code < 400:
                return antwort
            if 400 <= antwort.status_code < 500:
                antwort.raise_for_status()
            letzter = requests.HTTPError(
                f"HTTP {antwort.status_code} von {url}", response=antwort)
        except requests.RequestException as fehler:
            letzter = fehler
            if isinstance(fehler, requests.HTTPError) and fehler.response is not None:
                if 400 <= fehler.response.status_code < 500:
                    raise
        if versuch < versuche - 1:
            time.sleep(2 ** versuch)
    raise letzter if letzter else RuntimeError(f"Abruf fehlgeschlagen: {url}")


# --------------------------------------------------------------------------- #
# Zeitreihe                                                                    #
# --------------------------------------------------------------------------- #

@dataclass
class Reihe:
    key: str
    punkte: list[tuple[str, float]] = field(default_factory=list)
    status: str = "ok"          # "ok" | "fehler"
    fehler: str | None = None
    quelle: str = ""

    @property
    def leer(self) -> bool:
        return not self.punkte

    @property
    def letzter_wert(self) -> float | None:
        return self.punkte[-1][1] if self.punkte else None

    @property
    def letztes_datum(self) -> str | None:
        return self.punkte[-1][0] if self.punkte else None

    def sortiert(self) -> "Reihe":
        self.punkte = sorted(self.punkte, key=lambda p: p[0])
        return self

    def wert_am(self, tag: str) -> float | None:
        """Letzter bekannter Wert am oder vor `tag`.

        Das ist die oekonomisch richtige Verknuepfung ungleich frequenter
        Reihen: Wer am 15. Maerz den Realzins bildet, kennt die Inflation des
        Februars, nicht die des Maerzes.
        """
        if not self.punkte:
            return None
        daten = [p[0] for p in self.punkte]
        i = bisect_right(daten, tag)
        return self.punkte[i - 1][1] if i else None

    def als_dict(self) -> dict:
        return {
            "key": self.key,
            "status": self.status,
            "fehler": self.fehler,
            "quelle": self.quelle,
            "letztes_datum": self.letztes_datum,
            "punkte": [[d, w] for d, w in self.punkte],
        }

    @staticmethod
    def aus_dict(roh: dict) -> "Reihe":
        return Reihe(
            key=roh["key"],
            punkte=[(p[0], p[1]) for p in roh.get("punkte", [])],
            status=roh.get("status", "ok"),
            fehler=roh.get("fehler"),
            quelle=roh.get("quelle", ""),
        )


def fehlerreihe(key: str, grund: str) -> Reihe:
    return Reihe(key=key, punkte=[], status="fehler", fehler=grund)


# --------------------------------------------------------------------------- #
# Speicherung                                                                  #
# --------------------------------------------------------------------------- #

def reihe_laden(key: str) -> Reihe | None:
    pfad = REIHEN / f"{key}.json"
    if not pfad.exists():
        return None
    try:
        return Reihe.aus_dict(json.loads(pfad.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, KeyError):
        return None


def reihe_speichern(reihe: Reihe) -> None:
    REIHEN.mkdir(parents=True, exist_ok=True)
    pfad = REIHEN / f"{reihe.key}.json"
    pfad.write_text(
        json.dumps(reihe.als_dict(), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def mit_bestand_verschmelzen(neu: Reihe) -> Reihe:
    """Bei Ausfall die zuletzt versionierten Werte behalten und markieren.

    Der Ausfall wird dabei nicht verschwiegen: status bleibt "fehler", und die
    Website zeigt an dem Chart einen sichtbaren Hinweis samt Datum des letzten
    erfolgreichen Abrufs. Stillschweigend veraltete Zahlen waeren die
    gefaehrlichste Variante - man wuerde einen technischen Ausfall fuer eine
    ereignislose Datenlage halten.
    """
    if neu.status == "ok" and not neu.leer:
        return neu
    alt = reihe_laden(neu.key)
    if alt is None or alt.leer:
        return neu
    alt.status = "fehler"
    alt.fehler = neu.fehler or "Abruf fehlgeschlagen"
    return alt


# --------------------------------------------------------------------------- #
# Umrechnungen                                                                 #
# --------------------------------------------------------------------------- #

def _monate_zurueck(tag: str, monate: int) -> str:
    j, m, t = int(tag[:4]), int(tag[5:7]), int(tag[8:10])
    gesamt = (j * 12 + (m - 1)) - monate
    j2, m2 = divmod(gesamt, 12)
    m2 += 1
    # Auf einen gueltigen Monatstag begrenzen (29. Februar, 31. April).
    letzter = [31, 29 if (j2 % 4 == 0 and (j2 % 100 != 0 or j2 % 400 == 0)) else 28,
               31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m2 - 1]
    return f"{j2:04d}-{m2:02d}-{min(t, letzter):02d}"


def jahresrate(basis: Reihe, key: str) -> Reihe:
    """Prozentuale Veraenderung gegenueber dem Wert zwoelf Monate zuvor."""
    aus = Reihe(key=key, quelle=f"abgeleitet aus {basis.key}")
    for tag, wert in basis.punkte:
        vor = basis.wert_am(_monate_zurueck(tag, 12))
        if vor is None or vor == 0:
            continue
        aus.punkte.append((tag, (wert / vor - 1.0) * 100.0))
    return aus


def differenz(minuend: Reihe, subtrahend: Reihe, key: str) -> Reihe:
    """Differenz zweier Reihen auf dem Datumsraster des Minuenden."""
    aus = Reihe(key=key, quelle=f"{minuend.key} minus {subtrahend.key}")
    for tag, wert in minuend.punkte:
        anderer = subtrahend.wert_am(tag)
        if anderer is None:
            continue
        aus.punkte.append((tag, wert - anderer))
    return aus


def quotient(zaehler: Reihe, nenner: Reihe, key: str, faktor: float = 1.0) -> Reihe:
    aus = Reihe(key=key, quelle=f"{zaehler.key} geteilt durch {nenner.key}")
    for tag, wert in zaehler.punkte:
        unten = nenner.wert_am(tag)
        if unten in (None, 0):
            continue
        aus.punkte.append((tag, wert / unten * faktor))
    return aus


def indexiert(reihe: Reihe, key: str, basis: float = 100.0) -> Reihe:
    if reihe.leer:
        return Reihe(key=key)
    start = reihe.punkte[0][1]
    if start == 0:
        return Reihe(key=key)
    return Reihe(key=key, quelle=f"{reihe.key} indexiert",
                 punkte=[(t, w / start * basis) for t, w in reihe.punkte])


def qoq_annualisiert(basis: Reihe, key: str) -> Reihe:
    """Quartalsrate auf Jahresrate hochgerechnet - die US-Konvention.

    Der Euroraum und China weisen die reine Quartalsrate aus. Ohne diese
    Umrechnung waeren die drei Reihen im selben Chart nicht vergleichbar: Aus
    0,5 % Quartalswachstum werden 2,0 % annualisiert.
    """
    aus = Reihe(key=key, quelle=f"abgeleitet aus {basis.key}")
    for i in range(1, len(basis.punkte)):
        vorher = basis.punkte[i - 1][1]
        jetzt = basis.punkte[i][1]
        if vorher <= 0:
            continue
        aus.punkte.append((basis.punkte[i][0], ((jetzt / vorher) ** 4 - 1.0) * 100.0))
    return aus


def kreditimpuls(basis: Reihe, key: str) -> Reihe:
    """Veraenderung der Kredit/BIP-Quote gegenueber dem Vorjahr.

    Der Kreditimpuls ist definitionsgemaess die zweite Ableitung des
    Kreditvolumens - also die Veraenderung der Veraenderung. Weil die
    BIS-Reihe bereits als Quote zum BIP vorliegt, genuegt hier die Differenz
    zum Vorjahreswert in Prozentpunkten.
    """
    aus = Reihe(key=key, quelle=f"abgeleitet aus {basis.key}")
    for tag, wert in basis.punkte:
        vor = basis.wert_am(_monate_zurueck(tag, 12))
        if vor is None:
            continue
        aus.punkte.append((tag, wert - vor))
    return aus


def forward_1j1j(kurz: Reihe, lang: Reihe, key: str) -> Reihe:
    """Impliziter Einjahressatz in einem Jahr aus 1J- und 2J-Rendite.

    Aus (1+r2)^2 = (1+r1)(1+f) folgt f = (1+r2)^2/(1+r1) - 1. Das ist der
    Satz, den der Markt fuer das kommende Jahr erwartet - die frei verfuegbare
    Entsprechung zu Fed-Funds-Futures und OeSTR-Forwards.
    """
    aus = Reihe(key=key, quelle=f"Forward aus {kurz.key} und {lang.key}")
    for tag, r2 in lang.punkte:
        r1 = kurz.wert_am(tag)
        if r1 is None:
            continue
        a, b = 1 + r2 / 100.0, 1 + r1 / 100.0
        if b <= 0:
            continue
        aus.punkte.append((tag, (a * a / b - 1.0) * 100.0))
    return aus


def zscore(basis: Reihe, key: str) -> Reihe:
    """Auf Standardabweichungen vom eigenen Mittel normieren.

    Der Grund ist kein statistischer, sondern ein Lesbarkeitsgrund: Der
    Philadelphia-Fed-Index schwankt um null in Spannen von plus/minus vierzig,
    der europaeische ESI um hundert in Spannen von plus/minus zwanzig. Auf einer
    gemeinsamen Achse waere die eine Reihe eine flache Linie am Rand. Die
    Alternative - zwei Y-Achsen - ist der haeufigste schwere Chartfehler
    ueberhaupt, weil sich durch Skalenwahl jede beliebige Korrelation
    herbeizeichnen laesst. Also normieren.
    """
    if len(basis.punkte) < 24:
        return Reihe(key=key)
    werte = [w for _, w in basis.punkte]
    mittel = sum(werte) / len(werte)
    varianz = sum((w - mittel) ** 2 for w in werte) / len(werte)
    streuung = varianz ** 0.5
    if streuung == 0:
        return Reihe(key=key)
    return Reihe(key=key, quelle=f"{basis.key} normiert",
                 punkte=[(t, (w - mittel) / streuung) for t, w in basis.punkte])


def cape_aufbau(gewinnrendite: Reihe, key: str) -> Reihe:
    """CAPE aus laufender Gewinnrendite, geglaettet ueber bis zu zehn Jahre.

    Solange keine zehn Jahre Historie vorliegen, wird ueber den bisher
    verfuegbaren Zeitraum geglaettet. Die Reihe traegt dann ein Kennzeichen,
    das die Website als "im Aufbau" ausweist - sie ist bis dahin ein
    geglaettetes KGV, kein echtes CAPE.
    """
    aus = Reihe(key=key, quelle=f"abgeleitet aus {gewinnrendite.key}")
    fenster: list[float] = []
    for tag, rendite in gewinnrendite.punkte:
        if rendite <= 0:
            continue
        fenster.append(rendite)
        fenster = fenster[-120:]           # 120 Monate = zehn Jahre
        schnitt = sum(fenster) / len(fenster)
        if schnitt > 0:
            aus.punkte.append((tag, 100.0 / schnitt))
    return aus


# --------------------------------------------------------------------------- #
# Kleinkram                                                                    #
# --------------------------------------------------------------------------- #

def heute() -> str:
    return date.today().isoformat()


def jetzt_utc() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def zahl(text: str) -> float | None:
    """Robuste Zahlkonvertierung. FRED liefert '.' fuer fehlende Werte."""
    if text is None:
        return None
    t = str(text).strip().replace(",", "")
    if t in ("", ".", "-", "n/a", "NA", "null", "None"):
        return None
    try:
        wert = float(t)
    except ValueError:
        return None
    return None if wert != wert else wert     # NaN aussortieren


def umgebung(name: str, pflicht: bool = True) -> str:
    wert = os.environ.get(name, "").strip()
    if not wert and pflicht:
        raise RuntimeError(
            f"Umgebungsvariable {name} fehlt. Im Repository unter "
            f"Settings > Secrets and variables > Actions als Secret anlegen."
        )
    return wert
