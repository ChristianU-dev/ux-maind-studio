# UX-mAInd Studio · Systematische System-, Format- & Methodik-Grenzen

> [!IMPORTANT]
> **Verbindliche Aktualisierungs-Pflicht (Anti-Stale-Regel):**
> Dieses Dokument dokumentiert wahrheitsgemäß alle technischen, formatbezogenen und methodischen Grenzen des aktuellen Systems und wird live unter `Einstellungen → Handbuch & Systemgrenzen` ausgespielt. Sobald eine hier aufgeführte Grenze durch ein Update behoben, verschoben oder neu entdeckt wird, **muss diese Datei im selben Commit aktualisiert werden**.

---

## 1. Keine proprietären Software-Abhängigkeiten (Open-Source-Garantie)

- **Laufzeit-Kern (Python & Frontend):** 100 % OSI-lizenzierte Open-Source-Software (`MIT`, `Apache-2.0`, `BSD`, `ISC`), automatisiert geprüft durch `scripts/verify_open_source_licenses.py` und `frontend/build.mjs` (`ux_maind/app/web/generated/LICENSES.txt`).
- **Keine Runtime-CDNs:** Alle Web-Komponenten (`React`, `@xyflow/react`, `PDF.js`, `@docling/docling-components`, `Radix UI`) sind lokal gebündelt und funktionieren komplett offline.
- **Optionale lokale Anzeige-Hilfe:** Für die seitengetreue linke Originalvorschau von `.docx`-, `.pptx`- und `.odt`-Dateien sowie Ganzfolien-Renderings wird lokal installiertes **LibreOffice (`soffice`, MPL-2.0 Open Source)** genutzt. Ist LibreOffice nicht installiert, bleiben Docling-Konvertierung, `DoclingReader`-Vollansicht, Markdown-Export und KI-Pipeline uneingeschränkt nutzbar.
- **Sprach- & Bildmodelle:** Über `LiteLLM` frei wählbar zwischen **100 % lokalen Open-Weights-Modellen** (`Ollama`, lokales `vLLM`), **akademischen Open-Weights-Clustern** (`NHR@FAU`, z. B. `Qwen3.6`, `Mistral`, `Gemma-4`) und optionalen kommerziellen Referenz-APIs (`OpenAI`, `Gemini`, `Anthropic`).

---

## 2. Unterstützte Dokumentformate & Format-spezifische Grenzen

| Dateiformat | Erschließung & Stärken in `UX-mAInd` | Bekannte technische Grenzen |
| :--- | :--- | :--- |
| **PDF (`.pdf`)** | Layout-Analyse, mehrspaltige Lesereihenfolge, `TableFormer`-Tabellen, Bounding-Boxen, selektive/Vollseiten-OCR, Ligatur- & Silbentrennungs-Rückprojektion (`ﬁ`→`fi`, `-\n`). | Stark handschriftliche Notizen auf Scans hängen von der OCR-/Vision-Modellgüte ab; rein grafische Vektor-Diagramme ohne Textlayer benötigen `Vision = Aktiv`. |
| **Word & OpenDocument (`.docx`, `.odt`)** | Absätze, Überschriftenhierarchie, Tabellen inkl. verbundener Zellen, eingebettete Bilder sowie wortgenaue Durchstreichungen (`w:strike` in `.docx`). | Fließtext-Formate besitzen keine festen physischen Seitenumbrüche: Seitennummern in der linken PDF-Vorschau entstammen dem LibreOffice-Anzeigederivat, während rechts die exakte strukturelle Elementfolge (`#/texts/i`, `#/tables/j`) maßgeblich ist. |
| **PowerPoint (`.pptx`)** | Folientexte, Gruppen-Shapes, Tabellen, Sprechernotizen (`ContentLayer.NOTES`), partielle Durchstreichungen sowie 72-DPI-Ganzfolien-Kontextbilder (`slide_context`). | Frei platzierte Textboxen ohne Folienmaster-Titel werden von `Docling` als `TEXT` statt `SECTION_HEADER` eingestuft; animierte Folienübergänge werden statisch im Endzustand gerendert. |
| **Excel & CSV (`.xlsx`, `.csv`)** | Mehrblättrige Tabellen (`worksheet`-Name + ungekürzte Spalten-/Zeilenköpfe in Tabellen-Caption), automatische Disambiguierung wiederholter Spaltennamen (`Comments [Frage 12 ...]`), Übergabe von `column_header`/`row_header` bis Stufe B/C, verbundene Zellen (`row_span`/`col_span`) und Erhalt unzitierter Vergleichszeilen. | Excel-Formeln werden über ihren zuletzt gespeicherten Zellenwert gelesen (keine Live-Neuberechnung von Makros/Formeln ohne gespeicherten Cache-Wert); eingebettete Excel-Diagramme werden als Tabellenwerte, nicht als Pixel-Chart exportiert. |
| **WebVTT & Transkripte (`.vtt`, `.txt`, `.md`, `.html`)** | `.vtt` bewahrt Sprecher (`voice`) und exakte Zeitstempel (`start_time`–`end_time`) über `TrackSource`; `.txt` erhält Tab- und Sprecherabsätze ohne Fehlklassifikation als Quellcode. | Reine `.txt`-Dateien ohne Zeitstempel enthalten naturgemäß keine Audio-Zeitmarken und keine 2D-Seitenboxen. |
| **Bilder (`.png`, `.jpg`, `.webp`, `.tiff`)** | OCR-Texterkennung plus multimodale VLM-Bildbeschreibung und optionale Diagramm-Extraktion (`Chart2CSV`). | Reine Pixelquellen besitzen keinen nativen Textlayer; Zitate mit `origin="picture_description"` stützen sich auf den VLM-Beschreibungstext und werden transparent als abgeleitet gekennzeichnet. |
| **Roh-Audio & Roh-Video (`.mp3`, `.wav`, `.mp4`)** | *Bewusste Systemgrenze im aktuellen Kernprofil:* Noch kein automatisches Video-Keyframing im Standard-Job; zeitcodierte Transkripte werden über `.vtt` (`TrackSource`) eingespeist. | Direkte Whisper-ASR- und Screen-Recording-Keyframe-Pipelines benötigen große lokale Medienmodelle und sind als Ausbaustufe (Horizont 3) abgegrenzt. |

