# ADR 0014 · Docling-native Konsolidierung R2

Datum: 11.11.2026 · Basis: R1 `ae8ddae` · Branch: `codex/r2-docling-native-core-reader`

## Problem und Entscheidungsverfahren

R1 trennt Dienste, verwendet aber weiterhin eigene Tabellenprojektion, Tokenfenster und Readerlogik. R2 prüft native Ablösung gegen dieselben Quellen, Originalanker, Altstände und UI-Aktionen. Die bestehenden Fachschemata, Identitätsalgorithmen und Freigaben sind keine austauschbaren Rendererfunktionen. Keine zweite aktive Pipeline, kein Rückimport in Orchestrierung und keine proprietäre Pflicht.

Alternativen: R1 unverändert behalten; native APIs direkt einsetzen; einen zusätzlichen universellen Adapter/Viewer einführen. Der universelle Adapter wird verworfen. Native Wiederverwendung wird nur pro bestandenem Gate übernommen; bei Gegenbeweisen bleibt genau der begründete bisherige Weg aktiv.

## A · Versionsfundament: ADOPT, lokale Gates und beide Windows-CI-Jobs bestanden

Offizielle PyPI-Metadaten und GitHub-Release am 11.11.2026 bestätigen `docling==2.150.0`, `docling-slim[format-opendocument]==2.150.0`, `docling-core==2.106.0`. Gemeinsame Auflösung ändert zusätzlich nur `doclang` 0.8.1→0.9.0; keine neue Paketzahl/Extra-Pflicht. `docling-parse` 7.24.2, `docling-ibm-models` 4.0.4 und PDFium 5.15.1 bleiben gleich. Die bekannte PDFium-Rückzugsmeldung bleibt eine bestehende Grenze; kein ungeprüftes Nebenupgrade.

30 unveränderte R1-Tests bestanden vor und nach dem Upgrade. Sieben synthetische Formate konvertieren mit gleichen Elementzahlen/Quellenankern; ODT zeigt bei einer typisierten Zelle nun den sichtbaren Text `42 displayed` statt des Rohwerts `42`. Ein alleinstehendes PNG erreicht ohne weitere RapidOCR-Gewichte keine Konvertierung, in beiden Versionen gleich. Externe Downloadversuche wurden im Offline-Versuch gesperrt; kein Bild-OCR-PASS.

Alle v2–v4-Referenzzustände und Exporte sind identisch. Core serialisiert geladene alte Dokumente mit Schema-Version 1.11.0 statt 1.10.0; dies ist ein separater In-Memory-Befund, keine Änderung der kanonischen JSON-Dateien. Abgesehen davon bleiben die geladenen Dokumentdaten gleich. Original- und Referenzdateien sind SHA-256-unverändert.

Der Nutzer hat ausschließlich die beiden bisherigen offiziellen PDF-Modellpakete `docling-project/docling-layout-heron` und `docling-project/docling-models` für frische CI-Runner freigegeben. Der CI-Fixtureimport nutzt daher explizit `--no-ocr`; dadurch werden keine zusätzlichen RapidOCR-/ModelScope-Gewichte benötigt. Die bisherigen Testassertions und PDF-Regionenprüfungen bleiben unverändert. Lokal nur vorhandener Cache, keine generativen Anfragen.

