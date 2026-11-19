# ADR 0020 · R7 Fachgraph, Reviewqualifikation und nativer Kern

12.11.2026 · Ausgang R6 `9ab9c6d05aa9d3a9d4efda927b48b24673661e05`, R7-Branch `codex/r7-s2-graph-core-consolidation`. Problem/Alternativen/Gates vor Produktänderung festgelegt; Abschnitte werden erst nach tatsächlicher Prüfung ergänzt.

## A · Ausgang und Reichweite

R7-Paket vollständig in vorgeschriebener Reihenfolge00→01→02…08 gelesen, SHA256_MANIFEST15 Dateien verifiziert; beide vollständigen Referenzaudits gelesen und vier Bilder geprüft. Historisches Audit ist keine zusätzliche Lösch-/Installer-/Altdatenpflicht. S2 exakt a5adb118eab01d28da938942798e571ca2cb32d5 nur lesend per passendem Ref nachgeholt, Bericht/Prototyp/Gold/Tests/Evaluation/DOM-/Browsergrenzen vollständig geprüft.52.974-Zeilen-Rohrankings nicht kopiert oder produktiv importiert. Keine S3-Zwischenergebnisse gelesen/integriert, S3-Pfade bleiben unberührt.

Unveränderte lokale Basis **40/40 in56,913s** (a-baseline-tests.log, vorhandene gesperrte Python3.12.16-Runtime, HFoffline/Tokenizercache). R6-CI43177809687 frisch bestätigt: Windows3.12.16 Job131046208005 und3.13.18 Job131046208390 SUCCESS,40/40; vollständige Logs wurden im R6-Abschluss abgelegt. PR15 R6/PR14 S2/PR13 R5 weiterhin Draft, jeweilige Basis unverändert; noch kein S3-PR in abgefragter offener Liste. Fremde Nutzerordner erhalten; keine Inhalte daraus gelesen. Keine Originale/Reviews/Runs verändert und0 neue Modellaufrufe.

Native R6-Studio-Basis startet hier wieder ohne Windowsänderung. Vorhermessung am tatsächlich vorhandenen synthetischen R6-E-Paket:36 native Knoten/36 technische Klassenlabels in der Auswahlliste/12 Hashlabels; vollständiges Initiallayout und lokale Browserbilder a-before-graph-small.jpg/a-before-relation-small.jpg. Labels aus DOMoptionen, nicht erfundene OCRzählung. Beziehungsauswahl zeigt den vorhandenen closedNeighborhood-Fokus mit technischen Labels; beide korrekten ODT-/DOCX-Originale geöffnet. Exaktes Zitat standardmäßig zusätzlich aufgeklappt, doppelte Lesefläche bestätigt. Dies ist ein kleinerer echter Vergleichsfall, keine Reproduktion des historischen453/626-Graphen. Die beigefügten Screenshots belegen Unübersichtlichkeit, keine bekannte Script-Ausführung. Keine historischen Graphkanten als UX-Relationszahl ausgegeben.

Unabhängiger S2-Gegenversuch ausgeführt:159 native Knoten/215 Kanten, View.verified akzeptiert answers und context_for mit SOURCE_COMPARED trotz ausschließlich synthetic_technical_reviewer. Native Daten unverändert,0 Calls. a-s2-actor-counterexample.json: COUNTEREXAMPLE_CONFIRMED, ausdrücklich kein Übernahme-PASS. Erster Treiber vergaß Path-Import, scheiterte vor Ausführung und bleibt separat erhalten. Alte R6-Technikfixtures können zudem durch damaligen Default reviewer='local_user' enthalten; dieser String allein ist kein echter Menschennachweis. Kein Umdeuten alter synthetischer Reviews.

## Warum15 Dateien existieren

Alle aktiven Produktmodule sind referenziert. Docling-Parser und notwendiger Hostkleber werden nicht gleichgesetzt; keine Datei nur zur KPIreduktion zusammenlegen.