---

## 3. Behobene Bibliothekslücken vs. Verbleibende Pipeline-Grenzen

### 3.1 Durch `UX-mAInd` bereits gezielt geschlossene Upstream-Lücken
1. **Tabellen-Adressierung in `DocLang` (`B-05`):** `docling-core` lässt `TableItem.meta` im `DocLang`-Prompt weg → `UX-mAInd` injiziert auf der temporären Analyse-Kopie automatisch `[ux_maind: source_ref=#/tables/k | worksheet=... | columns: ...]`, ohne das Originaldokument zu verändern.
2. **Bewertungsskalen & Formularfelder (`D-05`, `US-27`, `US-36`):** `DocItemLabel.GRADING_SCALE`, `FormItem` und `KeyValueItem` gehen im Standard-`DocLang`-Export nicht mehr verloren, sondern werden für Stufe A explizit serialisiert.
3. **Keine 250-Zeichen-Regelkappung (`D-01`, `US-32`, `US-71`):** Alle Schema-Feldregeln in `templates.py` sind unter die 250-Zeichen-Grenze von `docling-graph` optimiert, inklusive expliziter Skalenpolarität (`scale_direction='unknown'`) sowie etablierter UX- und Barrierefreiheits-Normen (`Nielsen H1–H10`, `ISO 9241-110`, `W3C WCAG 2.2`).
4. **Erkennung stiller Schema-Reparaturen (`D-02`, `US-33`):** Repariert `docling-graph` eine fehlerhafte Modellantwort im Hintergrund (*Salvage*), protokolliert `UX-mAInd` dies transparent als `SCHEMA_SALVAGED` statt es still zu übergehen.
5. **Vermeidung doppelter API-Aufrufe bei 0 Relationen (`D-04`, `US-35`):** Legitime Enthaltung (`relations: []`) in Stufe B löst keinen unstrukturierten Zweitaufruf mehr aus.
6. **Typografie, Ligaturen & Vorzeichen-Zahlen (`D-08..D-13`):** PDF-Ligaturen (`ﬁ`, `ﬂ`), Zeilenumbruch-Silbentrennung, Unicode-Minus (`−2,5`), Prozent-/Vorzeichen-Wortgrenzen (`5%` vs. `15%`) und seitenübergreifende Zitate über Kopf-/Fußzeilen hinweg werden exakt und ohne unscharfes Fuzzy-Matching verankert.
7. **Mehrschichtiges Stream-Idle- & Wall-Clock-Timeout ohne Retry-Multiplikation (`US-69`):** `DiagnosticClient` ersetzt skalare Socket-Timeouts und doppelte SDK-Retry-Schleifen (`LiteLLM × OpenAI`) durch explizite `httpx.Timeout`-Grenzen, einen überwachten Chunk-Streaming-Watchdog (Abbruch bei echtem Token-Leerlauf statt Hängen auf HTTP/2-Keepalives) und sofortige Live-Konsolenmeldungen (`model_timeout`, `stream_stalled`, `structured_fallback`, `api_error`) ohne Preisgabe von Geheimnissen.
8. **Kontaminationsschutz für Experten-Codebooks & breite Fragebogen-Tabellen (`US-72`):** Referenzdateien (`corpus_role='reference'`) bleiben im `Quelleninspektor` einsehbar, werden aber serverseitig (`studio.py:_forbid_reference_documents`) vor versehentlicher Einspeisung in blinde A/B/C-Syntheseläufe geschützt; breite Umfrage-Exporte behalten sämtliche Spaltenindizes (`> 12` Spalten) inklusive automatischer Disambiguierung identischer Unterspalten (`Comments`).

