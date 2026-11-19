# ADR0026 · Native Workspace-Integration

Status: umgesetzt in R13 ab R12 db1a69f; wissenschaftliche Modellqualität und einzelne optionale Gegenproben begrenzt. S7-Bericht samt ausführbaren Proben und Wireframes wurde vollständig ausgewertet, nicht gemergt.

Problem: R12 hatte native Dokumente/Extraktion, aber Quellen-/Ergebnisnavigation, Seiteninteraktion, Graphanzeige und Profilwiederöffnung waren praktisch unzureichend. R11s eigene Geometrie-, Reader-, Modell- und Graphschichten sollen entfernt bleiben.

Alternativen: eigener SVG-/PDFviewer (erneute Doppelarbeit); großer React-/UI-Neubau (kein notwendiger Vorteil); HTML als einziger Reader (keine native Seiteninteraktion); Officekonvertierung als Voraussetzung (lokal nicht verfügbar, keine sichere Ref/Pixelparität); universeller ItemTable-Viewer (setzt berechnetes grid voraus); zweiter Python-Graphspeicher (unnötig). Gewählt: bestehende kleine Starlette-App, native Webkomponenten für Seiten, nativer HTMLserializer für Office, bedarfsgerechte table_cells-Fenster und ein Renderer vorhandener Graphdaten. Wireframe A bestimmt den Fokus, B nur den optionalen Vergleich.

Bibliotheken/Build:

| Bibliothek | Version / Lizenz | Zweck / Auslieferung | Alternative / Aufwand |
|---|---|---|---|
| @docling/docling-components |0.0.11 / MIT|native Seiten, Boxen, Tooltip, Text/Provenienz; ESM57308B|ersetzt eigene PDFseiten-HTMLsteuerung; eigener BBoxlayer verworfen|
| @docling/docling-core |2.106.0 / MIT|offizielle JS-Referenzauflösung; im Komponentenbundle|keine eigene Ref-Auflösungspipeline|
| Cytoscape.js |3.35.0 / MIT|ein lazy ESM451279B; native Layout/Fit/Interaktion|kein Python-Graphsystem, JSONdownload bleibt|
| Lit samt offiziellen Taskabhängigkeiten |lit3.3.3, lit-html3.3.3, lit-element4.2.2, reactive-element2.1.2, task1.0.3 / BSD-3-Clause|transitiv im Komponentenbundle; Notice mitgeliefert|kein zusätzlicher Appframework-Neubau|
| esbuild |0.25.11 / MIT|nur lokaler Build, kein Runtime-Server|ungebündelte Bare-Imports im Browser ungeeignet|
| jsdom |26.1.0 / MIT|nur Registrierung-/DOMtests|ersetzt keinen visuellen Browsernachweis|

`frontend/package-lock.json` fixiert Integritäten. Originales Komponenten-dist SHA25634f047f22965a0a1d4d08bf937f2e3ecd34e1f3e82e6311196ed7b44659dead9 stimmt mit S7 überein. Kleiner gemeinsamer ESMchunk106B; generierte Lizenzen9076B und Buildmetadaten2837B. Gesamte generierte Auslieferung520606B unkomprimiert. Kein CDN, React oder Node-Server. Minifizierte Fremdquellen werden lokal reproduziert und im Wheel mit Notices ausgeliefert, nicht als unlesbare Vendorblobs committed. Build: npm ci, npm run build; zwei zusätzliche Buildentrypoints exportieren native Bibliotheken. Exportnamespace verhindert unerwünschtes Wegoptimieren der custom-element-Registrierung bei sideEffects:false; tatsächlicher Bundle-DOMtest besteht.

Entscheidung: native Alias-JSONausgabe statt Ref-Rewrite; flache lokale Bildressourcen-Kopie statt veränderter Originaldatei. Ein Quellenzustand, öffentliche native Klickschnittstelle, echter Tooltip und Tastaturliste statt eigener Geometrieengine. Profilpersistenz enthält keine Geheimnisse; ein neues kleines models.py bündelt diese neue Verantwortung und die vorhandene native Konfiguration. Keine neue Modellklasse. Nativer Graph bleibt Ergebnisdatenquelle; UIqualifikation von IDs verändert ihn nicht.

Risiken/Grenzen: experimentelle Komponenten0.0.11 haben keine öffentliche Hover-/Fokussteuerung für alle SVGboxen. Host benötigt kleine Navigation und Tastaturalternative. Native HTML-/KI-Serializer großer Tabellen können grid materialisieren; nur Ansicht ist ohne Vollraster bewiesen. LibreOffice fehlt lokal; keine Derivatabnahme oder Officegeometrie behauptet. Parameterkonfiguration ist keine Gatewayfähigkeitsprüfung; Thinking fehlt öffentlich. Modellqualität bleibt PARTIAL, native Provenienz kein Humanreview. Browserdownload-Automation blockierte unerwartet lange, tatsächliche Exportdatei anschließend validiert. Ein veralteter Buildcache enthielt gelöschte R11-Dateien; verlustfrei außerhalb build gesichert, frisches Wheel geprüft. CI vergleicht Paketnamen und Dateiinhalt mit dem aktiven Quellbestand.

Nachweise und echte Lösch-/Wachstumsbilanz: [ACCEPTANCE](../ACCEPTANCE.md). Keine R14-Implementierung als Nebenwirkung.
