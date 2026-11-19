# UX-mAInd Studio · R30 Abschluss-Audit, Empirische FAU-Evaluation & Verifikationsnachweis

> **Stand:** 18.11.2026 (`R30`) · **Prüfstatus:** `72 / 72` Python-Unittests grün · Frontend- & Komponenten-Tests grün · `0` proprietäre Abhängigkeiten (`OSI-konform`) · `12 / 12` interaktive Edge-CDP-Ansichten (`0` JS-Ausnahmen) · `69 / 69` User Stories (`US-01..US-69`) abgeschlossen.

---

## 1. Zusammenfassung der Audit-Auflösung (`Teil 1`, `Teil 2`, `R30 Studio` & `US-69`)

Dieses Abschluss-Audit prüft den fertigen `R30`-Systemstand gegen sämtliche Befunde aus:
1. **Technisches Codebase-Audit (`Teil 1`, `B-01..B-32` / `US-01..US-24`)**
2. **Wissenschaftliches Tiefenaudit (`Teil 2`, `D-01..D-20` / `US-25..US-52`)**
3. **Interaktive Studio-, Graph-, Handbuch- & Preis-Anforderungen (`US-53..US-68`)**
4. **FAU-Gateway Stream-/Read-Timeout & Live-Konsolen-Diagnose (`US-69`, [`docs/audits/AUDIT_HINWEIS_FAU_TIMEOUT_R30.md`](audits/AUDIT_HINWEIS_FAU_TIMEOUT_R30.md))**

### 1.1 Behobene Kernrisiken in Datenübergabe, Re-Grounding & Laufzeitstabilität

| Prüfbereich | Vorheriges Risiko (`R26–R28`) | Verifizierte Lösung in `R30` | Nachweis (Code & Test) |
| :--- | :--- | :--- | :--- |
| **Schema-Vollständigkeit (`D-01`)** | `build_compact_semantic_guide` schnitt Feldbeschreibungen `> 250` Zeichen und Tiefe-3-Regeln (`scale_direction`) ab. | Alle `Field(description=...)` in `templates.py` auf `<= 240` Zeichen geschärft (`0` Trunkierungen); Skalenregeln auf Tiefe 2 verankert; `usability_heuristic` (Nielsen / ISO 9241-110) ergänzt. | `templates.py`, `test_r30_schema_zero_truncation_and_salvaged_status` |
| **Tabellen & Skalen in Stufe A/B/C (`B-04..B-06`, `D-05`, `US-27`)** | `TableItem.meta` fehlte im `DocLang`-Prompt; Mehrzeilen-Tabellen mit einem Einzelzitat fielen in `_compact_context` weg; `GRADING_SCALE` & `FormItem` gingen verloren. | Temporäre `[ux_maind: source_ref=#/tables/k | worksheet=... | columns: ...]`-Captions in `model_source()`; Zeilenabdeckungs-Prüfung (`< 85 %` bewahrt Resttabelle); `GRADING_SCALE`/`FormItem`/`KeyValueItem`-Serialisierung; `numeric_value` & `uncertainty` in `_compact_measurement`. | `evidence.py`, `interpretation.py`, `test_b04..test_b06` |
| **Daten- vs. Instruktions-Trennung (`D-03`, `US-34`, `US-54`)** | Fokusfrage und Sprachregeln standen als Textabsätze im Daten-Dokument `evidence.json`; Basis-Prompts waren nicht in der UI editierbar. | `evidence.json` enthält ausschließlich strukturierte Evidenzdaten; Fokus & Sprache laufen über `DiagnosticClient.system_appendix`; Basis-Prompts (`base_prompts`) + Zusatzinstruktionen (`stage_prompts`) sind für Vision, A, B und C editierbar & rücksetzbar. | `prompts_config.py`, `PromptsSettingsTab.jsx` |
| **Exaktes Re-Grounding (`D-08..D-13`, `US-38..US-43`)** | `"5%"` konnte in `"15%"` matchen; PDF-Ligaturen (`ﬁ`, `ﬂ`), Zeilenumbruch-Silbentrennung (`-\n`), verbundene Zellen und Kopf-/Fußzeilen an Seitenumbrüchen verhinderten Treffer. | Unabhängige linke/rechte Wort- & Zifferngrenzen (`(?<!\d)` / `(?!\d)`); index-erhaltende Ligatur- & Silbentrennungs-Projektion; Zellspann-Intervalle; `FURNITURE`-Skip in `adjacent_spans()`; schneller Zitatlisten-Parser inkl. `„..."`. | `evidence.py`, `test_r30_regrounding_*` |
| **Epistemische Integrität & Preise (`D-15..D-20`, `US-45..US-56`)** | Verworfene Stützen blieben teilweise im Finding-Zähler; Cloud-Schätzpreise konnten bei unbekannten Modellen irritieren; `Qwen3.6` fehlte das Multimodal-Badge. | `_finding_epistemics()` prüft alle 4 Belegrollen, setzt `contains_rejected_support`, zählt `distinct_speakers`; `0,00 $` für FAU/Ollama und `null` (`"Kein Tarif"`) ohne verifizierten `litellm.model_cost`-Eintrag; Open-Weight-Multimodal-Erkennung + Live `1×1`-PNG-Vision-Probe. | `research.py`, `models.py`, `telemetry.py` |
| **Wissensgraph & Dual-View (`US-59`, `US-60`)** | `<MiniMap>` blieb weiß; reine Text-/Tabellendateien wirkten ohne B/C isoliert; Sprung vom Finding verlor den Finding-Kontext im Inspektor. | Explizite Knotendimensionen & Farben für `<MiniMap>`; `Dokumentquelle`-Ankerkarten im `Gesamtnetz`; 1-Klick `Verbindung lösen`; aktive `.lx-finding-context-strip`-Belegleiste & rückkopplungsfreier PDF/PPTX-Seiten-Sync. | `graphLayout.js`, `GraphView.jsx`, `InspectorView.jsx` |
| **FAU Stream-/Timeout-Watchdog & Live-Konsole (`US-69`)** | Skalare `httpx`-Timeouts + doppelte `LiteLLM × OpenAI`-Retries führten bei hängenden Proxies oder `29k`-Reasoning-Läufen zu stummen 25–120-Minuten-Blockaden; `receipts.symbol()` schnitt Klartext-Fehler ab. | Explizites `httpx.Timeout`, `num_retries=0` auf SDK-Schicht, überwachter Chunk-Streaming-Watchdog (`idle_s` gegen Proxy-Hänger + `active_wall_s` für echte Reasoning-Streams), `safe_detail()` in `receipts.py` und sofortige `✖`/`⚠`-Meldungen in CLI & Web-Konsole. | `native_graph.py`, `receipts.py`, `terminal_ui.py`, `TerminalView.jsx` |

