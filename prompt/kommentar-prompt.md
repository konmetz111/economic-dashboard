# Wochenauftrag: Kommentare zum volkswirtschaftlichen Briefing

Du schreibst zwei Dinge: unter jeden Graphen einen kurzen Absatz zu den
möglichen Folgen, und über alle Graphen die Zusammenfassung „Lage auf einen
Blick". Stufe 1 (GitHub Actions) hat die Daten bereits abgerufen und sämtliche
Kennzahlen ausgerechnet.

## Datenquellen

**Die Zahlen** kommen ausschließlich aus `data/kennzahlen.json`. Diese Datei
enthält je Graph alles Gerechnete:

| Feld | Bedeutung |
|---|---|
| `titel`, `einheit` | Bezeichnung und Maßeinheit |
| `was_der_indikator_misst` | die Erläuterung, die auf der Seite über dem Graphen steht |
| `bekannte_schwaeche` | wo der Indikator lügt oder Fehlsignale liefert |
| `schwellenwerte` | historische Faustregeln, sofern es welche gibt |
| `reihen[]` | je Reihe: `stand`, `wert`, `frequenz`, `aenderung_woche/monat/quartal/jahr`, `perzentil_10j`, `min_10j`, `max_10j`, `mittel_10j` |

**Den Nachrichtenstand** recherchierst du selbst im Netz. Das ist ausdrücklich
erwünscht: Ohne Nachrichten kannst du keine Ursachen und keine Folgen benennen,
sondern nur Zahlen umschreiben – und genau das soll hier nicht passieren.

### Die Grenze zwischen beidem

**Jede Zahl in deinem Text muss aus `kennzahlen.json` stammen.** Aus den
Nachrichten übernimmst du Ereignisse, Beschlüsse, Begründungen und
Einordnungen – aber keine Messwerte. Kein Kurs, keine Rate, kein Stand, keine
Veränderung aus einer Nachrichtenquelle. Pressezahlen sind gerundet, veraltet
oder falsch abgeschrieben, und der Unterschied fällt im Briefing niemandem auf.

Qualitative Aussagen aus den Nachrichten sind dagegen willkommen: dass die Fed
getagt hat, dass ein Zollpaket in Kraft tritt, dass ein Streik die Produktion
stillgelegt hat, dass die Lage am Ölmarkt sich politisch zugespitzt hat.

Rechne auch nichts selbst aus – keine Prozentsätze, keine Differenzen, keine
Durchschnitte. Fehlt eine Angabe, die du für einen Satz bräuchtest, schreib den
Satz nicht.

## Die drei Zustände einer Reihe – unbedingt auseinanderhalten

- **`status: "ok"`** – aktueller Wert, normal kommentieren.
- **`status: "veraltet"`** – der Abruf lief, aber die Quelle hat nicht
  aktualisiert. Im Feld `warnung` steht seit wann. **Schreibe ausdrücklich, dass
  der Wert nicht aktuell ist**, und nenne das Datum. Ein technischer Stillstand
  darf sich nicht wie eine ruhige Datenlage lesen.
- **`status: "nicht_verfuegbar"`** – für diese Größe gibt es keine frei
  automatisierbare Quelle. Der Grund steht in
  `grund_der_nichtverfuegbarkeit`. Erwähne das knapp, suche keinen Ersatz und
  schätze nichts.

## Zuerst: Stand holen und Frische prüfen

**Hole den aktuellen Stand, bevor du etwas liest.** Stufe 1 committet, und das
kann nach dem Klonen deiner Sitzung passiert sein:

    git pull --rebase origin main

Lies dann `erzeugt_utc` und `datenstand` am Kopf von `data/kennzahlen.json`.
Liegt `erzeugt_utc` mehr als **acht Tage** zurück, wurde Stufe 1 nicht
ausgeführt. Schreibe dann **keine Kommentare**, überschreibe
`docs/data/commentary.json` nicht, und melde stattdessen, dass die Kennzahlen
veraltet sind, mit dem Zeitstempel.

**Setze nicht voraus, dass die Zahlen von heute sind.** Stufe 1 ist samstags
früh geplant, aber GitHub stellt Cron-Läufe in eine Warteschlange und
verzögerte den Abruf seit Oktober 2026 regelmäßig um vier bis sechs Stunden –
also bis nach deinem Lauf. Der Datenstand, auf dem du arbeitest, ist dann der
der Vorwoche, und die frischeren Zahlen kommen erst Stunden später dazu. Zwei
Folgen:

- **Beziehe dich im Text nie auf „heute" oder „die Zahlen dieser Woche".** Was
  du schreibst, kann neben einem jüngeren Datenstand erscheinen. Die Seite weist
  das an jeder Karte aus, aber dein Text darf keine Frische behaupten, die er
  nicht hat. Schreibe über die Lage, nicht über den Tag.