| Modul | Physische Zeilen | Tatsächliche Verantwortung |
|---|---:|---|
| __init__.py | 2 | Paketmetadaten/Installation; keine Fachpipeline |
| analysis.py | 197 | Freigegebene Textbatches und einzelne Bildanalyse über denselben Modelltransport |
| cli.py | 104 | Ein installierter Einstieg auf dieselben Produktstufen |
| contract.py | 167 | Bewusste Quellauswahl, Herkunft/Hashes/Manifest und Pfadsicherheit |
| documents.py | 173 | Genau eine native Konvertierung plus sparse Zell-/Kontextbindung |
| graph.py | 134 | UX-Entitäten/Referenzen an nativen GraphConverter; keine Extraktion |
| model_settings.py | 297 | Profile/DPAPI/ENV und tatsächliche Anfragebudgets; kein eigener Providerclient |
| model_transport.py | 152 | Ein LiteLLM/Pydantic-Aufruf, Fingerprints/Token-/Fehlerdiagnose |
| preview.py | 182 | Hashgeprüfte Original-/native Refbindung und sichere Anzeigeprojektion |
| quality.py | 130 | Modellzitat an bestimmte angebotene Quelle/Vorkommen binden |
| relations.py | 382 | Paarraum, Review-/Quellenbindung, aktuelle Entscheidungen/Exporte, optionale lokale Suche |
| review.py | 142 | Begründete Korrektur-/Relevanzereignisse und getrennte Annotationen |
| studio.py | 545 | Starlette-Routen, Sitzungs-/Quellschutz, Freigaben und UIzustand |
| study.py | 137 | Ein Quellenimport und ein laufgebundener lokaler Zustand |
| template.py | 193 | Minimaler UX-Pydantic-Fachvertrag; kein Docling-Dokumentschema |

## Alternativen und vorläufige Entscheidung

1. Komplettes S2-View/bundle inklusive aller inspections importieren: NO_ADOPT, zusätzliche213-Zeilen-Pythonprojektion und Vollmaterialisierung; kein belegter Vorteil gegenüber vorhandenen Cytoscape-Collections/Hoststatus.
2. Vorhandene native Graphdaten/IDs in genau einer Cytoscapeansicht filtern/beschriften, Details erst bei Auswahl: gewählter Integrationskandidat. Technischer Vollgraph bleibt auf Wunsch zugänglich; Quellen-/Reviewknoten dominieren nicht den Standard. Kein neuer Pythonproduktbaustein/Paket/Graphpersistenzpfad.
3. SOURCE_COMPARED oder alter local_user-String als menschliche Fachfreigabe: durch Gegenfall verworfen. Kleine nachvollziehbare Reviewherkunft ist Hostverantwortung; wirklicher lokaler Benutzerhandgriff wird getrennt vom technischen Test nachgewiesen oder OPEN gelassen. Originalbelege, aktuelle Entscheidung, Richtung und primäre Rolle müssen zusätzlich stimmen. Keine v7-Extraktionsfelder für UIlabels.
4. BM25/TF-IDF statt vorhandener lokaler Embeddings: NO_ADOPT. S2 berichtet R5-Gold Recall@5 BM253/8, TF-IDF1/8; kein Modellreplay/kein Gewinner, keine neue Retrievalbibliothek oder Cloudprobe nötig. Manuelle Paarwahl bleibt offen.
5. Native Chunk-/Tabellen-/Caption-/Officeengine erneut umfassend umbauen: außerhalb R7/S3 vorbehalten. Vorliegende negative Sparse-/Caption-/Mappingbelege gelten, keine dritte Ersatzengine erfinden.

## Vorab fixiertes Ledger und Löschgates

Maschinenlesbares Ledger; `removed:false` ist noch kein Rückbau. Vollständige syntaktische Imports/Caller/Symbole und15 Dateihashes in a-before.json; dynamische Route-/DOMaufrufe zusätzlich manuell gesucht. Dieselben Bereiche nachher zählen; Forschungs-/Testcode separat.

