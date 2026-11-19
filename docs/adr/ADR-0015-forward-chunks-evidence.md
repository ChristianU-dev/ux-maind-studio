# ADR 0015 · Native Modellkontexte und Originalvorkommen

Datum: 11.11.2026 · ersetzt die pauschale Altfortsetzungspflicht, nicht historische Nachweise.

## Problem und Alternativen

R1 koppelte eigene Unicode-/Legacy-Fenster und v1–v4-Übernahme an den Fortschrittszeiger. Der Nutzer hebt diese Laufzeitpflicht mit der R2-Kurskorrektur ausdrücklich auf. Originale, Dokumentstände, Entscheidungen und Exporte bleiben unverändert archiviert. Historische Ergebnisse werden mit dem passenden R1-Snapshot gelesen, nicht in R2 migriert.

Erneut geprüft: HybridChunker mit/ohne Peer-Merge; native LineBasedTokenChunker-Serialisierung; dessen öffentliche `chunk_text`-Methode auf den bereits quellengebundenen Originalwerten. Hybrid ist nicht mehr wegen alter Cursor ausgeschlossen. Seine Markdown-/Mehr-Item-Kontexte liefern aber keine fertigen itemlokalen Unicode-Intervalle; die Gegenprobe mit CRLF und wiederholtem Wortlaut rekonstruiert die Originalwerte nicht vollständig. Ein zusätzlicher Alignment-Algorithmus wäre mehr Eigeninfrastruktur.

## Entscheidung

`documents.model_records` verwendet ausschließlich Doclings `LineBasedTokenChunker.chunk_text`, ohne Prefix, mit cl100k_base und 900 Tokens. Native Hierarchie, Nachbartexte und Tabellenheader bleiben Kontext. Nur native Textwerte werden geteilt; Zellen und Bilder behalten ihre bestehenden expliziten Referenzen. Es gibt keine zweite aktive Teilungslogik. Vor Erzeugung eines Offsets muss die vollständige Konkatenation aller nativen Stücke exakt dem Original-Unicode-Wert entsprechen. Kumulative Zeichenlängen beweisen dann die Originalintervalle; fehlende Gleichheit bricht ab. Serializer-`Span.item` wird nicht als Zeichenoffset ausgegeben.

Laufvertrag `ux-maind-ux/5`, Datei `study-v5.json`: Manifestbindung schützt Quellenhash, native JSON-Bytes und Dokumentstand. Chunkalgorithmus/-budget, Core- und Tokenizerversion werden gebunden; pro Quelle schützt ein Eingabefingerprint die tatsächliche Recordfolge einschließlich Kontexte. Cursor und Retryintervalle adressieren ausschließlich diese Laufkontexte. Andere Tokenizer/Versionen oder veränderte Eingaben verlangen einen neuen Lauf. Ein anderes Modellprofil darf dieselbe geprüfte Recordfolge fortsetzen; tatsächliche Einstellungen bleiben je Quelle/Aufruf protokolliert.

Originalbeleg ist das geprüfte Paket/Manifest → Quelle mit Dokumenthash → self_ref → Unicode-Vorkommen beziehungsweise Zell-/Bildreferenz. Chunkindex, Chunkbudget und Modellantwortformulierung gehören nicht zur Ankeridentität. Identische Zitate innerhalb desselben angebotenen Stücks bleiben AMBIGUOUS; verschiedene nachweisbare Vorkommen bleiben verschieden. Keine Fuzzy-Suche und keine geratene Auswahl. Ein über die Chunkgrenze reichendes, nicht vollständig angebotenes Zitat bleibt ungelöst.

Entfernt: `quality.text_windows`, Legacy-Fensterschleife, `pipeline.upgrade_legacy`, v1/v2/v3-Übernahmezweige, Vorgängerhashverkettung, `CoverageRecord.legacy_windows` und nur dafür benötigtes `ground(stored_ids=...)`. Historische JSON-Dateien werden weder gelöscht noch neu gespeichert. Ein Ergebnisordner mit ausschließlich v1–v4-Checkpoint wird ausdrücklich abgewiesen; damit gibt es keinen stillen Neustart über gespeicherten Reviews.

## Risiken und Abnahme

Keine Fortsetzung alter Läufe im neuen Runtimevertrag. R1 und die zugehörigen Tests bleiben über Git und vorhandenes Wheel reproduzierbar. Zwei Tests mit eingebauter Altübernahme werden durch v5-Neustart/-Wiederöffnung und unveränderte historische Dateien mit expliziter Ablehnung ersetzt; die alte Unicode-/Cursorprobe durch native Rekonstruktion, Budget- und Ankeridentitätstests. Aktive Review-, Relations-, Export-, Wiederaufnahme-, Provider- und Bilderfreigaben bleiben geprüft. Keine neue Runtime-Abhängigkeit.

900 Tokens sind die feste Kontextstückgrenze, kein zugesichertes Gesamtpromptbudget. `complete` prüft weiterhin die tatsächlich gewählte Modelleingabe; übergroße Zellen/Metadaten können blockieren. Der native OpenAI-Tokenizer kann reservierte Tokenliterale ablehnen; dann keine Modellanfrage und kein erfundener Quellenbeleg. Live-Inferenz und fachliche Extraktionsgüte werden dadurch nicht bewiesen. Messbelege und Testergebnisse stehen in [ACCEPTANCE](../ACCEPTANCE.md).
