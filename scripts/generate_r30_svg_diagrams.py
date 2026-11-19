"""Generate 6 crisp, infinitely zoomable vector .svg architecture diagrams for UX-mAInd R30 (`US-63`)."""

from __future__ import annotations

from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIAG_DIR = ROOT / "docs" / "diagrams"


STYLE_DEFS = """
  <defs>
    <style>
      .bg { fill: #f8fafc; }
      .title { font: 700 22px 'Segoe UI', Inter, system-ui, sans-serif; fill: #0f172a; }
      .subtitle { font: 400 13px 'Segoe UI', Inter, system-ui, sans-serif; fill: #475569; }
      .lane-title { font: 700 13px 'Segoe UI', Inter, system-ui, sans-serif; fill: #0f172a; letter-spacing: 0.04em; }
      .box { fill: #ffffff; stroke: #cbd5e1; stroke-width: 1.5; rx: 10; ry: 10; }
      .box-teal { fill: #f0fdfa; stroke: #0d9488; stroke-width: 1.8; rx: 10; ry: 10; }
      .box-sky { fill: #f0f9ff; stroke: #0284c7; stroke-width: 1.8; rx: 10; ry: 10; }
      .box-amber { fill: #fffbeb; stroke: #d97706; stroke-width: 1.8; rx: 10; ry: 10; }
      .box-emerald { fill: #ecfdf5; stroke: #059669; stroke-width: 1.8; rx: 10; ry: 10; }
      .box-rose { fill: #fff1f2; stroke: #e11d48; stroke-width: 1.8; rx: 10; ry: 10; }
      .box-slate { fill: #f1f5f9; stroke: #64748b; stroke-width: 1.6; rx: 10; ry: 10; }
      .lane { fill: #f1f5f9; stroke: #cbd5e1; stroke-width: 1.2; stroke-dasharray: 5 4; rx: 14; ry: 14; }
      .box-head { font: 700 13.5px 'Segoe UI', Inter, system-ui, sans-serif; fill: #0f172a; }
      .box-code { font: 600 11.5px Consolas, 'JetBrains Mono', monospace; fill: #0f766e; }
      .box-text { font: 400 12px 'Segoe UI', Inter, system-ui, sans-serif; fill: #334155; }
      .badge { font: 700 10.5px Consolas, monospace; fill: #ffffff; }
      .edge { stroke: #475569; stroke-width: 1.8; fill: none; marker-end: url(#arrow); }
      .edge-teal { stroke: #0d9488; stroke-width: 2.0; fill: none; marker-end: url(#arrow-teal); }
      .edge-amber { stroke: #d97706; stroke-width: 1.9; stroke-dasharray: 6 4; fill: none; marker-end: url(#arrow-amber); }
      .edge-label { font: 600 11px 'Segoe UI', Inter, system-ui, sans-serif; fill: #334155; }
    </style>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#475569" />
    </marker>
    <marker id="arrow-teal" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#0d9488" />
    </marker>
    <marker id="arrow-amber" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#d97706" />
    </marker>
  </defs>
"""


def card(
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    code: str,
    lines: list[str],
    cls: str = "box",
    badge: tuple[str, str] | None = None,
) -> str:
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" class="{cls}" />']
    if badge:
        b_txt, b_col = badge
        bw = max(54, len(b_txt) * 7 + 14)
        parts.append(
            f'<rect x="{x + w - bw - 12}" y="{y + 11}" width="{bw}" height="20" rx="5" fill="{b_col}" />'
        )
        parts.append(
            f'<text x="{x + w - bw // 2 - 12}" y="{y + 25}" text-anchor="middle" class="badge">{escape(b_txt)}</text>'
        )
    parts.append(f'<text x="{x + 14}" y="{y + 26}" class="box-head">{escape(title)}</text>')
    cur_y = y + 45
    if code:
        parts.append(f'<text x="{x + 14}" y="{cur_y}" class="box-code">{escape(code)}</text>')
        cur_y += 20
    for ln in lines:
        parts.append(f'<text x="{x + 14}" y="{cur_y}" class="box-text">{escape(ln)}</text>')
        cur_y += 18
    return "\n".join(parts)


def arrow(x1: int, y1: int, x2: int, y2: int, label: str = "", cls: str = "edge") -> str:
    out = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="{cls}" />']
    if label:
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2 - 7
        out.append(f'<text x="{mx}" y="{my}" text-anchor="middle" class="edge-label">{escape(label)}</text>')
    return "\n".join(out)


def path_arrow(d: str, label: str = "", lx: int = 0, ly: int = 0, cls: str = "edge") -> str:
    out = [f'<path d="{d}" class="{cls}" />']
    if label:
        out.append(f'<text x="{lx}" y="{ly}" text-anchor="middle" class="edge-label">{escape(label)}</text>')
    return "\n".join(out)


def wrap_svg(w: int, h: int, heading: str, subheading: str, body: list[str]) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
{STYLE_DEFS}
  <rect x="0" y="0" width="{w}" height="{h}" class="bg" />
  <text x="32" y="42" class="title">{escape(heading)}</text>
  <text x="32" y="65" class="subtitle">{escape(subheading)}</text>
  {chr(10).join(body)}
