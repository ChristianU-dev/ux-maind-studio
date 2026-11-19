# ADR 0013 · Modelltransport und native Dokumentdienste

Datum: 10.11.2026 · Basis: R0 `d516ad6` · Status: entschieden, in R1 umgesetzt und technisch abgenommen

## Problem und geprüfte Alternativen

`pipeline.py` vereint Studienkoordination, fachliche Algorithmen, LiteLLM-Transport und native Konvertierung. `preview` lädt Dokumente über die gesamte Pipeline. Das erschwert eindeutige Zuständigkeiten und gezieltes Testen.

Untersucht wurden Beibehalten des Monolithen, Weiterleitungsfunktionen im bisherigen Modul und zwei direkte Dienstmodule. Ein allgemeines Adapterframework, zusätzliche Parser und eine Aufteilung der Fachalgorithmen würden den begrenzten Schnitt überschreiten. Der bestehende `DocumentConverter` und die installierten Docling-/LiteLLM-Schnittstellen genügen; kein Ersatzverfahren ist nötig.

## Entscheidung

Genau zwei Produktmodule: `model_transport` besitzt Ausnahmetypen, Aufrufkontext, Modelloptionen und LiteLLM-Antwortbehandlung; `documents` besitzt PDF-Backendwahl, bestehende Konvertierung und hashgeprüftes Laden. Die bisherigen Implementierungen werden jeweils entfernt. Direkte Ausnahmetyp-Aliase erhalten die Klassenidentität; keine Wrapper. Fachfunktionen verwenden den Transport über seinen Modulnamen, damit Tests den tatsächlichen Eigentümer ersetzen.

LiteLLM-Umgebungsoptionen werden beim Laden des Transportmoduls vor dem verzögerten LiteLLM-Import gesetzt. Zeitstempel verwenden unverändert UTC; Fingerprint, Schema und Aufrufprotokoll bleiben gleich. `documents` darf nur die bestehenden Vertrags- und Qualitätshelfer benötigen. Keines der neuen Module importiert `pipeline`, `studio` oder das jeweils andere Dienstmodul. `preview` lädt direkt über `documents`.

## Risiken und Grenzen

Falsch platzierte Testpatches könnten echte Modellaufrufe auslösen; alle bisherigen Patchziele werden daher mit unveränderten Assertions umgesetzt. Kontextvariablen, Fehlerklassen und Meldungen dürfen nicht verdoppelt werden. Eine falsche Importreihenfolge könnte LiteLLM-Metadatenzugriffe ermöglichen. Native Bilder, JSON-Roundtrip und Hashschutz benötigen Regressionen im installierten Wheel.

`extractor_sha256` bleibt die bestehende Diagnose über `pipeline.py`, kein neuer Gesamtcodehash. Originale, native Dokumente, Checkpoints und Datenverträge werden nicht migriert. Der Schnitt ist keine neue wissenschaftliche Methode und behebt keine fachlichen Reader-, Bild- oder Relationslücken. Nachweise und verbleibende Abnahmegrenzen stehen in [ACCEPTANCE](../ACCEPTANCE.md).

## Abnahme

A1 und A2 wurden nach bestandenen Tests getrennt gesichert (`a84a6e8`, `0df71f1`). 30/30 Regressionen im installierten Produkt und in beiden Windows-CI-Jobs bestanden. Die AST-Analyse belegt entfernte Altimplementierungen, unveränderte Fachfunktionen und einen azyklischen Produktimportgraphen. Originalbelege, v2–v4-Referenzdaten und Exportidentitäten bleiben erhalten. Die Codehashdiagnose einer neuen Übernahme wird getrennt verglichen und darf sich ändern; vorhandene v4-Bindings werden nicht umgeschrieben. Historisches v1 und neue fachliche Leistungsnachweise bleiben ausdrücklich offen; Details einschließlich Fehlversuchen in ACCEPTANCE.