```json
[
  {
    "symbol": "studio.js:nativeGraphPanel old initial allgraph / host-id labels / Map+edge-find",
    "file": "ux_maind/app/web/studio.js",
    "old_commit": "9ab9c6d",
    "new_commit": "8239365",
    "old_callers": [
      "findings"
    ],
    "new_callers": [
      "findings"
    ],
    "replacement": "Cytoscape3.28.1 native collections/getElementById/outgoers/targets/filter/layout/resize/fit over identical native GraphConverter output",
    "gold": "44/44;3039 native IDs/3061 edges parity; actual1440/390/keyboard/two originals/1000 units",
    "removed": true,
    "remaining": "One necessary nativeGraphPanel; only visible nodes layout, provenance on demand",
    "status": "PASS_TECHNICAL_NOT_HUMAN"
  },
  {
    "symbol": "relations.findings automatic pair FindingCandidate branch",
    "file": "ux_maind/app/relations.py",
    "old_commit": "9ab9c6d",
    "new_commit": "8239365",
    "old_callers": [
      "findings_for",
      "reviewed_export",
      "Studio.results"
    ],
    "new_callers": [
      "same callers, individual findings plus explicit relations"
    ],
    "replacement": "Saved typed native relations and individually reviewed units; no automatic multi-source synthesis",
    "gold": "exactly3 individual findings/3 relations/no pair or clique synthesis; history/export/current source bindings preserved",
    "removed": true,
    "remaining": "Host domain validation and individual relevance remain necessary",
    "status": "PASS"
  },
  {
    "symbol": "Settings(Contract) → template import",
    "file": "ux_maind/app/model_settings.py",
    "old_commit": "9ab9c6d",
    "new_commit": "23b3320",
    "old_callers": [
      "cli",
      "studio",
      "analysis",
      "model_transport",
      "relations"
    ],
    "new_callers": [
      "same Settings callers"
    ],
    "replacement": "Pydantic2.14.1 BaseModel+identical ConfigDict",
    "gold": "all8 existing Settings tests passed including DPAPI/ENV/limits/profile lifecycle",
    "removed": true,
    "remaining": "Provider budgets/consent/DPAPI are not duplicated by SDK; no unproved capability deletion",
    "status": "PASS"
  },
  {
    "symbol": "relations unused phase_a import",
    "file": "ux_maind/app/relations.py",
    "old_commit": "9ab9c6d",
    "new_commit": "8239365",
    "old_callers": [],
    "new_callers": [],
    "replacement": "none; no references in this module",
    "gold": "AST unused import search +44/44",
    "removed": true,
    "remaining": "phase_a itself remains used by real callers elsewhere",
    "status": "PASS"
  },
  {
    "symbol": "nativeView exact codepoint details default-open flag",
    "file": "ux_maind/app/web/studio.js",
    "old_commit": "9ab9c6d",
    "new_commit": "8239365",
    "old_callers": [
      "showEvidence"
    ],
    "new_callers": [
      "showEvidence"
    ],
    "replacement": "Existing native HTMLDocSerializer reader, optional closed exact-span disclosure",
    "gold": "DOCX/ODT/PPTX originals, exact refs/codepoints/ambiguous and sparse native tests; browser details.closed",
    "removed": true,
    "remaining": "Exact span renderer preserved for scientific audit; no renderer-removal claim",
    "status": "PASS_EXPOSURE_CHANGE_ONLY"
  },
  {
    "symbol": "documents.table_window/cell_record/context refs",
    "file": "ux_maind/app/documents.py",
    "old_callers": [
      "documents.records",
      "preview.document_view"
    ],
    "new_callers": [
      "same"
    ],
    "replacement": "No proved native sparse viewport equivalent; native TableData.grid materializes full rectangle",
    "gold": "existing merged-cell/sparse/no-full-grid/section/Unicode tests",
    "removed": false,
    "remaining": "Host quote/cell/source scope not replaced by full native serializer",
    "status": "NOT_REPLACEABLE"
  },
  {
    "symbol": "graph.project host entities/provenance/review mapping",
    "file": "ux_maind/app/graph.py",
    "old_callers": [
      "Studio.graph_data",
      "graph.save",
      "cli"
    ],
    "new_callers": [
      "same"
    ],
    "replacement": "Existing GraphConverter1.9.2 remains native authority; no S2 View imported",
    "gold": "native IDs/edges parity, refs/multiple kinds/withdrawal/roles/history",
    "removed": false,
    "remaining": "Domain/source identities still host responsibility; derived qualification added",
    "status": "KEEP_NATIVE_ADAPTER"
  },
  {
    "symbol": "model_settings.capabilities/request_limits and consent/DPAPI",
    "file": "ux_maind/app/model_settings.py",
    "old_callers": [
      "transport",
      "studio"
    ],
    "new_callers": [
      "same"
    ],
    "replacement": "Already uses LiteLLM1.106.6 metadata; no equivalent complete native host policy proved",
    "gold": "8 Settings and transport tests; S3 not imported",
    "removed": false,
    "remaining": "User budgets/unknown capabilities/loopback/consent need host validation",
    "status": "NOT_PROVEN"
  }
]
```

