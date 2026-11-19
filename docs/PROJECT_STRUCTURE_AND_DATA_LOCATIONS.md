# UX-mAInd · Projektstruktur & Vollständige Speicherort-Landkarte (`US-76`)

> **Ordnungs- & Erhaltungsprinzip:** Diese Übersicht dokumentiert sämtliche Quellcode-, Dokumentations-, Evaluations- und Studien-Speicherorte des Projekts, damit sich jeder Entwickler, Prüfer oder Folge-Chat sofort zurechtfindet — **ohne bestehende Forschungsdaten, historische Nachweise oder Evaluationsergebnisse zu löschen**.

---

## 1. Kern-Anwendung & Build-Artefakte (`c:\ux-maind-docling`)

| Pfad | Inhalt & Verantwortung | Git-Status (`ux-maind-docling` / `ux-maind-studio`) |
| :--- | :--- | :--- |
| `ux_maind/app/` | Schlanker Python-Kern (`studio.py` HTTP/Job-Server, `workspace.py` SQLite-WAL & Docling-Versionen, `conversion_config.py` native Docling-Optionen, `enrichment.py` Vision/Charts, `evidence.py` 7-Stufen-Re-Grounding, `native_graph.py` LiteLLM/Watchdog, `interpretation.py` B/C-Synthese, `research.py` Epistemik/Graph/Decisions, `auth.py` Prüfer-Profile & OIDC, `telemetry.py` Preise & A4-Handout, `terminal_ui.py` CLI/Web-Verlauf, `prompts_config.py`, `templates.py`). | Versioniert in beiden Repos |
| `frontend/` | Modulares React-18-Studio (`src/App.jsx`, `src/views/*.jsx`, `src/components/*.jsx`, `src/studio.css`, `build.mjs`, `test-components.mjs`). | Versioniert in beiden Repos |
| `ux_maind/app/web/generated/` | Durch `node frontend/build.mjs` erzeugtes Offline-Web-Bundle inkl. `LICENSES.txt` und synchronisierten In-App-Dokumenten (`docs/USER_MANUAL.md`, `docs/SYSTEM_LIMITS.md`). | Lokal generiert (`.gitignore`), im Wheel/Docker enthalten |
| `install.ps1`, `install.sh`, `start-ux-maind.cmd`, `Dockerfile`, `docker-compose.yml` | 1-Klick-Setup-Skripte für Windows, Linux/macOS sowie mehrstufiges Open-Source-Container-Setup (`US-75`). | Versioniert in beiden Repos |
| `tests/` | Automatisierte Test-Suiten (`test_r23_carbon.py`, `test_r29_studio_audit.py`, `test_r31_adversarial_pipeline.py`, `check_wheel.py` u. a. — `77+` Unittests). | Versioniert in beiden Repos |

---

## 2. Dokumentation, Diagramme & Bachelorarbeits-Unterlagen (`docs/`)

| Pfad | Zweck |
| :--- | :--- |
| [`docs/USER_MANUAL.md`](USER_MANUAL.md) | **Single Source of Truth** für Bedienung, Docling-Einstellungen, Modell-Ratgeber und Metadaten-Lexikon (live in der App unter `Einstellungen → Handbuch & Systemgrenzen`). |
| [`docs/SYSTEM_LIMITS.md`](SYSTEM_LIMITS.md) | Ehrliches technisches, formatbezogenes und methodisches Grenzen-Verzeichnis (ebenfalls live in der App lesbar). |
| [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) | Chronologische Architektur- und Revisionsdokumentation bis `R31`. |
| [`docs/HANDOFF_BACKLOG_UND_STATUS.md`](HANDOFF_BACKLOG_UND_STATUS.md) | Bereinigtes Übergabe-Backlog (enthält stets nur noch offene Punkte; erledigte Stories stehen im Tracker/Archiv). |
| [`docs/R30_FINAL_AUDIT_AND_LIMITS.md`](R30_FINAL_AUDIT_AND_LIMITS.md) | Vollständiger Audit-Abschlussbericht über die gelösten Befunde aus Audit 1 & Audit 2 (`US-01..US-69`). |
| `docs/diagrams/01..06_*.svg` | 6 stufenlos zoombare Vektor-Architekturdiagramme für die Bachelorarbeit. |
| `docs/thesis/` | Gliederung, Bauplan, Evaluations-Schreibleitfaden ([`05_BA_EVALUATION_UND_SCHREIBLEITFADEN.md`](thesis/05_BA_EVALUATION_UND_SCHREIBLEITFADEN.md)) und Zotero-Literaturabgleich ([`06_ZOTERO_LITERATUR_UND_METHODIK_ABGLEICH.md`](thesis/06_ZOTERO_LITERATUR_UND_METHODIK_ABGLEICH.md)). |
| `docs/audits/` | Historische Prüf- und Evaluationsberichte (u. a. `AUDIT_HINWEIS_FAU_TIMEOUT_R30.md`, `R31_SERDIF_EXPERT_EVALUATION.md`). |

