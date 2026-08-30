# CLAUDE.md

Woechentliches volkswirtschaftliches Briefing als statische Seite auf GitHub
Pages. Der Ablauf ist bewusst dreigeteilt; die Trennung ist inhaltlich begruendet
und sollte nicht zusammengelegt werden.

## Architektur

| Stufe | Wo | Was | Warum getrennt |
|---|---|---|---|
| 1 | `scripts/build_data.py` | Abruf, Ableitung, Aktualitaetspruefung | Laeuft ohne Sprachmodell und kostet daher kein Nutzungslimit |
| 2 | `scripts/build_commentary.py` | Kennzahlen rechnen, Text formulieren lassen | Siehe unten - die Zahlen entstehen in Python, nicht im Modell |
| 3 | `docs/` | Statische Seite, laedt die JSON-Dateien | Kein Backend, keine Fremdabhaengigkeit |

## Verbindliche Regeln

- **Zahlen kommen nie aus dem Sprachmodell.** `build_commentary.py` rechnet
  Stand, Veraenderungen, Perzentil und Schwellenlage in Python aus und uebergibt
  sie als Block `KENNZAHLEN`. Das Modell formuliert ausschliesslich. Wer diese
  Reihenfolge umdreht, holt sich erfundene Zahlen ins Briefing.
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