</svg>
"""


def build_01_master() -> str:
    b = [
        # Lanes
        '<rect x="24" y="86" width="1752" height="225" class="lane" />',
        '<text x="42" y="110" class="lane-title">EBENE 1 · LOKALE ERSCHLIESSUNG &amp; OPT. VISION-ANREICHERUNG (KEIN EXTERNER TEXTABFLUSS IN STUFE 01)</text>',
        '<rect x="24" y="330" width="1752" height="260" class="lane" />',
        '<text x="42" y="354" class="lane-title">EBENE 2 · STUFE A: DOKUMENTGEBUNDENE EVIDENZEXTRAKTION &amp; DETERMINISTISCHES RE-GROUNDING</text>',
        '<rect x="24" y="608" width="1752" height="240" class="lane" />',
        '<text x="42" y="632" class="lane-title">EBENE 3 · STUFEN B &amp; C: DOKUMENTÜBERGREIFENDE TRIANGULATION, EPISTEMIK &amp; PERSISTENZ</text>',
        '<rect x="24" y="866" width="1752" height="230" class="lane" />',
        '<text x="42" y="890" class="lane-title">EBENE 4 · FORSCHUNGSOBERFLÄCHE (REACT 19 STUDIO), DUAL-VIEW-INSPEKTOR &amp; A4-ÜBERGABE</text>',
        # Row 1
        card(
            42, 126, 360, 165,
            "Heterogener Studienkorpus",
            "workspace.import_paths() · SHA-256",
            [
                "• PDF, DOCX, PPTX, ODT, XLSX, CSV",
                "• WebVTT, Markdown, HTML, TXT, PNG/JPG",
                "• Frei gewählter Ordner ohne Pflicht-Whitelist",
                "• Unveränderte Kopie in work/stored/",
            ],
            "box-slate",
            ("INPUT", "#475569"),
        ),
        card(
            452, 126, 420, 165,
            "Stufe 01 · Lokale Docling-Struktur",
            "DocumentConverter · PdfPipelineOptions · office.py",
            [
                "• Layout, TableFormer (FAST/ACCURATE), RapidOCR",
                "• PPTX/DOCX Durchstreichungen & Vortragsnotizen",
                "• LibreOffice Ganzfolien-Render (slide_context)",
                "• Basis-DoclingDocument JSON (work/native/)",
            ],
            "box-teal",
            ("LOKAL", "#0d9488"),
        ),
        card(
            922, 126, 410, 165,
            "Stufe 02 · Visuelle Analyse (Optional)",
            "enrichment.py · PictureDescriptionApiOptions",
            [
                "• Explizite Pixel-Freigabe (send_pixels=True)",
                "• VLM-Bildbeschreibung & Chart-Tabellenextraktion",
                "• Editierbarer Basis-Prompt + Zusatzhinweise",
                "• Neue versionierte DoclingDocument-Fassung",
            ],
            "box-sky",
            ("VISION", "#0284c7"),
        ),
        card(
            1382, 126, 372, 165,
            "Dynamischer Modellkatalog & Profile",
            "models.py · LiteLLM · /v1/models · Vision-Probe",
            [
                "• FAU NHR, Ollama, Gemini, OpenRouter, Custom",
                "• Multimodal-Erkennung (z.B. Qwen3.6-35B-A3B)",
                "• Live 1×1 PNG Vision-Probe & echte Tarife",
                "• 0,00 € für FAU/Lokal · null ohne Schätzpreis",
            ],
            "box",
            ("CONFIG", "#334155"),
        ),
        arrow(402, 208, 452, 208, "Original"),
        arrow(872, 208, 922, 208, "Bilder/Folien", "edge-teal"),
        # Row 2
        card(
            42, 372, 390, 196,
            "Modell-Quellaufbereitung (Stufe A)",
            "evidence.model_source() · DocLang / Markdown",
            [
                "• Temporäre Tabellen-Captions [source_ref=#/tables/i]",
                "• Spaltenköpfe + Worksheet-Kontext sichtbar",
                "• GRADING_SCALE & FormItems verlustfrei",
                "• Original-DoclingDocument bleibt unberührt",
            ],
            "box-teal",
            ("PREP", "#0d9488"),
        ),
        card(
            482, 372, 410, 196,
            "Stufe A · Evidenzextraktion (Docling-Graph)",
            "native_graph.py · UXEvidenceDocument",
            [
                "• Feldtexte <= 240 Zeichen (0 Schema-Trunkierung)",
                "• httpx.Timeout + Stream-Idle-Watchdog + Live-Konsole",
                "• Extrahiert Zitate, Messwerte, Skalenpolung, Kontext",
                "• Erkennt SCHEMA_SALVAGED & reasoning_tokens",
            ],
            "box-teal",
            ("STUFE A", "#0d9488"),
        ),
        card(
            942, 372, 410, 196,
            "Deterministisches Re-Grounding",
            "evidence.Sources.locate() · observation_view()",
            [
                "• 1. Exakter Span · 2. Ligaturen (ﬁ/ﬂ) & Trennstriche",
                "• 3. Wortgrenzen ('5%' matcht niemals in '15%')",
                "• 4. Verbundene Tabellenzellen & Zitatlisten („...“)",
                "• Kandidaten-Anker + ambiguous_count bei Mehrdeutigkeit",
            ],
            "box-emerald",
            ("VERIFY", "#059669"),
        ),
        card(
            1402, 372, 352, 196,
            "Stufe-A-Gatekeeper & Heilung",
            "a_status.dimensions() · exclusion_reasons",
            [
                "• Trennt zitierbare vs. ausgeschlossene Belege",
                "• Transparente Ausschlussgründe im Popover",
                "• 1-Klick Kandidaten-Heilung durch Forscher",
                "• Carry-Forward bestätigter Entscheidungen",
            ],
            "box-amber",
            ("GATE", "#d97706"),
        ),
        path_arrow("M 662 291 L 662 315 L 237 315 L 237 372", "DoclingDocument", 450, 311, "edge-teal"),
        path_arrow("M 1127 291 L 1127 315 L 237 315 L 237 372", "", 0, 0, "edge-teal"),
        arrow(432, 470, 482, 470, "DocLang/MD"),
        arrow(892, 470, 942, 470, "Roh-JSON"),
        arrow(1352, 470, 1402, 470, "SOURCE_RESOLVED", "edge-teal"),
        # Row 3
        card(
            42, 648, 400, 180,
            "Reiner JSON-Synthese-Handoff",
            "interpretation._build_synthesis_document()",
            [
                "• Reine Daten in evidence.json (ohne Prompt-Mischung)",
                "• Sprach-/Zusatzregeln strikt in system_appendix",
                "• Übergibt numeric_value, scale_direction, outline,",
                "  track, strikethrough_spans & Mehrzeilen-Tabellen",
            ],
            "box-amber",
            ("HANDOFF", "#d97706"),
        ),
        card(
            492, 648, 390, 180,
            "Stufe B · Dokumentübergreifende Relationen",
            "UXRelationProposals · structured_sparse_check=False",
            [
                "• Verbindet Beobachtungen über Dateien hinweg",
                "• corroborates, contradicts, elaborates, causes",
                "• Unterscheidet dokumentintern vs. -übergreifend",
                "• Eigener nativer Laufbeleg in SQLite",
            ],
            "box-amber",
            ("STUFE B", "#d97706"),
        ),
        card(
            932, 648, 410, 180,
            "Stufe C · UX-Findings & Epistemik",
            "UXFindingProposals · research._finding_epistemics()",
            [
                "• Supports, Opposes, Qualifies + Nielsen/ISO-Heuristik",
                "• Prüft alle 4 Rollenlisten & verworfene Stützbelege",
                "• Dedupliziert Folienrender-Überlappung + Sprecherzahl",
                "• Unabhängigkeitsmaße pro Finding",
            ],
            "box-emerald",
            ("STUFE C", "#059669"),
        ),
        card(
            1392, 648, 362, 180,
            "SQLite WAL Workspace & Audit-Ledger",
            "workspace.db · files / runs / ux_objects / ux_decisions",
            [
                "• KI-Rohvorschläge niemals überschrieben",
                "• Forscher-Review: confirmed, corrected, rejected",
                "• Rekonstruiert kompletten Job-Verlauf aus SQLite",
                "• Revisionssichere Basis- & Lauf-Versionierung",
            ],
            "box-slate",
            ("SQLITE WAL", "#475569"),
        ),
        path_arrow("M 1578 568 L 1578 594 L 242 594 L 242 648", "Nur verankerte A-Basis", 910, 590, "edge-teal"),
        arrow(442, 738, 492, 738, "evidence.json"),
        arrow(882, 738, 932, 738, "A + Relationen B"),
        arrow(1342, 738, 1392, 738, "Persistenz"),
        # Row 4
        card(
            42, 908, 400, 168,
            "Synthese-Workbench & Modell-Telemetrie",
            "SynthesisView · StudyAnalyticsView · telemetry.py",
            [
                "• Master-Detail-Prüfung mit Korrekturleitfaden",
                "• Triangulations-Matrix (ohne verworfene Vorschläge)",
                "• Modell-Evaluationsmatrix (Ertrag, Anker-%, Tokens)",
                "• CSV-Export für Kapitel Evaluation der BA",
            ],
            "box",
            ("VIEW 3", "#0f766e"),
        ),
        card(
            492, 908, 410, 168,
            "Interaktiver Evidenz- & Wissensgraph",
            "GraphView (@xyflow/react + Dagre) · MiniMap",
            [
                "• Modi: Findings-Ketten, Gesamtnetz, Gegenbelege, Visuell",
                "• Dokumentquellen- & Bildquellen-Hubs für alle Formate",
                "• Freies Drag & Drop + farbige MiniMap ab 1 Knoten",
                "• Fehlerhafte KI-Kanten per Klick ‚Verbindung lösen‘",
            ],
            "box",
            ("VIEW 4", "#0284c7"),
        ),
        card(
            952, 908, 410, 168,
            "Synchroner Dual-View-Quelleninspektor",
            "InspectorView · PDF.js + DoclingReader + docling-img",
            [
                "• Aktive Finding-Belegleiste zum Durchklicken aller Zitate",
                "• Rückkopplungsfreie PDF/PPTX-Seitensynchronisation",
                "• Volle Tabellen, Streichungen, Notizen & SVG-Boxen",
                "• Protokollierter Modell-Input & .MD / JSON Export",
            ],
            "box",
            ("VIEW 5", "#059669"),
        ),
        card(
            1412, 908, 342, 168,
            "Druckbares A4-Handout & Handbuch",
            "html_handout() · USER_MANUAL.md · SYSTEM_LIMITS.md",
            [
                "• Druckfertiges A4-Übergabedokument (Strg+P / PDF)",
                "• Zeigt bestätigte/korrigierte Findings + Zitatbelege",
                "• Verworfene KI-Vorschläge sauber abgetrennt",
                "• In-App Handbuch & ehrliche Systemgrenzen",
            ],
            "box-emerald",
            ("EXPORT", "#059669"),
        ),
        path_arrow("M 1137 828 L 1137 854 L 242 854 L 242 908", "", 0, 0),
        path_arrow("M 1137 828 L 1137 854 L 697 854 L 697 908", "", 0, 0),
        arrow(442, 992, 492, 992, "Fokus"),
        arrow(902, 992, 952, 992, "Belegkette", "edge-teal"),
        arrow(1362, 992, 1412, 992, "Übergabe"),
    ]
    return wrap_svg(
        1800,
        1120,
        "UX-mAInd Studio (R30) — Gesamtarchitektur & Quellengebundener Datenfluss",
        "Vollständige Open-Source-Pipeline auf Basis von Docling, Docling Core, Docling Graph, LiteLLM, SQLite WAL und React 19",
        b,
    )


def build_02_conversion_vision() -> str:
    b = [
        '<rect x="24" y="88" width="1512" height="310" class="lane" />',
        '<text x="42" y="112" class="lane-title">STUFE 01 · LOKALE DOCLING-KONVERTIERUNG &amp; OFFICE-FORMATIERUNGSBRÜCKE (KEIN CLOUD-AUFRUF)</text>',
        '<rect x="24" y="420" width="1512" height="310" class="lane" />',
        '<text x="42" y="444" class="lane-title">STUFE 02 · OPTIONALE VISUELLE ANALYSE (BEWUSSTE PIXEL-FREIGABE &amp; VERSIONIERTES DOCLINGDOCUMENT)</text>',
        card(
            44, 130, 330, 245,
            "Eingangsformate im Korpus",
            "InputFormat (Docling v2.88+)",
            [
                "• PDF & Scans (PNG, JPG, TIFF, WEBP)",
                "• Word (.docx) & OpenDocument (.odt)",
                "• PowerPoint (.pptx) inkl. Speaker Notes",
                "• Tabellen (.xlsx, .csv)",
                "• Transkripte (.vtt, .txt, .md, .html)",
                "• SHA-256 Deduplizierung beim Import",
            ],
            "box-slate",
            ("FORMATE", "#475569"),
        ),
        card(
            424, 130, 360, 245,
            "Docling Standard-Pipeline",
            "DocumentConverter · PdfPipelineOptions",
            [
                "• OCR: RapidOCR / EasyOCR / Tesseract / Mac",
                "• TableFormer: ACCURATE oder FAST + Zellmatching",
                "• Layout-BBoxen, Lesereihenfolge & Seitenbilder",
                "• Code-/Formel-Erkennung & Seitenbereich-Limit",
                "• Qualitätsmetriken: layout / parse / table / ocr",
            ],
            "box-teal",
            ("DOCLING", "#0d9488"),
        ),
        card(
            834, 130, 340, 245,
            "UX-mAInd Office-Erweiterung",
            "office.py (Nachgewiesene Bibliothekslücke)",
            [
                "• pptx_formatting(): Run- & Teil-Streichungen",
                "• docx_formatting(): Absatz- & Zellen-Streichungen",
                "• office_pdf(): LibreOffice Headless Anzeige-PDF",
                "• attach_slide_views(): Ganzfolien als PictureItem",
                "• attach_pdf_page_views(): Seitenkontext für PDFs",
            ],
            "box-amber",
            ("BRIDGE", "#d97706"),
        ),
        card(
            1224, 130, 290, 245,
            "Basis-DoclingDocument",
            "work/native/<id>.json",
            [
                "• Einheitlicher JSON-Baum (v1.10)",
                "• texts, tables, pictures, groups",
                "• key_value_items & form_items",
                "• ContentLayer: BODY, NOTES, FURNITURE",
                "• Unveränderbare Basis-Version",
            ],
            "box-emerald",
            ("NATIVE V0", "#059669"),
        ),
        arrow(374, 252, 424, 252, "Lokal"),
        arrow(784, 252, 834, 252, "PPTX/DOCX/PDF"),
        arrow(1174, 252, 1224, 252, "JSON + SHA256", "edge-teal"),
        # Vision row
        card(
            44, 464, 350, 240,
            "Explizite Datenschutz-Freigabe",
            "send_pixels=True · Vision-Probe",
            [
                "• Ohne Freigabe verlassen 0 Pixel den PC",
                "• Einstellbare Mindestbildfläche (z.B. 5%)",
                "• Live-Test ‚Vision testen‘ (1×1 PNG Probe)",
                "• Unterstützt Lokal (Ollama), FAU (Qwen3.6)",
                "  oder Cloud-VLMs über OpenAI-kompatible API",
            ],
            "box-rose",
            ("CONSENT", "#e11d48"),
        ),
        card(
            444, 464, 370, 240,
            "Editierbarer Vision-Prompt & Modi",
            "prompts_config.py · enrichment.py",
            [
                "• Standard-Basisprompt vollständig editierbar",
                "• + Optionale projektspezifische Zusatzregeln",
                "• 1-Klick Reset auf Werkseinstellung",
                "• Automatische Aktivierung von FigureClassifier,",
                "  sobald Chart-Extraktion eingeschaltet wird",
            ],
            "box-sky",
            ("PROMPT", "#0284c7"),
        ),
        card(
            864, 464, 330, 240,
            "Docling Vision-Anreicherung",
            "PictureDescriptionApiOptions · GraniteChart",
            [
                "• Schreibt PictureMeta.description.text",
                "• Extrahiert Balken-/Liniendiagramme in",
                "  PictureMeta.tabular_chart.chart_data",
                "• Speichert Modell, Parameter & Dauer im",
                "  Versions-Beleg (versions-Tabelle)",
            ],
            "box-sky",
            ("ENRICH", "#0284c7"),
        ),
        card(
            1244, 464, 270, 240,
            "Angereicherte Version",
            "work/versions/<sha256>.json",
            [
                "• Basis-JSON bleibt erhalten!",
                "• Jede Bildaussage trägt Herkunft:",
                "  picture_description oder",
                "  chart_enrichment / slide_context",
                "• Sofort bereit für Stufe A",
            ],
            "box-emerald",
            ("NATIVE V1+", "#059669"),
        ),
        path_arrow("M 1369 375 L 1369 405 L 219 405 L 219 464", "Bilder & Folien", 790, 401, "edge-teal"),
        arrow(394, 584, 444, 584, "Freigabe"),
        arrow(814, 584, 864, 584, "API / Lokal"),
        arrow(1194, 584, 1244, 584, "Meta-Felder", "edge-teal"),
    ]
    return wrap_svg(
        1560,
        760,
        "Detaildiagramm 02 — Lokale Docling-Konvertierung, Office-Brücke & Visuelle Anreicherung",
        " Zusammenspiel von nativen Docling-Pipelines, gezielten UX-mAInd-Formatierungsbrücken und versionierter Vision-Analyse",
        b,
    )


def build_03_stage_a() -> str:
    b = [
        '<rect x="24" y="88" width="1512" height="315" class="lane" />',
        '<text x="42" y="112" class="lane-title">TEIL A1 · VERLUSTFREIE QUELLAUFBEREITUNG &amp; DOCLING-GRAPH SCHEMA-EXTRAKTION</text>',
        '<rect x="24" y="425" width="1512" height="330" class="lane" />',
        '<text x="42" y="449" class="lane-title">TEIL A2 · MEHRSTUFIGES DETERMINISTISCHES RE-GROUNDING &amp; KANDIDATEN-HEILUNG</text>',
        card(
            44, 130, 350, 250,
            "1. Temporäre Modell-Quelle",
            "evidence.model_source()",
            [
                "• Klont DoclingDocument nur für den LLM-Lauf",
                "• Injiziert Tabellen-Caption:",
                "  [ux_maind: source_ref=#/tables/0 | cols=...]",
                "• Bewahrt Worksheet-Namen & Spaltenköpfe",
                "• Fallback GRADING_SCALE -> TEXT für DocLang",
                "• Projiziert KeyValueItem & FormItem Texte",
            ],
            "box-teal",
            ("STEP 1", "#0d9488"),
        ),
        card(
            444, 130, 350, 250,
            "2. Prompt- & Schema-Vertrag",
            "UXEvidenceDocument · prompts_config.py",
            [
                "• Alle Feld-Descriptions <= 240 Zeichen",
                "  (verhindert 250-Zeichen-Abschnitt in Docling-Graph)",
                "• scale_direction auf Tiefe 2 voll sichtbar",
                "• Editierbarer Basis-Prompt + Zusatzhinweise",
                "• Modi: Auto / Direct (One-Pass) / Standard / Dense",
            ],
            "box-sky",
            ("STEP 2", "#0284c7"),
        ),
        card(
            844, 130, 340, 250,
            "3. Docling-Graph + LiteLLM Aufruf",
            "native_graph.py · _diag_lock",
            [
                "• Thread-sichere Request-Diagnose (_diag_lock)",
                "• httpx.Timeout + Chunk-Idle- & Wall-Clock-Watchdog",
                "• Kontrollierte Retries & Live-Konsolen-Diagnose",
                "• Erfasst prompt-, completion-, reasoning- &",
                "  cached_tokens exakt im Laufbeleg",
            ],
            "box-teal",
            ("STEP 3", "#0d9488"),
        ),
        card(
            1234, 130, 280, 250,
            "4. Roh-Extraktionsbeleg",
            "runs-Tabelle (SQLite)",
            [
                "• Unveränderte Modell-Antwort",
                "• Erkennt partielle Schema-Rettung",
                "  als SCHEMA_SALVAGED",
                "• Speichert Modell-Input für",
                "  Inspektor-Prüfung",
            ],
            "box-slate",
            ("RAW RUN", "#475569"),
        ),
        arrow(394, 255, 444, 255, "DocLang / MD"),
        arrow(794, 255, 844, 255, "JSON-Schema"),
        arrow(1184, 255, 1234, 255, "LLM Output"),
        # Row 2: Re-grounding cascade
        card(
            44, 468, 360, 262,
            "5. Text- & Typografie-Verifikation",
            "Sources.locate() · _normalized_spans()",
            [
                "• Pass 1: Exakter Unicode-Codepoint-Span im Element",
                "• Pass 2: Index-erhaltende Normalisierung:",
                "  – PDF-Ligaturen (ﬁ -> fi, ﬂ -> fl, ﬀ -> ff)",
                "  – Silbentrennung am Zeilenende (-\\n)",
                "  – Unsichtbare Soft-Hyphens (\\u00ad, \\u200b)",
                "• Pass 3: Unabhängige Wortgrenzen ('5%' != '15%')",
            ],
            "box-emerald",
            ("TEXT CHECK", "#059669"),
        ),
        card(
            454, 468, 350, 262,
            "6. Tabellen-, Chart- & Seiten-Anker",
            "_table_matches() · adjacent_spans()",
            [
                "• Prüft exakte Zelle sowie verbundene Spans",
                "  (start_row..end_row, start_col..end_col)",
                "• Minus-Normalisierung ('−2,5' == '-2,5')",
                "• Zitatlisten inkl. deutscher Anführungszeichen „...“",
                "• Seitenumbruch-Spans überspringen Kopf-/Fußzeilen",
            ],
            "box-emerald",
            ("STRUCT CHECK", "#059669"),
        ),
        card(
            854, 468, 330, 262,
            "7. Mehrdeutigkeit & Kandidaten",
            "candidate_anchors · ambiguous_count",
            [
                "• Wenn Zitat mehrfach vorkommt: KEIN blindes",
                "  Raten der ersten Fundstelle!",
                "• Status bleibt offen (MULTIPLE_MATCHES)",
                "• Bis zu 5 konkrete Kandidatenstellen +",
                "  Gesamtzahl zur 1-Klick-Auswahl in der UI",
            ],
            "box-amber",
            ("AMBIGUITY", "#d97706"),
        ),
        card(
            1234, 468, 280, 262,
            "8. Freigabe an Stufe B & C",
            "a_status.py · research.catalog()",
            [
                "• Nur SOURCE_RESOLVED & nicht",
                "  verworfene Beobachtungen sind",
                "  zitierbar (citation_ready)",
                "• Ausgeschlossene Punkte mit",
                "  Klartext-Grund dokumentiert",
            ],
            "box-teal",
            ("VERIFIED A", "#0d9488"),
        ),
        path_arrow("M 1374 380 L 1374 410 L 224 410 L 224 468", "Jedes Zitat & jeder Messwert", 800, 406, "edge-teal"),
        arrow(404, 598, 454, 598, "Fallback"),
        arrow(804, 598, 854, 598, "Treffer > 1", "edge-amber"),
        arrow(1184, 598, 1234, 598, "1-Klick Heilung / Eindeutig", "edge-teal"),
    ]
    return wrap_svg(
        1560,
        780,
        "Detaildiagramm 03 — Stufe A: Evidenzextraktion & Deterministisches Re-Grounding",
        "Wie UX-mAInd jedes extrahierte Zitat und jeden Zahlenwert zeichen- und zellgenau gegen das Original-DoclingDocument prüft",
        b,
    )


def build_04_stage_bc_graph() -> str:
    b = [
        '<rect x="24" y="88" width="1512" height="315" class="lane" />',
        '<text x="42" y="112" class="lane-title">STUFEN B &amp; C · DOKUMENTÜBERGREIFENDE SYNTHESE MIT STRIKTER DATEN-INSTRUKTIONS-TRENNUNG</text>',
        '<rect x="24" y="425" width="1512" height="330" class="lane" />',
        '<text x="42" y="449" class="lane-title">EPISTEMISCHE PRÜFUNG &amp; INTERAKTIVER REACT-FLOW EVIDENZGRAPH</text>',
        card(
            44, 130, 360, 250,
            "Reines Synthese-Dokument",
            "evidence.json + system_appendix",
            [
                "• evidence.json enthält 100 % strukturierte Daten:",
                "  Observations, Anchors, Messwerte, Kontextblöcke",
                "• KEINE Prompt-Anweisungen im Daten-JSON!",
                "• Ausgabesprache & Zusatzprompt laufen sauber",
                "  über system_appendix im System-Prompt",
            ],
            "box-teal",
            ("PURE DATA", "#0d9488"),
        ),
        card(
            454, 130, 340, 250,
            "Stufe B · Relationen-Vorschläge",
            "UXRelationProposals (Stage B)",
            [
                "• Verbindet source -> target Beobachtungs-IDs",
                "• Typen: corroborates, contradicts,",
                "  elaborates, causes, sequence",
                "• structured_sparse_check=False verhindert",
                "  unnötigen Fallback bei prägnanten Antworten",
            ],
            "box-amber",
            ("STUFE B", "#d97706"),
        ),
        card(
            844, 130, 360, 250,
            "Stufe C · Finding-Kandidaten",
            "UXFindingProposals (Stage C)",
            [
                "• Synthetisiert UX-Befunde mit Pflicht-Ankern:",
                "  supports[], opposes[], qualifies[], relations[]",
                "• Klassifiziert Valenz, Scope, Observed Effect",
                "• Optional: Nielsen H1–H10 / ISO 9241-110",
                "• Gestaltungshypothese klar als ungeprüft markiert",
            ],
            "box-emerald",
            ("STUFE C", "#059669"),
        ),
        card(
            1254, 130, 260, 250,
            "Referenz-Validierung",
            "interpretation._valid_ref()",
            [
                "• Prüft jede vom LLM genannte",
                "  (document, run, observation)-ID",
                "• Unbekannte IDs werden als",
                "  unresolved protokolliert statt",
                "  stillschweigend geschluckt",
            ],
            "box-rose",
            ("AUDIT", "#e11d48"),
        ),
        arrow(404, 255, 454, 255, "Stufe B"),
        arrow(794, 255, 844, 255, "A + B"),
        arrow(1204, 255, 1254, 255, "ID-Prüfung"),
        # Row 2
        card(
            44, 468, 380, 262,
            "Epistemische Unabhängigkeitsprüfung",
            "research._finding_epistemics()",
            [
                "• Prüft supports, opposes, qualifies & improvement",
                "• Erkennt verworfene Beobachtungen sofort:",
                "  Flag contains_rejected_support + Abzug im Zähler",
                "• Verhindert Doppelzählung von Text + Ganzfolien-",
                "  Render derselben Seite (dependent_visual_overlap)",
                "• Zählt unabhängige Dokumente & Sprecherrollen",
            ],
            "box-amber",
            ("EPISTEMICS", "#d97706"),
        ),
        card(
            474, 468, 370, 262,
            "Wissensgraph-Topologie & Modi",
            "nx.DiGraph + GraphView.jsx + graphLayout.js",
            [
                "• Findings-Ketten: C -> B -> A -> Bildquelle",
                "• Gesamtnetz: projiziert Dokumentquellen-Karten",
                "  für Text/Tabellen (.txt, .docx, .odt) + Bildquellen",
                "• Gegenbelege: isoliert rot gestrichelte Widersprüche",
                "• 16:9 Shelf-Layout + farbige MiniMap ab 1 Knoten",
            ],
            "box-sky",
            ("GRAPH UI", "#0284c7"),
        ),
        card(
            894, 468, 330, 262,
            "Interaktive Korrektur im Graphen",
            "Drag & Drop · ‚Verbindung lösen‘",
            [
                "• Jede Karte frei verschiebbar + Auto-Layout-Reset",
                "• Relationen direkt im Inspektor verwerfen",
                "• Fehlerhafte Stütz-/Gegen-/B-Kanten einzeln",
                "  vom Finding lösen (ux-decision: corrected)",
                "• Verworfene Knoten verschwinden aus aktivem Netz",
            ],
            "box-emerald",
            ("INTERACTIVE", "#059669"),
        ),
        card(
            1274, 468, 240, 262,
            "Nahtloser Belegsprung",
            "onShowSource(findingContext)",
            [
                "• 1 Klick auf beliebigen Beleg",
                "  öffnet Dual-View-Inspektor",
                "• Übergibt komplette Belegkette",
                "  des Findings als klickbare",
                "  Fokusleiste oben im Viewer",
            ],
            "box-teal",
            ("DEEP LINK", "#0d9488"),
        ),
        path_arrow("M 1384 380 L 1384 410 L 234 410 L 234 468", "Geprüfte Objekte", 810, 406, "edge-teal"),
        arrow(424, 598, 474, 598, "Flags & Metriken"),
        arrow(844, 598, 894, 598, "Auswahl"),
        arrow(1224, 598, 1274, 598, "Original prüfen", "edge-teal"),
    ]
    return wrap_svg(
        1560,
        780,
        "Detaildiagramm 04 — Stufen B & C: Triangulation, Epistemische Prüfung & Wissensgraph",
        "Wie Einzelbeobachtungen über Dokumentgrenzen hinweg vernetzt, epistemisch gewichtet und im Graphen kuratiert werden",
        b,
    )


def build_05_dual_view_human_loop() -> str:
    b = [
        '<rect x="24" y="88" width="1512" height="624" class="lane" />',
        '<text x="42" y="112" class="lane-title">GESCHLOSSENER PRÜF- &amp; ÜBERGABEKREISLAUF (SYNCHRONER DUAL-VIEW · AUDIT-LEDGER · A4-HANDOUT)</text>',
        card(
            44, 134, 460, 250,
            "Linkes Panel: Unverändertes Original / Anzeige-PDF",
            "PDF.js (pdf.html / pdf.js) & Plain-Text-Viewer",
            [
                "• PDF: Direktes Rendering der Originaldatei mit Textsuche",
                "• PPTX / DOCX / ODT: Lokales LibreOffice-Anzeige-PDF",
                "  (klar gekennzeichnet als ‚Anzeige-Derivat, keine Quelle‘)",
                "• TXT / MD / VTT: Zeichenexakte <mark>-Hervorhebung",
                "• Rückkopplungsfreie Seitensynchronisation beim Scrollen",
                "  (lastPdfReportedPageRef verhindert Scroll-Snapping)",
            ],
            "box-slate",
            ("LINKS: ORIGINAL", "#475569"),
        ),
        card(
            554, 134, 460, 250,
            "Rechtes Panel: Docling-Lesefassung & Seitengeometrie",
            "DoclingReader.jsx & <docling-img> Web Component",
            [
                "• Lesefassung: Alle Absätze, volle Tabellen (400 Zeilen),",
                "  Wort-Durchstreichungen, Speaker Notes & Vision-Boxen",
                "• Geometrie-Modus: Original-Seitenbild mit interaktiven",
                "  SVG-Bounding-Boxen aller erkannten Docling-Elemente",
                "• OCR-Fallback: Kein Textlayer-Treffer im Scan-PDF ->",
                "  automatischer Wechsel auf präzise Docling-BBox!",
            ],
            "box-teal",
            ("RECHTS: DOCLING", "#0d9488"),
        ),
        card(
            1064, 134, 450, 250,
            "Aktive Finding-Belegleiste & Transparenz-Modals",
            "lx-finding-context-strip · /api/model-input",
            [
                "• Zeigt beim Sprung aus Finding/Graph oben alle Belege",
                "  dieses Befunds über alle Dokumente zum Durchklicken",
                "• ‚Belege (N)‘: Alle verankerten A-Zitate des Dokuments",
                "• ‚Elemente‘: Vollsuche über #/texts/, #/tables/, #/pictures/",
                "• ‚Modell-Input‘: Exakter an das LLM gesendeter Text",
                "• Direkt-Download als .MD, Docling JSON oder Original",
            ],
            "box-sky",
            ("PROVENANCE", "#0284c7"),
        ),
        arrow(504, 259, 554, 259, "Seite & Zitat sync", "edge-teal"),
        arrow(1014, 259, 1064, 259, "Kontext"),
        # Bottom row
        card(
            44, 434, 460, 248,
            "Menschliche Forscher-Entscheidung (Human-in-the-Loop)",
            "ResearcherReviewBlock · /api/ux-decision",
            [
                "• Bestätigen (HUMAN_CONFIRMED): Zitat & Deutung geprüft",
                "• Korrigieren (HUMAN_CORRECTED): Titel, Scope, Valenz,",
                "  UX-Heuristik (Nielsen/ISO) oder Hypothese präzisieren",
                "• Verwerfen (HUMAN_REJECTED): Halluzination / Nebenaspekt",
                "  aussortieren (inkl. Pflichtbegründung im Audit-Trail)",
                "• Carry-Forward überträgt Reviews auf neue A-Läufe",
            ],
            "box-amber",
            ("REVIEW", "#d97706"),
        ),
        card(
            554, 434, 460, 248,
            "Revisionssichere Trennung: Modell vs. Mensch",
            "ux_objects (immutable) + ux_decisions (append-only)",
            [
                "• KI-Rohvorschlag bleibt für die BA-Evaluation unverändert",
                "• Aktive Ansicht berechnet effective = Modell + Korrektur",
                "• Verworfene Beobachtungen markieren abhängige Findings",
                "  sofort mit Warnflag contains_rejected_support",
                "• Verworfene Findings werden aus Diagrammen, Graphen",
                "  und aktivem Übergabe-Handout herausgefiltert",
            ],
            "box-slate",
            ("AUDIT TRAIL", "#475569"),
        ),
        card(
            1064, 434, 450, 248,
            "Geschlossene Ergebnisübergabe (A4-Handout & Report)",
            "telemetry.html_handout() · research.report()",
            [
                "• Druckoptimiertes A4-HTML-Handout (Strg+P -> PDF)",
                "• Enthält Studien-KPIs, bestätigte/korrigierte Findings,",
                "  UX-Heuristiken, Sprecherbreite & wörtliche Zitatanker",
                "• Dokumentiert verworfene KI-Vorschläge transparent im",
                "  separaten Prüfanhang für wissenschaftliche Nachvollziehbarkeit",
                "• Direkt im Projekt-Ausgabeordner archivierbar",
            ],
            "box-emerald",
            ("HANDOUT A4", "#059669"),
        ),
        path_arrow("M 784 384 L 784 408 L 274 408 L 274 434", "Geprüfte Fundstelle", 530, 404, "edge-teal"),
        arrow(504, 558, 554, 558, "Append-Only"),
        arrow(1014, 558, 1064, 558, "Kuratierte Synthese", "edge-teal"),
    ]
    return wrap_svg(
        1560,
        740,
        "Detaildiagramm 05 — Synchroner Dual-View-Inspektor, Forscher-Review & A4-Übergabe",
        "Wie menschliche Prüfung, unveränderliche KI-Belege und druckfertige Ergebnisdokumente ineinandergreifen",
        b,
    )


def build_06_capabilities_vs_limits() -> str:
    b = [
        # Column 1: Native Docling
        '<rect x="28" y="90" width="500" height="722" class="lane" />',
        '<text x="46" y="116" class="lane-title">1. GENUTZTE NATIVE DOCLING-STÄRKEN</text>',
        card(
            46, 134, 464, 155,
            "Einheitliches DoclingDocument (v1.10)",
            "docling + docling-core",
            [
                "• Gemeinsames typsicheres Datenmodell über 11+ Dateiformate",
                "• Bewahrt Seiten-Provenienz (page_no, BoundingBox, charspan)",
                "• Trennt sauber BODY, NOTES (Vortragsnotizen) & FURNITURE",
                "• Native Web-Komponenten (<docling-img>) für Geometrie-Overlay",
            ],
            "box-teal",
            ("NATIV", "#0d9488"),
        ),
        card(
            46, 306, 464, 155,
            "Lokale KI-Modelle für Layout, Tabellen & OCR",
            "PdfPipelineOptions · TableFormer · RapidOCR",
            [
                "• Komplett lokale Ausführung ohne API-Kosten & ohne Datenabfluss",
                "• TableFormer rekonstruiert komplexe Zeilen-/Spalten-Spans",
                "• Automatische Konfidenzwerte (layout, parse, table, ocr)",
                "• DocLang- & Markdown-Serialisierung für strukturtreue Prompts",
            ],
            "box-teal",
            ("LOKAL", "#0d9488"),
        ),
        card(
            46, 478, 464, 155,
            "Schema-geführte Extraktion & Vision-API",
            "docling-graph · PictureDescriptionApiOptions",
            [
                "• Pydantic-basierte Extraktionsverträge mit Gleaning-Option",
                "• HybridChunker für überlange Einzeltranskripte",
                "• Native Einbindung OpenAI-kompatibler Vision-Endpunkte",
                "• Optionale lokale Diagramm-Extraktion (Granite-Chart)",
            ],
            "box-teal",
            ("SCHEMA", "#0d9488"),
        ),
        card(
            46, 650, 464, 144,
            "100 % Open-Source Lizenzkonformität",
            "MIT / Apache-2.0 / BSD · 0 Proprietäre Pakete",
            [
                "• Verifiziert über scripts/verify_open_source_licenses.py",
                "• Gebündelte Drittanbieter-Lizenzen in generated/LICENSES.txt",
            ],
            "box-emerald",
            ("OSI-CLEAN", "#059669"),
        ),
        # Column 2: UX-mAInd Bridges
        '<rect x="550" y="90" width="500" height="722" class="lane" />',
        '<text x="568" y="116" class="lane-title">2. DURCH UX-MAIND GESCHLOSSENE LÜCKEN</text>',
        card(
            568, 134, 464, 155,
            "Office-Streichungen, Folienkontext & Tabellen-IDs",
            "office.py · evidence.model_source()",
            [
                "• Docling verwirft in PPTX/DOCX teilweise Run-Durchstreichungen ->",
                "  UX-mAInd extrahiert sie gezielt aus dem Office-XML",
                "• Rendert PPTX-Ganzfolien via LibreOffice für räumlichen Kontext",
                "• Injiziert #/tables/i + Header in DocLang gegen blinde Zellenanker",
            ],
            "box-sky",
            ("GELÖST", "#0284c7"),
        ),
        card(
            568, 306, 464, 155,
            "Deterministisches Zitat- & Zahlen-Re-Grounding",
            "evidence.Sources.locate() (R30)",
            [
                "• Docling-Graph prüft JSON-Typen, aber NICHT, ob ein Zitat",
                "  wirklich wörtlich im Dokument steht -> UX-mAInd verifiziert",
                "  jedes Zitat & jede Zahl inkl. Ligaturen, Trennstrichen &",
                "  Wortgrenzen ('5%' != '15%') und bietet 1-Klick-Kandidaten",
            ],
            "box-sky",
            ("GELÖST", "#0284c7"),
        ),
        card(
            568, 478, 464, 155,
            "Dokumentübergreifende Synthese & Epistemik",
            "interpretation.py · research.py",
            [
                "• Docling arbeitet einzeldateibezogen -> UX-mAInd ergänzt",
                "  Stufe B (Relationen) & Stufe C (Findings + Gegenbelege)",
                "• Verhindert Doppelzählung überlappender Folien- & Textbelege",
                "• Trennt KI-Vorschlag und Forscher-Entscheidung revisionssicher",
            ],
            "box-sky",
            ("GELÖST", "#0284c7"),
        ),
        card(
            568, 650, 464, 144,
            "Ehrliche Telemetrie, Prompt-Kontrolle & A4-Handout",
            "telemetry.py · prompts_config.py",
            [
                "• Editierbare Basis- & Zusatzprompts + Reset pro Stufe",
                "• Echte LiteLLM-Tarife (0,00 € FAU/Lokal, 0 fiktive Preise)",
                "• Druckfertiges A4-Handout + SQLite-Rekonstruktion im Terminal",
            ],
            "box-sky",
            ("GELÖST", "#0284c7"),
        ),
        # Column 3: Remaining System Boundaries
        '<rect x="1072" y="90" width="500" height="722" class="lane" />',
        '<text x="1090" y="116" class="lane-title">3. VERBLEIBENDE SYSTEMGRENZEN (BA-DISKUSSION)</text>',
        card(
            1090, 134, 464, 155,
            "LibreOffice-Anzeige & Floating-Shapes in Office",
            "SYSTEM_LIMITS.md · Grenze L1 & L2",
            [
                "• LibreOffice-PDF kann bei proprietären Windows-Schriften im",
                "  Seitenumbruch leicht vom nativen MS-Office-Layout abweichen",
                "  (daher explizites Badge ‚Anzeige-Derivat, keine Originalquelle‘)",
                "• Frei schwebende SmartArt-/Textfeld-XML-Knoten in DOCX teils",
                "  außerhalb der Standard-Absatzliste von python-docx",
            ],
            "box-amber",
            ("GRENZE", "#d97706"),
        ),
        card(
            1090, 306, 464, 155,
            "VLM-Deutungsfehler & Audio/Video-Rohdaten",
            "SYSTEM_LIMITS.md · Grenze L3 & L4",
            [
                "• Vision-Sprachmodelle können kleine UI-Icons oder komplexe",
                "  Diagrammachsen fehlinterpretieren -> als abgeleitete Quelle",
                "  markiert, im Dual-View immer gegen Originalbild prüfbar",
                "• Verarbeitet fertige Transkripte (.vtt/.txt); direkte Audio-/",
                "  Video-ASR & Sprecherdiarisierung sind bewusst vorgelagert",
            ],
            "box-amber",
            ("GRENZE", "#d97706"),
        ),
        card(
            1090, 478, 464, 155,
            "LLM-Kontextfenster & Sprachnuancen in Stufe B/C",
            "SYSTEM_LIMITS.md · Grenze L5 & L6",
            [
                "• Sehr große Korpora (>80 lange Dateien) können trotz kompaktem",
                "  JSON-Handoff das Kontextfenster kleiner lokaler Modelle füllen",
                "• Kleinere Modelle (z.B. 4B) übersehen teils implizite Ironie",
                "  oder mehrdeutige Fragebogen-Polung -> epistemische Warnflags",
            ],
            "box-amber",
            ("GRENZE", "#d97706"),
        ),
        card(
            1090, 650, 464, 144,
            "Lokale Einzelplatz-Architektur vs. Cloud-Web-App",
            "SYSTEM_LIMITS.md · Grenze L7 (Deployment)",
            [
                "• Aktuell lokaler 127.0.0.1-Server mit 1 Hintergrund-Job-Slot",
                "• Für Mehrbenutzer-Cloud-Betrieb: Worker-Queue (Redis/Celery)",
                "  + PostgreSQL + Mandanten-Auth entkoppeln",
            ],
            "box-rose",
            ("AUSBLICK", "#e11d48"),
        ),
    ]
    return wrap_svg(
        1600,
        840,
        "Detaildiagramm 06 — Docling-Fähigkeiten, UX-mAInd-Erweiterungen & Ehrliche Systemgrenzen",
        "Wissenschaftliche Einordnung für die Bachelorarbeit: Was Docling nativ leistet, welche Lücken UX-mAInd schließt und wo Grenzen bleiben",
        b,
    )


def main() -> None:
    DIAG_DIR.mkdir(parents=True, exist_ok=True)
    diagrams = {
        "01_master_architecture_r30.svg": build_01_master(),
        "02_docling_conversion_vision.svg": build_02_conversion_vision(),
        "03_stage_a_regrounding.svg": build_03_stage_a(),
        "04_stage_bc_synthesis_graph.svg": build_04_stage_bc_graph(),
        "05_dual_view_human_loop.svg": build_05_dual_view_human_loop(),
        "06_docling_capabilities_vs_limits.svg": build_06_capabilities_vs_limits(),
    }
    for fname, content in diagrams.items():
        out = DIAG_DIR / fname
        out.write_text(content, encoding="utf-8")
        print(f"Generated {out.relative_to(ROOT)} ({len(content):,} bytes)")


if __name__ == "__main__":
    main()
