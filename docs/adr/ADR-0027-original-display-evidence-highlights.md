# ADR0027 · Originaldarstellung und native Belegmarkierung

13.11.2026 · R14 · angenommen mit dokumentierten Grenzen. Basis R13 `7e29626`; S8 und S8b nur lesend ausgewertet.

## Problem und Entscheidung

R13 zeigte PDF-Originale nur als Download/Platzhalter; Office-PDFs waren lokal nicht abgenommen. Informationen sollen ohne Sucharbeit ihre Quelle sichtbar machen. Eine neue eigene PDF-/Officeengine oder ein Suchen-als-Produktworkflow erfüllt dieses Ziel nicht.

Wir verwenden den lokal ausgelieferten offiziellen PDF.js-Komponentenviewer für Original-PDF und ausdrücklich gekennzeichnete LibreOffice-Anzeige-PDFs. Die bestehenden Docling-Komponenten und Serializer behalten native Struktur/refs/Boxen. Pointer/Fokus beziehungsweise Auswahl einer Information steuern PDF.js' öffentliche FindController-/TextHighlighter-Funktionen. Trefferwechsel bleibt optional. Office-Texttreffer sind keine nachgewiesene self_ref-Geometrie. Identische Zitate bleiben mehrere Kandidaten, kein automatisch gewählter Beweis.

Die spezialisierte kleine Profiloberfläche bleibt mit einem einzigen SQLite-Speicher; Dateiimport/-export ergänzen den Austausch. Native Pydantic-Konfiguration und unveränderter Graph-LiteLLMClient bleiben die technische Modellstrecke. Kein Thinkingregler ohne öffentliches Forwarding.

## Geprüfte Alternativen