Primärbelege: [Docling-Release](https://github.com/docling-project/docling/releases/tag/v2.150.0), [Docling PyPI](https://pypi.org/project/docling/2.150.0/), [Core PyPI](https://pypi.org/project/docling-core/2.106.0/). Messbelege und Grenzen: [ACCEPTANCE](../ACCEPTANCE.md), [RESEARCH_PROTOCOL](../RESEARCH_PROTOCOL.md).

## B · Projektion und Tabelle: ADOPT; ursprüngliches B2-Gate: REJECT unter altem Vertrag

`document_quality`, `cell_record` und `native_records` haben genau einen Eigentümer in `documents`; keine neue Projektionsdatei. Pipeline und Preview verwenden diesen Eigentümer direkt. `quality` behält ID-/Fundstellenprüfung und das notwendige kompatible Textfenster. Alte Definitionen und Importkanten entfallen.

Der native `HierarchicalChunker` bleibt Strukturautorität. Sein Standard-`TripletTableSerializer` erzeugt jedoch selbst ein vollständiges `TableData.grid`/DataFrame, obwohl wir nur dessen Referenzen/Überschriften benötigen. Ein kleiner nativer Serializer/Provider fordert für einfache Tabellen nur Item-/Caption-/Footnote-Referenzen an; Zellwerte werden ausschließlich aus `TableData.table_cells` angeboten. Das sind zwei private Erweiterungspunkte der offiziellen API, keine allgemeine Adapterschicht. Für RichTableCell-Unterbäume bleibt Doclings eigene Referenzauflösung notwendig; dort ist der interne Vollgridpfad weiterhin eine ausdrücklich offene Grenze.

`table_window` erzeugt nur das angeforderte Rechteck in nativer Span-/Überschreibreihenfolge. `cell_record` erhält unverändert relative Zellkoordinaten, Header, Zeilenkontext und gleiche Zahlenwerte; keine Deutung als absolute Exceladresse. R1-Goldrecords einschließlich horizontaler/vertikaler Merges sind identisch. 6.001×40 mit sechs physischen Zellen: View 313.258.927→128.783 Peak-Bytes und 2,923→0,0027 s; Modellprojektion 315.083.956→36.674 Bytes und 13,238→0,00175 s. Tracemalloc-/Einzelprozessmessung dieses synthetischen Falls, keine allgemeine Leistungszusage. Native 1-Millionen-Zellen-Grenze bleibt unverändert.

Hierarchical, Hybrid (`merge_peers` true/false) und LineBasedTokenChunker wurden offline mit 256/900 Tokens geprüft. `SerializationResult.spans` enthält nur `item`, keine originalen Zeichenspannen. Neue Chunkzahlen ändern die bestehenden Cursor; ein eindeutiges Vorkommen mehrfacher Unicode-Zitate ist aus Serien-/Chunkmetadaten nicht direkt belegt. Deshalb kein produktiver Chunkerwechsel und keine zweite aktive Chunkerpipeline. Die vorhandenen `text_windows` inklusive Legacy bleiben als notwendiger E-02-/Resume-Kompatibilitätspfad bestehen.

34/34 Quelltests einschließlich vier neuer nativer Gold-/Sparse-/Limit-/Unicode-Gegenfälle bestanden. Auch im installierten Wheel bestanden 34/34 in 22,361 s; B wird getrennt gesichert.

Native Zellspannen, Serializer und Chunker wurden gegen Feldgleichheit, Unicode-Originalspannen und alte Cursor geprüft. `quality.identity/locate/ground` bleiben maßgeblich, bis ein fachlich gleichwertiger Ersatz belegt wäre. Keine Vollgrid-Optimierung als Aufhebung der nativen Tabellengrößengrenze ausgeben.

## C · Gemeinsamer Reader: OPEN

Offizielle lokal gebündelte Docling-Webkomponenten zuerst gegen Auswahl, Fokus, Elementgeometrie, Sicherheit und Paketgröße prüfen. Nur gleichwertige Teile übernehmen und dann Altcode entfernen. Office-HTML ist Struktur, kein originales Seitenlayout; LibreOffice ist optional. Ohne Mappingbeweis keine eindeutige Wortmarkierung.

## D · Picture, Extractor, Graph: OPEN, keine Produktübernahme

Einzelne nicht-generative/offline Gegenproben. Fehlende Gewichte als `MODEL_NOT_RUN`; Graph braucht echte geprüfte Endpunkte und Fachkanten. Keine neue Graph-, Extractor- oder Bildpipeline im Produkt.

## Kurskorrektur · neuer maßgeblicher Beschluss

Die Nutzeranweisung vom 11.11. hebt pauschale v1–v4-Fortsetzbarkeit und UI-Bestandsgarantie auf. Die vollständigen lokalen Dateien `UX_maind_R2_Kurskorrektur_Astro_2026-11-11.md` und `Docling_Tiefenanalyse_UX_maind_2026-11-11.md` wurden gelesen; ein Audit-ZIP war nicht vorhanden, die Tiefenanalyse liegt einzeln in Downloads. Keine Abweichung vom korrigierten Scope festgestellt. Die oben dokumentierten ursprünglichen B2-Gegenbefunde bleiben historische Messungen, ihre Cursorbegründung ist kein aktuelles Ausschlusskriterium.

B `41b0fcf` ist remote gesichert und auf beiden Windows-Versionen grün (Run 42929117779). Unfertiges C ist ausschließlich lokal unter `artifacts/r2-20261111/` erhalten; ZIP-Sicherung samt realer Wiederherstellung von 3.165 Dateien verifiziert. Keine unfertigen Studio-/Preview-/npm-Produktänderungen werden übernommen. Die Komponentenprobe bleibt ein Versuch, keine Freigabe.

Neubewertung B2: native `LineBasedTokenChunker.chunk_text` auf Originalwerten ADOPT nach 37/37 Quelltests; Hybrid bleibt als unmittelbarer Ersatz NOT_ADOPTED wegen zusätzlicher Zuordnung serialisierter Kontexte, nicht wegen alter Cursor. Neue Lauf-/Ankergrenze und tatsächlich entfernter Legacy-Code in [ADR 0015](ADR-0015-forward-chunks-evidence.md). Keine historische Datenmigration. Reader darf nach bestandenem Funktions-/Quellmapping-Gate ersetzt werden; Graph 1.9.2 wird optional aus gespeicherten geprüften Informationen getestet. Kein Serve-/Graph-/Office-Pflichtstack und keine verpflichtende EXE.

## C/D · Abschluss der korrigierten Alternativenprüfung

**C: NOT_ADOPTED, bestehender Reader bleibt der einzelne Produktpfad.** Components 0.0.11: nackter Import wird wegen `sideEffects:false` vollständig entfernt; explizit verwendete Exporte registrieren die Custom Elements tatsächlich (54.582 Bytes lokales ESM-Bundle). PDF-Seite 2, self_ref, Elementrahmen und Klick funktionierten im Browser. SVG-Frames haben jedoch keine eigene Tastaturaktivierung; der getestete Enter-Pfad wählte keinen Beleg. Zusätzliche Dokument-/Geometrie-/Fokusverkabelung wäre nötig. Kein Ersatz allein aufgrund eines erfolgreichen Bundles. Elementrahmen bleibt ausdrücklich kein Wort-Highlight.

Docxodus 15.1.0 (MIT, npm versionsfest) initialisiert lokal im Browser und zeigt DOCX, Unicode, Tabelle und drei gleiche Zitate an. 47.394.330 entpackte Paketbytes; sieben HTML-Anker, eigene OOXML-/Paragraphenanker statt Docling-Refs. Das getestete Docling-Dokument enthält fünf Texte und keine Tabelle (native Flattening-Entscheidung); eine ordinale Zuordnung ist daher nicht bewiesen. Kein Fuzzy-/Ordinalmapper. Native Docling-HTML-Ausgabe hat ebenfalls keine nachgewiesene Zuordnung der ausgewählten Originalvorkommen. Literal `<script>`/Datei-/Bild-URL blieb in beiden getesteten Darstellungen Text. LibreOffice ist nicht installiert: Originalseitenvergleich NOT_TESTED. Kommentare/Fußnoten/Änderungsmarkierungen wurden nach dem negativen Mapping-Gate nicht als Reader-PASS behauptet. PPTX bleibt geprüfte Struktur, keine neue Originalseitenbehauptung.

Tabulator 6.x bleibt ein dokumentierter virtueller UI-Kandidat. Der reale XLSX-Import scheitert bereits vor der Ansicht; keine zusätzliche Spreadsheet-Bibliothek als vermeintliche Importreparatur. OpenContracts und Label Studio werden als offene Workflowalternativen referenziert, ohne zusätzlichen Server-/Datenbankstack und ohne behauptete End-to-End-Abnahme. Keine neue UI-Produktabhängigkeit oder parallele Viewer-Engine, kein ersatzlos gelöschter Reader. [Docxodus-API 15.1.0](https://github.com/JSv4/Docxodus/blob/v15.1.0/docs/npm-package.md), [Tabulator](https://www.tabulator.info/docs/6.x/layout/), [OpenContracts](https://github.com/Open-Source-Legal/OpenContracts), [Label Studio](https://github.com/HumanSignal/label-studio).

**D3: PARTIAL, isolierter Graph-Gold statt Produktpflicht.** Graph 1.9.2 konvertiert gespeicherte geprüfte InformationUnits und zwei tatsächlich entschiedene historische Beziehungen ohne erneute KI. Quellen, Anker, Informationen und Relationsobjekte werden identifizierbare Entitäten: 20 Knoten / 18 Kanten einschließlich getrennt markiertem synthetischem Gleichtext-Gold. Historische Bildlesart bleibt IMAGE_INTERPRETED, kein wörtlicher Textbeleg. Die Referenz enthält keine zwei historischen Reviewereignisse desselben Paars; der Mehrfachreview-Gegenfall bleibt ausdrücklich synthetisch. Zwei direkte Feldkanten zum gleichen Ziel verlieren das erste Label im DiGraph; zwei Relationsentitäten erhalten beide Reviewzustände. Aufgaben-/Teilnehmerkontexte bleiben gespeicherte Eigenschaften, keine neu erfundenen Entitäten oder Claims.

Native InteractiveVisualizer-Ausgabe fällt wegen fehlender Template-/JS-Assets im veröffentlichten Wheel auf eine CDN-Ausgabe zurück. FAIL_OFFLINE, kein produktiver Graphrenderer und kein Live-Visualisierungspass. Der versionierte optionale `scripts/check_graph_gold.py` reproduziert unabhängig von historischen Daten einen gespeicherten synthetischen Zwei-Quellen-/Zwei-Review-Fall mit acht Knoten und acht Kanten, sowie den negativen Offlinebefund. Keine Pflichtabhängigkeit; Zusatzpakete bleiben im isolierten Zielverzeichnis. [Graph 1.9.2](https://github.com/docling-project/docling-graph/releases/tag/v1.9.2).

**D1/D2: PARTIAL / MODEL_NOT_RUN.** Kontrollierter nativer PictureDescriptionBaseModel-Aufruf auf einer In-Memory-Kopie: deaktiviert kein Callback, ausgewählt ein Bild, self_ref/Bildbytes/Geometrie unverändert, `docling__usage` erhalten. Das beweist die Schnittstelle, keine Bildinterpretationsqualität. Native freie Textbeschreibung ersetzt noch nicht sichtbaren Text, Unsicherheit, UX-Deutung und geprüfte Kontextbelege. Classification und Screenshot-/Foto-/Diagrammqualität mangels gesondert freigegebener Modelle NOT_TESTED. Kein neuer Gewichtsdownload und kein generativer API-Aufruf.

DocumentExtractor 2.150.0 wurde tatsächlich installiert geprüft: Default-all und DOCX (auch expliziter Override) werfen RuntimeError; explizit PDF/IMAGE konstruiert ohne initialisierte Pipeline. Eager Defaultauswertung bestätigt. Keine `.extract()`-Inferenz, keine Office-Eignung und keine eigene Universal-Extractor-Engine. Fachlicher Text-/Bild-/Relationsvertrag bleibt damit erhalten. Nachweise und Grenzen in ACCEPTANCE/RESEARCH_PROTOCOL.
