"""Generate 8 crisp, infinitely zoomable vector .svg architecture & dual-review diagrams for UX-mAInd Studio."""

from __future__ import annotations

from html import escape
from pathlib import Path
import xml.etree.ElementTree as ET

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
      .box-violet { fill: #f5f3ff; stroke: #7c3aed; stroke-width: 1.9; rx: 10; ry: 10; }
      .box-slate { fill: #f1f5f9; stroke: #64748b; stroke-width: 1.6; rx: 10; ry: 10; }
      .lane { fill: #f1f5f9; stroke: #cbd5e1; stroke-width: 1.2; stroke-dasharray: 5 4; rx: 14; ry: 14; }
      .box-head { font: 700 13.5px 'Segoe UI', Inter, system-ui, sans-serif; fill: #0f172a; }
      .box-code { font: 600 11.5px Consolas, 'JetBrains Mono', monospace; fill: #0f766e; }
      .box-text { font: 400 12px 'Segoe UI', Inter, system-ui, sans-serif; fill: #334155; }
      .badge { font: 700 10.5px Consolas, monospace; fill: #ffffff; }
      .edge { stroke: #475569; stroke-width: 1.8; fill: none; marker-end: url(#arrow); }
      .edge-teal { stroke: #0d9488; stroke-width: 2.0; fill: none; marker-end: url(#arrow-teal); }
      .edge-amber { stroke: #d97706; stroke-width: 1.9; stroke-dasharray: 6 4; fill: none; marker-end: url(#arrow-amber); }
      .edge-ext { stroke: #0284c7; stroke-width: 2.1; stroke-dasharray: 8 4; fill: none; marker-end: url(#arrow-sky); }
      .edge-file { stroke: #7c3aed; stroke-width: 2.4; stroke-dasharray: 3 3; fill: none; marker-end: url(#arrow-violet); }
      .edge-label { font: 600 11px 'Segoe UI', Inter, system-ui, sans-serif; fill: #334155; }
      .legend-box { fill: #ffffff; stroke: #94a3b8; stroke-width: 1.2; rx: 8; ry: 8; }
      .legend-txt { font: 600 11px 'Segoe UI', Inter, system-ui, sans-serif; fill: #1e293b; }
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
    <marker id="arrow-sky" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#0284c7" />
    </marker>
    <marker id="arrow-violet" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#7c3aed" />
    </marker>
  </defs>
"""


def legend_strip(x: int, y: int, w: int = 830) -> str:
    return "\n".join(
        [
            f'<rect x="{x}" y="{y}" width="{w}" height="48" class="legend-box" />',
            f'<line x1="{x + 16}" y1="{y + 24}" x2="{x + 62}" y2="{y + 24}" class="edge-teal" />',
            f'<text x="{x + 70}" y="{y + 28}" class="legend-txt">Lokaler In-App-Fluss (SQLite / 127.0.0.1)</text>',
            f'<line x1="{x + 318}" y1="{y + 24}" x2="{x + 364}" y2="{y + 24}" class="edge-ext" />',
            f'<text x="{x + 372}" y="{y + 28}" class="legend-txt">Opt. externer Modellaufruf (oder lokal Ollama)</text>',
            f'<line x1="{x + 640}" y1="{y + 24}" x2="{x + 686}" y2="{y + 24}" class="edge-file" />',
            f'<text x="{x + 694}" y="{y + 28}" class="legend-txt">Lokaler Dateitransfer</text>',
        ]
    )


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
        legend_strip(1006, 20, 830),
        # Lanes
        '<rect x="24" y="86" width="1812" height="225" class="lane" />',
        '<text x="42" y="110" class="lane-title">EBENE 1 · ARBEITSORDNER, DOKUMENTIMPORT, LOKALE DOCLING-STRUKTUR &amp; OPTIONALE VISION-ANREICHERUNG</text>',
        '<rect x="24" y="328" width="1812" height="252" class="lane" />',
        '<text x="42" y="352" class="lane-title">EBENE 2 · STUFE A: MODELLAUFRUF (LOKAL ODER OPT. EXTERN) &amp; 7-STUFIGE DETERMINISTISCHE QUELLENRÜCKBINDUNG</text>',
        '<rect x="24" y="598" width="1812" height="236" class="lane" />',
        '<text x="42" y="622" class="lane-title">EBENE 3 · STUFEN B &amp; C: TRIANGULATION, EPISTEMIK &amp; PERSISTENTE SPEICHERUNG (SQLITE WAL)</text>',
        '<rect x="24" y="852" width="1812" height="228" class="lane" />',
        '<text x="42" y="876" class="lane-title">EBENE 4 · SYNCHRONER DUAL-VIEW-QUELLENINSPEKTOR, WISSENSGRAPH &amp; EINZELPRÜFUNG</text>',
        '<rect x="24" y="1098" width="1812" height="260" class="lane" />',
        '<text x="42" y="1122" class="lane-title">EBENE 5 · OPTIONALE UNABHÄNGIGE ZWEITPRÜFUNG (1 RECHNER &amp; 2 RECHNER), STUDIENSTAND-ÜBERNAHME &amp; EXPORTE</text>',
        # Row 1
        card(
            42, 126, 380, 165,
            "Arbeitsordner & Studienkorpus-Import",
            "%LOCALAPPDATA%\\UX-mAInd\\workspace · --workspace",
            [
                "• PDF, DOCX, PPTX, ODT, XLSX, CSV, VTT, MD, TXT",
                "• Erkennt workspace-r12 (Übernahme per Kopie)",
                "• --workspace Vorrang für isolierte Tests/Dev",
                "• Unveränderte Originale per SHA-256 (stored/)",
            ],
            "box-slate",
            ("INPUT", "#475569"),
        ),
        card(
            468, 126, 420, 165,
            "Stufe 01 · Lokale Docling-Struktur",
            "DocumentConverter · PdfPipelineOptions · office.py",
            [
                "• Layout, TableFormer (FAST/ACCURATE), RapidOCR",
                "• PPTX/DOCX Durchstreichungen & Vortragsnotizen",
                "• Opt. LibreOffice Anzeige-PDF & Ganzfolien (display/)",
                "• Basis-DoclingDocument JSON (native/document.json)",
            ],
            "box-teal",
            ("100% LOKAL", "#0d9488"),
        ),
        card(
            934, 126, 420, 165,
            "Stufe 02 · Visuelle Analyse (Optional)",
            "enrichment.py · PictureDescriptionApiOptions",
            [
                "• Explizite Freigabe (send_pixels=True erforderlich)",
                "• VLM-Bildbeschreibung & Chart2CSV-Extraktion",
                "• Lokal (Ollama) oder opt. externes VLM-Gateway",
                "• Eigene SHA-256-Version unter native/enrichment/",
            ],
            "box-sky",
            ("OPT. VISION", "#0284c7"),
        ),
        card(
            1400, 126, 416, 165,
            "Modellzugang & LiteLLM-Gateway (Optional extern)",
            "models.py · LiteLLM · Lokal (Ollama) / NHR@FAU / API",
            [
                "• 100 % lokal (Ollama/vLLM) ODER opt. HTTPS-API",
                "• Getrennte Anzeige: Hardware / Planung / Wire",
                "• 0,00 € FAU & Lokal · echte Tarife ohne Schätzung",
                "• Zweitprüfung auf Rechner 2 benötigt 0 Modellaufrufe!",
            ],
            "box-sky",
            ("OPT. LLM", "#0284c7"),
        ),
        arrow(422, 208, 468, 208, "Original"),
        arrow(888, 208, 934, 208, "Bilder/Folien", "edge-teal"),
        arrow(1354, 208, 1400, 208, "Opt. VLM-Call", "edge-ext"),
        # Row 2
        card(
            42, 368, 390, 192,
            "Modell-Quellaufbereitung (Stufe A)",
            "evidence.model_source() · DocLang / Markdown",
            [
                "• Temporäre Tabellen-Captions [source_ref=#/tables/i]",
                "• Spaltenköpfe + Worksheet-Kontext + TrackSource",
                "• GRADING_SCALE, KeyValueItem & FormItem sichtbar",
                "• Original-DoclingDocument bleibt unberührt",
            ],
            "box-teal",
            ("PREP", "#0d9488"),
        ),
        card(
            482, 368, 420, 192,
            "Stufe A · Evidenzextraktion (Docling-Graph)",
            "native_graph.py · UXEvidenceDocument",
            [
                "• Schema-Regeln <= 240 Zeichen (0 Trunkierung)",
                "• httpx.Timeout + Stream-Idle-Watchdog + Live-Log",
                "• Lokal (Ollama) oder opt. externer Modellaufruf",
                "• Zitate, Messwerte, Skalenpolung & Sprecherrolle",
            ],
            "box-sky",
            ("STUFE A", "#0284c7"),
        ),
        card(
            952, 368, 420, 192,
            "7-Stufige Deterministische Quellenrückbindung",
            "evidence.Sources.locate() · observation_view()",
            [
                "• Exakter Span, PDF-Ligaturen (ﬁ/ﬂ) & Silbentrennung",
                "• Wortgrenzen ('5%' != '15%') & Tabellenzellen",
                "• Generiert deterministische evidence_id pro Anker",
                "• Mehrdeutige Treffer bleiben offen (candidate_anchors)",
            ],
            "box-emerald",
            ("RE-GROUND", "#059669"),
        ),
        card(
            1422, 368, 394, 192,
            "Stufe-A-Gatekeeper & Belegheilung",
            "a_status.dimensions() · exclusion_reasons",
            [
                "• Trennt zitierbare (SOURCE_RESOLVED) vs. offene Belege",
                "• 1-Klick Kandidaten-Heilung durch Forscher",
                "• Codebook-Schutz (corpus_role='reference')",
                "• Carry-Forward bestätigter Entscheidungen",
            ],
            "box-amber",
            ("GATE", "#d97706"),
        ),
        path_arrow("M 678 291 L 678 314 L 237 314 L 237 368", "DoclingDocument", 460, 310, "edge-teal"),
        path_arrow("M 1608 291 L 1608 344 L 692 344 L 692 368", "Opt. LLM-API / Ollama", 1150, 340, "edge-ext"),
        arrow(432, 464, 482, 464, "DocLang/MD", "edge-teal"),
        arrow(902, 464, 952, 464, "Roh-JSON"),
        arrow(1372, 464, 1422, 464, "SOURCE_RESOLVED", "edge-teal"),
        # Row 3
        card(
            42, 638, 400, 178,
            "Reiner JSON-Synthese-Handoff",
            "interpretation._build_synthesis_document()",
            [
                "• Reine Daten in evidence.json (0 Prompt-Mischung)",
                "• Sprach-/Zusatzregeln strikt in system_appendix",
                "• Übergibt numeric_value, scale_direction, outline,",
                "  track, strikethrough_spans & Tabellenkontext",
            ],
            "box-amber",
            ("HANDOFF", "#d97706"),
        ),
        card(
            492, 638, 400, 178,
            "Stufe B · Relationen & Stufe C · UX-Findings",
            "UXRelationProposals · UXFindingProposals",
            [
                "• B: corroborates, contradicts, elaborates, causes",
                "• C: Findings inkl. Gegenbelege & Nielsen/ISO/WCAG",
                "• Epistemik: Sprecherzahl & Folien-Überlappung",
                "• Lokal (Ollama) oder opt. externer Modellaufruf",
            ],
            "box-sky",
            ("B & C", "#0284c7"),
        ),
        card(
            942, 638, 430, 178,
            "SQLite WAL Speicherung & Prüfer-Profile",
            "workspace.sqlite · auth.py (ReviewerIdentityProvider)",
            [
                "• Tabellen: documents, runs, ux_objects, ux_decisions,",
                "  ux_review_sessions, workspace_settings, profiles",
                "• Lokale Profile (Name/Kürzel, 0 Cloud-/Login-Zwang)",
                "• Architektur-Hook: ReviewerIdentityProvider (SSO/OIDC)",
            ],
            "box-slate",
            ("SQLITE WAL", "#475569"),
        ),
        card(
            1422, 638, 394, 178,
            "Neustartfester Zustand & Lauf-Rekonstruktion",
            "library.paths() · terminal_ui.read_job_history()",
            [
                "• Alle Dokumentversionen, Belege, Ersturteile und",
                "  Zwischenstände überleben jeden Neustart verlustfrei",
                "• Zeigt geöffneten Arbeitsordner live in der UI an",
                "• Rekonstruiert kompletten Job-Verlauf aus SQLite",
            ],
            "box-teal",
            ("PERSISTENT", "#0d9488"),
        ),
        path_arrow("M 1619 560 L 1619 586 L 242 586 L 242 638", "Verankerte A-Basis", 930, 582, "edge-teal"),
        arrow(442, 727, 492, 727, "evidence.json", "edge-ext"),
        arrow(892, 727, 942, 727, "Laufbelege", "edge-teal"),
        arrow(1372, 727, 1422, 727, "WAL Sync", "edge-teal"),
        # Row 4
        card(
            42, 892, 430, 170,
            "Synthese-Werkbank & Direkte Einzelprüfung",
            "SynthesisView.jsx · ResearcherReviewBlock",
            [
                "• Normale Einzelprüfung direkt mit Standard-Prüfer",
                "  (zweites Profil bleibt 100 % freiwillig!)",
                "• Bestätigen, Korrigieren, Verwerfen + Prüfnotiz",
                "• Zustandsfeste Such- & Prüfstatusfilter",
            ],
            "box",
            ("EINZELPRÜFUNG", "#0f766e"),
        ),
        card(
            522, 892, 430, 170,
            "Synchroner Dual-View-Quelleninspektor",
            "InspectorView.jsx · PDF.js + DoclingReader + docling-img",
            [
                "• Links Original-PDF / gecachtes Office-Anzeige-PDF",
                "• Rechts Docling-Lesefassung & native BBox-Geometrie",
                "• Klickbare Finding-Belegleiste über alle Dokumente",
                "• Funktioniert identisch aus lokalem .zip-Prüfpaket!",
            ],
            "box-teal",
            ("DUAL-VIEW", "#0d9488"),
        ),
        card(
            1002, 892, 400, 170,
            "Interaktiver Evidenz- & Wissensgraph",
            "GraphView.jsx (@xyflow/react + Dagre) · MiniMap",
            [
                "• Findings-Ketten, Gesamtnetz, Gegenbelege, Visuell",
                "• Respektiert Verblindung während aktiver Zweitprüfung",
                "• Freies Ziehen + 1-Klick ‚Verbindung lösen‘",
                "• Nahtloser Sprung in die Dual-View-Fundstelle",
            ],
            "box",
            ("GRAPH", "#0284c7"),
        ),
        card(
            1452, 892, 364, 170,
            "In-App-Handbuch & Systemgrenzen",
            "docs/USER_MANUAL.md · docs/SYSTEM_LIMITS.md",
            [
                "• Lokal gebündelt (0 Runtime-CDNs)",
                "• Schritt-für-Schritt-Anleitungen für 1 & 2 Rechner",
                "• Ehrliche Abhängigkeits- & Methodik-Grenzen",
                "• Synchron mit jedem Build aktualisiert",
            ],
            "box-slate",
            ("DOCS", "#475569"),
        ),
        path_arrow("M 1157 816 L 1157 840 L 257 840 L 257 892", "", 0, 0, "edge-teal"),
        arrow(472, 977, 522, 977, "Belegsprung", "edge-teal"),
        arrow(952, 977, 1002, 977, "Netz-Fokus", "edge-teal"),
        # Row 5: Dual Review & Exports
        card(
            42, 1138, 415, 200,
            "1 & 2 · Ausgangsstand & Verblindete Bewertung",
            "dual_review.create_session() · save_judgment() · submit_slot()",
            [
                "• Auswahl der Findings -> friert baseline_sha256 ein",
                "• Weg A (Am selben Rechner): lokaler Profilwechsel",
                "• Weg B (Auf zwei Rechnern): Prüfpaket .zip & Abgabe .json",
                "• Vor Freigabe strikt verblindet (UI, Historie, Exporte)",
                "• Verbindliche Abgabe friert Ersturteil unveränderbar ein",
            ],
            "box-violet",
            ("BLINDED", "#7c3aed"),
        ),
        card(
            502, 1138, 420, 200,
            "3 · Freigabe nach beiden Abgaben & Überarbeitung",
            "release_comparison() · export_comparison_json()",
            [
                "• Sperre: Freigabe erst möglich, wenn Abgabe 1 UND 2 da",
                "• Zeigt Ersturteile, Begründungen & Feld-Diffs nebeneinander",
                "• Auf 2 Rechnern: Rückgabe ux-vergleich-<id>.json an R2",
                "• Optionale Folgebewertung (phase='revision') möglich;",
                "  abgegebenes Ersturteil (phase='initial') bleibt erhalten!",
            ],
            "box-amber",
            ("RELEASE", "#d97706"),
        ),
        card(
            967, 1138, 415, 200,
            "4 · Ausdrückliche Übernahme in den Studienstand",
            "adopt_resolution() · ADOPTED / OPEN_DISAGREEMENT",
            [
                "• Auswahl bei Abweichung: Fassung Prüfer 1, Prüfer 2,",
                "  Ausgangsvorschlag oder gemeinsame Konsensfassung",
                "• Oder bewusst als ‚Offene Abweichung‘ belassen",
                "• Atomarer, idempotenter Datei-Import (0 Duplikate,",
                "  fremde/beschädigte Pakete ändern 0 Daten)",
            ],
            "box-emerald",
            ("ADOPT", "#059669"),
        ),
        card(
            1427, 1138, 389, 200,
            "Berichte & Forschungs-JSON-Export",
            "html_handout() · markdown_report() · /api/ux-export",
            [
                "• A4-HTML & Markdown nutzen übernommenen Studienstand",
                "  und markieren offene Abweichungen deutlich sichtbar",
                "• Forschungs-JSON bewahrt Ersturteile (initial), spätere",
                "  Änderungen (revisions) & übernommene Fassung komplett",
                "• Originalbelege & gewählter Laufstand fest verknüpft",
            ],
            "box-emerald",
            ("EXPORT", "#059669"),
        ),
        path_arrow("M 257 1062 L 257 1138", "Optional starten", 315, 1094, "edge-teal"),
        arrow(457, 1238, 502, 1238, ".zip / .json", "edge-file"),
        arrow(922, 1238, 967, 1238, "Auswahl", "edge-teal"),
        arrow(1382, 1238, 1427, 1238, "Studienstand", "edge-teal"),
    ]
    return wrap_svg(
        1860,
        1390,
        "UX-mAInd Studio — Vollständige Gesamtarchitektur: Import, Docling, Re-Grounding, Dual-View, Zweitprüfung & Export",
        "Durchgängiger quellengebundener Datenfluss mit dauerhaftem Arbeitsordner, 1-/2-Rechner-Zweitprüfung und strikter Trennung lokaler vs. optionaler externer Aufrufe",
        b,
    )


def build_02_conversion_vision() -> str:
    b = [
        legend_strip(706, 20, 830),
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
        arrow(814, 584, 864, 584, "Opt. API / Lokal", "edge-ext"),
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
        legend_strip(706, 20, 830),
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
        arrow(794, 255, 844, 255, "Opt. LLM / Lokal", "edge-ext"),
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
            "Lokale Einzel-/Zweitprüfung vs. Echtzeit-Multi-User",
            "SYSTEM_LIMITS.md · Grenze L7 (Deployment)",
            [
                "• Unterstützt Einzelprüfung sowie 1- & 2-Rechner-Zweitprüfung lokal",
                "• Für gleichzeitigen Echtzeit-Mehrbenutzer-Server: Worker-Queue",
                "  (Redis) + PostgreSQL + ReviewerIdentityProvider-SSO anbinden",
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


def build_07_dual_review_state_and_workspace() -> str:
    b = [
        legend_strip(706, 20, 830),
        '<rect x="24" y="88" width="1512" height="275" class="lane" />',
        '<text x="42" y="112" class="lane-title">MODUL A · DAUERHAFTER ARBEITSORDNER, ALTBESTANDS-SCHUTZ (WORKSPACE-R12) &amp; LOKALE PRÜFERPROFILE</text>',
        '<rect x="24" y="384" width="1512" height="390" class="lane" />',
        '<text x="42" y="408" class="lane-title">MODUL B · GEMEINSAMER 4-STUFEN-ZUSTANDSAUTOMAT FÜR EINZELPRÜFUNG, 1-RECHNER- &amp; 2-RECHNER-ZWEITPRÜFUNG</text>',
        # Row 1: Workspace & Identity
        card(
            44, 130, 460, 212,
            "Dauerhafter Standardpfad & --workspace Vorrang",
            "library.default_workspace_path() · start-ux-maind.cmd",
            [
                "• Standard unter Windows: %LOCALAPPDATA%\\UX-mAInd\\workspace",
                "• Geöffneter Pfad sichtbar in Sidebar, Korpus & Einstellungen",
                "• Explizites --workspace <Pfad> hat immer Vorrang (trennt",
                "  Entwicklung & Abnahmetests sauber vom BA-Arbeitsstand)",
                "• Alle Versionen, Belege & Zwischenstände neustartfest in SQLite",
            ],
            "box-teal",
            ("WORKSPACE", "#0d9488"),
        ),
        card(
            550, 130, 460, 212,
            "Schreibgeschützte workspace-r12-Erkennung & Kopie",
            "library.probe_legacy_workspace() · ?mode=ro",
            [
                "• Prüft beim Start lesend Nachbarordner workspace-r12",
                "• Zeigt Dokument-, Lauf- & Finding-Zähler im Startbanner & UI",
                "• Übernahme bei geschlossenem Studio per Ordner-Kopie nach",
                "  workspace (workspace-r12 bleibt als Rückfallebene erhalten!)",
                "• Stellt Standard-Ausgabeordner automatisch auf workspace\\exports",
            ],
            "box-amber",
            ("MIGRATION", "#d97706"),
        ),
        card(
            1056, 130, 460, 212,
            "Lokale Prüferprofile & Architektur-Anschlusspunkt",
            "auth.py · LocalProfileIdentityProvider · ReviewerIdentityProvider",
            [
                "• Einzelprüfung direkt mit lokalem Standard-Prüfer (freiwilliges 2. Profil)",
                "• Für Zweitprüfung genügen Anzeigename oder Kürzel (z.B. CU / ZP2)",
                "• 100 % lokal ohne Cloud-Dienst, Login-Mauer oder kommerzielles Konto",
                "• Revisionssicherer Stempel in ux_decisions.payload.reviewer",
                "• Protokoll ReviewerIdentityProvider für spätere SSO/OIDC-Anbindung",
            ],
            "box-slate",
            ("IDENTITY", "#475569"),
        ),
        arrow(504, 236, 550, 236, "Prüft Altbestand"),
        arrow(1010, 236, 1056, 236, "SQLite Settings", "edge-teal"),
        # Row 2: 4-Stage Dual Review State Machine
        card(
            44, 430, 340, 318,
            "Schritt 1 · Ausgangsstand festhalten",
            "create_session() · IN_PROGRESS",
            [
                "• Auswahl beliebiger Findings der Studie",
                "• Wahl: ‚Am selben Rechner‘ ODER",
                "  ‚Auf zwei Rechnern‘",
                "• Friert kanonischen Snapshot ein:",
                "  – Originaldateien (source_sha256)",
                "  – DoclingDocument-Versionen",
                "  – Stufe-A-Läufe & Originalbelege",
                "  – Ausgewählte Findings (F1..Fn)",
                "• Berechnet Prüfsumme baseline_sha256",
            ],
            "box-slate",
            ("STEP 1", "#475569"),
        ),
        card(
            424, 430, 345, 318,
            "Schritt 2 · Unabhängig bewerten",
            "save_judgment(phase='initial') · submit_slot()",
            [
                "• Beide Prüfer sehen dieselben Vorschläge",
                "  & Originalbelege in der Dual-View",
                "• Aktion: Bestätigen / Korrigieren /",
                "  Verwerfen / Offen + Begründung",
                "• STRIKTE VERBLINDUNG vor Freigabe:",
                "  Kein Zugriff auf fremdes Urteil, fremde",
                "  Finding-Korrekturen, Historie, Graph",
                "  oder gespeicherte Exporte (HTTP 403)!",
                "• Abgabe friert Ersturteil fest ein",
            ],
            "box-violet",
            ("STEP 2 · BLIND", "#7c3aed"),
        ),
        card(
            809, 430, 345, 318,
            "Schritt 3 · Vergleichen & Revidieren",
            "release_comparison() · save_judgment('revision')",
            [
                "• Freigabe-Sperre: Erst aktiv, sobald",
                "  submitted_a_at UND submitted_b_at gesetzt",
                "• Zeigt Ersturteile, Begründungen &",
                "  abweichende Felder nebeneinander",
                "• Jede Person kann danach optional eine",
                "  Folgebewertung abgeben (phase='revision')",
                "• Abgegebenes Ersturteil (initial) bleibt",
                "  im Verlauf & JSON unverändert erhalten!",
            ],
            "box-amber",
            ("STEP 3 · COMPARE", "#d97706"),
        ),
        card(
            1194, 430, 322, 318,
            "Schritt 4 · Ergebnis übernehmen",
            "adopt_resolution() · Exporte",
            [
                "• Ausdrückliche Wahl für den Studienstand:",
                "  – Fassung Prüfer 1 / Prüfer 2",
                "  – Ausgangsvorschlag / Konsensfassung",
                "  – Oder ‚Offene Abweichung‘ belassen",
                "• A4-HTML & Markdown zeigen gewählten",
                "  Stand + offene Abweichungen",
                "• Forschungs-JSON enthält Ersturteile,",
                "  Revisionen & übernommene Fassung",
            ],
            "box-emerald",
            ("STEP 4 · ADOPT", "#059669"),
        ),
        arrow(384, 589, 424, 589, "Freeze", "edge-teal"),
        arrow(769, 589, 809, 589, "Beide abgegeben", "edge-amber"),
        arrow(1154, 589, 1194, 589, "Auswahl", "edge-teal"),
    ]
    return wrap_svg(
        1560,
        800,
        "Moduldiagramm 07 — Dauerhafter Arbeitsordner, Altbestands-Übernahme & 4-Stufen-Zweitprüfung",
        "Identischer lokaler Prüf- und Verblindungsablauf für ‚Am selben Rechner‘ und ‚Auf zwei Rechnern‘ ohne Cloud- oder Kontozwang",
        b,
    )


def build_08_two_machine_exchange_and_release() -> str:
    b = [
        legend_strip(706, 20, 830),
        # Two vertical machine swimlanes + center transfer lane
        '<rect x="28" y="88" width="560" height="820" class="lane" />',
        '<text x="48" y="114" class="lane-title">RECHNER 1 · AUSGANGSRECHNER (PRÜFER 1 · STUDIENLEITUNG)</text>',
        '<rect x="612" y="88" width="336" height="820" fill="#faf5ff" stroke="#c4b5fd" stroke-width="1.4" stroke-dasharray="6 4" rx="14" ry="14" />',
        '<text x="632" y="114" class="lane-title">LOKALER DATEITRANSFER (.ZIP / .JSON)</text>',
        '<rect x="972" y="88" width="560" height="820" class="lane" />',
        '<text x="992" y="114" class="lane-title">RECHNER 2 · EMPFÄNGER (PRÜFER 2 · 0 MODELLAUFRUFE · OFFLINE)</text>',
        # Step 1: Origin starts & exports assignment zip
        card(
            48, 134, 520, 142,
            "1. Zweitprüfung ‚Auf zwei Rechnern‘ starten & Prüfer 1 bewertet",
            "create_session(mode='two_machines') · save_judgment() · submit_slot()",
            [
                "• Optional zuvor gelaufene KI-Pipeline (Lokal Ollama / Opt. HTTPS-API)",
                "• Friert ausgewählte Findings, A-Läufe & Originaldokumente ein (baseline_sha256)",
                "• Prüfer 1 bewertet verblindet & gibt Ersturteil ab (bleibt auf R1 geschützt)",
            ],
            "box-teal",
            ("R1 · START", "#0d9488"),
        ),
        card(
            628, 148, 304, 114,
            "Datei 1 · Prüfpaket (.zip)",
            "ux-pruefpaket-<id>.zip",
            [
                "• Originale + Docling JSON + Display-PDF",
                "• A/B/C-Ausgangsstand + SHA-256-Manifest",
                "• ENTHÄLT 0 URTEILE VON PRÜFER 1!",
            ],
            "box-violet",
            ("TRANSFER 1", "#7c3aed"),
        ),
        card(
            992, 134, 520, 142,
            "2. Prüfpaket importieren & Originalbelege in Dual-View prüfen",
            "import_package(.zip) · _rebind_run_result_for_local_doc()",
            [
                "• Prüft package_sha256 & alle Datei-Hashes vor dem ersten Schreibzugriff",
                "• Öffnet Findings & Originalbelege (PDF/Office/TXT + Docling) komplett lokal",
                "• Keine Verbindung zu Rechner 1 und KEIN erneuter Sprachmodell-Lauf nötig!",
            ],
            "box-teal",
            ("R2 · IMPORT", "#0d9488"),
        ),
        arrow(568, 205, 628, 205, "", "edge-file"),
        arrow(932, 205, 992, 205, "", "edge-file"),
        # Step 2: R2 submits & returns JSON
        card(
            992, 306, 520, 136,
            "3. Prüfer 2 bewertet verblindet & gibt Ersturteil verbindlich ab",
            "save_judgment(slot='reviewer_b') · submit_slot()",
            [
                "• Prüfer 2 sieht nur den gemeinsamen Ausgangsvorschlag & eigene Eingaben",
                "• Verbindliche Abgabe friert submitted_b_at & Ersturteil (phase='initial') ein",
                "• Exportiert signierte Rückgabedatei für Rechner 1",
            ],
            "box-violet",
            ("R2 · ABGABE", "#7c3aed"),
        ),
        card(
            628, 316, 304, 116,
            "Datei 2 · Rückgabe Prüfer 2 (.json)",
            "ux-abgabe-<id>-reviewer_b.json",
            [
                "• Prüft session_id & baseline_sha256",
                "• Re-Import idempotent (0 Duplikate)",
                "• Fremde/defekte Datei -> atomarer Abbruch",
            ],
            "box-violet",
            ("TRANSFER 2", "#7c3aed"),
        ),
        card(
            48, 306, 520, 136,
            "4. Rückgabe einlesen & Freigabe-Schranke prüfen",
            "import_package(.json) -> release_comparison()",
            [
                "• Vor Freigabe: Fehlt Abgabe 1 oder Abgabe 2 -> Freigabe gesperrt!",
                "• Sobald BEIDE Ersturteile vorliegen -> Klick auf ‚Vergleich freigeben‘",
                "• Ab jetzt sind beide Urteile, Notizen & Korrekturen auf R1 sichtbar!",
            ],
            "box-amber",
            ("FREIGABE-GATE", "#d97706"),
        ),
        arrow(992, 374, 932, 374, "", "edge-file"),
        arrow(628, 374, 568, 374, "", "edge-file"),
        # Step 3: R1 exports released comparison back to R2
        card(
            48, 474, 520, 128,
            "5. Freigegebenen Vergleich für Rechner 2 bereitstellen",
            "export_comparison_json()",
            [
                "• Bündelt eingefrorene Ersturteile (Prüfer 1 & Prüfer 2) + Freigabezeitpunkt",
                "• Ermöglicht Prüfer 2 die transparente Einsicht auf dem eigenen Rechner",
            ],
            "box-amber",
            ("R1 · VERGLEICH", "#d97706"),
        ),
        card(
            628, 480, 304, 116,
            "Datei 3 · Vergleichsdatei (.json)",
            "ux-vergleich-<id>.json",
            [
                "• Enthält beide Ersturteile + Diffs",
                "• Schaltet Vergleichsansicht auf R2 frei",
                "• SHA-256-gesichert & idempotent",
            ],
            "box-violet",
            ("TRANSFER 3", "#7c3aed"),
        ),
        card(
            992, 474, 520, 128,
            "6. Vergleich auf Rechner 2 sichten & optional überarbeiten",
            "import_package(ux-vergleich) · save_judgment(phase='revision')",
            [
                "• Prüfer 2 sieht beide Bewertungen & Korrekturvorschläge nebeneinander",
                "• Optional: Folgebewertung erfassen (Ersturteil bleibt separat erhalten!)",
            ],
            "box-sky",
            ("R2 · REVISION", "#0284c7"),
        ),
        arrow(568, 538, 628, 538, "", "edge-file"),
        arrow(932, 538, 992, 538, "", "edge-file"),
        # Step 4: Optional revision return & final study adoption
        card(
            628, 646, 304, 116,
            "Datei 4 · Überarbeitung (opt. .json)",
            "ux-ueberarbeitung-<id>-reviewer_b.json",
            [
                "• Überträgt phase='revision'-Einträge",
                "• Überschreibt NIEMALS das Ersturteil",
                "• Idempotenter Import über decision_uid",
            ],
            "box-violet",
            ("TRANSFER 4", "#7c3aed"),
        ),
        card(
            48, 636, 520, 246,
            "7. Überarbeitung einlesen, Studienstand wählen & Berichte exportieren",
            "adopt_resolution() · html_handout() · markdown_report() · ux-export",
            [
                "• Übernimmt ausdrücklich gewählte Fassung (Prüfer 1, Prüfer 2, Konsens,",
                "  Ausgangsvorschlag) oder markiert ‚Offene Abweichung‘",
                "• A4-HTML & Markdown zeigen gewählten Studienstand + Originalbelege",
                "• Forschungs-JSON dokumentiert Ersturteile (BA-Auswertung!), spätere",
                "  Überarbeitungen und die übernommene Fassung lückenlos",
            ],
            "box-emerald",
            ("ABSCHLUSS & EXPORT", "#059669"),
        ),
        card(
            992, 636, 520, 246,
            "Schutzgarantien bei Unterbrechung & Fehlerfällen",
            "SQLite WAL · Transaktionale Paketprüfung",
            [
                "• Neustart zwischen Abgaben: Alle Stände & Belege sofort wieder offen",
                "• Doppelt eingelesene .zip/.json: Erzeugt exakt 0 doppelte Entscheidungen",
                "• Fremder Prüfauftrag (session_id / baseline_sha256 falsch): Abweisung",
                "• Beschädigtes Archiv / manipulierter JSON-Hash: 0 Teiländerungen!",
                "• BA-Auswertung nutzt unverfälschte Ersturteile (reviewer_a/b.initial)",
            ],
            "box-slate",
            ("SAFETY GUARANTEES", "#475569"),
        ),
        path_arrow("M 992 575 L 960 575 L 960 704 L 932 704", "", 0, 0, "edge-file"),
        arrow(628, 704, 568, 704, "", "edge-file"),
    ]
    return wrap_svg(
        1560,
        936,
        "Moduldiagramm 08 — Zweitprüfung auf zwei Rechnern: Dateiübergaben, Freigabe-Schranke & Überarbeitung",
        "Vollständiges Offline-Austauschprotokoll (.zip / .json) ohne Serververbindung oder erneuten Modelllauf auf Rechner 2",
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
        "07_dual_review_state_and_workspace.svg": build_07_dual_review_state_and_workspace(),
        "08_two_machine_exchange_and_release.svg": build_08_two_machine_exchange_and_release(),
    }
    for fname, content in diagrams.items():
        ET.fromstring(content.encode("utf-8"))
        out = DIAG_DIR / fname
        out.write_text(content, encoding="utf-8")
        print(f"Generated & XML-verified {out.relative_to(ROOT)} ({len(content):,} bytes)")


if __name__ == "__main__":
    main()