Ausgang:2937 Produkt-Pythonzeilen/15 Module, eigenes JS1138/CSS105, aktive Tests/Fixtures gesondert in a-before.json,10 direkte Runtimeanforderungen/154 universelle Lockdistributionen. Installierter Windows-RECORD-Umfang135 passende Distributionen/1.250.916.779 Bytes unter site-packages; kein Modellcache, Pythonstdlib, pycache, Downloadgrößen- oder Release-SBOM-Nachweis. Abweichung zur plattformübergreifenden154er Closure nicht als fehlende Runtimepakete behaupten. Rohabhängigkeiten/Dateiumfang in a-dependency-footprint.json. Docling-Metapaket/Graph ziehen Standardextras wieder ein; Slimumbenennung allein kein Einsparungsbeweis.

## Verbindliche weitere Abnahme

B1–B7/C1–C2/D1–D2/E1–E2/F1–F3 aus R7-Paket vorab fixiert. Aktuelle/native IDs und LEFT/RIGHT/LEFT_EVIDENCE/RIGHT_EVIDENCE bleiben gleich; falsche Rolle, IMAGE_INTERPRETED, fremde Studie, Richtung, gleicher Tasktext, mehrfache Reviewereignisse und technischer Akteur dürfen keine falsche Humanfreigabe erzeugen. Kein automatisch synthetisiertes Mehrdokumentfinding aus Pair/Komponente/Score. Tatsächliche Originalfälle/1000 Informationen benchmarken, keine vorberechneten inspections; echter Browser1440/390/Tab/Fokus/Reset und beide Originale. Menschliche Verständlichkeit/Realstudiengüte bleiben unabhängig von Techniktests offen. Modelle/Quellen ohne offenen Prüfbedarf nicht erneut ausführen. Bei nicht belegtem Netto-Rückbau/ersetzter aktiver Algorithmik PARTIAL statt Erfolgsetikett.

## C · Geprüfte Review- und Findinggrenze

44/44 aktuelle Tests in39,035s (bc-tests-first.log): vier neue Gegenfalltests zu technischem/alter local_user-Herkunft, passendem eindeutigem Ereignis, Simulation, primärer Rolle, Bildunsicherheit, Richtung, Neuprüfung und Studiengrenze. Drei frühere Assertions, die technische Testaufrufe als menschliche Paarabdeckung zählten, fachlich korrigiert; ursprüngliche Original-/Export-/Widerrufsassertions bleiben. No-clique-Test verschärft auf exakt drei einzelne Findings ohne automatisch erzeugte Paarfindings. Keine echte menschliche Prüfung durch diese Tests behauptet. Settings verwendet jetzt direkt Pydantic BaseModel mit exakt gleicher ConfigDict; alle acht Profil-/DPAPI-/ENV-/Budgettests bestanden. Graphidentitätsparität und neuer Browserteil noch ausstehend.

## B/D · Native Integration und Gegenprüfung