---

## 2. Empirische Live-Evaluation über das FAU NHR Gateway (`artifacts/r29-evaluation/fau_multi_model_evaluation.json`)

Alle Läufe wurden Ende-zu-Ende über den echten `UX-mAInd Studio`-Server gegen das akademische `NHR@FAU`-Gateway (`https://hub.nhr.fau.de/api/llmgw/v1`, Abrechnung `0,00 €`) ausgeführt. Eingebettete Folien- und Dokumentbilder in `monday_v1_1` (`29` Bildelemente über `.pptx` & `.docx`) wurden vorab mit `Qwen/Qwen3.6-35B-A3B-FP8` (`100 %` Erfolg, `0` Fehler) beschrieben.

### 2.1 Experiment A · 3-Modell-Größenvergleich auf `monday_v1_1` (6 heterogene Dateien: `.txt`, `.pptx`, `.docx`)

| Modell (`nhr_fau`) | Klasse | Gültige A-Dok. | Beobachtungen (A) | Verankert (`BOUND`) | Numerische Messwerte | Relationen (B) *(davon cross-doc)* | Findings (C) | Tokens gesamt *(davon Reasoning)* |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`google/gemma-4-E4B-it`** | 4B Edge | `2 / 6` | `54` | **`54` (`100,0 %`)** | `2` | `11` *(`11`)* | `4` | `58.288` *(`0`)* |
| **`gpt-oss-120b`** | 120B Reasoning | **`6 / 6`** | `182` | **`170` (`93,4 %`)** | `50` | **`16`** *(`8`)* | **`5`** | `330.162` *(`0`)* |
| **`deepseek-ai/DeepSeek-V4-Flash-0731`** | 1M-Ctx MoE CoT | `5 / 6` | **`311`** | **`309` (`99,4 %`)** | **`85`** | — *(Timeout B)* | — | `224.820` *(`121.878`)* |

**Zentrale wissenschaftliche Erkenntnisse für die Bachelorarbeit:**
1. **Untere Modellgrenze bei verschachtelten Schemata (`Gemma-4 4B`):** Das 4B-Edge-Modell verankert flache Interviewtranskripte (`document_01.txt`, `document_02.txt`) zu `100 %` buchstabengetreu, scheitert jedoch bei 4 von 6 komplexeren Dokumenten (`.pptx`/`.docx` mit verschachtelten `Locator`- und `Measurement`-Listen) an der strikten Pydantic-Strukturvalidierung.
2. **Robuster Produktions-Sweet-Spot (`gpt-oss-120b`):** Verarbeitet alle `6 / 6` heterogenen Dateien ohne einen einzigen Schema-Abbruch (`591,7` Tokens pro Beobachtung in Stufe A), bindet `50` strukturierte Zahlenwerte inklusive `numeric_value` und synthetisiert daraus `16` Relationen und `5` dokumentübergreifende Findings.
3. **Reasoning-Runaway vs. Extraktionstiefe (`DeepSeek-V4-Flash`):** Erreicht in Stufe A die höchste Detailtiefe (`311` Beobachtungen, **`99,4 %` Verankerungsquote**, `85` gebundene Messwerte), investiert dafür jedoch `121.878` interne Reasoning-Tokens (`~54 %` aller Completion-Tokens) und läuft bei dichten Ganzfolien-Decks (`document_06.pptx`) bzw. großen 311-Beobachtungs-Synthesen in lange Denkschleifen — die durch den neuen `US-69`-Stream-/Wall-Clock-Watchdog deterministisch abgefangen und protokolliert werden.

