# Volkswirtschaftliches Wochenbriefing

Woechentlich aktualisierte Zeitreihen zu Geldpolitik, Liquiditaet, Bewertung,
Marktpsychologie, Konjunktur und Rohstoffen fuer USA, Euroraum und Japan - als
statische Seite auf GitHub Pages, mit einem kurzen Kommentar unter jedem Graphen.

**Seite:** https://konmetz111.github.io/economic-dashboard/

## Wie es laeuft

Zwei strikt getrennte Stufen, die an **verschiedenen Orten** laufen - dasselbe
Muster wie im Schwesterprojekt `news-briefing`.

| Stufe | Wo | Was | Kosten |
|---|---|---|---|
| 1 | GitHub Actions (`.github/workflows/update.yml`) | `build_data.py` ruft alle Reihen ab und schreibt `docs/data/chart-*.json`; `build_kennzahlen.py` rechnet daraus jede Kennzahl aus und legt `data/kennzahlen.json` als Uebergabe an | nichts, laeuft ohne Sprachmodell |
| 2 | Claude-Code-Cloud-Routine (`prompt/kommentar-prompt.md`) | Liest `data/kennzahlen.json`, recherchiert den Nachrichtenstand, formuliert die Kommentare, schreibt `docs/data/commentary.json` zurueck und committet sie | laeuft ueber das Claude-Abo, keine API-Abrechnung |
| — | GitHub Pages | Liefert `docs/` als Website aus | nichts |

Die Trennung ist keine Formsache, sondern der Kern des Entwurfs: **Saemtliche
Zahlen werden in Stufe 1 in Python gerechnet und dem Sprachmodell fertig
uebergeben.** Stufe 2 formuliert nur und darf ausdruecklich nichts selbst
rechnen. Damit kann im Kommentar keine Zahl stehen, die nicht vorher
ausgerechnet wurde.

Stufe 2 darf seit Oktober 2026 im Netz recherchieren, weil sich Ursachen und
Folgen ohne Nachrichtenstand nicht benennen lassen. Die Grenze bleibt: Aus den
Nachrichten kommen Ereignisse und Einordnungen, **niemals Messwerte**.
Pressezahlen sind gerundet, veraltet oder falsch abgeschrieben, und der
Unterschied faellt im Briefing niemandem auf.

Stufe 1 schreibt zusaetzlich einen regelbasierten Grundtext in
`commentary.json`. Faellt Stufe 2 aus, steht dort also weiterhin ein korrekter,
nur nuechterner Zahlenbefund statt einer Luecke - erkennbar am Feld
`erzeugt_mit`, das die Website unter jedem Graphen anzeigt. Ist der Kommentar
aelter als die Daten, vermerkt die Seite auch das im Kopf.

## Einrichtung

1. **FRED-Schluessel besorgen** - kostenlos unter
   https://fredaccount.stlouisfed.org/apikeys
2. **Secret anlegen** unter *Settings -> Secrets and variables -> Actions*:
   `FRED_API_KEY`. Ein Anthropic-Schluessel wird **nicht** gebraucht.
3. **Pages einschalten** unter *Settings -> Pages*: Source `Deploy from a branch`,
   Branch `main`, Ordner `/docs`.
4. **Ersten Lauf ausloesen** unter *Actions -> Wochenbriefing aktualisieren ->
   Run workflow*.
5. **Cloud-Routine einrichten** mit `prompt/kommentar-prompt.md` als Auftrag.
   Sie braucht nur GitHub-Zugriff - sie ruft keine Webseiten ab, sondern liest
   ausschliesslich die committete Datei `data/kennzahlen.json`.

Die Seite laedt die Graphen erst beim Scrollen. `?alle` an die Adresse gehaengt
laedt alle 35 sofort - gebraucht zum Ausdrucken und beim Pruefen einzelner
Graphen.

## Zeitplan

| Stufe | Zeit (UTC) | Was |
|---|---|---|
| 1 | Samstag 04:00 | Actions holt die Daten und rechnet die Kennzahlen |
| 2 | Samstag 05:00 | Routine formuliert die Kommentare und committet sie |

Die Reihenfolge ist zwingend, die Stunde dazwischen der Puffer. Wer eine Zeit
aendert, muss die andere mitziehen - laeuft die Routine vor dem Abruf,
kommentiert sie die Zahlen der Vorwoche.

## Sichtbarkeit