### 3.2 Bewusst bestehende methodische & architektonische Grenzen (Wichtig für die Evaluation!)

| Grenze | Technische / Methodische Ursache | Auswirkung & Umgang in der Praxis |
| :--- | :--- | :--- |
| **1. Wörtlichkeits-Prinzip (*Verbatim Grounding Limit*)** | Jede Beobachtung in Stufe A verlangt einen zusammenhängenden wörtlichen Beleg oder eine Tabellenzelle, um Halluzinationen zu 100 % auszuschließen. | Rein nonverbale Phänomene (langes Schweigen, Zögern, verteiltes Hin-und-Her-Klicken über viele Absätze ohne zusammenfassende Beobachternotiz) können nicht frei paraphrasiert als Textzitat erfunden werden, sondern benötigen Beobachternotizen, Zeitmarken oder Folienannotationen. |
| **2. Geschlossene Evidenzbasis für Stufe B & C (*Closed-World Synthesis*)** | Stufen B und C dürfen als formale Belege ausschließlich verifizierte Beobachtungen (`O1..On`) aus Stufe A zitieren. | Übersieht ein sehr kleines Sprachmodell (z. B. 4B-Edge-Modell) in Stufe A ein Detail oder liefert es ein unauflösbares Zitat (`UNRESOLVED`), fehlt dieser Baustein in Stufe C — offene Stellen daher in der `Analyse-Pipeline` prüfen/heilen! |
| **3. Artefakt- vs. Stichproben-Unabhängigkeit** | Drei Einzeldateien desselben Probanden (`P1_Interview.txt`, `P1_Fragebogen.csv`, `P1_Zeiten.xlsx`) sind 3 Dateien, aber nur 1 Versuchsperson; umgekehrt enthält 1 Sammel-CSV oft 30 Personen. | Beide Werte (`Unabhängige Dokumente` **und** `Genannte Sprecher`) im Finding gemeinsam betrachten; keine automatische statistische Signifikanzbehauptung ableiten. |
| **4. Kontextfenster-Grenze bei sehr großen Korpora (`direct`-Synthese)** | Stufe B und C übergeben alle kompakten Beobachtungen der ausgewählten Studie gemeinsam an das Modell, um globale Querverbindungen ohne verlustbehaftetes Vor-Retrieval zu finden. | Ideal für typische Usability-Studien (`5–30` Dokumente, bis ~`200k–250k` Tokens). Bei Großstudien mit `> 80–100` einstündigen Interviews sollte kohorten- oder aufgabenweise gruppiert oder der `dense`-Vertrag genutzt werden. |
| **5. Lokaler Einzel-Workspace-Server vs. Echtzeit-Multi-User** | `studio.py` verarbeitet Hintergrund-Jobs seriell (`max_workers=1`) in einer lokalen `workspace.sqlite` (`%LOCALAPPDATA%\UX-mAInd\workspace` bzw. `--workspace`). Über `auth.py` (`LocalProfileIdentityProvider`) und `dual_review.py` unterstützt Studio sowohl die **Einzelprüfung** als auch die **verblindete unabhängige Zweitprüfung** **„Am selben Rechner"** (sequenzieller Profilwechsel) und **„Auf zwei Rechnern"** (Offline-Dateiaustausch per `.zip`/`.json` ohne Netzwerkverbindung und ohne erneuten Modelllauf). Nicht unterstützt ist das gleichzeitige Live-Editieren derselben `workspace.sqlite` durch mehrere Browser-Clients über das Netzwerk. | Für BA-Studien und lokale Zweitprüfungen auf einem oder zwei Rechnern vollständig lokal ohne Cloud-Dienst oder Login nutzbar; für spätere gleichzeitige Echtzeit-Team-Server stehen der Queue-Pfad in Abschnitt 4 sowie der Protokoll-Anschlusspunkt `ReviewerIdentityProvider` bereit. |
| **6. Stochastische Modellvarianz** | Trotz niedriger Temperatur (`0.1`) können Sprachmodelle bei identischem Dokument die Anzahl und Zuschnitt-Granularität atomarer Beobachtungen leicht variieren. | Für wissenschaftliche Vergleiche stets gespeicherte A-Läufe als feste Basis pinnen (`Gespeicherte A-Basis`) und bestätigte Forscher-Entscheidungen über `Entscheidungen übernehmen` weiterführen. |

