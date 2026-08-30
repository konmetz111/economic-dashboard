# Wochenauftrag: Kommentare zum volkswirtschaftlichen Briefing

Du schreibst die Kommentare unter den Graphen des Wochenbriefings und die
Zusammenfassung „Lage auf einen Blick" darüber. Stufe 1 (GitHub Actions) hat
die Daten bereits abgerufen und sämtliche Kennzahlen ausgerechnet.

## Datenquelle – ausschließlich lokale Dateien

Lies **ausschließlich** `data/kennzahlen.json`. Rufe **keine** Webseiten ab –
auch nicht ergänzend, zur Kontrolle oder bei Zweifeln an einer Zahl. Die Datei
enthält je Graph alles, was du brauchst:

| Feld | Bedeutung |
|---|---|
| `titel`, `einheit` | Bezeichnung und Maßeinheit |
| `was_der_indikator_misst` | die Erläuterung, die auf der Seite über dem Graphen steht |
| `bekannte_schwaeche` | wo der Indikator lügt oder Fehlsignale liefert |
| `schwellenwerte` | historische Faustregeln, sofern es welche gibt |
| `reihen[]` | je Reihe: `stand`, `wert`, `frequenz`, `aenderung_woche/monat/quartal/jahr`, `perzentil_10j`, `min_10j`, `max_10j`, `mittel_10j` |

## Die harte Regel: rechnen ist nicht deine Aufgabe

**Verwende ausschließlich die Zahlen aus `reihen[]`.** Rechne nichts selbst aus –
keine Prozentsätze, keine Differenzen, keine Durchschnitte, keine Umrechnungen.
Erfinde keine Zahl, keinen Termin, kein Zitat und kein Ereignis. Du hast keinen
Zugang zu Nachrichten und weißt nicht, was diese Woche passiert ist. Alles, was
du sagen kannst, steht in der Datei.

Fehlt eine Angabe, die du für einen Satz bräuchtest, dann schreib den Satz nicht.

## Die drei Zustände einer Reihe – unbedingt auseinanderhalten

- **`status: "ok"`** – aktueller Wert, normal kommentieren.
- **`status: "veraltet"`** – der Abruf lief, aber die Quelle hat nicht
  aktualisiert. Im Feld `warnung` steht seit wann. **Schreibe ausdrücklich, dass
  der Wert nicht aktuell ist**, und nenne das Datum. Ein technischer Stillstand
  darf sich nicht wie eine ruhige Datenlage lesen.
- **`status: "nicht_verfuegbar"`** – für diese Größe gibt es keine frei
  automatisierbare Quelle. Der Grund steht in
  `grund_der_nichtverfuegbarkeit`. Fasse ihn in einem Satz zusammen. Suche
  keinen Ersatz und schätze nichts.

## Frische der Daten prüfen

Lies zuerst `erzeugt_utc` und `datenstand` am Kopf der Datei. Liegt
`erzeugt_utc` mehr als **acht Tage** zurück, wurde Stufe 1 nicht ausgeführt.
Schreibe dann **keine Kommentare**, überschreibe `docs/data/commentary.json`
nicht, und melde stattdessen, dass die Kennzahlen veraltet sind, mit dem
Zeitstempel.

## Was du je Graph schreibst

Genau zwei Absätze, getrennt durch eine Leerzeile:

1. **Bedeutung.** Was sagen die jüngsten Zahlen? Nenne den Stand und die
   relevanteste Veränderung, ordne sie historisch ein – dafür sind
   `perzentil_10j`, `min_10j`, `max_10j` und `mittel_10j` da. Wähle den
   Vergleichszeitraum passend zur `frequenz`: bei einer Quartalsreihe niemals
   „gegenüber dem Vormonat".
2. **Folgen.** Was folgt daraus plausibel für Konjunktur, Zinsen oder Märkte?
   Formuliere als begründete Erwartung mit Unsicherheit, nicht als Vorhersage.
   Nenne, was diese Erwartung widerlegen würde.

Je Absatz zwei bis vier Sätze. Nüchtern, präzise, ohne Werbesprache und ohne
Floskeln wie „es bleibt spannend". Berücksichtige `bekannte_schwaeche`: Ein
Indikator mit dokumentiertem Fehlalarm-Problem darf nicht als Beweis auftreten.

## Was du zusätzlich schreibst: die Gesamtlage

Drei bis vier Absätze über alle Graphen hinweg. Achte auf **Konfluenz** –
mehrere unabhängige Gruppen, die in dieselbe Richtung zeigen, sind
aussagekräftiger als ein einzelner Ausschlag. Nenne ausdrücklich, wo sich
Indikatoren widersprechen. Halte die Wirkungskette ein: Liquidität und Kredit
laufen vorne, Umfragen folgen, Gewinne danach, harte Konjunkturdaten zuletzt;
Bewertung sagt etwas über die Dekade und nichts über das nächste Jahr.

## Keine Anlageberatung

Keine Kauf- oder Verkaufsempfehlung, keine Kursziele, keine Aussage darüber,
was jemand tun sollte. Du beschreibst die Lage und ihre plausiblen Folgen.

## Ausgabeziel

Schreibe `docs/data/commentary.json` mit genau dieser Struktur:

```json
{
  "erzeugt": "<ISO-Zeitstempel UTC, z. B. 2026-09-07T07:12:00Z>",
  "datenstand": "<Feld datenstand aus kennzahlen.json, unverändert>",
  "gesamtlage": "Absatz eins.\n\nAbsatz zwei.\n\nAbsatz drei.",
  "modell": "Cloud-Routine",
  "charts": {
    "<chart-id>": { "text": "Absatz eins.\n\nAbsatz zwei.", "erzeugt_mit": "Cloud-Routine" }
  }
}
```

Für **jede** `id` aus `kennzahlen.json` muss ein Eintrag unter `charts`
existieren – auch für Graphen, deren Reihen sämtlich nicht verfügbar sind. Dort
genügt ein Absatz, der den Grund nennt.

Anschließend committen und pushen:

```
git add docs/data/commentary.json
git commit -m "Kommentare <JJJJ-MM-TT>"
git push
```

Committe **ausschließlich** `docs/data/commentary.json`. Nichts anderes – die
Datenstände gehören Stufe 1. Ohne diesen Commit ist die Arbeit verloren, sobald
die Cloud-Sitzung endet.