Die Seite traegt `<meta name="robots" content="noindex, nofollow">` und taucht
damit in keiner Suchmaschine auf. **Oeffentlich erreichbar bleibt sie
trotzdem** - GitHub Pages kennt fuer oeffentliche Repositories keinen
Zugriffsschutz. Wer die Adresse kennt, kommt hinein. Wirklich nicht-oeffentlich
wird die Seite nur mit einem privaten Repository und GitHub Pages im
Enterprise-Tarif, oder indem man sie woanders hinter einer Anmeldung ausliefert.

## Lokal ausfuehren

```bash
pip install -r requirements.txt
export FRED_API_KEY=...
python scripts/build_data.py
python scripts/build_kennzahlen.py
python -m http.server -d docs 8000
```

Einzelne Graphen erneuern, ohne alles abzurufen:

```bash
python scripts/build_data.py --nur kreditspreads,zinskurve
```

## Einen Indikator hinzufuegen

Alles steht in `config/indicators.yaml`; Code ist dafuer in der Regel nicht
noetig. Ein Eintrag unter `charts:` erzeugt einen Graphen samt Erklaertext,
Kommentar und Quellenangabe. Braucht eine Reihe eine Vorstufe - etwa den
Indexstand, aus dem eine Jahresrate wird -, kommt diese unter `rohreihen:`.

Verfuegbare `adapter`: `fred`, `ecb`, `eurostat`, `oecd`, `yahoo`, `shiller`,
`finra`, `sec_edgar`, `stoxx`, `berechnet`.

Verfuegbare Formeln fuer `berechnet`: `differenz`, `jahresrate`,
`qoq_annualisiert`, `kreditimpuls`, `zscore`, `cape_aufbau`, `quotient`,
`quotient_prozent`, `quotient_indexiert`, `quotient_index_ab`, `forward_1j1j`,
`index_ab`, `linearkombination`, `durchschleifen`.

Weitere Felder je Reihe: `farbe` und `farbe_dunkel` (Hexwerte je Modus),
`strich: gestrichelt`, `frist_tage` (eigene Veraltungstoleranz, wenn der Verzug
zur Quelle gehoert), `verfuegbar: false` mit `grund`. Je Chart zusaetzlich
`achse: {typ: symlog, knick: 10}` fuer eine ab dem Knick gestauchte Wertachse
und `legende_erzwingen: true`.

## Ausfallverhalten

Der wichtigste Entwurfsgrundsatz des Projekts: **Ein technischer Ausfall darf
sich nie wie eine ereignislose Datenlage lesen.**

- Faellt eine Quelle aus, bleibt der letzte erfolgreiche Stand stehen, aber die
  Reihe traegt den Status `fehler` - sichtbar als Marke am Graphen und in einem
  Kasten oben auf der Seite.
- Laeuft der Abruf durch, ohne dass die Quelle aktualisiert hat, bekommt die
  Reihe den Status `veraltet` mit dem Datum des letzten Wertes.
- Schlaegt mehr als die Haelfte aller Reihen fehl, bricht der Lauf ab und
  committet nichts. Das ist dann kein Quellenproblem, sondern ein Netz- oder
  Schluesselproblem.

## Bekannte Grenzen

Nicht alles Gewuenschte ist frei verfuegbar. Wo ein Ersatz verwendet wird, steht
das als *Schwaeche* unter dem jeweiligen Graphen. Die wichtigsten Faelle:

| Gewuenscht | Warum nicht | Was stattdessen |
|---|---|---|
| Forward-KGV (S&P 500, MSCI World, DAX, ATX) | Analystenschaetzungen sind lizenziert (FactSet, LSEG) | Nachlaufendes KGV nur fuer den S&P 500, aus dem Shiller-Datensatz |
| ISM und PMI | seit 2016 lizenzpflichtig, nicht mehr auf FRED | Philadelphia-Fed-Index und OECD-Geschaeftsklima Euroraum, auf Standardabweichungen normiert |
| Conference Board LEI | proprietaer | OECD Composite Leading Indicator |
| A/D-Linie NYSE | keine freie Breadth-Quelle | Verhaeltnis RSP zu SPY |
| Fed-Funds-Futures, OeSTR-Forwards | CME und Eurex lizenziert | Forward-Pfad aus der Staatsanleihekurve |
| Chinesischer Kreditimpuls | PBoC-TSF ohne freie Schnittstelle | BIS-Kredit/BIP-Quote, Impuls gerechnet |
| Shiller-CAPE Europa, Aktienrisikopraemie Europa | keine freie Quelle fuer die Gewinne eines europaeischen Index | entfaellt, siehe unten |
| Put/Call-Ratio | die freie Cboe-Datei endet 2019 | entfaellt; der VIX misst dasselbe Phaenomen |
| Berkshire-Gesamtbarreserve | die kurzlaufenden Staatsanleihen tragen kein eigenes XBRL-Konzept | eng gefasste Zahlungsmittel, ausdruecklich gekennzeichnet |
| BIP China | die FRED-Reihe endet 2023, keine freie Quartalsalternative gefunden | entfaellt; der Kreditimpuls bleibt der China-Indikator |
| Fruehindikator Euroraum | kein aktueller zusammengesetzter Index frei verfuegbar | entfaellt; die Einzelbausteine stehen ohnehin im Briefing |
| Wilshire 5000 als Buffett-Zaehler | Wilshires FRED-Reihen wurden eingestellt | Unternehmensaktien aus der Fed-Finanzierungsrechnung (Z.1) |