---

## 4. Web- & Container-Deployment: Wie verhalten sich Terminal & Hintergrund-Jobs?

Für den lokalen Forschungsbetrieb läuft `UX-mAInd Studio` als eigenständiger `Starlette/Uvicorn`-Prozess auf `127.0.0.1` mit einer lokalen `SQLite-WAL`-Datenbank:
- **Neustart- & Container-Festigkeit (`terminal_ui.read_job_history()`):** Selbst wenn ein Server- oder Docker-Container neu startet und der flüchtige Arbeitsspeicher leer ist, rekonstruiert `Terminal & Verlauf` automatisch alle bisherigen Konvertierungs-, Vision-, Stufe-A-, Stufe-B- und Stufe-C-Läufe chronologisch aus den SQLite-Tabellen (`versions`, `runs`, `ux_objects`). Es gehen also **keine** Verlaufs-, Token- oder Ergebnisdaten verloren.
- **Skalierung als gehostete Mehrbenutzer-Web-App (Architektur-Ausblick):** Soll die Anwendung später für viele gleichzeitige Studierende oder UX-Teams auf einem zentralen Webserver betrieben werden, darf `uvicorn --workers 4` **nicht** blind mit lokalem Prozessspeicher (`activity`-Dict) gestartet werden, da sonst HTTP-Anfragen auf unterschiedliche Worker treffen würden. Der saubere Entkopplungspfad besteht aus drei klaren Bausteinen:
  1. **Persistente Job-Queue (`Redis` + `Celery` / `ARQ`):** Die Pipeline-Funktionen (`workspace.convert`, `workspace.enrich`, `workspace.extract`, `interpretation.run`) sind bereits vollständig vom HTTP-Layer getrennt und können 1:1 in eigene Hintergrund-Worker ausgelagert werden.
  2. **Zentraler Event-Stream (`Redis Streams` / `PostgreSQL LISTEN/NOTIFY` + `SSE`):** `receipts.event()` schreibt Fortschrittsmeldungen in den geteilten Stream, sodass das Web-Terminal in jedem Browser-Tab verzögerungsfrei per Server-Sent Events (`SSE`) mitliest.
  3. **Mandanten-Trennung, Objektspeicher & `ReviewerIdentityProvider`:** Austausch von `SQLite` durch `PostgreSQL` (pro Projekt/Team isolierte `workspace_id`), Ablage von `stored/`-Originalen in einem S3-kompatiblen Bucket (`MinIO`) und Anbindung einer angemeldeten Prüferidentität (z. B. Hochschul-SSO / OIDC) über das in `ux_maind/app/auth.py` vorbereitete Protokoll `ReviewerIdentityProvider`.

---

## 5. Abhängigkeits-Abgrenzung (Pflicht vs. Optional vs. Entwicklung)

- **Zwingend für Prüfung, Zweitprüfung & Dateiaustausch:** Python `3.12+` mit der lokalen Open-Source-Laufzeitumgebung (`.venv` via `uv sync --locked` / `install.ps1`), lokaler Webbrowser und die bereits gebauten Offline-Web-Assets (`ux_maind/app/web/generated/`). Weder ein proprietäres Produkt noch ein kommerzielles Konto oder eine Internetverbindung wird benötigt.
- **Optional:** Lokales **LibreOffice (`soffice`)** für das erstmalige Rendern von `.docx`/`.pptx`/`.odt` zu Anzeige-PDFs (bereits gerenderte Anzeige-PDFs reisen im `.zip`-Prüfpaket auf Rechner 2 mit) sowie ein lokaler (`Ollama`) oder externer (`NHR@FAU` / Cloud-API) Modellzugang ausschließlich für **neue** KI-Analyseläufe.
- **Nur für Entwicklung:** `Node.js 20+` / `npm` zum Neubauen des React-Frontends (`npm run build --prefix frontend`) nach Quellcode-Änderungen.

