# CLAUDE.md

Woechentliches volkswirtschaftliches Briefing als statische Seite auf GitHub
Pages. Der Ablauf ist bewusst dreigeteilt; die Trennung ist inhaltlich begruendet
und sollte nicht zusammengelegt werden.

## Architektur

Zwei strikt getrennte Stufen an **verschiedenen Orten** - dasselbe Muster wie im
Schwesterprojekt `news-briefing`.

| Stufe | Wo | Was | Netzzugang |
|---|---|---|---|
| 1 | GitHub Actions | `build_data.py` (Abruf, Ableitung, Aktualitaetspruefung) und `build_kennzahlen.py` (rechnet jede Kennzahl aus, schreibt `data/kennzahlen.json`) | frei |
| 2 | Claude-Code-Cloud-Routine | Liest `data/kennzahlen.json`, formuliert, schreibt und committet `docs/data/commentary.json`. Auftrag: `prompt/kommentar-prompt.md` | nur GitHub noetig |
| — | `docs/` | Statische Seite, laedt die JSON-Dateien | kein Backend |

Die Aufteilung hat zwei Gruende. Erstens laeuft Stufe 1 ohne Sprachmodell und
kostet daher kein Nutzungslimit. Zweitens - und wichtiger - kommen so
saemtliche Zahlen aus Python. Anders als beim news-briefing ist die Sandbox hier
kein Zwang: Stufe 2 braucht nur GitHub-Zugriff, weil sie ausschliesslich
committete Dateien liest.

## Verbindliche Regeln

- **Zahlen kommen nie aus dem Sprachmodell.** `build_kennzahlen.py` rechnet
  Stand, Veraenderungen ueber vier Zeitraeume, Perzentil, Spannweite und Mittel
  in Python aus und legt sie in `data/kennzahlen.json` ab. Die Routine
  formuliert ausschliesslich und darf nichts selbst rechnen. Wer diese
  Reihenfolge umdreht, holt sich erfundene Zahlen ins Briefing.
- **Stufe 2 darf recherchieren, aber keine Zahlen uebernehmen.** Seit Oktober
  2026 hat die Routine WebSearch und WebFetch, weil sich Ursachen und Folgen
  ohne Nachrichtenstand nicht benennen lassen. Die Grenze ist scharf: Ereignisse
  und Einordnungen ja, Messwerte nein. Diese Grenze nicht aufweichen - eine
  gerundete Pressezahl neben den exakten Reihen faellt niemandem auf.
- **Stufe 2 committet ausschliesslich `docs/data/commentary.json`.** Die
  Datenstaende gehoeren Stufe 1; ein Commit von `data/` oder `docs/data/chart-*`
  aus der Routine heraus wuerde den naechsten Actions-Lauf mit einem Konflikt
  begruessen.
- **Der regelbasierte Grundtext bleibt.** `build_kennzahlen.py` schreibt bei
  jedem Lauf eine nuechterne Fassung in `commentary.json`. Faellt die Routine
  aus, steht dort ein korrekter Zahlenbefund statt einer Luecke. Diesen
  Rueckfallweg nicht entfernen.
- **Ein technischer Ausfall darf sich nie wie eine ereignislose Datenlage
  lesen.** Faellt eine Quelle aus, bleibt der letzte Stand stehen, aber die
  Reihe traegt `status: fehler` bzw. `veraltet` - sichtbar als Marke am Graphen
  und in einem Kasten oben auf der Seite. Diese Kennzeichnung nie entfernen.
- **Niemals zwei Y-Achsen in einem Graphen.** Reihen unterschiedlicher
  Groessenordnung werden normiert (`zscore`), indexiert oder auf zwei Graphen
  getrennt. Zwei Skalen erlauben es, jede beliebige Korrelation
  herbeizuzeichnen. Erledigte Faelle: `stimmung` (normiert),
  `zentralbankbilanz` (auf 2007 indexiert, weil Dollar und Euro nicht
  vergleichbar sind).
- **Eine gestauchte Achse ist erlaubt, eine zweite Achse nicht.** Bei den
  Jahresraten (`bip`, `einzelhandel`, `industrieproduktion`) steht
  `achse: {typ: symlog, knick: 10}`: bis zehn Prozentpunkte linear, darueber
  logarithmisch gestaucht. Ohne das druecken die Ausschlaege von 2020 alle
  uebrigen Jahre zu einer flachen Linie. Die Verzerrung ist am engeren
  Linienabstand sichtbar und damit nicht verschwiegen - anders als bei zwei
  Achsen, wo sie unsichtbar bleibt.