Ausdruecklich **nicht** enthalten, weil kein tragfaehiger Weg gefunden wurde:
CAPE Europa, Aktienrisikopraemie Europa und das KGV des MSCI World. Der Plan
war, das nachlaufende KGV von den iShares-Produktseiten zu lesen und
woechentlich fortzuschreiben. BlackRock liefert die Kennzahl aber nicht im
Seitenquelltext, sondern laedt sie ueber eine Schnittstelle nach, die ohne
Sitzungskennung nicht erreichbar ist. Findet sich eine freie Gewinnquelle fuer
einen europaeischen Index, sind diese drei Reihen schnell nachgeruestet.

## Getestet, und was dabei herauskam

Alle 55 Abrufe wurden gegen das echte Netz geprueft, danach lief ein
vollstaendiger Durchlauf. Der erste Test hatte 17 Ausfaelle von 28, der zweite
brachte weitere eingestellte FRED-Reihen ans Licht. Unter anderem:

- **Stooq** hat eine JavaScript-Bot-Sperre und antwortet auf jeden
  automatischen Abruf mit HTML statt CSV. Ersetzt durch LBMA (Gold, Silber) und
  Yahoo (Kupfer, Weizen, DXY, RSP, SPY).
- **Yahoo** verdichtet bei `range=max` stillschweigend auf Monatswerte, obwohl
  Tagesdaten angefordert sind - beim S&P-500-ETF 404 statt 8453 Punkte. Deshalb
  wird ein explizites Zeitfenster uebergeben.
- **Shillers Datei** hat eine Versionskennung im Downloadpfad. Eine fest
  verdrahtete Adresse liefert weiterhin HTTP 200, aber eine zwei Jahre alte
  Fassung. Die aktuelle Adresse wird jetzt von der Startseite gelesen.
- **Die EZB-Schnittstelle** aendert mit `detail=dataonly` je nach Datenfluss die
  Spaltennamen oder antwortet mit HTTP 400. Der Parameter ist entfernt. Ausserdem
  kommt die Eurosystem-Bilanz im ISO-Wochenformat `2026-W34`.
- **Die SEC** weist User-Agents ohne Mozilla-Praefix ab, und auch solche, die
  eine URL enthalten.
- **Berkshires Cash-Konzept** heisst seit 2018 anders; die alten Bezeichnungen
  lieferten anstandslos eine Reihe, die neun Jahre zu frueh endete.
- **Eingestellte FRED-Reihen antworten weiter.** Die OECD-Fruehindikatoren
  (`USALOLITONOSTSAM`, `EA19LOLITONOSTSAM`), das chinesische BIP
  (`CHNGDPNQDSMEI`) und das Euroraum-Geschaeftsklima lieferten ohne Murren
  Werte - die letzten von Januar 2024, Juli 2023 bzw. November 2022. Der
  Fruehindikator kommt jetzt direkt von der OECD, die beiden anderen entfallen.
- **Der FRED-Schluessel stand in Fehlermeldungen.** FRED erwartet ihn als
  URL-Parameter; `requests` schreibt die volle URL in seine Ausnahme, und diese
  Meldung waere ueber `docs/data/meta.json` auf der oeffentlichen Website
  gelandet. `sources/fred.py` entfernt ihn jetzt, und `sources/__init__.py`
  filtert zusaetzlich jede Meldung aller Module gegen `api_key`, `token`,
  `secret` und `password`.

### Die Fallen, die schon zugeschnappt sind

Alle vom Typ "laeuft durch, liefert aber Falsches". Sie sind behoben; die
Kommentare im Code erklaeren jeweils warum. Nicht rueckgaengig machen:

1. **Shiller-URL nicht fest verdrahten.** Der Pfad traegt eine
   Versionskennung. Eine alte Adresse antwortet mit HTTP 200 und einer zwei
   Jahre alten Datei.
