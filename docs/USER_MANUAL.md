# UX-mAInd Studio · Benutzerhandbuch, Einstellungs-Ratgeber & Metadaten-Lexikon

> [!IMPORTANT]
> **Verbindliche Synchronisations-Regel (Single Source of Truth für Entwickler & KI-Agenten):**
> Dieses Handbuch (`docs/USER_MANUAL.md`) und das Grenzen-Register (`docs/SYSTEM_LIMITS.md`) werden **live in der Anwendung** unter `Einstellungen → Handbuch & Systemgrenzen` angezeigt und als Download angeboten. Jede Code-Änderung, die Funktionen, Pipeline-Stufen, Parameter, Status-Bezeichnungen oder bisherige Systemgrenzen verändert, **muss im selben Arbeitsschritt hier aktualisiert werden**. Die Anwendung darf dem Nutzer niemals veraltete oder unzutreffende Angaben anzeigen.

---

## 1. Überblick: Was macht UX-mAInd Studio?

**UX-mAInd Studio** ist eine lokal ausführbare, quellengebundene Analyse- und Synthese-Umgebung für heterogene Usability- und UX-Forschungsdaten (Interviews, Think-Aloud-Protokolle, Fragebögen, Zeitmessungstabellen, Berichte und annotierte Präsentationsfolien). Das System benötigt **keine proprietäre Zusatzsoftware** (100 % Open-Source-Bibliotheken; optionales lokales LibreOffice für Office-Vorschau-PDFs) und arbeitet streng nach drei Prinzipien:

1. **Unveränderliche Originale & Inhaltsadressierte Versionen:** Jede importierte Datei bleibt bitgenau erhalten (`source_sha256`). Konvertierungen und Bildanreicherungen erzeugen eigene SHA-256-Versionen, ohne jemals Vorstufen zu überschreiben.
2. **Deterministische Rückwärts-Verifikation (Zero-Trust gegenüber KI-Zitaten):** Jede vom Sprachmodell vorgeschlagene Beobachtung wird deterministisch gegen das konkrete `DoclingDocument` rückgeprüft (`7-Stufen-Re-Grounding`). Unbelegte oder mehrdeutige Zitate werden **niemals** stillschweigend durchgewunken.
3. **Menschliche Prüfhoheit (Human-in-the-Loop):** Technische Verankerung (`BOUND`) bedeutet „Das Zitat steht dort im Dokument" — **nicht** „Die Interpretation ist inhaltlich wahr". Erst die Forscher-Entscheidung (`Bestätigen`, `Korrigieren`, `Verwerfen`) legt den fachlichen Status fest.

---

## 2. Der 5-Schritt-Arbeitsfluss in der Praxis

| Schritt | Ansicht (Tastenkürzel) | Aufgabe & Ergebnis |
| :--- | :--- | :--- |
| **1. Studienkorpus zusammenstellen** | `Studienkorpus` (`Taste 1`) | Alle Dateien einer Studie gemeinsam importieren (temporäre Office-Lockdateien `~$*` und IDE-Ordner `.git`/`.idea` werden beim Ordnerimport automatisch übersprungen). Falls deine Studie bereits ein menschliches Experten-Codebook oder eine Ground-Truth-Tabelle enthält, klicke in der Spalte **Rolle** auf **`Referenz / Codebook`**: Die Datei bleibt im `Quelleninspektor` lesbar, ist aber vor versehentlicher Kontamination der blinden induktiven A/B/C-Synthese geschützt. |
| **2. Pipeline & Basis prüfen** | `Analyse-Pipeline` (`Taste 2`) | **Gesamtanalyse starten** (`01 Docling → 02 Vision → 03 Evidenz A → 04 Relationen B → 05 Findings C`) oder einzelne Stufen gezielt mit Fokusfrage ausführen. Eine sekündlich fluide mitwachsende Laufzeitleiste zeigt den Echtzeit-Fortschritt (inklusive Stream-Chunks & Laufzeit `MM:SS`); in der Tabelle *Gespeicherte A-Basis* siehst du pro Dokument exakt, wie viele Beobachtungen verankert sind und warum einzelne Einträge ausgeschlossen wurden. |
| **3. Befunde prüfen, korrigieren & exportieren** | `Synthese & Findings` (`Taste 3`) | Vorgeschlagene Findings (`C`), Beziehungen (`B`) und Beobachtungen (`A`) sichten. Fehlerhafte KI-Formulierungen über **„Korrigieren"** direkt anpassen (inkl. Valenz sowie Nielsen-, ISO-9241-110- oder W3C-WCAG-2.2-Kriterium) oder über **„Verwerfen"** ausschließen (verworfene Einträge verschwinden aus aktiven Berichten und wandern in den Revisions-Anhang). Aktive Such- und Prüfstatusfilter bleiben beim Belegsprung in den Quelleninspektor und Zurückkehren erhalten. Am Ende als **A4-HTML-Handout** (Druck/PDF) oder **Markdown-Bericht** speichern. |
| **4. Zusammenhänge visuell explorieren** | `Wissensgraph` (`Taste 4`) | Karten frei per Drag & Drop anordnen, über die MiniMap (unten rechts) navigieren, zwischen *Findings-Ketten*, *Gesamtnetz*, *Gegenbelegen* und *Bildbelegen* umschalten und fehlerhafte Verbindungen im rechten Inspektor direkt lösen. |
| **5. Originalbelege gegenprüfen** | `Quelleninspektor` (`Taste 5`) | Synchroner **Dual-View**: Links das Original-PDF / Office-Anzeige-PDF, rechts die strukturierte Docling-Lesefassung oder native Bounding-Box-Geometrie. Oben zeigt die *Finding-Belegleiste* alle Stützen und Gegenbelege des aktiven Befunds zum direkten Durchklicken. |

