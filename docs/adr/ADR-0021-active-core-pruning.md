# ADR 0021 · R8: aktiven Produktkern bereinigen

12.11.2026 · Basis `0af9982fd7a7554068aa881e4e007ebbc76a4b4a`, Branch `codex/r8-active-core-pruning`. R8-Paket vollständig 00→01→02…06 gelesen, sieben Manifesthashes geprüft. Referenzbefunde sind keine zusätzlichen Arbeitsaufträge. S3 bleibt isoliert; keine unfertigen Ergebnisse übernommen.

## Problem, Nutzenverlust und Entscheidung vor Löschung

R7 enthält 15 Produktmodule/2.979 physische Pythonzeilen, 1.200 eigenes JS/105 CSS, zehn direkte Anforderungen/154 universelle Lockdistributionen. Fremde unversionierte Nutzerordner bleiben unverändert und ungelesen. Keine Forschungsoriginale, Schlüssel oder bestehenden Runs werden bearbeitet.

- **Doppelte Bedienung:** `pyproject` ruft nur `cli:main`; README empfiehlt `ux-maind ui` und `doctor`. Kein anderer Produktcaller der CLI. Convert/extract/graph/inspect/doctor haben bereits Import/Analyse/Graphdownload/Ergebnisöffnen/Laufzeitdiagnose im Studio. Geplanter Ersatz: ein kleiner `studio:main` mit ausschließlich Webstartoptionen; keine Weiterleitung alter Unterbefehle. `graph.save` ist nach CLI-Entfernung nur noch im alten Experiment und einem bisherigen Test benutzt; nativer Graphdownload aus `project` ersetzt diese zusätzliche Dateierzeugung.
- **Experimentelle Suche aussetzen:** `retrieve_package`→`embedding_identity`/`local_embeddings`→`nearest`, Studioaktion/JSfeld/CLI/Cache bilden einen fakultativen Entwicklungsweg. Kein belegter produktiv notwendiger Nutzerfall, historische nomic/BM25-Güte jeweils Recall@5=3/8, TF-IDF1/8. Entfernung reduziert die aktive Suchfunktion; **sie löst semantische dokumentübergreifende Beziehungserkennung nicht**. Manuelle Paarwahl, explizit gewählter Modellvergleich, Review, zwei Originale, Graph/Exporte bleiben verpflichtend. Kein Ersatzretriever, keine versteckte Route/Kompatibilitätsdatei. Alte Cache-/Ergebnisbytes nicht löschen.
- **Abhängigkeiten:** direkten SciPy-Pin nur nach Callerprüfung entfernen und Lock aktualisieren; transitive Herkunft prüfen, keine Installationsersparnis behaupten, falls Docling/Graph SciPy behalten.
- **Historische Treiber:** R6/R7-Experimente und der R5-Reproduktionstreiber sind keine Runtime-/CIimporte. Letzterer hängt an entfallender Suche/graph.save; kein über eine tote Schnittstelle weiterhin beworbener aktiver Treiber. Gitstand und unveränderte ADR-/Forschungsberichte bewahren die Reproduktion im damaligen Vertrag. Kein neues Archiv.
- **Nicht umbauen:** Ref-/Codepointbindung, sparse TableCell-Zugriff, fachliche Review-/Hash-/Studienpflichten bleiben KEEP_HOST/BLOCKED_BY_PROVENANCE. Office-PDF/Enrichment/Extractor bleiben S3_RESEARCH_PENDING.

## Kleine Ausgangsabnahme und begrenzte Gates

Neue lokale synthetische DOCX-/ODT-Originale, Rollen/Hashes/Local-Kanal/DEV-Partition vor Parse festgehalten; keine Korpusdatei, Gewichte oder generative Anfragen. Drei neue aktuelle Tests prüfen kontrollierte Extraktion, zwei Originalanker/Antwort→Frage, technische vs simulierte Nutzer-Selbstauskunft, JSON/CSV/native Graphdaten, Relokation, Hashschutz, wörtlichen HTMLangriff/Unicodemehrdeutigkeit, Scope und tatsächlich angelegten NTFS-Junction-Gegenfall. Baseline 3/3 in15,127s. Simulierte Protokollbestätigung im temporären Test ist **kein echter Nutzerreview**; der persistente Browserfall enthält ausschließlich work_agent_technical.