- **Die Farbreihenfolge in `styles.css` ist keine Geschmacksfrage.** Sie stammt
  aus der validierten Referenzpalette der dataviz-Vorgaben; die Slot-Reihenfolge
  ist die Absicherung gegen Farbfehlsichtigkeit. Wer sie aendert, muss
  `scripts/validate_palette.js` aus dem dataviz-Skill erneut laufen lassen -
  fuer beide Modi und gegen die tatsaechlichen Flaechenfarben.

## Aenderungen am Indikatorensatz

Alles steht in `config/indicators.yaml`. Ein Eintrag unter `charts:` erzeugt
Graph, Erklaertext, Kommentar und Quellenangabe. Vorstufen - etwa der
Indexstand, aus dem eine Jahresrate wird - kommen unter `rohreihen:`. Python
ist dafuer in der Regel nicht anzufassen.

## Die fragilen Stellen

- `sources/finra.py` haengt an einem festen XLSX-Pfad.
- `sources/shiller.py` haengt an der Spaltenanordnung in `ie_data.xls`.
- `sources/yahoo.py` haengt an einer Schnittstelle, die Zugriffe aus
  Rechenzentren drosselt.
- `sources/sec_edgar.py` haengt an einer WAF, die beim User-Agent eigen ist.

Alle scheitern absichtlich laut mit einer Meldung, die sagt, welche Datei
anzupassen ist. Kein stiller Rueckfall auf Naeherungswerte.

## Fallen, die schon zugeschnappt sind

Alle vom Typ "laeuft durch, liefert aber Falsches" - die gefaehrlichste Klasse,
weil ein gruener Lauf sie nicht zeigt. Behoben; die Kommentare im Code erklaeren
jeweils warum. Nicht rueckgaengig machen. Der vollstaendige Katalog mit
Begruendungen steht im README; in Kurzform:

1. Shiller-URL nicht fest verdrahten (Versionskennung im Pfad).
2. Yahoo nie mit `range=max` (verdichtet still auf Monatswerte).
3. EZB ohne `detail=dataonly`.
4. SEC-Konzeptbezeichnungen altern.
5. Der FRED-Schluessel stand in Fehlermeldungen, die auf der Website landen.
6. `h_vstoxx.txt` ist seit Februar 2016 tot und laedt trotzdem; die lebende
   Datei heisst `h_v2tx.txt`.
7. `CRDQCNAPABIS` ist ein Kreditbestand in Milliarden Yuan, keine BIP-Quote.
8. Eurostat-Filtercodes: `PRD` nicht `PROD`, `VOL_SLS` nicht `TOVV` - ein
   falscher Code liefert eine gueltige Struktur mit null Werten.
9. www.stoxx.com sendet sein Zwischenzertifikat nicht (liegt in `scripts/certs/`).

Gemeinsamer Nenner: **Aktualitaetspruefung schlaegt Abrufpruefung.** Fuenf der
neun Faelle haetten keinen Fehler erzeugt. Entdeckt wurden sie, weil
`build_data.py` das Alter jeder Reihe prueft. Diese Pruefung nicht
abschwaechen, nur weil eine Warnung unbequem ist - dafuer gibt es `frist_tage`
je Reihe, und zwar nur dann, wenn der Verzug zur Quelle gehoert.

## Aufbauende Reihen

`build_data.py` kann Reihen verlaengern statt ersetzen, wenn das Quellmodul
`ANHAENGEND = True` setzt - fuer Quellen, die nur den aktuellen Wert liefern.
Derzeit nutzt das kein Modul: Der dafuer vorgesehene iShares-Abruf hat sich als
nicht durchfuehrbar erwiesen (siehe README). Der Mechanismus bleibt, weil er
fuer eine kuenftige europaeische Gewinnquelle gebraucht wird. Sobald wieder eine
solche Reihe existiert, gilt: **`data/series/*.json` ist versioniert und darf
nicht geloescht werden** - dort liegt dann die einzige Kopie ihrer Historie.

## Zeitplanung

Beide Stufen laufen samstags, und ihre Reihenfolge ist zwingend:

| Stufe | Zeit | Was |
|---|---|---|
| 1 | Samstag 04:00 UTC | GitHub Actions holt die Daten und schreibt `data/kennzahlen.json` |
| 2 | Samstag 05:00 UTC | Cloud-Routine liest diese Datei und schreibt `docs/data/commentary.json` |

Die Stunde dazwischen ist der Puffer. Wer eine der beiden Zeiten aendert, muss
die andere mitziehen: Laeuft die Routine vor dem Abruf, kommentiert sie die
Zahlen der Vorwoche - und weil `commentary.json` danach trotzdem gueltig
aussieht, faellt das nur ueber den Abgleich von `datenstand` auf, den die
Website im Kopf anzeigt.

Beide Cron-Zeiten sind UTC-fest. Das ist Absicht: Eine in Ortszeit gedachte
Planung verrutscht bei der Zeitumstellung gegen die Veroeffentlichungstermine
der Statistikaemter.
