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
- **Stufe 2 ruft keine Webseiten ab.** Auch nicht ergaenzend oder zur Kontrolle.
  Sie kennt nur `data/kennzahlen.json` und hat keinen Zugang zu Nachrichten.
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
  herbeizuzeichnen. Erledigte Faelle: `stimmung` (normiert), `berkshire` und
  `berkshire_cash` (getrennt).
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
  Rechenzentren drosselt - auf dem Actions-Runner kann sie ausfallen.

Alle scheitern absichtlich laut mit einer Meldung, die sagt, welche Datei
anzupassen ist. Kein stiller Rueckfall auf Naeherungswerte.

## Fallen, die schon einmal zugeschnappt sind

Diese vier Fehler waren im ersten Entwurf drin und sind alle vom Typ "laeuft
durch, liefert aber Falsches". Sie sind behoben; die Kommentare im Code
erklaeren jeweils warum. Nicht rueckgaengig machen:

1. **Shiller-URL nicht fest verdrahten.** Der Pfad traegt eine Versionskennung.
   Eine alte Adresse antwortet mit HTTP 200 und einer zwei Jahre alten Datei.
2. **Yahoo nie mit `range=max` abfragen.** Die Schnittstelle verdichtet dann auf
   Monatswerte, obwohl `interval=1d` gesetzt ist, ohne das anzuzeigen.
   `period1`/`period2` verwenden.
3. **EZB ohne `detail=dataonly`.** Der Parameter aendert je nach Datenfluss die
   Spaltennamen oder loest HTTP 400 aus.
4. **SEC-Konzeptbezeichnungen altern.** Berkshires Cash-Konzept heisst seit 2018
   anders; die alten Namen liefern klaglos eine Reihe, die 2017 endet.

## Aufbauende Reihen

`build_data.py` kann Reihen verlaengern statt ersetzen, wenn das Quellmodul
`ANHAENGEND = True` setzt - fuer Quellen, die nur den aktuellen Wert liefern.
Derzeit nutzt das kein Modul: Der dafuer vorgesehene iShares-Abruf hat sich als
nicht durchfuehrbar erwiesen (siehe README). Der Mechanismus bleibt, weil er
fuer eine kuenftige europaeische Gewinnquelle gebraucht wird. Sobald wieder eine
solche Reihe existiert, gilt: **`data/series/*.json` ist versioniert und darf
nicht geloescht werden** - dort liegt dann die einzige Kopie ihrer Historie.

## Zeitplanung

Cron steht auf Montag 06:00 UTC und ist UTC-fest. Eine in Ortszeit gedachte
Planung verrutscht bei der Zeitumstellung gegen die Veroeffentlichungstermine
der Statistikaemter.
