# API-Übersicht, Datenschutz-Einordnung & Betriebskonzept (UX-mAInd)

Diese Übersicht dokumentiert alle in `ux_maind` verfügbaren Modell- und Dokument-APIs sowie die Begründung ihrer Trennung für Entwicklung, Evaluation (Bachelorarbeit) und produktiven Unternehmenseinsatz.

---

## 1. Übersicht der konfigurierten API-Zugänge

| Anbieter-ID | Name & Zweck | Umgebungsvariable | Kontingent / Kosten | Datenschutz & On-Prem-Tauglichkeit | Nutzung in UX-mAInd |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`nhr_fau`** *(Standard)* | **FAU NHR LLM-Gateway** (`https://hub.nhr.fau.de/api/llmgw/v1`) | `LLMAPI_KEY` | Kostenloses akademisches Kontingent (Rate-/Modelllimits der FAU) | Offene Gewichte (`Qwen/Qwen3.6-35B-A3B-FP8`, `DeepSeek-V4`, `google/gemma-4-E4B-it`) – identisch **lokal/on-prem** in Unternehmen hostbar | **Primär-Standard** für Entwicklung, Tests & Hauptstudien (SERDIF, Monday V1.1, DiagramLab) |
| **`gemini`** *(300€ Trial)* | **Google AI Studio** ( separates Billing-Projekt) | `GEMINI_TRIAL_KEY` *(Fallback-Alias: `GEMINI_API_KEY`, `GeminiAI_Key`, `GeminiAPI_Key`)* | 300 € Startguthaben (90 Tage) über hinterlegtes Zahlungsprofil | Externe Cloud-API (nur nach expliziter Freigabe für Evaluationsvergleiche) | Multimodale Vision-/Kontext-Gegenprüfung & Modellvergleich in der Bachelorarbeit |
| *Privat-Key (geschützt)* | Privater kostenloser Gemini-Key | `GeminiAPI_Key` | Free-Tier (für private Zwecke reserviert) | Externe Cloud-API | Wird **nicht** für UX-mAInd-Läufe angetastet |
| **`anthropic`** *(Hochschule)* | **Usability-Labor Anthropic** | `ANTHROPIC_API_KEY` | **Striktes 30 €-Laborkontingent** | Externe Cloud-API | **Für automatisierte Skripte gesperrt**; nur manuelle Einzel-Stichproben auf Abruf |
| **`ollama`** | **Lokales Ollama** (`http://127.0.0.1:11434`) | *(kein Schlüssel)* | Komplett kostenlos (lokale GPU/CPU) | **100 % On-Premises / Offline** – maximaler Datenschutz | Zielbetrieb für strikt vertrauliche Unternehmensstudien |
| **`mistral`** / **`groq`** / **`nvidia_nim`** | Weitere OpenAI-/Open-Weights-Anbieter | `MistralAPI_Key` / `GROQ_API_KEY` / `NvidiaAPI_Key` | Free-Tier / Credits | Cloud-APIs (Mistral mit EU-Standort; Open-Weights-Modelle) | Optionale Vergleichsprofile über „Modelle & Profile“ |

> **Sicherheitshinweis:** Profile speichern in `workspace.sqlite` **ausschließlich den Namen** der Umgebungsvariable (`key_env`), niemals einen geheimen Schlüsselwert. Einrichtung des 300-€-Keys verdeckt über `scripts/setup_gemini_trial_key.ps1`.

---

## 2. Architekturentscheidung für die Bachelorarbeit: Warum FAU Open-Weights + Docling im Zentrum stehen

Für die praxisnahe UX-Forschung in Unternehmen gelten zwei zentrale Anforderungen aus **AGENTS.md**:
1. **Datenschutz & Souveränität:** Usability-Interviews, Transkripte, PSSUQ-Kommentare und interne Produkt-Screenshots enthalten personenbezogene Daten und Betriebsgeheimnisse. Durch Ausrichtung der Hauptpipeline auf **Open-Weights-Modelle (FAU-Gateway als Testbett für selbst hostbare vLLM/Ollama-Instanzen)** bleibt die komplette Architektur ohne Qualitätsverlust auf eigene Firmenserver übertragbar.
2. **Keine Herstellerbindung (Zero Vendor Lock-in):** Kommerzielle Spitzenmodelle (Google AI Studio / Anthropic) dienen über denselben `LiteLLM`-Pfad als **wissenschaftliche Referenz- und Gegenprüfungs-Baselines** in der Evaluation, nicht als harte Laufzeitabhängigkeit.

---

## 3. Exkurs für *Related Work*: Google Cloud Document AI (Enterprise Document OCR / Layout Parser) vs. Docling

Im Kontext der Google-Cloud-/AI-Studio-Umgebung existiert mit **Google Cloud Document AI** (*Enterprise Document OCR* / *Layout Parser*) ein verwalteter Cloud-Dienst für Texterkennung, Formular- und Tabellenextraktion. Warum nutzt **UX-mAInd** stattdessen bewusst **IBM Docling (Open Source)**:

| Kriterium | Google Cloud Document AI | IBM Docling (+ LibreOffice / PDF.js lokal) |
| :--- | :--- | :--- |
| **Lizenz & Abhängigkeit** | Proprietäre Cloud-API, GCP-Projekt-/IAM-Bindung, pro-Seite-Abrechnung | **Open Source (MIT)**, vollständige lokale Ausführung (`DocumentConverter`), keine Cloud-Gebühren pro Seite |
| **Datenschutz** | Jedes Dokument verlässt zwingend die lokale Infrastruktur Richtung Google Cloud | Originale werden **lokal** in versionierte `DoclingDocument`-JSONs überführt; Cloud-Aufrufe erfolgen frühestens bewusst in nachgelagerten Schritten |
| **Multiformat & Native Geometrie** | Fokus auf PDF/Bild-OCR (Office-Dateien meist vorab zu PDF gerendert → Verlust nativer Run-Formatierung) | Erschließt `.docx`, `.pptx`, `.odt`, `.csv`, `.txt` und `.pdf` **nativ** inkl. `w:strike`/`strikethrough_spans`, Zellkoordinaten, `self_ref`-Hierarchie und separater Ganzfolien-Kontextbilder |
| **Rolle in der Bachelorarbeit** | Wertvoller Vergleichspunkt im Kapitel *Stand der Technik / Alternativen* für stark verrauschte historische Scans | Architektonisches Fundament gemäß Regel 1 (keine proprietäre Abhängigkeit, nachprüfbare lokale Provenienz) |