- Browser-PDF-Plugin: in R13 unzuverlässig und keine einheitliche öffentliche Belegmarkierung; ersetzt.
- Eigene Overlay-/Rechteckengine: nicht erforderlich. Das zum Nutzervideo gefundene MIT-Repository [madebyagents/doc-approval-demo](https://github.com/madebyagents/doc-approval-demo/tree/33ff0c67f19b752b36f64f36ee1411474620b684) implementiert tatsächlich Hover, Grounding-Heuristik und eigene Bildrechtecke. Nur das Interaktionsprinzip wird übernommen; weder React-App, LangExtract, Rechnungsmodell noch dessen fuzzy Grounding/Koordinatenengine werden eingebaut.
- JSONEditor10.4.3: S8s DOM-Probe belegt JSONbearbeitung, keine bessere spezialisierte Modellbedienung. Zusätzliches Bundle, rohe JSONbedienung und Ersatz der sicheren Speicherung wären nötig. Nicht übernommen; kein neuer JSONEditor-/Proxy-/PostgreSQLbetrieb.
- docx-preview/zweiter Officeviewer: würde ODT/PPTX nicht abdecken und keine native Docling-Geometrie liefern. Nicht als weiterer Produktpfad aufgenommen.
- Native Docling allein: liefert Struktur, Provenienz und Seitenabbilder, aber keine originalgetreue Office-Paginierung. Ergänzendes freies Anzeige-PDF ist notwendig.

## Versionen, Lizenzen und Betrieb

| Bestandteil | Version / Lizenz | Verwendung und zusätzlicher Aufwand |
|---|---|---|
| Mozilla pdfjs-dist | 6.5.438 · Apache-2.0 | öffentliche Viewer-/Find-/Textlayerkomponenten, lokaler Worker, CMaps/Fonts/Wasm; npm-lock und bestehender Assetbuild, kein neuer Server |
| PDF.js enthaltene Fonts/Decoder | jeweilige mitgelieferte Lizenztexte | u.a. PDFium/Foxit-BSD, Liberation-GPL2 mit Fontausnahme, OpenJPEG-BSD, MIT/BSD; Lizenzdateien werden unverändert in standard_fonts/wasm mitgeliefert |
| LibreOffice | 26.8.3.1, Build861effc5289d539f15c4c18d1ba8579ffd78728b · MPL-2.0 und mitgelieferte Drittlizenzen | optionaler lokaler Windows-Konsolenprozess, kein Dienst; Originale bleiben unverändert |
| Docling Components / JSCore | 0.0.11 / 2.106.0 · MIT | unverändert native Seitenboxen, Tooltip, Klick und Refauflösung |
| Docling/Core/Graph/LiteLLM | 2.150.0 / 2.106.0 / 1.9.2 / 1.106.6 · MIT-Kerne | bestehende Python-Lockdatei unverändert, kein neuer Modellclient |
| Cytoscape | 3.35.0 · MIT | bestehender einziger Graphrenderer unverändert |

Gebaut werden offizielle PDF-Display-/Worker-/Viewerdateien, CSS/Bilder und benötigte Ressourcen. Unbenutzter Sandbox-JS-Build und Source-Maps werden nicht ausgeliefert. Der vorhandene Frontendbuild regeneriert ausschließlich seinen geprüften generierten PDF.js-Unterordner. Paketinhalt wird gegen aktive Quellen/Assets bytegeprüft. PDF.js' optionale Node-Canvas-Pakete sind kein zusätzlicher Browser-/Python-Runtimedienst.

Die Windows-MSIbereitstellung über winget blockierte zunächst. Das hashgeprüfte offizielle MSI wurde zur Gegenprobe mit lessmsi2.12.9 (MIT, nur lokales Entwicklungswerkzeug) entpackt. Anschließend wurde auch die systemweit vorhandene LibreOffice26.8.3.1-Version bestätigt und erfolgreich ausgeführt. Kein Installer oder entpacktes Programmpaket wird in Git oder Wheel aufgenommen.

## Risiken, Grenzen und Ergebnis

Reale Browserbelege zeigen automatische DOCX-/Draw.io-Zitatmarkierung, doppelte Office-Zitate auf zwei Seiten, ODT, gedrehte PPTX und native PDF-Boxauswahl. Für Scans ohne PDF-Textlayer führt die bewusste Belegwahl automatisch zur bereits vorhandenen nativen OCR-Seitenbox. Der Originaltab bleibt ohne Rücksprung benutzbar; keine eigene Overlayrechnung oder erneute OCR. Ein älteres minimal erzeugtes ODT wird vom Renderer abgewiesen; keine Originalreparatur. Microsoft-Font-/Officepixelparität, universelle Office-ref-Pixelbindung, Wortboxen aus OCR sowie fachliche Modellqualität sind nicht bewiesen. Keine menschliche Entscheidung oder Crossdockante wird aus einem Suchtreffer erzeugt.

Eigener Rest: sichere Ressourcen/Derivatcache, gemeinsame Auswahl und kurze Beleg-Nachrichtenbrücke, Bedienkontrollen sowie nicht geheime Profile/ENV-Grenze. PDF.js übernimmt tatsächliches Zeichnen, Texthighlight und Scrollen. Graph und Quellenprüfung bleiben erhalten. R14 ist eine zusätzliche native Integration, keine Netto-Löschrunde. Messwerte und Fehler stehen in [ACCEPTANCE](../ACCEPTANCE.md).

## Offizielle Gegenprüfung

[Mozilla simpleviewer v6.5.438](https://github.com/mozilla/pdf.js/blob/v6.5.438/examples/components/simpleviewer.mjs), [FindController](https://github.com/mozilla/pdf.js/blob/v6.5.438/web/pdf_find_controller.js), [TextHighlighter](https://github.com/mozilla/pdf.js/blob/v6.5.438/web/text_highlighter.js), [LibreOffice Startparameter](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html), [PDF-Export](https://help.libreoffice.org/latest/en-US/text/shared/guide/pdf_params.html), [Graph-Konfiguration](https://github.com/docling-project/docling-graph/blob/v1.9.2/docling_graph/llm_clients/config.py), [LiteLLM Reasoning](https://docs.litellm.ai/docs/reasoning_content). Aktueller öffentlicher Graphrelease bei Prüfung weiterhin1.9.2; kein nutzloses Paketupgrade.

Die zusätzliche Scan-Gegenprüfung fand im installierten Core2.106.0 keinen öffentlichen searchable-PDF-Export. [OCRmyPDF17.14.1](https://ocrmypdf.readthedocs.io/en/stable/installation.html) bietet einen solchen Derivatweg und unterstützt Windows, benötigt jedoch weitere OCR-/Systemkomponenten. Installation und Ausführung sind hier NOT_EXECUTED: Die tatsächlich benötigte Belegmarkierung ist bereits mit vorhandener Docling-Provenienz gelöst. Dies ist kein generelles Verbot eines später ausdrücklich benötigten durchsuchbaren PDF-Exports.
