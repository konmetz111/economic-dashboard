/* Wochenbriefing - Aufbau der Seite und Zeichnen der Graphen.
 *
 * Bewusst ohne Chart-Bibliothek: Die Anforderung ist eng umrissen - Linien auf
 * einer Zeitachse, Ablesen per Zeiger, umschaltbare Fenster. Selbst gezeichnet
 * bleibt die Seite ohne Fremdabhaengigkeit, laedt sofort und laesst sich exakt
 * an die validierte Palette binden.
 *
 * Zwei Regeln aus den Gestaltungsvorgaben, die hier tragen:
 *  - Niemals zwei Y-Achsen. Reihen unterschiedlicher Groessenordnung werden
 *    schon beim Datenaufbau normiert oder auf eigene Graphen getrennt.
 *  - Farbe folgt der Reihe, nicht ihrem Rang. Das Abschalten einer Reihe ueber
 *    die Legende faerbt die uebrigen deshalb nicht um.
 */

const DATEN = "data";
const FENSTER = {
  max: { label: "Max", tage: null },
  "10y": { label: "10 Jahre", tage: 3653 },
  "5y": { label: "5 Jahre", tage: 1826 },
  "2y": { label: "2 Jahre", tage: 730 },
  "6m": { label: "6 Monate", tage: 183 },
  "1m": { label: "1 Monat", tage: 31 },
};

const TAG = 86400000;
const zahlformat = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 2 });
const datumformat = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "short", year: "numeric" });

const charts = new Map();
let standardFenster = "10y";

/* ------------------------------------------------------------- Helfer -- */

const $ = (auswahl, wurzel = document) => wurzel.querySelector(auswahl);
const el = (tag, klasse, text) => {
  const knoten = document.createElement(tag);
  if (klasse) knoten.className = klasse;
  if (text != null) knoten.textContent = text;
  return knoten;
};

function farbe(index) {
  const stil = getComputedStyle(document.documentElement);
  return stil.getPropertyValue(`--serie-${(index % 8) + 1}`).trim() || "#2a78d6";
}