---

## 3. Lokale Studienkorpora & Menschliche Experten-Referenzen (`data/datasets/`)

> `data/` bleibt bewusst lokal außerhalb von Git (`.gitignore`), wird aber vollständig im verschlüsselten/privaten Google-Drive-Disaster-Recovery-Tresor gesichert.

| Verzeichnis | Art der Daten & Verwendung |
| :--- | :--- |
| `data/datasets/real/serdif/` | **Menschlich annotierte Open-Access-Usability-Studie** (*Navarro-Gallinad et al., Semantic Web Journal 2022*): `data/notes/*.txt`, `data/PSSUQ/comments/*.odt`, `data/PSSUQ/scores/SERDIF_PSSUQ_P2.csv`, `data/transcripts/raw/*.odt` (Primärquellen) sowie `data/transcripts/thematic-analysis/codebooks/codebook_20220303_8.csv` (`22` menschliche Experten-Codes — im Korpus als `Referenz / Codebook` markieren!). |
| `data/datasets/real/subjective_data_models/` | Reale heterogene Studie (`.md`, `.txt`, `.csv`) — genutzt in der Live-FAU-Evaluation (`R29/R30`). |
| `data/datasets/real/*` (`35+` weitere Korpora) | Weitere reale Usability-, Review- und Interview-Korpora (`cue9`, `oss_usability_issues`, `gui_reviews`, `ami_design_meetings` u. a.) für Zusatzexperimente. |
| `data/datasets/synthetic/monday_v1_1/` | Heterogener 6-Dateien-Prüfkorpus (`.txt`, `.docx`, `.pptx` mit Diagrammen, Folienkontext & Durchstreichungen) für reproduzierbare Multi-Modell-Benchmarks. |
| `data/datasets/synthetic/audacity_schnittplatz_v1/` & `qgis_radservice_v1/` | Synthetische Blindlauf-Studien (`import/` für Blindlauf, `evaluation/GROUND_TRUTH.json` erst zur Auswertung öffnen — siehe `GEMINI.md`). |
| `data/datasets/synthetic/structure_variance_v1/` | Technischer Format-Härtetestkorpus (verbundene Zellen, BOM, defekte Dateien, E-Mail-Threads, TSV-Dialekte). |

---

## 4. Gespeicherte Evaluationsläufe, Arbeitsbereiche & Externe Ziele

| Ort | Beschreibung |
| :--- | :--- |
| `%LOCALAPPDATA%\UX-mAInd\workspace-r12` *(Windows-Standard)* | Standard-Arbeitsbereich beim regulären Start von `ux-maind` (`workspace.sqlite`, `exports/`, inhaltsadressierte Dokumentkopien). |
| `artifacts/r29-evaluation/` | Gespeicherte Multi-Modell-Evaluationsdaten (`fau_multi_model_evaluation.json`: `Gemma-4 4B`, `gpt-oss-120b`, `DeepSeek-V4-Flash`, `Qwen3.6 Vision`). |
| `artifacts/r31-serdif/` | Gespeicherter Blindlauf & Experten-Codebook-Abgleich auf `SERDIF` (`serdif_expert_comparison.json` + Workspace). |
| `artifacts/r30-screenshots/` & `artifacts/r31-viewports/` | Verifizierte Headless-Edge-CDP-Abnahme-Screenshots über alle Ansichten und Display-Seitenverhältnisse (`21:9`, `16:9`, `16:10`, `4:3`). |
| `C:\ux-maind-tracker` | Eigenständige lokale Ticket- & Meilenstein-Web-App (`http://127.0.0.1:8470`, `tracker.db` + `seed_tickets.py`). |
| `C:\Users\Chris\Zotero` | Lokale Zotero-10-Literaturdatenbank (Zugriff über `zotero-cli` mit `ZOTERO_LOCAL=true`, Sammlung `Bachelor Arbeit`). |
| GitHub Haupt-Repo | `https://github.com/ChristianU-dev/ux-maind-docling` (vollständige Entwicklungshistorie). |
| GitHub Vorzeige-/Professoren-Repo | `https://github.com/ChristianU-dev/ux-maind-studio` (bereinigter Release-Stand über `scripts/prepare_clean_professor_repo.py`). |
| Google Drive Backup-Tresor | Ordner-ID `1uIIxoyt3j7EOk6yShf3dKSptDqSrDlVM` (`scripts/sync_google_drive.py` — inkl. Code, Docs, Diagrammen und Datensätzen). |