Frische synthetische Originale, Quellen-/Hash-/Kanal-/Partitionreceipt vor Parse: bc-native/source-receipt-before-parse.json. Alle11 Quellen (DOCX/ODT/PPTX/PDF/XLSX/ODS/CSV/TXT/Bilder) konvertiert,1000 kontrolliert gespeicherte und tatsächlich nativ geerdete Informationseinheiten. Keine generative Extraktion gemessen. Native3039 Knoten/3061 Kanten, IDs und Kanten vollständig mit R6-graph.py auf identischem Zustand verglichen: gleich. Snapshot vor/nach zwei Graph-/Exportwiederholungen bytegleich,0 Modellcalls; technische/source-compared, ungeprüfte und einzeln zurückgezogene Relation getrennt. Keine automatische Kante aus gleichem PPTX-Wortlaut/anderer Aufgabe. Native Projektion6,143s, kompletter begrenzter Versuch30,711s; JSON2132559 Bytes kompakt (formatierte Artefaktdatei größer). Torch ist trotz no-LLM-Graph im tatsächlichen Prozess importiert; keine künstliche Slim-Ersparnis behauptet.

Echter lokaler Browser: DOCX-Frage #/texts/7 und ODT-Antwort mit Task B/Participant P2, gleiche Readeransicht neben genau ausgewählter Relation; PDF-Originalseite und XLSX-Zelle Zeile2/Spalte3, PPTX-Folie1 Task A/P1 vs Folie2 Task B/P2 mit gleichem Unicodewortlaut getrennt geöffnet. Codepointdetails standardmäßig zu; HTML-Angriff bleibt literal,0 inline script/img-onerror/x-Elemente im angezeigten DOM.1000-Informationen-Modus1000 Auswahlknoten,0 vorserialisierte pre-Detailbäume,1112 DOMelemente, kein horizontaler Überlauf; einmaliger CUA-Umschaltvorgang420ms einschließlich Automation, kein statistischer Rendererbenchmark. Technischer Vergleichsmodus4 Aussagen/3 Beziehungen/7 sichtbare Knoten statt3039; Standard0/0 korrekt. Screenshot-/Messartefakte unter artifacts/r7-20261112, keine Forschungsfreigabe aus Bildern.

Lokale aktuelle Suite44/44 in38,982s (bcd-tests-final.log), JSsyntax gültig. Nutzerantwort zur angefragten eigenen Prüfung: „Noch nicht – als offen dokumentieren“. Deshalb echter Benutzerhandgriff/Humanreview-Gate OPEN, keine Simulation als Nutzerurteil speichern; Gesamtstatus bleibt PARTIAL. Synthetische Technikbelege sind kein Real-/SERDIF-/Retrieval-PASS. R5/S2 Recall@5=3/8 unverändert, kein neues Retrieval.


Browsergegenbefund vor B-Abschluss: Nach dem ehrlichen Nullzustand blieb die Zeichenfläche zunächst leer; nach Fenstergrößenwechsel waren Knoten außerhalb des sichtbaren Ausschnitts. Nicht als bestandene Sichtprüfung gezählt. Behebung mit nativen Cytoscape resize/fit und ohne Layout für leere Collections, anschließend visuell erneut geprüft. Letzte1000-Informationen-Resetmessung584ms inklusive Automation,0 pre-Detailbäume/1112 DOMelemente/1000 Auswahloptionen, kein horizontaler Überlauf. Keyboard Home/ArrowDown/Escape/Tab/Enter öffnet korrekt ODT; sichtbarer Fokus.390px Reader/Graph und1440px Desktop tatsächlich geprüft; technische Herkunft im optionalen Detail, exakter Unicodebeleg eingeklappt. Mehrfachtypen answers+complements bleiben gleichzeitig, einzelner zurückgezogener PPTX-Kontrast samt beiden Ereignissen sichtbar. Dokumentinternfilter schließt technische Cross-doc-Paare aus; Reset zeigt sie wieder. Keine Browserfehler in abgefragtem Konsolenfenster. Reproduzierbarer begrenzter Versuch als tests/r7_experiments.py (optional, kein Produktimport): im gesperrten Runtime aus Repositoryroot mit neuem Ausgabeordner aufrufen. Erzeugt eigene synthetische Originale und Quellenreceipt, delegiert alle Stufen an Produktfunktionen, prüft1000 Einheiten/IDs/Kanten/Snapshots und0 Calls; benötigt lokal den bereits freigegebenen Cache und R6-Gitobjekt. Kein eigener Parser/Graphadapter.

