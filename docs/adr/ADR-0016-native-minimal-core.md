# ADR 0016 · Native-first-Entwicklungskern

Datum: 11.11.2026 · R3-Basis `f48c5a6` · Status: A–E umgesetzt, lokales/Windows-Entwicklungs-Gate abgenommen, Draft #10; D05 PARTIAL.

## Problem und Alternativen

R2 entkoppelt Dienste, behält aber allgemeine Dokumentprojektion, unsichtbare lexikalische Vorauswahl, automatische Synthese und umfangreiche Lauf-/Schemaadapter. Alternative A: Altsuite und Modulgrenzen konservieren. Alternative B: neuen Framework-/Graph-/Readerstack hinzufügen. Beide widersprechen der ausdrücklichen R3-Priorität. Gewählt wird gezielter Nettoabbau mit nativen vorhandenen APIs und wenigen notwendigen Fachzuständigkeiten.

## Entscheidung vor Implementierung

Löschliste und aktuelle Aufrufer stehen in ARCHITECTURE. Native Items/Layer/Zellen und Tokenchunker ersetzen allgemeine Projektion soweit quellengetreu; LiteLLM/Pydantic ersetzt redundante Schemapatches. Wortgewichtung, Distanzlane, 48er-Cap, versteckte Kürzungen und Clique-/Ähnlichkeitsautorität entfallen. Transparente Kandidatenzählung ersetzt keinen menschlichen Befund. Freie Ordnerwahl, sichere Pfade/Hashes, genaue Originalvorkommen, Teilnehmer-/Aufgabenkontext, Einwilligung und Review bleiben erforderlich.

Ein einzelner neuer Vorwärtsvertrag darf v1–v5 ablehnen; keine Migration und keine parallele aktive Pipeline. Historische Dateien werden weder gelöscht noch geändert. Höchstens vier neue Produktmodule mit realem Eigentümer, keine Aliasfassaden. Änderungen werden nur nach aktuellen Fach-/E2E-Gates übernommen.

## Abnahme und Risiken

Die ausdrückliche R3-Anweisung ersetzt Installer-/Wheel-/ZIP-/Zweiversions-Release-Gates und die alte 37er-Suite als aktiven Vertrag. Neue Entwicklungsprüfungen D01–D14 sichern Scope, native Formatstatus, Beleg-/Kontexttreue, Paarabdeckung, Review und Export. Historische Tests bleiben am R2-Commit reproduzierbar; gestrichene Erwartungen werden mit ihrer neuen Entsprechung dokumentiert. Kein stilles Skip aktueller Fachfehler.

Risiken sind Serializerverluste, ungeklärte Layer-/Rollenwahl, unvollständige Paarräume und Providerunterschiede. Fehlende native Gleichwertigkeit rechtfertigt einen kleinen benannten Rest, keinen zusätzlichen Universaladapter. Keine unfreigegebenen Modelle/Downloads, kein neuer Parser/Stack. `#39.xlsx` bleibt geschlossen; R2-Negativbefund wird übernommen. Architektur-/Lösch- und Dependencybilanz wird beim jeweiligen Gate aktualisiert. Nach R3 stoppen.

## Umsetzung A–D und Gegenbefunde

`pipeline.py`/`consolidation.py` entfallen. Vier echte Eigentümer: `study` (Import/Lauf), `analysis` (explizite Text-/Bildaktion), `review` (Belegkorrektur/menschliche Einordnung), `relations` (Paarraum/Urteil/einfache Findings/Export). Studio und CLI importieren sie direkt. Kein Rückimport und keine Aliasfassade.

LiteLLM erhält das native Pydantic-Modell als `response_format`, wenn seine Metadaten Schemaunterstützung bestätigen; sonst unverändertes Pydantic-JSON-Schema im Prompt und strikte lokale Validierung (ggf. native `json_object`-Option). Keine eigene Schemaoperation, Handleübersetzung, Reparatur oder Antwort-Salvage. Native Feldvalidatoren ersetzen manuelle Settings-Ranges. Die kleine Ollama-`/api/show`-Abfrage bleibt begründet: die installierte Runtime-Info liefert Kontext-/Preis-/Tooldaten, aber keine verlässlichen `supports_vision`-/`supports_reasoning`-/Stufenwerte. Blindes Ersetzen würde lokale Modelle falsch sperren oder Fähigkeiten behaupten.

Die drei alten Implementierungstestsuiten entfallen als aktiver Vertrag. Aktuelle elf Eigenschafts-/E2E-Tests sichern Belege und Sicherheitsgrenzen. Ein E2E-Testfehler durch nicht URL-kodiertes `#` war ein Testclientfehler; korrigiert auf Queryparameter. Native XLSX-Gegenprobe: oberer zusammengeführter Header wird separater Text; Hierarchie D05 deshalb PARTIAL, kein neuer Parser. Ein doppelter unmittelbar anschließender Checkpoint-Write verursachte lokal einmal WinError 5; redundanter Write entfernt. Rohfehler bleiben erhalten. Kein Gate wird rückwirkend als bestanden erklärt.

E entdeckt im tatsächlichen Browserdownload eine Exportlücke für geprüfte Frage-Antwort-Beziehungen: nicht jeder fachlich wichtige Kontext ist selbst UX-Finding. Entscheidung: menschlich geprüfte Beziehungen zu exportierten Findings separat mit beiden Originalankern und SOURCE_COMPARED-Status erhalten, den Kontext nicht als UX-Finding hochstufen. Getestet mit negativer Antwort, Task-/Teilnehmerbelegen, ursprünglicher Annotation und erneuter Belegkorrektur. Endbilanz netto −562 Python-Zeilen, keine neue Abhängigkeit. Der Reader bleibt mit dokumentierter R2-Gegenprobe; kein neues Framework und keine R4-Arbeit.

CI-Gegenbefund konkretisiert die Windows-PDF-Entscheidung: im diagnostischen Job 43023873032 (technisch grün) meldet Faulthandler eine Access Violation in docling_parse.pdf_parser._page_timings_from_raw beim unload nach fehlender Pipeline-Ressource. Zweiter Job war ohne Diagnose mit Exit 1 abgebrochen. „Nicht reproduziert“ wäre falsch. Alternative A: nur bei Nicht-ASCII-Pfaden PDFium wählen und den instabilen nativen Cleanup behalten. Alternative B: auf Windows den bereits vorhandenen nativen PyPdfiumDocumentBackend generell verwenden. B ist kleiner, bereits lokal mit/ohne Cache bewährt und fügt keinen Parser/keine Abhängigkeit hinzu. Andere Plattformen behalten Docling Parse; PDF/IMAGE-Ressourcenmangel bleibt explizit NOT_CONVERTED. Neuer lokaler/CI-Gegencheck vor endgültiger Abnahme.

Entscheidung B bestätigt: bd85366, lokal mit/ohne Cache 11/11, Windows-CI 43025182310 11/11 in 20,435 s ohne native Ausnahme. Finale Bilanz −562 Produkt-Python-Zeilen. Native Header-/XXL-/Modellgütegrenzen bleiben offen; kein R4 und kein Professor-Release.