2. **Yahoo nie mit `range=max` abfragen.** Die Schnittstelle verdichtet dann
   auf Monatswerte, obwohl `interval=1d` gesetzt ist, ohne das anzuzeigen.
3. **EZB ohne `detail=dataonly`.** Der Parameter aendert je nach Datenfluss die
   Spaltennamen oder loest HTTP 400 aus.
4. **SEC-Konzeptbezeichnungen altern.** Berkshires Cash-Konzept heisst seit
   2018 anders; die alten Namen liefern klaglos eine Reihe, die 2017 endet.
5. **Der FRED-Schluessel stand in Fehlermeldungen**, die ueber `meta.json` auf
   der oeffentlichen Seite gelandet waeren. Wird jetzt an zwei Stellen
   herausgefiltert.
6. **`h_vstoxx.txt` ist seit Februar 2016 tot.** Sie laedt weiter mit HTTP 200
   und liefert 4357 saubere Punkte - nur enden sie vor einem Jahrzehnt. Die
   lebende Datei heisst `h_v2tx.txt` und hat ein anderes Format. Aufgefallen ist
   es erst, als die Aktualitaetspruefung 3901 Tage Rueckstand meldete.
7. **Die BIS-Reihe `CRDQCNAPABIS` ist ein Kreditbestand in Milliarden Yuan**,
   keine BIP-Quote. Der daraus gerechnete "Kreditimpuls" ergab Achsenwerte um
   15.000 statt Prozentpunkte. Richtig ist `QCNPAM770A`.
8. **Eurostat-Filtercodes pruefen.** Der Indikator heisst `PRD`, nicht `PROD`,
   und der Einzelhandelsumsatz `VOL_SLS`, nicht `TOVV`. Ein falscher Code
   liefert keinen Fehler, sondern eine gueltige Struktur mit null Werten.
   `sources/eurostat.py` prueft deshalb, dass jede Filterdimension genau eine
   Kategorie trifft.
9. **www.stoxx.com sendet sein Zwischenzertifikat nicht.** Windows holt es
   selbsttaetig nach, OpenSSL und damit Python nicht - der Abruf brach
   monatelang ab, lokal wie auf dem Runner. Das fehlende Zertifikat liegt jetzt
   unter `scripts/certs/`; die Pruefung bleibt vollstaendig aktiv.

### Fragile Stellen

`finra` (fester XLSX-Pfad), `shiller` (Spaltenanordnung in einer Excel-Datei),
`yahoo` (drosselt Zugriffe aus Rechenzentren) und `sec_edgar` (die SEC-WAF ist
beim User-Agent eigen). Alle scheitern laut und sichtbar, nicht still.

### Was dauerhaft stillsteht

Das Industrievertrauen fuer den Euroraum endet im Januar 2026 - bei der OECD
ueber FRED und bei Eurostat gleichermassen, eine dritte freie Quelle gibt es
nicht. Die Reihe bleibt deshalb als veraltet gekennzeichnet, statt den
Rueckstand mit einer grosszuegigen Toleranz unsichtbar zu machen.

## Farben

Die Farbcodes je Reihe stehen in `config/indicators.yaml` (`farbe` fuer den
Hellmodus, `farbe_dunkel` fuer den Dunkelmodus). Rot steht fuer die USA, Blau
fuer den Euroraum, damit die Zuordnung ueber alle Graphen gleich bleibt.

Zwei Faelle brauchen Sorgfalt. Erstens Dunkelmodus: `#B31942` und `#003399`
erreichen auf dem dunklen Grund nur 2,6 bzw. 1,6 zu 1 und sind dort kaum zu
erkennen - deshalb die aufgehellten Varianten `#CE1D4C` und `#085AFF` im selben
Farbton. Zweitens Hellmodus: Weizen `#F5DEB3` (1,3 zu 1) und Gold `#EFBF04`
(1,7 zu 1) sind auf der hellen Flaeche fast unsichtbar. Statt die Farbe zu
verfaelschen zeichnet die Website unter solche Linien eine dunklere Kontur - der
Farbton bleibt, die Linie wird sichtbar. Die Schwelle dafuer steht in
`docs/app.js` in `_linie`.

## Haftung

Diese Seite stellt Kennzahlen dar. Sie ist keine Anlageberatung und keine
Empfehlung zu einzelnen Anlagen. Die genannten Schwellenwerte sind historische
Faustregeln, ueberwiegend aus US-Daten, und haben mehrfach Fehlsignale geliefert.