function chrom(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Sinnvolle Nachkommastellen: Zinsen brauchen zwei, Indexstaende keine. */
function formatiere(wert, einheit = "") {
  if (wert == null || Number.isNaN(wert)) return "–";
  const betrag = Math.abs(wert);
  const stellen = betrag >= 1000 ? 0 : betrag >= 100 ? 1 : betrag >= 1 ? 2 : 4;
  const text = new Intl.NumberFormat("de-DE", {
    minimumFractionDigits: stellen === 4 ? 2 : stellen,
    maximumFractionDigits: stellen,
  }).format(wert);
  return einheit ? `${text} ${einheit}` : text;
}

function alsZeit(iso) { return Date.parse(iso + "T00:00:00Z"); }

/* --------------------------------------------------------- Chartobjekt -- */

class Zeitreihenchart {
  constructor(leinwand, daten) {
    this.leinwand = leinwand;
    this.ctx = leinwand.getContext("2d");
    this.daten = daten;
    this.fenster = standardFenster;
    this.zeiger = null;

    // Reihen einmalig in Zahlenpaare umrechnen. Das Neuzeichnen laeuft danach
    // ohne Datumsparsing, was bei taeglichen Reihen ueber Jahrzehnte zaehlt.
    this.reihen = daten.reihen
      .filter((r) => r.punkte && r.punkte.length)
      .map((r, i) => ({
        key: r.key,
        name: r.name,
        status: r.status,
        farbindex: i,
        sichtbar: true,
        punkte: r.punkte.map(([t, w]) => [alsZeit(t), w]),
      }));

    this.band = null;
    if (daten.band) {
      const von = this.reihen.find((r) => r.key === daten.band.von);
      const bis = this.reihen.find((r) => r.key === daten.band.bis);
      if (von && bis) {
        this.band = { von, bis, name: daten.band.name };
        // Das Band ist eine Aussage und belegt daher einen Farbslot, nicht zwei.
        von.imBand = bis.imBand = true;
        bis.farbindex = von.farbindex;
      }
    }

    this._binden();
  }

  get sichtbareReihen() {
    return this.reihen.filter((r) => r.sichtbar && !(this.band && r === this.band.bis));
  }

  _binden() {
    const c = this.leinwand;
    c.addEventListener("pointermove", (e) => this._zeigen(e));
    c.addEventListener("pointerdown", (e) => this._zeigen(e));
    c.addEventListener("pointerleave", () => this._verbergen());
    c.addEventListener("pointercancel", () => this._verbergen());
    c.addEventListener("keydown", (e) => this._tastatur(e));
    c.tabIndex = 0;
    c.setAttribute("role", "img");
  }

  /* -- Fensterlogik -- */

  spanne() {
    let ende = -Infinity;
    for (const r of this.reihen) if (r.punkte.length) ende = Math.max(ende, r.punkte.at(-1)[0]);
    if (!Number.isFinite(ende)) return null;
    const tage = FENSTER[this.fenster]?.tage;
    if (!tage) {
      let start = Infinity;
      for (const r of this.reihen) if (r.punkte.length) start = Math.min(start, r.punkte[0][0]);
      return [start, ende];
    }
    return [ende - tage * TAG, ende];
  }

  /** Punkte im Fenster plus je einem Anker davor und danach, damit die Linie
   *  am Rand nicht abreisst, sondern durchlaeuft. */
  ausschnitt(reihe, von, bis) {
    const p = reihe.punkte;
    let a = 0;
    while (a < p.length - 1 && p[a + 1][0] < von) a++;
    let b = p.length - 1;
    while (b > 0 && p[b - 1][0] > bis) b--;
    return p.slice(a, b + 1);
  }

  /* -- Zeichnen -- */

  zeichne() {
    const ctx = this.ctx;
    const verhaeltnis = window.devicePixelRatio || 1;
    const breite = this.leinwand.clientWidth;
    const hoehe = this.leinwand.clientHeight;
    if (!breite || !hoehe) return;

    this.leinwand.width = Math.round(breite * verhaeltnis);
    this.leinwand.height = Math.round(hoehe * verhaeltnis);
    ctx.setTransform(verhaeltnis, 0, 0, verhaeltnis, 0, 0);
    ctx.clearRect(0, 0, breite, hoehe);

    const spanne = this.spanne();
    if (!spanne) return;
    const [von, bis] = spanne;

    // Wertebereich aus dem Sichtfenster, nicht aus der ganzen Historie -
    // sonst waere jedes kurze Fenster eine waagrechte Linie.
    let unten = Infinity, oben = -Infinity;
    for (const r of this.sichtbareReihen) {
      for (const [t, w] of this.ausschnitt(r, von, bis)) {
        if (t < von || t > bis) continue;
        if (w < unten) unten = w;
        if (w > oben) oben = w;
      }
    }
    if (this.band && this.band.von.sichtbar) {
      for (const r of [this.band.von, this.band.bis]) {
        for (const [t, w] of this.ausschnitt(r, von, bis)) {
          if (t < von || t > bis) continue;
          if (w < unten) unten = w;
          if (w > oben) oben = w;
        }
      }
    }
    if (!Number.isFinite(unten)) return;

    for (const s of this.daten.schwellen || []) {
      if (s.wert >= unten - Math.abs(unten) && s.wert <= oben + Math.abs(oben)) {
        unten = Math.min(unten, s.wert); oben = Math.max(oben, s.wert);
      }
    }
    if (this.daten.nulllinie) { unten = Math.min(unten, 0); oben = Math.max(oben, 0); }

    if (unten === oben) { unten -= 1; oben += 1; }
    const luft = (oben - unten) * 0.08;
    unten -= luft; oben += luft;

    const rand = { oben: 12, rechts: 10, unten: 26, links: 56 };
    const plotB = breite - rand.links - rand.rechts;
    const plotH = hoehe - rand.oben - rand.unten;

    const x = (t) => rand.links + ((t - von) / (bis - von)) * plotB;
    const y = (w) => rand.oben + (1 - (w - unten) / (oben - unten)) * plotH;
    this._projektion = { x, y, von, bis, unten, oben, rand, plotB, plotH };

    this._raster(ctx, unten, oben, von, bis, rand, plotB, plotH, y, x);
    if (this.band && this.band.von.sichtbar) this._bandFlaeche(ctx, von, bis, x, y);
    for (const r of this.sichtbareReihen) this._linie(ctx, r, von, bis, x, y);
    if (this.zeiger != null) this._fadenkreuz(ctx, rand, plotH);

    this.leinwand.setAttribute(
      "aria-label",
      `${this.daten.titel}. ${this.sichtbareReihen.length} Reihen, Zeitraum ` +
      `${datumformat.format(von)} bis ${datumformat.format(bis)}. ` +
      `Die Werte stehen zusaetzlich in der Tabellenansicht.`
    );
  }

  _raster(ctx, unten, oben, von, bis, rand, plotB, plotH, y, x) {
    const linie = chrom("--raster");
    const achse = chrom("--achse");
    const text = chrom("--ink-gedaempft");

    ctx.font = '11px ui-monospace, SFMono-Regular, Menlo, monospace';
    ctx.lineWidth = 1;

    // Waagrechte Hilfslinien auf runden Werten.
    const schritt = this._schrittweite(oben - unten);
    ctx.strokeStyle = linie;
    ctx.fillStyle = text;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let w = Math.ceil(unten / schritt) * schritt; w <= oben; w += schritt) {
      const yy = Math.round(y(w)) + 0.5;
      ctx.beginPath(); ctx.moveTo(rand.links, yy); ctx.lineTo(rand.links + plotB, yy); ctx.stroke();
      ctx.fillText(zahlformat.format(w), rand.links - 8, yy);
    }

    // Nulllinie und Schwellen deutlicher als das Raster.
    ctx.textAlign = "left";
    if (this.daten.nulllinie && unten < 0 && oben > 0) {
      const yy = Math.round(y(0)) + 0.5;
      ctx.strokeStyle = achse; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(rand.links, yy); ctx.lineTo(rand.links + plotB, yy); ctx.stroke();
      ctx.lineWidth = 1;
    }
    for (const s of this.daten.schwellen || []) {
      if (s.wert < unten || s.wert > oben) continue;
      const yy = Math.round(y(s.wert)) + 0.5;
      ctx.save();
      ctx.setLineDash([3, 3]); ctx.strokeStyle = achse;
      ctx.beginPath(); ctx.moveTo(rand.links, yy); ctx.lineTo(rand.links + plotB, yy); ctx.stroke();
      ctx.restore();
      if (s.label) {
        ctx.fillStyle = text;
        ctx.fillText(s.label, rand.links + 4, yy - 7);
      }
    }

    // Zeitachse.
    ctx.strokeStyle = achse;
    ctx.beginPath();
    ctx.moveTo(rand.links, rand.oben + plotH + 0.5);
    ctx.lineTo(rand.links + plotB, rand.oben + plotH + 0.5);
    ctx.stroke();

    ctx.fillStyle = text;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (const marke of this._zeitmarken(von, bis, plotB)) {
      ctx.fillText(marke.text, x(marke.zeit), rand.oben + plotH + 7);
    }
  }

  _schrittweite(spanne) {
    const roh = spanne / 5;
    const groesse = Math.pow(10, Math.floor(Math.log10(roh)));
    const rest = roh / groesse;
    return (rest >= 5 ? 5 : rest >= 2 ? 2 : 1) * groesse;
  }

  _zeitmarken(von, bis, breite) {
    const tage = (bis - von) / TAG;
    const wieviele = Math.max(2, Math.min(7, Math.floor(breite / 90)));
    const marken = [];
    const a = new Date(von), b = new Date(bis);

    if (tage > 1500) {
      const schritt = Math.max(1, Math.ceil((b.getUTCFullYear() - a.getUTCFullYear()) / wieviele));
      for (let j = Math.ceil(a.getUTCFullYear() / schritt) * schritt; j <= b.getUTCFullYear(); j += schritt) {
        const zeit = Date.UTC(j, 0, 1);
        if (zeit >= von && zeit <= bis) marken.push({ zeit, text: String(j) });
      }
    } else if (tage > 120) {
      const schritt = Math.max(1, Math.round(tage / 30 / wieviele));
      let d = new Date(Date.UTC(a.getUTCFullYear(), a.getUTCMonth(), 1));
      while (d.getTime() <= bis) {
        if (d.getTime() >= von) {
          marken.push({
            zeit: d.getTime(),
            text: d.toLocaleDateString("de-DE", { month: "short", year: "2-digit", timeZone: "UTC" }),
          });
        }
        d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + schritt, 1));
      }
    } else {
      const schritt = Math.max(1, Math.round(tage / wieviele));
      for (let t = von; t <= bis; t += schritt * TAG) {
        marken.push({
          zeit: t,
          text: new Date(t).toLocaleDateString("de-DE", { day: "2-digit", month: "short", timeZone: "UTC" }),
        });
      }
    }
    return marken;
  }

  _bandFlaeche(ctx, von, bis, x, y) {
    const o = this.ausschnitt(this.band.bis, von, bis);
    const u = this.ausschnitt(this.band.von, von, bis);
    if (!o.length || !u.length) return;
    ctx.save();
    ctx.fillStyle = farbe(this.band.von.farbindex);
    ctx.globalAlpha = 0.16;
    ctx.beginPath();
    o.forEach(([t, w], i) => (i ? ctx.lineTo(x(t), y(w)) : ctx.moveTo(x(t), y(w))));
    for (let i = u.length - 1; i >= 0; i--) ctx.lineTo(x(u[i][0]), y(u[i][1]));
    ctx.closePath(); ctx.fill();
    ctx.restore();
  }

  _linie(ctx, reihe, von, bis, x, y) {
    const punkte = this.ausschnitt(reihe, von, bis);
    if (punkte.length < 1) return;
    ctx.save();
    ctx.strokeStyle = farbe(reihe.farbindex);
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.beginPath();
    punkte.forEach(([t, w], i) => (i ? ctx.lineTo(x(t), y(w)) : ctx.moveTo(x(t), y(w))));
    ctx.stroke();
    if (punkte.length === 1) {
      ctx.fillStyle = farbe(reihe.farbindex);
      ctx.beginPath(); ctx.arc(x(punkte[0][0]), y(punkte[0][1]), 3.5, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
  }

  _fadenkreuz(ctx, rand, plotH) {
    const { x, y } = this._projektion;
    const zeit = this.zeiger;
    ctx.save();
    ctx.strokeStyle = chrom("--achse");
    ctx.lineWidth = 1;
    const xx = Math.round(x(zeit)) + 0.5;
    ctx.beginPath(); ctx.moveTo(xx, rand.oben); ctx.lineTo(xx, rand.oben + plotH); ctx.stroke();

    for (const r of this.sichtbareReihen.concat(this.band && this.band.von.sichtbar ? [this.band.bis] : [])) {
      const treffer = this._letzterBis(r, zeit);
      if (!treffer) continue;
      // 2px Ring in Flaechenfarbe, damit sich ueberlagernde Punkte trennen.
      ctx.beginPath(); ctx.arc(x(treffer[0]), y(treffer[1]), 5.5, 0, Math.PI * 2);
      ctx.fillStyle = chrom("--flaeche"); ctx.fill();
      ctx.beginPath(); ctx.arc(x(treffer[0]), y(treffer[1]), 4, 0, Math.PI * 2);
      ctx.fillStyle = farbe(r.farbindex); ctx.fill();
    }
    ctx.restore();
  }

  /** Letzter Wert am oder vor `zeit` - oder null, wenn die Reihe da noch nicht lief.
   *
   *  Bewusst nicht "der naechstgelegene Punkt". Reihen beginnen zu sehr
   *  verschiedenen Zeitpunkten: Das Fed-Zielband gibt es erst seit Dezember
   *  2008, den japanischen Tagesgeldsatz seit 1985. Mit "naechstgelegen" haette
   *  ein Zeiger auf 1991 beim Fed-Zielband auf dessen ersten Punkt von 2008
   *  gegriffen und dieses Datum in die Kopfzeile geschrieben - der Tooltip
   *  behauptete dann Dezember 2008, waehrend die anderen Zeilen Werte von 1991
   *  zeigten. Wer erst gar keinen Wert hat, bekommt jetzt keine Zeile.
   */
  _letzterBis(reihe, zeit) {
    const p = reihe.punkte;
    if (!p.length || p[0][0] > zeit) return null;
    let lo = 0, hi = p.length - 1;
    while (lo < hi) {
      const mitte = (lo + hi + 1) >> 1;
      if (p[mitte][0] <= zeit) lo = mitte; else hi = mitte - 1;
    }
    return p[lo];
  }

  /* -- Ablesen -- */

  _zeigen(ereignis) {
    if (!this._projektion) return;
    const kasten = this.leinwand.getBoundingClientRect();
    const px = ereignis.clientX - kasten.left;
    const { x, von, bis, rand, plotB } = this._projektion;
    const anteil = Math.min(1, Math.max(0, (px - rand.links) / plotB));
    this.zeiger = von + anteil * (bis - von);
    this.zeichne();
    this._tipp(ereignis.clientX, kasten);
  }

  _tastatur(ereignis) {
    if (!this._projektion) return;
    const schritte = { ArrowLeft: -1, ArrowRight: 1 };
    if (!(ereignis.key in schritte)) return;
    ereignis.preventDefault();
    const { von, bis } = this._projektion;
    const weite = (bis - von) / 60;
    this.zeiger = Math.min(bis, Math.max(von, (this.zeiger ?? bis) + schritte[ereignis.key] * weite));
    this.zeichne();
    const kasten = this.leinwand.getBoundingClientRect();
    this._tipp(kasten.left + this._projektion.x(this.zeiger), kasten);
  }

  _verbergen() {
    this.zeiger = null;
    this.zeichne();
    $("#tipp").hidden = true;
  }

  _tipp(clientX, kasten) {
    const tipp = $("#tipp");
    tipp.innerHTML = "";

    const reihen = this.sichtbareReihen.concat(
      this.band && this.band.von.sichtbar ? [this.band.bis] : []);
    const treffer = reihen
      .map((r) => ({ r, p: this._letzterBis(r, this.zeiger) }))
      .filter((e) => e.p);
    if (!treffer.length) { tipp.hidden = true; return; }

    // Kopfzeile ist die Position des Zeigers, nicht das Datum irgendeiner
    // einzelnen Reihe. Jede Zeile darunter zeigt den zu diesem Zeitpunkt
    // zuletzt veroeffentlichten Wert - bei einer Quartalsreihe also den des
    // laufenden Quartals, bei einer Tagesreihe den des Vortags am Wochenende.
    tipp.append(el("div", "tipp-datum", datumformat.format(this.zeiger)));

    const zeileBauen = (farbindex, name, wert) => {
      const zeile = el("div", "tipp-zeile");
      const punkt = el("span", "punkt");
      punkt.style.background = farbe(farbindex);
      zeile.append(punkt, el("span", "name", name), el("span", "wert", wert));
      tipp.append(zeile);
    };

    // Das Band wird als eine Zeile mit Spanne ausgegeben, nicht als zwei
    // Einzelwerte - es ist im Diagramm auch eine Flaeche und ein
    // Legendeneintrag. Zwei Zeilen wuerden eine Groesse als zwei ausgeben.
    const bandGezeigt = this.band && this.band.von.sichtbar;
    if (bandGezeigt) {
      const u = this._letzterBis(this.band.von, this.zeiger);
      const o = this._letzterBis(this.band.bis, this.zeiger);
      if (u && o) {
        zeileBauen(this.band.von.farbindex, this.band.name,
                   `${formatiere(u[1])} – ${formatiere(o[1])}`);
      }
    }

    for (const { r, p } of treffer) {
      if (bandGezeigt && (r === this.band.von || r === this.band.bis)) continue;
      zeileBauen(r.farbindex, r.name, formatiere(p[1]));
    }

    tipp.hidden = false;
    const breite = tipp.offsetWidth;
    const links = Math.min(window.innerWidth - breite - 12,
                           Math.max(12, clientX - breite / 2));
    tipp.style.left = `${links}px`;
    tipp.style.top = `${Math.max(12, kasten.top - tipp.offsetHeight - 10)}px`;
  }

  setzeFenster(name) {
    this.fenster = name;
    this.zeiger = null;
    this.zeichne();
  }
}

/* -------------------------------------------------------- Kartenaufbau -- */

function standBadge(reihe) {
  const punkte = reihe.punkte || [];
  if (!punkte.length) return null;
  const [tag, wert] = punkte.at(-1);
  const huelle = el("div", "stand");
  huelle.append(el("span", "stand-wert", formatiere(wert)));

  const zielzeit = alsZeit(tag) - 30 * TAG;
  const vorher = punkte.filter(([t]) => alsZeit(t) <= zielzeit).at(-1);
  if (vorher) {
    const delta = wert - vorher[1];
    const pfeil = delta > 0 ? "▲" : delta < 0 ? "▼" : "▪";
    // Bewusst farblich neutral. Gruen fuer "gestiegen" waere hier eine
    // Wertung, und sie waere bei der Mehrzahl dieser Reihen falsch: Steigende
    // Kreditaufschlaege, steigende Inflation oder ein steigender
    // Finanzstressindex sind keine guten Nachrichten. Die Richtung sagt der
    // Pfeil, die Bewertung steht im Kommentar.
    huelle.append(el("span", "stand-delta",
      `${pfeil} ${formatiere(Math.abs(delta))} ggü. Vormonat`));
  }
  huelle.append(el("span", "stand-delta", `Stand ${tag}`));
  return huelle;
}

function marken(reihen) {
  const liste = el("span", "");
  for (const r of reihen) {
    let klasse = null, text = null;
    if (r.status === "nicht_verfuegbar") { klasse = "fehlt"; text = `${r.name}: nicht verfügbar`; }
    else if (r.status === "fehler") { klasse = "fehler"; text = `${r.name}: Abruf gescheitert`; }
    else if (r.status === "veraltet") { klasse = "veraltet"; text = `${r.name}: steht seit ${r.letztes_datum}`; }
    else if (r.aufbauend) { klasse = "aufbau"; text = `${r.name}: im Aufbau`; }
    if (klasse) liste.append(el("span", `marke ${klasse}`, text), document.createTextNode(" "));
  }
  return liste.childNodes.length ? liste : null;
}

function tabelle(daten) {
  const huelle = el("div", "tabelle-huelle");
  huelle.hidden = true;
  const t = el("table");
  const reihen = daten.reihen.filter((r) => r.punkte && r.punkte.length);

  const kopf = el("tr");
  kopf.append(el("th", "", "Datum"));
  for (const r of reihen) kopf.append(el("th", "", r.name));
  const thead = el("thead");
  thead.append(kopf);
  t.append(thead);

  const daten_map = reihen.map((r) => new Map(r.punkte));
  const alleTage = [...new Set(reihen.flatMap((r) => r.punkte.map(([t]) => t)))]
    .sort().reverse().slice(0, 400);

  const koerper = el("tbody");
  for (const tag of alleTage) {
    const zeile = el("tr");
    zeile.append(el("td", "", tag));
    daten_map.forEach((karte) => zeile.append(el("td", "", karte.has(tag) ? formatiere(karte.get(tag)) : "")));
    koerper.append(zeile);
  }
  t.append(koerper);
  huelle.append(t);
  return huelle;
}

function alsCSV(daten) {
  const reihen = daten.reihen.filter((r) => r.punkte && r.punkte.length);
  const karten = reihen.map((r) => new Map(r.punkte));
  const tage = [...new Set(reihen.flatMap((r) => r.punkte.map(([t]) => t)))].sort();
  const zeilen = [["Datum", ...reihen.map((r) => r.name)].join(";")];
  for (const tag of tage) {
    zeilen.push([tag, ...karten.map((k) => (k.has(tag) ? String(k.get(tag)).replace(".", ",") : ""))].join(";"));
  }
  return zeilen.join("\n");
}

function absatzweise(text) {
  const huelle = el("div", "");
  for (const teil of (text || "").split(/\n{2,}/)) {
    if (teil.trim()) huelle.append(el("p", "", teil.trim()));
  }
  return huelle;
}

function karteBauen(daten, kommentar) {
  const karte = el("article", "karte");
  karte.id = daten.id;
  karte.dataset.suchtext =
    `${daten.titel} ${daten.reihen.map((r) => r.name).join(" ")} ${daten.aussagekraft}`.toLowerCase();

  const kopf = el("div", "karte-kopf");
  const titel = el("div", "karte-titel");
  const h3 = el("h3");
  const anker = el("a", "", daten.titel);
  anker.href = `#${daten.id}`;
  h3.append(anker);
  titel.append(h3);
  if (daten.einheit) titel.append(el("p", "karte-einheit", daten.einheit));
  kopf.append(titel);

  const ersteMitDaten = daten.reihen.find((r) => r.punkte && r.punkte.length);
  if (ersteMitDaten && daten.reihen.filter((r) => r.punkte?.length).length === 1) {
    const badge = standBadge(ersteMitDaten);
    if (badge) kopf.append(badge);
  }
  karte.append(kopf);

  if (daten.aussagekraft) karte.append(el("p", "aussagekraft", daten.aussagekraft));

  const hinweise = marken(daten.reihen);
  if (hinweise) {
    const zeile = el("p", "reihenhinweis");
    zeile.append(hinweise);
    karte.append(zeile);
  }

  // Werkzeugleiste: Zeitfenster, Tabelle, CSV.
  const werkzeuge = el("div", "chart-werkzeuge");
  const fensterChips = el("div", "chips");
  werkzeuge.append(fensterChips);
  const rechts = el("div", "werkzeug-rechts");
  const tabellenKnopf = el("button", "chip", "Tabelle");
  tabellenKnopf.type = "button";
  tabellenKnopf.setAttribute("aria-pressed", "false");
  const csvKnopf = el("button", "chip", "CSV");
  csvKnopf.type = "button";
  rechts.append(tabellenKnopf, csvKnopf);
  werkzeuge.append(rechts);
  karte.append(werkzeuge);

  const buehne = el("div", "buehne");
  const leinwand = el("canvas");
  buehne.append(leinwand);
  karte.append(buehne);

  const chart = new Zeitreihenchart(leinwand, daten);
  charts.set(daten.id, chart);

  for (const [name, konf] of Object.entries(FENSTER)) {
    const chip = el("button", "chip", konf.label);
    chip.type = "button";
    chip.setAttribute("aria-pressed", String(name === standardFenster));
    chip.addEventListener("click", () => {
      fensterChips.querySelectorAll(".chip").forEach((c) =>
        c.setAttribute("aria-pressed", String(c === chip)));
      chart.setzeFenster(name);
    });
    fensterChips.append(chip);
  }

  // Legende - ab zwei Reihen Pflicht, bei einer nennt der Titel die Reihe.
  if (chart.sichtbareReihen.length > 1 || chart.band) {
    const legende = el("div", "legende");
    const eintraege = chart.band
      ? [{ name: chart.band.name, farbindex: chart.band.von.farbindex, ziel: chart.band.von }]
        .concat(chart.reihen.filter((r) => !r.imBand).map((r) => ({ name: r.name, farbindex: r.farbindex, ziel: r })))
      : chart.reihen.map((r) => ({ name: r.name, farbindex: r.farbindex, ziel: r }));

    for (const eintrag of eintraege) {
      const knopf = el("button");
      knopf.type = "button";
      knopf.setAttribute("aria-pressed", "true");
      const punkt = el("span", "punkt");
      punkt.style.background = farbe(eintrag.farbindex);
      knopf.append(punkt, el("span", "", eintrag.name));
      knopf.addEventListener("click", () => {
        const an = knopf.getAttribute("aria-pressed") === "true";
        knopf.setAttribute("aria-pressed", String(!an));
        eintrag.ziel.sichtbar = !an;
        if (chart.band && eintrag.ziel === chart.band.von) chart.band.bis.sichtbar = !an;
        chart.zeichne();
      });
      legende.append(knopf);
    }
    karte.append(legende);
  }

  const tab = tabelle(daten);
  karte.append(tab);
  tabellenKnopf.addEventListener("click", () => {
    tab.hidden = !tab.hidden;
    tabellenKnopf.setAttribute("aria-pressed", String(!tab.hidden));
  });
  csvKnopf.addEventListener("click", () => {
    const blob = new Blob(["﻿" + alsCSV(daten)], { type: "text/csv;charset=utf-8" });
    const a = el("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${daten.id}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });

  if (daten.hinweis) karte.append(el("p", "reihenhinweis", daten.hinweis));

  if (kommentar?.text) {
    const block = el("div", "kommentar");
    block.append(el("h4", "", "Bedeutung und mögliche Folgen"));
    block.append(absatzweise(kommentar.text));
    karte.append(block);
  }

  if (daten.schwaeche) {
    const s = el("p", "schwaeche");
    s.append(el("b", "", "Schwäche"), document.createTextNode(daten.schwaeche));
    karte.append(s);
  }

  const quelle = el("p", "quelle");
  quelle.append(el("span", "", `Quelle: ${daten.quelle || "–"}`));
  if (kommentar?.erzeugt_mit) {
    quelle.append(el("span", "", `Kommentar: ${kommentar.erzeugt_mit}`));
  }
  karte.append(quelle);

  return karte;
}

/* --------------------------------------------------------------- Start -- */

async function hole(pfad) {
  const antwort = await fetch(`${DATEN}/${pfad}`, { cache: "no-cache" });
  if (!antwort.ok) throw new Error(`${pfad}: HTTP ${antwort.status}`);
  return antwort.json();
}

/** Das tatsaechlich sichtbare Thema, auch wenn der Nutzer nie umgeschaltet hat.
 *  Ohne diese Aufloesung waere der erste Klick auf den Schalter bei einem
 *  hellen Betriebssystem wirkungslos: Er wuerde von "nicht gesetzt" auf "hell"
 *  stellen, also auf den Zustand, der ohnehin schon zu sehen ist. */
function aktuellesThema() {
  const gesetzt = document.documentElement.dataset.theme;
  if (gesetzt === "dark" || gesetzt === "light") return gesetzt;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function themaSetzen(wert) {
  document.documentElement.dataset.theme = wert;
  try { localStorage.setItem("briefing-thema", wert); } catch {}
  $("#thema-text").textContent = wert === "dark" ? "Hell" : "Dunkel";
  for (const c of charts.values()) c.zeichne();
}

function warnungen(meta) {
  const echte = (meta.probleme || []).filter((p) => p.status !== "ok");
  if (!echte.length) return;
  const kasten = el("section", "warnung-kasten");
  kasten.append(el("h2", "", `${echte.length} Reihen mit Befund im letzten Lauf`));
  kasten.append(el("p", "", "Die betroffenen Graphen zeigen den letzten erfolgreich " +
    "abgerufenen Stand. Sie sind unten am jeweiligen Indikator gekennzeichnet."));
  const liste = el("ul");
  for (const p of echte.slice(0, 12)) {
    liste.append(el("li", "", `${p.chart} / ${p.reihe} — ${p.status}` +
      (p.grund ? `: ${p.grund}` : "") + (p.letztes_datum ? ` (Stand ${p.letztes_datum})` : "")));
  }
  kasten.append(liste);
  $("#warnbereich").append(kasten);
}

async function start() {
  let meta, kommentare = { charts: {} };
  try {
    meta = await hole("meta.json");
  } catch (fehler) {
    $("#ladehinweis").textContent =
      "Die Daten konnten nicht geladen werden. Vermutlich ist der erste " +
      "Aktualisierungslauf noch nicht durchgelaufen. " + fehler.message;
    return;
  }
  try { kommentare = await hole("commentary.json"); } catch {}

  standardFenster = meta.standard_fenster in FENSTER ? meta.standard_fenster : "10y";

  $("#seitentitel").textContent = meta.titel;
  $("#seitenuntertitel").textContent = meta.untertitel;
  $("#meta-datenstand").textContent = meta.erzeugt.replace("T", " ").replace("Z", " UTC");
  $("#meta-modell").textContent = kommentare.modell || "–";
  $("#meta-umfang").textContent =
    `${meta.charts.length} Graphen, ${meta.charts.reduce((s, c) => s + c.reihen.length, 0)} Reihen`;
  document.title = meta.titel;

  if (kommentare.gesamtlage) {
    $("#lage").hidden = false;
    $("#lage-text").append(absatzweise(kommentare.gesamtlage));
    $("#lage-fuss").textContent =
      `Erzeugt ${kommentare.erzeugt?.replace("T", " ").replace("Z", " UTC")} mit ${kommentare.modell}. ` +
      `Sämtliche Zahlen darin stammen aus den unten stehenden Reihen.`;
  }

  warnungen(meta);

  // Globale Fensterumschaltung.
  const global = $("#globale-fenster");
  for (const [name, konf] of Object.entries(FENSTER)) {
    const chip = el("button", "chip", konf.label);
    chip.type = "button";
    chip.setAttribute("aria-pressed", String(name === standardFenster));
    chip.addEventListener("click", () => {
      global.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", String(c === chip)));
      for (const c of charts.values()) c.setzeFenster(name);
      document.querySelectorAll(".karte .chart-werkzeuge .chips .chip").forEach((c) =>
        c.setAttribute("aria-pressed", String(c.textContent === konf.label)));
    });
    global.append(chip);
  }

  // Gruppen und Karten anlegen; die Daten je Chart kommen erst beim Scrollen.
  const behaelter = $("#gruppen");
  behaelter.innerHTML = "";
  const nav = $("#sprungnav");

  for (const gruppe of meta.gruppen) {
    const charts_der_gruppe = meta.charts.filter((c) => c.gruppe === gruppe.id);
    if (!charts_der_gruppe.length) continue;

    const link = el("a", "", gruppe.titel);
    link.href = `#gruppe-${gruppe.id}`;
    nav.append(link);

    const abschnitt = el("section", "gruppe");
    abschnitt.id = `gruppe-${gruppe.id}`;
    const kopf = el("div", "gruppe-kopf");
    kopf.append(el("h2", "", gruppe.titel));
    if (gruppe.einleitung) kopf.append(el("p", "", gruppe.einleitung));
    abschnitt.append(kopf);

    const karten = el("div", "karten");
    for (const uebersicht of charts_der_gruppe) {
      const platzhalter = el("article", "karte");
      platzhalter.id = uebersicht.id;
      platzhalter.dataset.laden = uebersicht.id;
      platzhalter.append(el("h3", "karte-titel", uebersicht.titel));
      karten.append(platzhalter);
    }
    abschnitt.append(karten);
    behaelter.append(abschnitt);
  }

  // Verzoegertes Laden: 34 Graphen auf einmal zu zeichnen kostet spuerbar Zeit.
  const beobachter = new IntersectionObserver(async (eintraege) => {
    for (const eintrag of eintraege) {
      if (!eintrag.isIntersecting) continue;
      const knoten = eintrag.target;
      // unobserve allein genuegt nicht: Zwischen zwei Rueckrufen liegt ein
      // await, und ein bereits eingereihter zweiter Rueckruf fuer denselben
      // Knoten laeuft trotzdem noch. Ohne diese Sperre entstuende die Karte
      // zweimal - die zweite Fassung wuerde den Eintrag in `charts`
      // ueberschreiben und haenge dann an einem Canvas ausserhalb des
      // Dokuments. Umschalten und Neuzeichnen liefen ins Leere.
      if (knoten.dataset.geladen) continue;
      knoten.dataset.geladen = "1";
      beobachter.unobserve(knoten);
      const id = knoten.dataset.laden;
      try {
        const daten = await hole(`chart-${id}.json`);
        const karte = karteBauen(daten, kommentare.charts?.[id]);
        knoten.replaceWith(karte);
        charts.get(id).zeichne();
      } catch (fehler) {
        knoten.append(el("p", "reihenhinweis", `Konnte nicht geladen werden: ${fehler.message}`));
      }
    }
  }, { rootMargin: "600px 0px" });

  document.querySelectorAll("[data-laden]").forEach((k) => beobachter.observe(k));

  // Scrollspy fuer die Sprungnavigation.
  const spy = new IntersectionObserver((eintraege) => {
    for (const e of eintraege) {
      if (!e.isIntersecting) continue;
      nav.querySelectorAll("a").forEach((a) =>
        a.setAttribute("aria-current", String(a.hash === `#${e.target.id}`)));
    }
  }, { rootMargin: "-20% 0px -70% 0px" });
  document.querySelectorAll(".gruppe").forEach((g) => spy.observe(g));

  // Suche.
  $("#suchfeld").addEventListener("input", (e) => {
    const begriff = e.target.value.trim().toLowerCase();
    let sichtbar = 0;
    document.querySelectorAll(".karte").forEach((k) => {
      const passt = !begriff || (k.dataset.suchtext || k.textContent.toLowerCase()).includes(begriff);
      k.hidden = !passt;
      if (passt) sichtbar++;
    });
    document.querySelectorAll(".gruppe").forEach((g) => {
      g.hidden = ![...g.querySelectorAll(".karte")].some((k) => !k.hidden);
    });
    $("#leertreffer").hidden = sichtbar > 0;
  });

  if (location.hash) {
    const ziel = document.querySelector(location.hash);
    if (ziel) setTimeout(() => ziel.scrollIntoView(), 100);
  }

  try {
    const archiv = await hole("archiv/index.json");
    if (archiv.length > 1) {
      $("#archiv-zeile").textContent =
        `Archiv: ${archiv.length} frühere Ausgaben unter data/archiv/ im Repository.`;
    }
  } catch {}
}

/* Thema wiederherstellen, bevor gezeichnet wird. */
try {
  const gespeichert = localStorage.getItem("briefing-thema");
  if (gespeichert) document.documentElement.dataset.theme = gespeichert;
} catch {}
$("#thema-text").textContent = aktuellesThema() === "dark" ? "Hell" : "Dunkel";
$("#thema-schalter").addEventListener("click", () =>
  themaSetzen(aktuellesThema() === "dark" ? "light" : "dark"));

// Folgt dem Betriebssystem, solange nicht ausdruecklich umgeschaltet wurde.
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  const gesetzt = document.documentElement.dataset.theme;
  if (gesetzt === "dark" || gesetzt === "light") return;
  $("#thema-text").textContent = aktuellesThema() === "dark" ? "Hell" : "Dunkel";
  for (const c of charts.values()) c.zeichne();
});

let neuzeichnen;
window.addEventListener("resize", () => {
  clearTimeout(neuzeichnen);
  neuzeichnen = setTimeout(() => { for (const c of charts.values()) c.zeichne(); }, 120);
});

start();