*Ergänzende Werkzeuge:* `Terminal & Verlauf` (`Taste 6`) zeigt das vollständige Auftragsprotokoll über alle Stufen (`Docling`, `Vision`, `A`, `B`, `C`) inklusive Echtzeit-Stream-Heartbeats, `json_schema → json_object`-Fallbacks, Retries, HTTP-Fehlercodes und Reasoning-Token-Zählern (ohne Roh-Prompts oder API-Schlüssel); `Ctrl + K` öffnet überall die Schnellsuche & Befehlspalette.

---

## 3. Empfohlene Einstellungen nach Dokumenttyp

| Dokumenttyp | Empfohlene Docling- & Pipeline-Einstellungen | Warum? |
| :--- | :--- | :--- |
| **Digitale PDFs** (Berichte, Export-Protokolle) | `do_ocr = An` (selektiv), `force_full_page_ocr = Aus`, `table_mode = accurate` | Nutzt den exakten eingebetteten PDF-Textlayer und wendet OCR nur auf eingebettete Screenshot-Bilder an. |
| **Gescannte PDFs / abfotografierte Bögen** | `do_ocr = An`, `force_full_page_ocr = An`, `ocr_scale = 3.0`, `ocr_lang = de, en` | Erzwingt hochauflösende Vollseiten-Texterkennung über die gesamte Seite; defekte Scan-Textlayer werden ersetzt. |
| **PDF-Fragebögen mit Formularfeldern** | `extract_form_fields = An`, `do_table_structure = An` | Liest ausgefüllte Checkboxen, Radiobuttons und Schlüssel-Wert-Paare (`FormItem` / `KeyValueItem`) zusätzlich aus. |
| **Word- & OpenDocument-Dateien (`.docx`, `.odt`)** | Standard (`table_mode = accurate`), Dual-View `Lesefassung` im Quelleninspektor | Erhält Überschriften, Tabellen-Header und wortweise Durchstreichungen (`w:strike`) für verworfene Aussagen. |
| **PowerPoint-Präsentationen (`.pptx`)** | `Vision = Aktiv` (`Multimodal-Modell`), `scale = 2.0`, `input_format = auto` (`doclang-geo`) | Kombiniert exakten Folientext + Sprechernotizen (`NOTES`) mit gerenderten 72-DPI-Ganzfolien (`slide_context`), sodass Pfeile, Callouts und räumliche Bezüge sichtbar werden. |
| **Tabellen & Fragebogen-Exporte (`.xlsx`, `.csv`)** | `input_format = auto` (`doclang-geo`), kein Vision nötig | Übergibt alle Spaltenindizes (auch bei breiten 40-Spalten-Umfragen), disambiguiert wiederholte Spaltenköpfe (`Comments [Frage 12 ...]`) automatisch, reicht `column_header` & `row_header` bis Stufe B/C weiter und bewahrt unzitierte Vergleichszeilen. |
| **Interview-Transkripte (`.txt`, `.vtt`)** | Standard; bei `.vtt` automatische `TrackSource`-Übernahme | Bewahrt Sprecherkennzeichnungen (`voice`) und exakte Sekundenspannen (`start_time`–`end_time`) bis in den Beleganker. |

