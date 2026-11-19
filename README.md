# UX-mAInd Studio

**Quellengebundene Analyse- und Synthese-Umgebung für heterogene Usability-Studien**

`UX-mAInd Studio` ist eine lokal ausführbare Open-Source-Forschungsanwendung zur strukturierten, belegtreuen Auswertung heterogener Usability-Artefakte (`.pdf`, `.docx`, `.pptx`, `.odt`, `.xlsx`, `.csv`, `.vtt`, `.md`, `.html`, `.txt`, `.png`/`.jpg`). Das System verbindet lokale Dokumentstrukturierung (**IBM Docling**), schema-geführte Extraktion (**Docling Graph** & **LiteLLM**), deterministische Rückwärts-Verifikation jedes Zitats am Originaldokument und menschliche Prüfhoheit in einer interaktiven **React-19-Werkbank**.

---

## Kernmerkmale

1. **100 % Open-Source & Offline-fähige Oberfläche:** Ausschließlich OSI-lizenzierte Open-Source-Abhängigkeiten (`MIT`, `Apache-2.0`, `BSD`, `ISC`), lokal gebündelt ohne externe Runtime-CDNs (`ux_maind/app/web/generated/LICENSES.txt`).
2. **Mehrstufige, prüfbare Synthese-Pipeline:**
   - **Stufe 01 · Lokale Docling-Struktur:** Layout-, Tabellen- (`TableFormer`), OCR-, Foliennotiz- und Durchstreichungs-Erkennung ohne externen Datenabfluss.
   - **Stufe 02 · Visuelle Analyse (optional):** Explizit freigegebene Bild- und Folienbeschreibung über multimodale Open-Weights- oder Cloud-Modelle.
   - **Stufe A · Dokumentgebundene Evidenz:** Atomare Beobachtungen, Zitate, Messwerte und Skalenrichtungen mit **7-stufigem deterministischem Re-Grounding** am `DoclingDocument`.
   - **Stufe B & C · Dokumentübergreifende Triangulation & Findings:** Verknüpfung bestätigter/verankerter Beobachtungen zu Relationen (`corroborates`, `contradicts`, `causes`) und prüfbaren UX-Findings inkl. Gegenbelegen, Epistemik-Flags und Nielsen-/ISO-9241-110-Zuordnung.
3. **Interaktive Prüfwerkzeuge & Unabhängige Zweitprüfung:** Synchroner **Dual-View-Quelleninspektor** (Original-PDF/Office-Vorschau neben nativer Docling-Struktur & Geometrie), direkte **Einzelprüfung** mit dem lokalen Standardprofil, optionale verblindete **Zweitprüfung („Am selben Rechner" & „Auf zwei Rechnern" per selbsttragendem `.zip`/`.json`-Austausch ohne Cloud-Konto oder erneuten Modelllauf)**, interaktiver **React-Flow-Wissensgraph** sowie druckfertiger **A4-HTML-Übergabebericht**, **Markdown-Bericht** und **Forschungs-JSON**.

---

## Schnellstart & Dauerhafter Arbeitsordner