- **Dein Text wird nicht mehr überschrieben.** Stufe 1 lässt eine vorhandene
  Fassung stehen, solange sie nicht älter als acht Tage ist. Es gibt also keinen
  Grund zur Eile und keinen, einen halbfertigen Stand zu committen.

Hat ein früherer Lauf **denselben** `datenstand` schon kommentiert – in
`docs/data/commentary.json` steht dieser Datenstand und eine `gesamtlage` –,
dann ändere nichts und committe nichts. Melde es in einem Satz. Eine zweite
Fassung derselben Zahlen bringt niemandem etwas.

## Was du je Graph schreibst

**Genau ein Absatz, drei bis vier Sätze.**

Darin ausschließlich: **was aus der aktuellen Lage plausibel folgt.** Du darfst
auf die Ursachen der Entwicklung eingehen und sollst dafür den
Nachrichtenstand heranziehen.

Was **nicht** hineingehört:

- **Keine Wiedergabe der Zahlen.** Der Stand steht auf der Seite neben dem
  Graphen, die Veränderungen liest man an der Kurve ab. Ein Satz wie „Der Euro
  notiert bei 1,1193 Dollar und hat gegenüber dem Vormonat 0,0434 verloren" ist
  verschenkter Platz. Einzelne Zahlen als Belegstelle sind erlaubt, wenn der
  Satz sie wirklich braucht – nicht als Aufzählung.
- **Keine Erklärung, was der Indikator misst.** Dieser Text steht vom
  Herausgeber selbst über dem Graphen. Wiederholung ist überflüssig.
- Keine Anlageberatung, keine Kauf- oder Verkaufsempfehlung, keine Kursziele.

Formuliere als begründete Erwartung mit Unsicherheit, nicht als Vorhersage, und
nenne wo möglich, was die Erwartung widerlegen würde.

**Zum Ton:** Schreib so, dass man es gerne liest. Konkret heißt das: kurze
Hauptsätze, Aktiv statt Passiv, keine Floskeln („es bleibt spannend",
„angesichts der Tatsache, dass"), keine aufzählenden Dreierfiguren, keine
Einleitungssätze, die nur ankündigen, was kommt. Fang mit der Sache an. Nüchtern
und präzise, aber nicht steif – wie ein guter Wirtschaftsjournalist, der weiß,
dass seine Leser wenig Zeit haben.

## Was du zusätzlich schreibst: die Lage auf einen Blick

**Rund zehn kurze Sätze in drei Absätzen. Nicht mehr.**

Dieser Text fasst die **Nachrichtenlage** zu den Themen des Briefings zusammen –
Geldpolitik, Kredit und Liquidität, Bewertung, Konjunktur, Rohstoffe. Was ist in
der vergangenen Woche passiert, das für diese Größen zählt? Notenbanksitzungen,
Konjunkturdaten, politische Beschlüsse, Marktbewegungen und ihre Begründungen.

**Keine Aufzählung von Werten und Veränderungen.** Der bisherige Text begann mit
einer Bestandsaufnahme der Datenlage und zählte Perzentile auf; das ist gestrichen.
Wenn eine Zahl den Punkt trägt, nenne sie – aber der Text lebt von den
Ereignissen, nicht von den Ständen.

Achte auf **Konfluenz**: Mehrere unabhängige Entwicklungen, die in dieselbe
Richtung zeigen, sind mehr wert als ein einzelner Ausschlag. Nenne ausdrücklich,
wo sich die Signale widersprechen.

## Ausgabeziel

Schreibe `docs/data/commentary.json` mit genau dieser Struktur:

```json
{
  "erzeugt": "<ISO-Zeitstempel UTC, z. B. 2026-10-24T05:12:00Z>",
  "datenstand": "<Feld datenstand aus kennzahlen.json, unverändert>",
  "gesamtlage": "Absatz eins.\n\nAbsatz zwei.\n\nAbsatz drei.",
  "charts": {
    "<chart-id>": { "text": "Ein Absatz, drei bis vier Sätze." }
  }
}
```

Für **jede** `id` aus `kennzahlen.json` muss ein Eintrag unter `charts`
existieren – auch für Graphen, deren Reihen sämtlich nicht verfügbar sind. Dort
genügt ein Satz, der den Grund nennt.

Anschließend committen und pushen:

```
git add docs/data/commentary.json
git commit -m "Kommentare <JJJJ-MM-TT>"
git push
```

Committe **ausschließlich** `docs/data/commentary.json`. Nichts anderes – die
Datenstände gehören Stufe 1. Ohne diesen Commit ist die Arbeit verloren, sobald
die Cloud-Sitzung endet.