Layout bleibt Bibliotheksverantwortung: nur sichtbare Teilmenge, kleine Netze (<80 Knoten) mit nativem cose für weniger überlagerte Kanten, große mit grid; kein wieder eingeführtes Allgraph-Initiallayout. Zufällige Layoutpositionen sind ausschließlich Anzeige, niemals Quellen-/Relationsidentitäten. Settings-Entkopplung separat mit unverändertem ConfigDict und bestandenem Profiltest gesichert; keine Capability-/Budgetlogik auf Verdacht gelöscht. Ein nach vollständiger Suche unbenutzter phase_a-Import in relations entfällt; andere Modulgrenzen bleiben begründet.


## E · Tatsächliche Bilanz gegen R6, keine neue Zielzahl

UTF-8 splitlines, sämtliche physischen aktiven Produktzeilen: Python2937→2979 (**+42**),15→15 Module; eigenes JS1138→1200 (**+62**), CSS105→105. Tests/Fixture-/Experimentcode1715→1871 separat (+156), keine Verschiebung von Produktlogik ins Experiment.53→52 gerichtete eigene Modulimportkanten, eine entfernte Settings→template-Kopplung,0 neue Kanten/0 Zyklen (auch lokale Imports erfasst). Native Graph-/Quellen-ID-Parität tatsächlich geprüft. Kein Produktimport von research/scripts/archive_sync/S2 View. Altes Allgraph-Initiallayout, eigener Graph-Map-/Kantensuchindex und automatische Paarfinding-Ableitung sind entfernt; Fachansichtsfilter/bedarfsweise Details und konservative Herkunftsprüfung sind notwendiger neuer Hostcode. **Keine Nettoverkleinerung des Produktcodes**, deshalb kein vollständiger Rückbauerfolg.

Keine Paketinstallation oder Lockänderung in R7: pyproject.toml/uv.lock/requirements-app.lock, template.py und vendortes Cytoscape bytegleich zu R6.10 direkte Runtimeanforderungen,154 universelle Lockdistributionen unverändert. Vorhandener Windowsruntime-Footprint135 zum Lock passende Distributionen/1.250.916.779 Bytes in RECORD, nicht Cache/Download/peak RAM. Graphimport enthält Torch; bloße Docling-Slim-Umbenennung spart wegen verlangter Extras/Graph keine nachgewiesenen Pakete. Keine Abhängigkeit auf Verdacht entfernt. Neue schwere Infrastruktur, Modell-/Gewichtsdownloads und Modellcalls:0. Keine wissenschaftliche Eigenleistung für native Bibliotheksfunktionen beansprucht. Hauptstatus bleibt PARTIAL (eigener Nutzerreview/Realqualität offen und netto größer), sauber getestete Integration veröffentlicht; keine Ersatzengine für nicht belegte Alternativen erfunden.


## F · Veröffentlichung und Grenze

Commits A0b811bd, Settings23b3320, B–D8239365; Draft-PR16 gegen codex/r6-docling-reader-vision-settings mit Basis9ab9c6d, keine Zusammenführung. PR-CI43191461804: Python3.12.16/3.13.18 jeweils44/44 SUCCESS (34,004s/40,754s), Joblogs vollständig abgefragt. Abschließendes Dokumentationscommit getrennt, finales CIergebnis im Abschlussbericht. Hauptstatus **PARTIAL**, nicht nachträglich an Testausgänge angepasst: tatsächlicher Nutzerreview ausdrücklich offen, Realstudiengüte nicht untersucht, netto größer. Native Graph-/Readerfunktion technisch nachgewiesen; übernommene SDKfunktionen sind keine wissenschaftliche Eigenleistung. Keine S3-Zwischenintegration, keine neue Runtimeabhängigkeit oder fremde Originaländerung; nach R7 stoppen.