Voraussetzungen: **Python 3.12+** (empfohlen mit [`uv`](https://docs.astral.sh/uv/)). Die Web-Assets sind bereits fertig gebaut im Paket enthalten; Node.js (`20+`) wird nur bei Änderungen am Frontend benötigt. Optional wird lokal installiertes **LibreOffice (`soffice`)** automatisch für die seitengetreue Office-Vorschau erkannt.

Unter Windows nutzt die Anwendung dauerhaft **`%LOCALAPPDATA%\UX-mAInd\workspace`** als Standard-Arbeitsordner (ein vorhandener Altbestand in `workspace-r12` wird schreibgeschützt erkannt und lässt sich bei geschlossenem Studio per Kopie übernehmen). Ein explizites `--workspace <Pfad>` hat Vorrang, um Entwicklung und Tests getrennt vom regulären Arbeitsstand zu starten:

```powershell
# Option A: 1-Klick-Setup & App-Starter (Windows / Linux / macOS / Docker)
powershell -ExecutionPolicy Bypass -File install.ps1   # Linux/macOS: ./install.sh
start-ux-maind.cmd                                    # Standardpfad %LOCALAPPDATA%\UX-mAInd\workspace
start-ux-maind.cmd --port 8470 --workspace C:\Temp\probe-ws   # Isolierter Test-Arbeitsordner

# Option B: Über uv installieren & starten
uv sync --locked
uv run --locked ux-maind
```

Anschließend öffnet sich `UX-mAInd Studio` unter **`http://127.0.0.1:8465`**. API-Zugänge werden dynamisch über System-Umgebungsvariablen erkannt (z. B. lokales `Ollama` ohne Schlüssel, akademisches `NHR@FAU`-Gateway über `LLMAPI_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY` oder beliebige OpenAI-kompatible `vLLM`-Endpunkte).

### Optional: Frontend neu bauen & Test-Suite ausführen

```powershell
# Frontend-Bundle & Komponenten-Tests
npm ci --prefix frontend --ignore-scripts --no-audit --no-fund
npm run build --prefix frontend
node frontend/test-components.mjs

# Vollständige Python-Unittest-Suite & Lizenzprüfung
uv run --locked python -m unittest discover -s tests -p "test_*.py" -v
uv run --locked python scripts/verify_open_source_licenses.py
```

---

## Dokumentation & Architekturdiagramme

- **Benutzerhandbuch & Metadaten-Lexikon:** [`docs/USER_MANUAL.md`](docs/USER_MANUAL.md) *(auch direkt in der App unter `Einstellungen → Handbuch & Systemgrenzen` verfügbar)*
- **System-, Format- & Methodik-Grenzen:** [`docs/SYSTEM_LIMITS.md`](docs/SYSTEM_LIMITS.md)
- **Systemarchitektur:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Abschluss-Audit & Verifikation:** [`docs/R30_FINAL_AUDIT_AND_LIMITS.md`](docs/R30_FINAL_AUDIT_AND_LIMITS.md) · [`docs/R32_DUAL_REVIEW_ACCEPTANCE.md`](docs/R32_DUAL_REVIEW_ACCEPTANCE.md)
- **Stufenlos zoombare Vektor-Architekturdiagramme (`.svg`):**
  1. [`docs/diagrams/01_master_architecture_r30.svg`](docs/diagrams/01_master_architecture_r30.svg) — Vollständige Gesamtarchitektur (Import, Docling, Re-Grounding, Dual-View, Zweitprüfung & Export)
  2. [`docs/diagrams/02_docling_conversion_vision.svg`](docs/diagrams/02_docling_conversion_vision.svg) — Lokale Docling-Struktur & optionale Vision
  3. [`docs/diagrams/03_stage_a_regrounding.svg`](docs/diagrams/03_stage_a_regrounding.svg) — Stufe A, Stream-Watchdog & Re-Grounding
  4. [`docs/diagrams/04_stage_bc_synthesis_graph.svg`](docs/diagrams/04_stage_bc_synthesis_graph.svg) — Stufen B/C, Epistemik & Wissensgraph
  5. [`docs/diagrams/05_dual_view_human_loop.svg`](docs/diagrams/05_dual_view_human_loop.svg) — Dual-View-Inspektor & A4-Handout
  6. [`docs/diagrams/06_docling_capabilities_vs_limits.svg`](docs/diagrams/06_docling_capabilities_vs_limits.svg) — Docling-Stärken vs. Brücken vs. Grenzen
  7. [`docs/diagrams/07_dual_review_state_and_workspace.svg`](docs/diagrams/07_dual_review_state_and_workspace.svg) — Dauerhafter Arbeitsordner, `workspace-r12`-Übernahme & 4-Stufen-Zweitprüfung
  8. [`docs/diagrams/08_two_machine_exchange_and_release.svg`](docs/diagrams/08_two_machine_exchange_and_release.svg) — 2-Rechner-Dateiübergaben (`.zip`/`.json`), Freigabe-Schranke & Überarbeitung

---

## Mitgelieferte Referenz-Datensätze

Unter [`data/datasets/`](data/datasets/) liegen zwei direkt importierbare Studienkorpora zum sofortigen Nachvollziehen aller Pipeline-Stufen bereit:
- `data/datasets/synthetic/monday_v1_1/inputs/` — Multimodaler Mixed-Methods-Korpus (`.txt`, `.docx`, `.pptx` inkl. Tabellen, Diagrammen und Foliennotizen)
- `data/datasets/real/subjective_data_models/` — Reale Open-Access-Studie (`.txt`, `.csv`, `.md`)

---

## Lizenz

Veröffentlicht unter der [MIT License](LICENSE).