### 3.2 Empirisch getesteter Modell- & Vertrags-Ratgeber (`docling-graph` + Open-Weights)

Auf Basis realer Evaluationsläufe über heterogene Usability-Studien (`monday_v1_1`, `subjective_data_models`, `SERDIF`) empfehlen sich folgende Kombinationen:

| Einsatzszenario | Empfohlene Modellklasse | Empfohlene Vertrags-Optionen (`Stufe A / B / C`) | Empirische Begründung & Literaturbezug |
| :--- | :--- | :--- | :--- |
| **Standard-Usability-Studie** (`5–25` gemischte Dateien: `.txt`, `.docx`, `.odt`, `.pptx`, `.csv`) | **30B–120B Open-Weights** (`Qwen/Qwen3.6-35B-A3B-FP8`, `RedHatAI/gemma-4-31B-it-FP8-block`, `gpt-oss-120b`, `DeepSeek-V4-Flash`) | `extraction_contract = direct`, `processing_mode = many-to-one`, `use_chunking = Aus`, `gleaning_enabled = Aus` (oder `An` für Zweitdurchlauf bei sehr dichten Protokollen) | Erzielte `93,4–99,4 %` exakte Verankerungsquote über alle Formate ohne JSON-Trunkierung; vermeidet Aufmerksamkeitsverluste im Mittelteil durch verdichtetes `evidence.json` in B/C (*Lost in the Middle*, Liu et al. 2024). |
| **Visuelle Folien- & Screenshot-Analyse** (`.pptx`, UI-Screenshots, Diagramme) | **Multimodales VLM** (`Qwen/Qwen3.6-35B-A3B-FP8`, `Gemma-4`, `Pixtral` / `Mistral-Small-3.2`) | `Vision = Aktiv`, `vision.scale = 2.0`, `do_picture_classification = An`, `do_chart_extraction = An` | Kombiniert lokale Diagramm-Tabellenextraktion mit VLM-Beschreibung (`29/29` Folien-/Bildankern auf `monday_v1_1`); überlappende Folienbelege werden in Stufe C automatisch dedupliziert (`dependent_visual_overlap`). |
| **Sehr lange Einzeltranskripte / Großkorpora** (`> 60` Seiten pro Datei oder kleines Kontextfenster `< 32k`) | **Ab 24B–35B** (oder lokal `14B–32B` via `Ollama`) | `use_chunking = An` (Stufe A) bzw. `extraction_contract = dense` bei sehr engem Ausgabefenster | Teilt überlange Einzeldokumente an nativen Docling-Strukturgrenzen, ohne das Schema-Limit (`JSONSchemaBench`, Geng et al. 2025) zu sprengen. |
| **Schneller Vorab-Check auf reinen Textnotizen** (Laptop / Edge-Ressourcen) | **Kompakte 4B–8B Modelle** (`google/gemma-4-E4B-it`, `qwen3:8b`) | Nur für kurze `.txt`/`.md`-Notizen (`one-to-one` oder `direct` ohne große Tabellen); bei `SCHEMA_SALVAGED` auf `>= 30B` wechseln | Erreicht auf kurzen Textnotizen `100 %` Verankerung, stößt aber bei breiten 40-Spalten-Fragebögen oder komplexen `.pptx`-Decks an Ausgabegrenzen (*Albalawi & Bryce*, SEKE 2025). |
| **Methoden-Evaluation gegen menschliches Codebook** (z. B. `SERDIF`) | **30B–120B Open-Weights** | Codebook-Datei im Korpus auf **`Referenz / Codebook`** stellen; bei mehrdeutigen `"Same as above"`-Zellen offene Stellen heilen oder `Teilbasis erlauben` nutzen | Verhindert deduktiven Codebook-Leakage (*Xiao et al.*, IUI '23) und hält Quellenverankerung strikt getrennt von menschlicher Qualitätsprüfung (*Agreement Is Not Quality*, Liu et al. 2026). |

---

## 4. Vollständiges Status- & Metadaten-Lexikon (Was bedeutet welcher Begriff?)

### 4.1 Quellenverankerungs-Status (Stufe A, Korpus & Pipeline)

| Anzeige / Code | Exakte Bedeutung | Was ist zu tun? |
| :--- | :--- | :--- |
| **Vollständig verankert** (`UNREVIEWED` / `eligible = true`) | **100 %** aller extrahierten Beobachtungen dieses Dokuments besitzen einen eindeutigen, buchstabengetreuen Fundort im `DoclingDocument`, und kein technischer Blocker liegt vor. | Direkt bereit für Stufe B & C. |
| **Quellengebunden · Offen** *(im Studienkorpus)* | Alle Beobachtungen sind im Quelltext lokalisiert, aber es wurde noch keine menschliche Fachprüfung durchgeführt (`UNREVIEWED`) **oder** sekundäre Zusatzhinweise (z. B. ein ungebundener Neben-Messwert) stehen zur Durchsicht bereit. | Kann in `Synthese & Findings` geprüft werden; blockiert Stufe B/C nicht, sofern `eligible = true`. |
| **Teilweise verankert** (`PARTIAL` / `a_source_open`) | Ein Teil der Beobachtungen (z. B. `21/28`) ist exakt verankert, aber mindestens **eine** Beobachtung konnte nicht eindeutig gebunden werden (`UNRESOLVED` — etwa wegen Mehrdeutigkeit, Tippfehler des Modells oder `"..."`-Auslassung). | Klicke in der `Analyse-Pipeline` auf **„X offene prüfen"**: Bei mehrdeutigen Stellen per **1-Klick „Festlegen"** den richtigen Kandidaten wählen oder fehlerhafte KI-Einträge **„Verwerfen"** → danach wechselt der Lauf sofort auf **„Menschlich geklärt"**! Alternativ `Teilbasis erlauben` aktivieren, um nur die verankerten `21` Beobachtungen an B/C zu übergeben. |
| **Menschlich geklärt** (`human_reconciled = true`) | Zuvor offene Beobachtungen wurden durch verbindliche Forscher-Entscheidungen (Kandidatenauswahl oder Ausschluss) vollständig geklärt. | Der A-Lauf ist ohne erneuten Modellaufruf voll für Stufe B & C freigegeben! |
| **Referenz / Herkunft korrigiert** (`REF_RECONCILED` / `ORIGIN_RECONCILED`) | Das Zitat war im Dokument **weltweit eindeutig** auffindbar, das Modell hatte lediglich eine benachbarte Element-ID oder `"original"` statt `"picture_description"` angegeben. `evidence.py` hat den Zeiger deterministisch korrigiert und dies transparent protokolliert. | Automatisch verankert und zitierbar; Prüfhinweis bleibt nachvollziehbar sichtbar. |
| **Schema-Salvage** (`SCHEMA_SALVAGED` / `a_schema_salvaged`) | Das Sprachmodell lieferte ein formal unvollständiges JSON-Teilobjekt, das `docling-graph` automatisch repariert oder bereinigt hat. | Prüfen, ob alle erwarteten Aspekte/Gegenbelege enthalten sind, oder mit einem stärkeren Modell wiederholen. |

### 4.2 Finding-Klassifikation: Valenzen & Usability-Standards (Stufe C)

Damit Findings nach anerkannten Usability-Standards statt nach willkürlichen Labels eingeordnet werden, trennt `UX-mAInd` drei Dimensionen:

1. **`valence` (Bewertungsrichtung):**
   - `problem` / `negative`: Nachgewiesene Nutzungshürde, Verwirrung, Fehlbedienung oder Verzögerung.
   - `positive` / `strength`: Nachgewiesene Stärke, flüssige Aufgabenlösung oder hilfreiche Systemrückmeldung.
   - `mixed`: Ambivalenter Befund (z. B. hilfreiche Funktion, deren Einstieg jedoch schwer auffindbar ist, oder Widerspruch zwischen Teilnehmenden).
   - `neutral`: Sachliche Kontext- oder Prozessbeobachtung ohne Wertung.
   - `unclear`: Bewertungsrichtung mangels belegter Skalenpolarität bewusst offengelassen (Schutz vor Fehlinterpretation!).
2. **`finding_type` (Fachlicher Befundtyp):**
   - `usability_problem` (Nutzungsproblem), `positive_practice` (Positivbefund), `recovery_pattern` (Selbstkorrektur / Workaround), `design_opportunity` (Gestaltungspotenzial), `workflow_dependency` (Prozessabhängigkeit), `context_note` (Rahmenbedingung).
3. **`usability_heuristic` (Anerkannte UX-Heuristik / Norm — optional):**
   - **Jakob Nielsens 10 Usability Heuristics (`H1`–`H10`):**
     - `Nielsen H1: Visibility of system status` (Sichtbarkeit des Systemstatus)
     - `Nielsen H2: Match between system and the real world` (Übereinstimmung mit der realen Welt)
     - `Nielsen H3: User control and freedom` (Nutzerkontrolle und Freiheit)
     - `Nielsen H4: Consistency and standards` (Konsistenz und Standards)
     - `Nielsen H5: Error prevention` (Fehlervermeidung)
     - `Nielsen H6: Recognition rather than recall` (Wiedererkennen statt Erinnern)
     - `Nielsen H7: Flexibility and efficiency of use` (Flexibilität und Effizienz)
     - `Nielsen H8: Aesthetic and minimalist design` (Ästhetisches und minimalistisches Design)
     - `Nielsen H9: Help users recognize, diagnose, and recover from errors` (Fehlermeldungen & Behebung)
     - `Nielsen H10: Help and documentation` (Hilfe und Dokumentation)
   - **DIN EN ISO 9241-110 (Grundsätze der Dialoggestaltung):**
     - `ISO 9241-110: Aufgabenangemessenheit`
     - `ISO 9241-110: Selbstbeschreibungsfähigkeit`
     - `ISO 9241-110: Erwartungskonformität`
     - `ISO 9241-110: Erlernbarkeit`
     - `ISO 9241-110: Steuerbarkeit`
     - `ISO 9241-110: Fehlertoleranz / Gebrauchsfehler-Robustheit`
     - `ISO 9241-110: Nutzerbindung`
   - **W3C WCAG 2.2 (Barrierefreiheits-Erfolgskriterien bei A11y-Befunden):**
     - `W3C WCAG 2.2 · 1.1.1 Non-text Content (Textalternativen)`
     - `W3C WCAG 2.2 · 1.3.1 Info and Relationships (Semantik & Struktur)`
     - `W3C WCAG 2.2 · 1.4.3 Contrast Minimum (Kontrast)`
     - `W3C WCAG 2.2 · 2.1.1 Keyboard (Tastaturbedienbarkeit)`
     - `W3C WCAG 2.2 · 2.4.7 Focus Visible / 2.4.11 Focus Appearance`
     - `W3C WCAG 2.2 · 2.5.8 Target Size Minimum (Zielgröße)`
     - `W3C WCAG 2.2 · 3.3.1 Error Identification / 3.3.3 Error Suggestion`
     - `W3C WCAG 2.2 · 3.3.8 Accessible Authentication`

### 4.3 Epistemische Schutz-Flags & Unabhängigkeits-Metriken am Finding

- **`independent_documents` vs. `distinct_speakers`:** `independent_documents` zählt die verschiedenen Quelldateien der Stützbelege; `distinct_speakers` zählt die namentlich unterscheidbaren Ersthand-Teilnehmenden (`participant_firsthand`). So erkennst du sofort, ob 3 Dateien nur von 1 Person stammen oder 1 Sammel-CSV 15 verschiedene Personen enthält!
- **`dependent_visual_overlap`:** Auf derselben Folie/Seite wurden sowohl Originaltext als auch die VLM-Beschreibung der gerenderten Ganzfolie zitiert. `effective_independent_supports` zieht diese Doppelung automatisch ab!
- **`unanchored_scale_direction`:** Ein numerischer Fragebogenwert (`rating_scale`) wurde ohne explizite Polung (`1 = sehr gut` vs. `5 = sehr gut`) im Dokument gefunden (`scale_direction = "unknown"`). Im Originaldokument prüfen!
- **`contains_negated_or_struck`:** Mindestens ein Beleg stammt aus einer durchgestrichenen oder verneinten Passage (`<strikethrough>`).
- **`contains_rejected_support`:** Eine vom Finding genutzte Beobachtung oder B-Relation wurde nachträglich vom Forscher verworfen (`HUMAN_REJECTED`). Bitte Finding im Editor prüfen/aktualisieren!
- **`technical_source_only`:** Alle Zitate sind technisch verankert, aber der Befund wurde noch nicht menschlich bestätigt (`UNREVIEWED`).

---

## 5. Wissensgraph: Ansichten, Navigation & Verbindungen lösen

Im `Wissensgraph` (`Taste 4`) steuern vier Filtermodi den Blickwinkel:

1. **`Findings-Ketten` (Standard sobald Stufe C vorliegt):** Zeigt fokussiert jedes aktive Finding (`C`) samt seinen genutzten Beziehungen (`B`), Stütz-/Gegenbelegen (`A`) und Quellankern. *(Hinweis: Ist dieser Modus ausgegraut, liegt für die aktuell ausgewählte Dokumentmenge noch kein C-Lauf vor — starte Stufe B/C in der Analyse-Pipeline oder stelle im Synthese-Verlauf einen früheren Lauf wieder her.)*
2. **`Gesamtnetz`:** Zeigt das komplette Beziehungsnetz über alle aktiven Stufen hinweg — inklusive Dokumentquellen-Ankern (`Dokumentquelle`), sodass auch vor Stufe B/C sichtbar ist, welche Text-, Tabellen- und Bildbeobachtungen aus welchem Quelldokument entspringen.
3. **`Gegenbelege`:** Filtert gezielt alle Widersprüche (`contradicts` in Stufe B sowie `COUNTEREVIDENCE` / `QUALIFIES` an Findings), um vorschnelle Konsens-Annahmen kritisch zu prüfen.
4. **`Visuell (Bild & Folie)`:** Zeigt alle Beobachtungen, die aus eingebetteten Screenshots, Diagrammen oder gerenderten Ganzfolien (`PictureSourceNode`) stammen.

**Interaktion im Graphen:**
- **Freies Ziehen:** Jede Karte lässt sich per Maus verschieben; *„Layout neu ordnen"* stellt die automatische Hierarchie wieder her.
- **MiniMap (rechts unten):** Zeigt alle Knoten farbcodiert in der Übersicht; das Sichtfenster lässt sich direkt in der MiniMap verschieben.
- **Fehlerhafte Verbindungen lösen:** Klicke auf eine Beziehung (`B`) oder ein Finding (`C`) → im rechten Inspektor kannst du fehlerhafte KI-Beziehungen per **1-Klick „Verbindung lösen / verwerfen"** trennen oder einzelne Fehl-Stützen aus einem Finding entfernen, ohne die Pipeline neu starten zu müssen!

---

## 6. Parameter-, Prompt- & Preis-Transparenz

### 6.1 Die 3 Parameter-Ebenen (Warum gibt es 3 Werte?)
In `Einstellungen → Modelle & APIs` zeigt die Parameter-Matrix transparent drei getrennte Werte:
1. **Modell-Hardwarelimit (lt. API):** Das gesamte Kontextfenster des Modells (z. B. `262.144` Tokens bei `Qwen3.6` auf FAU).
2. **Interner Docling-Graph-Planungswert (`plan_max_output_tokens`):** Bestimmt intern, ob ein Dokument in einem Stück (`direct`) oder in Teilblöcken (`dense`) verarbeitet wird.
3. **Gesendeter HTTP-Wire-Parameter (`wire_max_tokens`):** Was tatsächlich im JSON-Request über das Netzwerk geht. Bei Gateways mit geteiltem Ein-/Ausgabefenster (wie `nhr_fau`) lässt `UX-mAInd` `max_tokens` im Automatikmodus bewusst weg (`Anbieterautomatik`), damit der Server die maximale Restkapazität dynamisch zuteilen kann.

### 6.2 Prompts einsehen, überarbeiten & zurücksetzen
Unter `Einstellungen → Stufen-Prompts` siehst du für **alle 4 KI-Stufen (`Vision`, `Stufe A`, `Stufe B`, `Stufe C`)**:
- **Was geht rein (`Input`) & was kommt raus (`Output`)**
- **Haupt-Prompt bearbeiten:** Du kannst den Standard-Systemprompt jeder Stufe direkt umschreiben.
- **Zusatz-Instruktionen ergänzen:** Du kannst projektspezifische Zusatzhinweise anhängen, ohne den Haupt-Prompt zu verändern.
- **Original-Standard wiederherstellen:** Setzt Haupt- und Zusatz-Prompt jederzeit mit einem Klick auf den geprüften Werkszustand zurück.

### 6.3 Ehrliche API-Preisberechnung (Null fiktive Zahlen)
- **Lokale & Akademische Endpunkte (`ollama`, `nhr_fau`):** Tatsächliche Abrechnung ist exakt **`0,00 € / $0.00`**.
- **Kommerzielle Cloud-APIs (`OpenAI`, `Anthropic`, `Gemini`, `Mistral`, `OpenRouter`, ...):** Kosten werden ausschließlich dann berechnet, wenn für genau diese Modellkennung ein verifizierter Tarif in der öffentlichen `LiteLLM`-Preistabelle oder der `/models`-API hinterlegt ist:
  $$\text{Kosten} = \frac{(\text{Prompt}_{\text{ungecacht}} \cdot P_{\text{in}}) + (\text{Prompt}_{\text{gecacht}} \cdot P_{\text{cache}}) + (\text{Completion} \cdot P_{\text{out}})}{1\,000\,000}$$
- **Neue / unbekannte Modelle ohne gelisteten Tarif:** Werden ehrlich als **`Kein Tarif hinterlegt`** ausgewiesen — es werden **niemals** fiktive Schätzpreise erfunden.

---

## 7. Betrieb, Prüfer-Profile, 1-Klick-Installation & Server-Deployment

- **1-Klick-Installation & App-Fenster-Start (`US-75`):**
  - **Windows:** `powershell -ExecutionPolicy Bypass -File install.ps1` installiert `.venv` und alle Open-Source-Abhängigkeiten; ein Doppelklick auf `start-ux-maind.cmd` startet Server + eigenständiges Desktop-App-Fenster (`http://127.0.0.1:8465/`).
  - **Linux / macOS:** `./install.sh` richtet `.venv` ein (`.venv/bin/ux-maind`).
  - **Container / Docker:** `docker compose up --build` startet das mehrstufig gebaute Image (`Dockerfile` inkl. headless LibreOffice und persistentem `/data/workspace`-Volume).
- **Wechselbare Prüfer-Profile & optionale OIDC-/Google-Anmeldung (`US-74`):** Über den Prüfer-Chip oben rechts in der Kopfleiste können verschiedene lokale Forscher-Profile (z. B. *Erstprüfer* / *Zweitprüfer*) ohne Login-Zwang gewechselt werden. Jede Prüfentscheidung (`Bestätigen`, `Korrigieren`, `Verwerfen`) stempelt den aktiven Prüfernamen revisionssicher in `ux_decisions.payload.reviewer`. Für gehostete Team-Umgebungen lässt sich optional OpenID Connect / Google OAuth 2.0 über `UX_MAIND_OIDC_CLIENT_ID`, `UX_MAIND_OIDC_CLIENT_SECRET` und `UX_MAIND_OIDC_ISSUER` aktivieren.
- **Lokaler Standardbetrieb:** `ux-maind` startet einen geschützten Loopback-Server (`127.0.0.1`) mit CSRF-Token-Schutz (`X-Workspace-Token`) und speichert alle Daten revisionssicher in `workspace.sqlite` (`WAL`-Modus).
- **Terminal & Verlauf bei Web-/Container-Deployment:** Das Web-Terminal (`GET /api/job-history`) liest nicht aus flüchtigem Browser-Speicher, sondern direkt aus der persistenten SQLite-Datenbank des Servers (inklusive automatischer Rekonstruktion aller Konvertierungs-, Vision-, A-, B- und C-Läufe). Für Mehrbenutzer- oder Cloud-Deployments lässt sich der Hintergrund-Job-Worker (`studio.py:job`) über denselben SQLite-/Queue-Vertrag in einen dedizierten Worker-Prozess auslagern, während die API-Schlüssel ausschließlich als Server-Umgebungsvariablen verbleiben.