### 2.2 Experiment B · Reale Open-Access-Studie `subjective_data_models` (`4` Dateien: `.txt`, `.csv`, `.md` mit `gpt-oss-120b`)

- **Konvertierung & Stufe A:** `4 / 4` Dateien erfolgreich (`1_transcription.txt`, `codebook.csv`, `file_mapping_responses.csv`, `readme.md`).
- **Evidenz & Re-Grounding:** **`93` Beobachtungen extrahiert, davon `87` (`93,5 %`) deterministisch im Original verankert**, `18` numerische Messwerte gebunden.
- **Synthese (Stufe B & C):** `7` Relationen und `4` prüfbare Findings in `267,1 s` Gesamtlaufzeit (`154.843` Tokens gesamt, `0` Fehlerläufe).

---

## 3. Ehrliche Restgrenzen & Offene Punkte nach R30 (Anti-Stale-konform zu [`docs/SYSTEM_LIMITS.md`](SYSTEM_LIMITS.md))

Nach Abschluss aller `69` User Stories verbleiben **keine bekannten Datenverlust- oder UI-Defekte** im definierten Funktionsumfang. Folgende architektonischen und methodischen Grenzen sind bewusst abgegrenzt und in [`docs/SYSTEM_LIMITS.md`](SYSTEM_LIMITS.md) sowie im externen Tracker (`C:\ux-maind-tracker`, `FW-01..FW-06`) festgehalten:

1. **Wörtlichkeits-Schranke (*Verbatim Grounding*):** Rein implizite, nonverbale Eindrücke ohne Text-, Tabellen-, Zeitmarken- oder Bildbeschreibungskorrelat werden absichtlich nicht frei hinzuerfunden.
2. **Kontextfenster bei sehr großen Ganzstudien (`> 80–100` lange Sitzungen):** Der einphasige `direct`-Syntheseweg in Stufe B/C hält alle verankerten Beobachtungen gleichzeitig im Modellkontext; für sehr große Langzeitkorpora empfiehlt sich Kohortenbildung oder eine hierarchische Vor-Clusterung (`FW-05`).
3. **Unbegrenzte Denkschleifen starker CoT-Modelle bei ausgelassenem `max_tokens`:** Wie `DeepSeek-V4-Flash` auf `document_06.pptx` zeigt, können einzelne Reasoning-Modelle ohne explizites Profil-`max_tokens` über `10.000` Denk-Chunks emittieren. Der `US-69`-Watchdog verhindert Hänger zuverlässig; für solche Modelle empfiehlt sich in den Profil-Einstellungen zusätzlich ein explizites `max_output_tokens`-Budget (z. B. `16.384` oder `24.576`).
4. **Lokaler Einzel-Arbeitsbereich vs. Multi-User-Webhosting:** `studio.py` arbeitet lokal revisionssicher auf `SQLite-WAL` (`max_workers=1`). Für parallelen Mehrbenutzer-Webbetrieb ist die Entkopplung über eine externe Worker-Queue (`Redis/PostgreSQL`, `FW-01`) in [`docs/SYSTEM_LIMITS.md` Abschnitt 4](SYSTEM_LIMITS.md) spezifiziert.
5. **Induktive Analyse vs. Codebook-Dateien:** Wird ein deduktives `codebook.csv` gemeinsam mit Transkripten importiert und ausgewählt, behandelt Stufe A auch die Codebook-Definitionen als Quelldokument. Für eine streng blinde induktive Auswertung sollten Codebook-Dateien im `Studienkorpus` abgewählt und erst nachträglich zum Abgleich herangezogen werden.

---

## 4. Reproduzierbare Prüfkommandos

```powershell
# 1. Frontend bauen & Komponenten-/Design-Garantien prüfen
npm run build --prefix frontend
node frontend/test-components.mjs

# 2. Vollständige Python-Testsuite (72 Tests) & OSI-Lizenzprüfung
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.venv\Scripts\python.exe scripts/verify_open_source_licenses.py

# 3. Interaktive 12-Ansichten-Browserabnahme (Edge CDP + Ticket-Tracker)
.\.venv\Scripts\python.exe scripts/verify_ui_r30_studio.py
```