Erster Testentwurf verlangte vollständigen Aufgaben-/Teilnehmerkontext bei beiden Formaten und scheiterte. Tatsächlich bietet der native DOCX-Pfad Task B/P2 an, der kleine ODT-Pfad keinen solchen Kontext. Korrektes Gate ist belegte Zuordnung oder ausdrücklich unbekannt, keine erfundene Vollständigkeit: ODT bleibt leer, falscher Task A/P1 wird nicht übernommen. Das ist bestehende fachliche PARTIAL-Grenze, keine R8-Reparatur/Retro-Freigabe. Kein historischer44er-/1000er-/Excel-/EXE-Gate.

## Native Batchprüfung vor Entscheidung

Docling2.150.0, offizieller [DocumentConverter-Vertrag](https://docling-project.github.io/docling/reference/document_converter/) und tatsächlich installierter Quellcode geprüft. `convert` delegiert selbst bereits an `convert_all([source])`; Batch ist keine neue Parserengine. Begrenzter Offlineversuch: gültiges DOCX mit eingebetteten16×16-Pixeln/Merge-Zelle, beschädigtes DOCX und unbekannte Erweiterung. Native `raises_on_error=False` liefert in Eingabereihenfolge success/failure/skipped, jeweils Started/Completed-Ereignisse mit Index/Name. Native erfolgreiche JSONrunde identisch, Bildressource vorhanden, Zellspannen2/1/1, Originalhashes unverändert,0 Modellcalls. Bestehender Hostweg liefert CONVERTED/NOT_CONVERTED/UNSUPPORTED mit unverwechselbaren source_id und je Vorher-/Nachherprogress.

**NO_REPLACEMENT_PROVEN:** kein Funktionsfehler der Batch-API in diesen drei Fällen. Die verbleibende Schleife ist aber Source-ID-/Fortschritts-/Fehlerklassifikation sowie unabhängige JSON-/Bild-/Roundtripprüfung. Batch plus Indexbindung/Callback/Serialisierungsfehlerbehandlung entfernt diese Pflichten nicht und beweist keinen Nettoabbau. Deshalb bestehenden einzelnen nativen Converter behalten, keinen zweiten Batchadapter hinzufügen. Rohreceipt `artifacts/r8-20261112/d-native-batch/receipt.json`; keine Behauptung einer universellen Batchunfähigkeit.

## Abschlussledger

Die vorab fixierten Löschgates werden unten mit tatsächlichen Ergebnissen abgeschlossen; technische Produktabnahme bleibt von offener semantischer Such-/Realstudiengüte getrennt.


## B · Ganzer zweiter Bedienweg entfernt und geprüft

cli.py vollständig gelöscht, kein launcher/Wrapper. pyproject zeigt direkt auf studio:main (nur result/port/no-browser). graph.save als zusätzliche CLI-Dateierzeugung entfernt; vorhandene /api/graph-Projektion/Download bleibt. Bisheriger Graphtest nutzt project mit unveränderten ID-/Quellen-/Reviewassertions. 15 gezielte Tests PASS in19,350s: vier aktuelle Kerntests, acht Profile/DPAPI/ENV/Budgettests, drei native Transport-/Schema-/Consentgegenfälle. Tatsächlicher installierter UVstart zeigt dieselben sechs Ansichten; kein Modell-/Schlüsselprompt.

Installationsgegenbefunde: isolierter vollständiger Offline-sync nicht ausführbar, weil Torch-Wheel nicht im uv-Cache; keine neue Bibliothek/Gewichte geladen. Nur eigenes Produkt mit vorhandener gesperrter3.12.16-Runtime installiert. Erste Standardbuildausgabe enthielt aus altem generiertem build/lib noch cli/consolidation/pipeline; nicht als Lösch-PASS gezählt. Erneut mit nativer Setuptools --global-option=build/--build-base in frischer R8-Ausgabe installiert, bestehende Builddateien nicht gelöscht. Tatsächlich installierte Distribution enthält14 aktuelle Module und ausschließlich studio:main; Aufruf außerhalb Quellpfadinjektionen und realer Browserstart bestätigt. Das ist eine lokale Entwicklungsinstallation, kein Release-/EXE-/Wheelgate.


## C · Ganze experimentelle Suchkette entfernt

nearest/retrieve_package/local_embeddings/embedding_identity sowie ausschließlich benötigtes capabilities.embedding-Feld, Studio.retrieve/APIaktion, JS-Suchinformation/Modell/Consentknopf, retrieved-Rankingaggregation und Cacheerzeugung entfernt. Kein fallback/deprecated service. Manuelle Paarwahl und gezielter Modellvergleich bleiben dieselben Funktionen. Alte Cache-/Forschungsdateien bleiben unverändert; ihre bloße Existenz aktiviert keinen Suchpfad. Vier rein suchbezogene Tests entfernt, nativer Ollama-Pydanticschematest unter passendem Transportnamen behalten. Fünf aktuelle R8-Kerngates plus acht Profil-, vier Herkunfts- und drei native Transporttests:20/20 in17,746s. Kein64-/1000er-/Excel-/Realmodelllauf.

Direkte Anforderungen10→9, universelle Lockclosure154→154, keinerlei Paketversions-/Artefakthashänderung. SciPy1.18.1 bleibt über docling-slim[standard] transitiv; requirements-app.lock nennt nun ausschließlich diesen Caller. Kein behaupteter Festplatten-/Installationsgewinn. Offline uv lock/export geprüft; bestehende Metadatenwarnungen typer[all]/yanked pypdfium2 nicht durch spontane Versionserhöhung kaschiert, keine neue R8-Paketänderung. Die Entfernung setzt eine schlecht validierte Suchfunktion aus; manuelle Paarprüfung ist **kein semantischer Retrievalersatz**, historische3/8 bleiben unverändert und als offener Forschungsbedarf dokumentiert.


## E · Treiber und Teststrategie

Vollständige Referenzsuche: tests/r6_experiments.py334 Zeilen, tests/r7_experiments.py95 und research/r5/reproduce.py171 sind ausschließlich optionale damalige Treiber, keine CI-/Produktimporte; R5 hängt zudem an entfernten Suchfunktionen/graph.save. Alle drei aus aktivem Baum entfernt (**600 Entwicklungs-/Forschungszeilen, keine Produktzeilen**). Historische Befund-/ADRtexte und originale Runs bleiben unverändert; damaliger Code vollständig am R7-Endcommit0af9982 verfügbar. Kein legacy-/deprecated-Ersatz. Eingefrorenes synthetisches Relationsgold bleibt KEEP_SCIENTIFIC_FIXTURE, R6-Fixturehelper bleibt KEEP_TEST_FIXTURE, da aktuelle native Reader-/Visiontests ihn verwenden. Nicht wahllos wissenschaftliche Nachweise löschen.

CI erhält20 risikobezogene aktuelle Fälle (Core5, Settings8, Herkunft4, Transport3), statt alte44 als Freigabezahl zu verteidigen. Keine fehlgeschlagene Fachprüfung aus CI entfernt: nur vier Tests ausschließlich gelöschter Suche entfallen; übrige Native-/Schema-/Reader-/Visiontests bleiben ausführbar und werden bei dortigen Änderungen gewählt. Aktueller Kerntest durchläuft die lokale Review-API einschließlich fehlender/expliziter Bestätigung und beide Originalexporte; positive Bestätigung ist ausdrücklich Testsimulation, keine Nutzerfreigabe. Fach-/Realreview und künftige semantische Suchgüte bleiben unabhängig offen.


## F · Tatsächliche Abschlussbilanz und Browser

```json
[
  {
    "symbol": "cli.py:main + convert/extract/retrieve/graph/inspect/ui/doctor",
    "old_callers": [
      "pyproject.scripts",
      "README"
    ],
    "decision": "DELETE",
    "replacement": "studio:main, same Studio; import/analysis/diagnostics/open/graph/export already available",
    "deleted": "entire cli.py; second argparse subcommands/getpass/error-result routing",
    "gate": "installed14 modules + sole entry + actual uv/browser start, Core.WebStart",
    "commit": "40c519d",
    "delta": "CLI104 lines removed; studio launcher10 added, no new module"
  },
  {
    "symbol": "graph.save",
    "old_callers": [
      "cli.main",
      "research/r5/reproduce.py",
      "native graph test"
    ],
    "decision": "DELETE",
    "replacement": "existing graph.project and /api/graph download",
    "deleted": "extra graph.json writer and write_json import",
    "gate": "native ID/LEFT/RIGHT/evidence/history assertions retained; actual graph/export without new graph.json",
    "commit": "40c519d",
    "delta": "graph137→131"
  },
  {
    "symbol": "relations.nearest/retrieve_package + comparison_plan retrieved aggregation",
    "old_callers": [
      "CLI retrieve",
      "Studio.retrieve",
      "R5 experiment/tests"
    ],
    "decision": "DELETE",
    "replacement": "no automatic search; manual pair selection + explicit model judgment remain",
    "deleted": "KDTree/ranking/vector cache/new embeddings.json/retrieved status and results",
    "gate": "manual two-source answer→question, API retired404, provenance/exports/scope, runtime zero callers",
    "commit": "0ebe939",
    "delta": "relations418→360"
  },
  {
    "symbol": "model_transport.local_embeddings / model_settings.embedding_identity + capabilities.embedding",
    "old_callers": [
      "relations.retrieve_package",
      "retired feature tests"
    ],
    "decision": "DELETE",
    "replacement": "none; shared LiteLLM request and provider profile/consent/DPAPI limits unchanged",
    "deleted": "embedding wire calls/digest/tags guards/embedding-only metadata",
    "gate": "8 profile +3 transport +4 provenance +5 core cases",
    "commit": "0ebe939",
    "delta": "transport152→125; settings297→270"
  },
  {
    "symbol": "Studio.retrieve / API retrieve / comparePanel search controls",
    "old_callers": [
      "JS act(retrieve)",
      "API action dispatch",
      "CLI retrieve"
    ],
    "decision": "DELETE",
    "replacement": "existing manual pair controls, existing compare/review routes",
    "deleted": "search unit/model/consent button and ranked suggestions; no hidden endpoint",
    "gate": "actual browser manual selectors2/retired controls0; retired API404",
    "commit": "0ebe939",
    "delta": "studio548→548 incl launcher; own JS1200→1186"
  },
  {
    "symbol": "direct scipy==1.18.1 pin",
    "old_callers": [
      "relations.nearest"
    ],
    "decision": "DELETE_DIRECT_PIN",
    "replacement": "SciPy remains transitively needed by docling-slim[standard]",
    "deleted": "direct pyproject/lock requirement and ux-maind export attribution",
    "gate": "offline uv lock/export; all154 package versions unchanged",
    "commit": "0ebe939",
    "delta": "direct10→9; lock154→154; no disk saving claim"
  },
  {
    "symbol": "tests/r6_experiments.py; tests/r7_experiments.py; research/r5/reproduce.py",
    "old_callers": [
      "optional historical commands in ADR/research reports"
    ],
    "decision": "DELETE_ACTIVE_DRIVERS",
    "replacement": "historical Git0af9982 + unchanged original runs/ADR/research reports",
    "deleted": "three standalone one-off entrypoints; no legacy copies",
    "gate": "no product/CI imports; 20 focused current tests pass",
    "commit": "a6b4f01",
    "delta": "334+95+171=600 development/research lines; excluded from product count"
  },
  {
    "symbol": "documents.convert_sources",
    "old_callers": [
      "study.prepare_package"
    ],
    "decision": "NATIVE_ALREADY_USED / NO_REPLACEMENT_PROVEN",
    "replacement": "keep one DocumentConverter.convert, internally convert_all",
    "deleted": false,
    "gate": "3 fresh sources success/failure/skipped; embedded image/merged cell/roundtrip/hash/progress; no net simplification proven",
    "commit": "5b9611b records decision",
    "delta": "documents173 unchanged"
  },
  {
    "symbol": "ReferencedHTML/sparse cells/quality/review/contract/schema + scientific fixtures",
    "old_callers": [
      "current inspector/core tests"
    ],
    "decision": "KEEP_HOST / BLOCKED_BY_PROVENANCE / S3_RESEARCH_PENDING",
    "replacement": "existing native serializers/refs/spans with necessary host boundaries; no speculative replacement",
    "deleted": false,
    "gate": "current hash/Unicode/literal/Junction/scope/actor/consent tests; no new parser/ontology",
    "commit": "R8 scope",
    "delta": "no source/fixture/holdout destruction"
  }
]
```

Methode: UTF-8 splitlines aller aktiven Produktdateien, keine Änderung der Messbasis. Python2.979→2.757 (−222), Module15→14, eigenes JS1.200→1.186 (−14), CSS105→105; eigene Modulimportkanten52→45/keine neuen Kanten/0 Zyklen. Keine Verschiebung in neue Produktdateien/Adapter. documents/template/preview/quality/review unverändert zu R7. Direkte Runtimeanforderungen10→9; universelle Lockeinträge154 inklusive Produkt (153 externe) unverändert, keine Paketversion oder Distributionshash geändert.600 entfernte Forschungs-/Testtreiberzeilen separat; Sicherheits-/Quellen-/Schemaversionen nicht künstlich gelöscht.

Nach Wiederaufnahme installierte Distribution außerhalb Quellpfadinjektion geprüft:14 Module,9 requirements, kein nearest/retrieve_package/local_embeddings/embedding_identity, einzig studio:main. Tatsächlich installierter UV-Webstart → leerer Studien-Inspektor → Browserauswahl/Import DOCX+ODT →2/2 konvertiert → Wiederöffnung → manuelle Zwei-Informationen-Wahl → beide Originale im vorhandenen Inspektor. Kontrollierte Extraktion/technische Beziehung lokal über denselben Produktkern ergänzt, Netzwerk vor Modellaufrufen gesperrt;0 generative Calls. Vorhandene Modellprofile nur angesehen, keine Nutzerprofile/Schlüssel geändert. Alle sechs Ansichten erreichbar, freie Modellaktion bleibt ohne Freigabe deaktiviert. Speichern ohne eigenes Reviewhäkchen verweigert; keine tatsächliche Humanprüfung behauptet. Separater temporärer APItest simuliert die positive Bestätigung samt Export, kein realer Nutzerreview.

Browser: technisch getrennte Relation2 Aussagen/1 Beziehung/3 sichtbare von15 nativen Knoten, Nutzerstandard0/0 ehrlich; manuelle Selektoren2 und alter Suchpfad0. ODT/DOCX korrekt geöffnet, Frage #/texts/5 im richtigen Task B/P2-Abschnitt, wiederholtes Unicode und Literalangriff als Text,0 aktive Script-/onerror/x-Knoten. Tastatur Tab/Enter öffnet ODT mit sichtbarem Fokus. JSON tatsächlich über Weblink heruntergeladen:2 Einheiten/1 answers/0 Findings/2 Quellen/TECHNICAL_SOURCE_COMPARED. CSV und retired404 auf exakt demselben Ergebnis über lokale TestClient-API geprüft; kein zweiter Browserdownload als bestanden behauptet. Manifest/Zustand/Original-/Doclinghashes nach Lesezugriffen unverändert; kein neues graph.json oder embeddings.json. Native Batch-/Einzelkonvertierungs-JSON zusätzlich direkt gleich verglichen, Ergebnis im Post-Browserreceipt. Bestehende unbekannte ODT-Kontextzuordnung bleibt offen, keine künstliche Zuordnung aus Überschrifttext.

Letzte aktuelle lokale Suite20/20 in17,103s; PR [17](https://github.com/ChristianU-dev/ux-maind-docling/pull/17) gegen exakten R7-Branch. Produkt-CI [43221280623](https://github.com/ChristianU-dev/ux-maind-docling/actions/runs/43221280623): Windows3.12.16 Job131193130777 und3.13.18 Job131193131181 SUCCESS, tatsächlich abgefragte Logs20/20 (36,417s/30,488s). Abschlussdokumentationscommit erhält getrennte CIabfrage. Lokale Rohartefakte artifacts/r8-20261112; kein neues Forschungsarchiv und keine Modell-/Gewichtsdownloads. S3/main/R6/R7 und fremde Nutzerordner unverändert.

**Abnahme:** technischer R8-Löschauftrag nachgewiesen (Nettoabbau und beide wesentlichen Deletions vollständig), optionale Batchablösung NO_REPLACEMENT_PROVEN. Wissenschaftliche semantische Kandidatenfindung, reale Relationsgüte und echter Nutzerreview bleiben OPEN; Entfernung ist kein Retrievalfortschritt. Nach R8 STOP, kein eigenmächtiger R9-/S3-/Reader-/Schemaumbau.
