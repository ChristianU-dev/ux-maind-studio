import React, { useEffect, useState } from "react";
import { Cpu, FileScan, Layers, RotateCcw, Table2 } from "lucide-react";
import { usePrefs } from "../lib/i18n.jsx";
import { InfoPopover, Select, Switch } from "./ui.jsx";

export const DOCLING_CONVERSION_DEFAULTS = {
  do_ocr: true,
  force_full_page_ocr: false,
  replace_broken_text_layer: false,
  ocr_lang: [],
  ocr_scale: 3.0,
  force_backend_text: false,
  do_table_structure: true,
  table_mode: "accurate",
  do_cell_matching: true,
  extract_form_fields: false,
  images_scale: 1.0,
  heading_hierarchy: false,
  do_code_enrichment: false,
  do_formula_enrichment: false,
  document_timeout: null,
  accelerator_device: "auto",
  num_threads: 4,
};

function SettingSwitchRow({ checked, onChange, title, subtitle, infoTitle, infoBody, badge }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 10,
        padding: "7px 0",
        borderBottom: "1px solid var(--border-subtle, rgba(128,128,128,0.12))",
      }}
    >
      <label className="lx-inline-switch" style={{ alignItems: "center", flex: 1, minWidth: 0 }}>
        <Switch checked={Boolean(checked)} onCheckedChange={onChange} />
        <span style={{ fontWeight: 500, fontSize: "12.5px" }}>{title}</span>
        {badge && (
          <span className="lx-badge lx-badge-neutral" style={{ fontSize: "10px" }}>
            {badge}
          </span>
        )}
      </label>
      {(subtitle || infoBody) && (
        <InfoPopover title={infoTitle || title} align="end">
          {subtitle && (
            <p style={{ marginBottom: infoBody ? 6 : 0 }}>
              <strong>Funktion:</strong> {subtitle}
            </p>
          )}
          {infoBody && (
            <p>
              <strong>Empfehlung:</strong> {infoBody}
            </p>
          )}
        </InfoPopover>
      )}
    </div>
  );
}

export function DoclingSettingsTab({ conversion = {}, onUpdateConversion }) {
  const { t } = usePrefs();
  const cfg = { ...DOCLING_CONVERSION_DEFAULTS, ...(conversion || {}) };
  const [langInput, setLangInput] = useState(() => (cfg.ocr_lang || []).join(", "));
  const [numDrafts, setNumDrafts] = useState({
    ocr_scale: String(cfg.ocr_scale ?? 3.0),
    images_scale: String(cfg.images_scale ?? 1.0),
    num_threads: String(cfg.num_threads ?? 4),
    document_timeout: cfg.document_timeout == null ? "" : String(cfg.document_timeout),
  });

  useEffect(() => {
    setLangInput((conversion?.ocr_lang || []).join(", "));
  }, [conversion?.ocr_lang]);

  useEffect(() => {
    setNumDrafts({
      ocr_scale: String(cfg.ocr_scale ?? 3.0),
      images_scale: String(cfg.images_scale ?? 1.0),
      num_threads: String(cfg.num_threads ?? 4),
      document_timeout: cfg.document_timeout == null ? "" : String(cfg.document_timeout),
    });
  }, [cfg.ocr_scale, cfg.images_scale, cfg.num_threads, cfg.document_timeout]);

  const commitNumber = (key, fallback, minVal, maxVal, allowNull = false) => {
    const raw = String(numDrafts[key] ?? "").trim();
    if (raw === "") {
      onUpdateConversion({ [key]: allowNull ? null : fallback });
      return;
    }
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) {
      setNumDrafts((prev) => ({ ...prev, [key]: allowNull && cfg[key] == null ? "" : String(cfg[key] ?? fallback) }));
      return;
    }
    const clamped = Math.max(minVal, Math.min(maxVal, parsed));
    setNumDrafts((prev) => ({ ...prev, [key]: String(clamped) }));
    onUpdateConversion({ [key]: clamped });
  };

  const commitLangs = () => {
    const parsed = langInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    onUpdateConversion({ ocr_lang: parsed });
  };

  return (
    <div className="lx-form-stack" style={{ gap: 16 }}>
      {/* Top Banner + Reset */}
      <section className="lx-card lx-card-subtle">
        <div className="lx-between" style={{ gap: 12, flexWrap: "wrap" }}>
          <div style={{ maxWidth: 680 }}>
            <h2 className="lx-card-title">
              {t(
                "Native Docling-Konvertierungs-Engine (Lokal · Kein Hardcoding)",
                "Native Docling Conversion Engine (Local · Zero Hardcoding)"
              )}
            </h2>
            <p className="lx-card-sub">
              {t(
                "Alle Einstellungen wirken direkt auf Doclings PdfPipelineOptions und ConvertPipelineOptions beim Importieren oder Neu-Konvertieren von Dokumenten. Keine Option ist im Code hart verdrahtet.",
                "All controls map directly to Docling's native PdfPipelineOptions and ConvertPipelineOptions during import or re-conversion. Zero hardcoded pipeline flags."
              )}
            </p>
          </div>
          <button
            type="button"
            className="lx-btn lx-btn-xs"
            onClick={() => onUpdateConversion(DOCLING_CONVERSION_DEFAULTS)}
          >
            <RotateCcw size={12} />
            <span>{t("Docling-Standards wiederherstellen", "Reset Docling Defaults")}</span>
          </button>
        </div>
      </section>

      <div className="lx-grid-2" style={{ alignItems: "start" }}>
        {/* CARD 1: OCR & Text Layer */}
        <section className="lx-card lx-form-stack">
          <div className="lx-between">
            <div className="lx-row-gap">
              <FileScan size={15} className="lx-icon-muted" />
              <h3 className="lx-card-title">
                {t("1. OCR & PDF-Textebene", "1. OCR & PDF Text Layer")}
              </h3>
            </div>
            <InfoPopover title={t("Wann brauche ich welche OCR-Option?", "When to adjust OCR?")}>
              <p>
                {t(
                  "Digitale PDFs bringen meist eine eigene Textebene mit. Docling führt OCR standardmäßig nur auf gescannten Bereichen oder eingebetteten Bildern aus. Bei kompletten Papier-Scans oder kaputten PDF-Schriften helfen Vollseiten-OCR und ‚Defekte Textebene ersetzen‘.",
                  "Digital PDFs include a native text layer; Docling runs OCR selectively on scanned regions by default. Enable Full-Page OCR or Broken Text Layer Replacement for scanned forms or garbled font encodings."
                )}
              </p>
            </InfoPopover>
          </div>

          <SettingSwitchRow
            checked={cfg.do_ocr}
            onChange={(v) => onUpdateConversion({ do_ocr: v })}
            title={t("Optische Zeichenerkennung (do_ocr)", "Optical Character Recognition (do_ocr)")}
            subtitle={t(
              "Erkennt Text in gescannten PDF-Seiten und Bilddateien automatisch lokal.",
              "Automatically extracts text from scanned PDF regions and image files locally."
            )}
            infoBody={t(
              "Nutzt Doclings native OcrAutoOptions auf dem System. Nur deaktivieren, wenn alle PDFs rein digital erzeugt wurden und maximale Konvertierungsgeschwindigkeit gewünscht ist.",
              "Uses Docling's native OcrAutoOptions. Only disable if all PDFs are born-digital and maximum conversion speed is needed."
            )}
          />

          <SettingSwitchRow
            checked={cfg.force_full_page_ocr}
            onChange={(v) => onUpdateConversion({ force_full_page_ocr: v })}
            title={t("Vollseiten-OCR erzwingen (force_full_page_ocr)", "Force Full-Page OCR")}
            subtitle={t(
              "Liest jede PDF-Seite vollständig optisch neu ein statt eingebetteten PDF-Text zu nutzen.",
              "Re-OCRs every full page optically instead of trusting embedded PDF text."
            )}
            infoBody={t(
              "Ideal für abfotografierte Fragebögen, handschriftlich markierte Druckbögen oder PDFs mit falsch codierten Sonderzeichen.",
              "Recommended for scanned paper questionnaires or PDFs where embedded character encoding is corrupted."
            )}
          />

          <SettingSwitchRow
            checked={cfg.replace_broken_text_layer}
            onChange={(v) => onUpdateConversion({ replace_broken_text_layer: v })}
            title={t(
              "Defekte PDF-Textebene automatisch ersetzen",
              "Replace Broken PDF Text Layer"
            )}
            subtitle={t(
              "Prüft eingebetteten PDF-Text auf Zeichensalat (Mojibake) und wechselt bei Bedarf auf OCR.",
              "Detects garbled PDF font encodings and seamlessly falls back to OCR."
            )}
            infoBody={t(
              "Schützt besonders ältere PDF-Exporte aus Statistik- oder Transkriptionssoftware vor kaputten Umlauten und Ligaturen.",
              "Prevents broken umlauts or missing ligatures in older PDF exports without slowing down clean PDFs."
            )}
          />

          <SettingSwitchRow
            checked={cfg.force_backend_text}
            onChange={(v) => onUpdateConversion({ force_backend_text: v })}
            title={t("Reinen PDF-Backend-Text bevorzugen", "Force Native PDF Backend Text")}
            subtitle={t(
              "Verwendet direkt die Zeichenkoordinaten des PDF-Backends (PyPdfium2) ohne Layout-Neuschnitt.",
              "Reads character cells directly from the PDF parser backend."
            )}
            infoBody={t(
              "Spezialoption für digital gesetzte Berichte, bei denen die exakte PDF-Zeichenkette unverändert übernommen werden soll.",
              "Specialized toggle for born-digital PDFs where raw PDF text stream order should be preserved verbatim."
            )}
          />

          <div className="lx-grid-2" style={{ paddingTop: 4 }}>
            <label className="lx-field">
              <div className="lx-between">
                <span className="lx-field-label">
                  {t("OCR-Sprachcodes (Komma)", "OCR Languages (comma)")}
                </span>
                <InfoPopover title={t("OCR-Sprachen", "OCR Languages")}>
                  <p>
                    {t(
                      "Leer lassen für Systemautomatik oder ISO-Codes angeben, z. B. ‚de, en‘ für zweisprachige Usability-Studien.",
                      "Leave empty for automatic engine defaults, or specify codes like 'de, en' for bilingual studies."
                    )}
                  </p>
                </InfoPopover>
              </div>
              <input
                type="text"
                className="lx-input lx-input-sm tabular"
                value={langInput}
                onChange={(e) => setLangInput(e.target.value)}
                onBlur={commitLangs}
                onKeyDown={(e) => e.key === "Enter" && commitLangs()}
                placeholder={t("Auto (z. B. de, en)", "Auto (e.g. de, en)")}
              />
            </label>

            <label className="lx-field">
              <div className="lx-between">
                <span className="lx-field-label">
                  {t("OCR-Skalierung (0.5 – 6.0)", "OCR Scale (0.5 – 6.0)")}
                </span>
                <InfoPopover title={t("OCR-Auflösung", "OCR Scale")}>
                  <p>
                    {t(
                      "Standard 3.0 (~216 DPI). Höhere Werte verbessern kleine Fußnoten in Scans, benötigen aber mehr RAM.",
                      "Default 3.0 (~216 DPI). Higher values improve tiny footnotes in scans at higher memory cost."
                    )}
                  </p>
                </InfoPopover>
              </div>
              <input
                type="number"
                step="0.5"
                min="0.5"
                max="6.0"
                className="lx-input lx-input-sm tabular"
                value={numDrafts.ocr_scale}
                onChange={(e) => setNumDrafts((p) => ({ ...p, ocr_scale: e.target.value }))}
                onBlur={() => commitNumber("ocr_scale", 3.0, 0.5, 6.0)}
                onKeyDown={(e) => e.key === "Enter" && commitNumber("ocr_scale", 3.0, 0.5, 6.0)}
              />
            </label>
          </div>
        </section>

        {/* CARD 2: TableFormer & Form Fields */}
        <section className="lx-card lx-form-stack">
          <div className="lx-between">
            <div className="lx-row-gap">
              <Table2 size={15} className="lx-icon-muted" />
              <h3 className="lx-card-title">
                {t("2. Tabellen-Rekonstruktion & Formulare", "2. TableFormer & Form Fields")}
              </h3>
            </div>
            <InfoPopover title={t("TableFormer & Fragebögen", "TableFormer & Questionnaires")}>
              <p>
                {t(
                  "Usability-Studien enthalten oft komplexe SUS-/PSSUQ-Auswertungstabellen, Codebücher und ausgefüllte Fragebögen. TableFormer (Accurate) rekonstruiert verbundene Kopfzeilen und exakte Zellkoordinaten für die Messwert-Verankerung.",
                  "UX studies frequently contain SUS/PSSUQ score tables, codebooks, and questionnaires. TableFormer Accurate reconstructs merged headers and cell coordinates for exact metric grounding."
                )}
              </p>
            </InfoPopover>
          </div>

          <SettingSwitchRow
            checked={cfg.do_table_structure}
            onChange={(v) => onUpdateConversion({ do_table_structure: v })}
            title={t("KI-Tabellenstruktur (do_table_structure)", "Table Structure Recognition")}
            subtitle={t(
              "Erkennt Zeilen, Spalten und Kopfzellen in PDFs und Bildern über Doclings TableFormer.",
              "Reconstructs rows, columns, and headers in PDFs and images via Docling TableFormer."
            )}
            infoBody={t(
              "Unverzichtbar, damit Stufe A Messwerte zeilen- und spaltengenau (Zelle [r, c]) gegen das Originaldokument prüfen kann.",
              "Essential so Stage A can verify numerical measurements against exact [row, column] table cells."
            )}
          />

          <div className="lx-field" style={{ paddingTop: 4 }}>
            <div className="lx-between">
              <span className="lx-field-label">
                {t("TableFormer-Präzisionsmodus", "TableFormer Mode")}
              </span>
              <InfoPopover title={t("Accurate vs. Fast", "Accurate vs. Fast")}>
                <p>
                  {t(
                    "‚Accurate‘ (empfohlen) erkennt mehrzeilige Header und komplexe Gitterlinien zuverlässiger. ‚Fast‘ beschleunigt sehr lange Berichte mit einfachen Tabellen.",
                    "'Accurate' (recommended) handles multi-row headers and borderless grids best. 'Fast' speeds up huge documents with simple tables."
                  )}
                </p>
              </InfoPopover>
            </div>
            <Select
              size="sm"
              value={cfg.table_mode}
              onValueChange={(v) => onUpdateConversion({ table_mode: v })}
              options={[
                ["accurate", t("Accurate · Höchste Zellpräzision (Empfohlen)", "Accurate · Highest cell precision")],
                ["fast", t("Fast · Schnellere Tabellenanalyse", "Fast · High-speed table parsing")],
              ]}
            />
          </div>

          <SettingSwitchRow
            checked={cfg.do_cell_matching}
            onChange={(v) => onUpdateConversion({ do_cell_matching: v })}
            title={t("PDF-Zelltext-Matching (do_cell_matching)", "PDF Cell Text Matching")}
            subtitle={t(
              "Ordnet erkannte PDF-Textblöcke präzise den rekonstruierten Tabellengitterzellen zu.",
              "Maps native PDF text tokens directly into reconstructed table grid cells."
            )}
            infoBody={t(
              "Nur deaktivieren, wenn ein fehlerhaftes PDF-Layout Text aus Nachbarspalten zusammenzieht und TableFormer eigene Zellgrenzen schneiden soll.",
              "Keep enabled for crisp cell boundaries; only disable if broken PDF spacing bleeds across adjacent columns."
            )}
          />

          <SettingSwitchRow
            checked={cfg.extract_form_fields}
            onChange={(v) => onUpdateConversion({ extract_form_fields: v })}
            title={t(
              "Interaktive Formularfelder & Checkboxen (extract_form_fields)",
              "Extract Form Fields & Checkboxes"
            )}
            subtitle={t(
              "Liest ausfüllbare PDF-Formularfelder, Checkboxen und Key-Value-Paare als strukturierte Elemente.",
              "Extracts interactive PDF form inputs, checkboxes, and key-value items."
            )}
            infoBody={t(
              "Besonders hilfreich für digital ausgefüllte Demografie-, Consent- oder Screening-Fragebögen im PDF-Format.",
              "Ideal for digitally filled demographic, consent, or participant screening PDF forms."
            )}
          />
        </section>

        {/* CARD 3: Layout Hierarchy, Scaling & Code/Formula Enrichment */}
        <section className="lx-card lx-form-stack">
          <div className="lx-between">
            <div className="lx-row-gap">
              <Layers size={15} className="lx-icon-muted" />
              <h3 className="lx-card-title">
                {t("3. Hierarchie, Bildauflösung & Fachblöcke", "3. Hierarchy, Scaling & Enrichments")}
              </h3>
            </div>
            <InfoPopover title={t("Dokumentstruktur & Spezialmodelle", "Structure & Specialized Models")}>
              <p>
                {t(
                  "Diese nativen Docling-Stufen verbessern die Überschriften-Gliederung für das Chunking sowie die Erkennung von Code-Blöcken (z. B. IDE-/Developer-Studien) und mathematischen Formeln (z. B. Statistik-Codebücher).",
                  "These native Docling stages refine heading trees for chunking and parse code blocks or mathematical formulas."
                )}
              </p>
            </InfoPopover>
          </div>

          <SettingSwitchRow
            checked={cfg.heading_hierarchy}
            onChange={(v) => onUpdateConversion({ heading_hierarchy: v })}
            title={t(
              "Überschriften-Hierarchie rekonstruieren (HeadingHierarchy)",
              "Reconstruct Heading Hierarchy"
            )}
            subtitle={t(
              "Leitet verschachtelte Kapitel-Ebenen (H1/H2/H3) aus Typografie und Nummerierung ab.",
              "Infers nested section hierarchy (H1/H2/H3) for cleaner semantic chunking."
            )}
            infoBody={t(
              "Verbessert die Abschnitts-Zuordnung im Quelleninspektor und hilft Docling-Graph beim kontexttreuen Schneiden langer Berichte.",
              "Improves section breadcrumbs in the Inspector and keeps related subsections together during Docling-Graph chunking."
            )}
          />

          <SettingSwitchRow
            checked={cfg.do_code_enrichment}
            onChange={(v) => onUpdateConversion({ do_code_enrichment: v })}
            title={t("Code-Block-Erkennung (do_code_enrichment)", "Code Block Enrichment")}
            badge={t("Zusatzmodell", "Extra Model")}
            subtitle={t(
              "Erkennt und formatiert Programmcode-Ausschnitte (z. B. in Developer-UX- oder Data-Science-Studien).",
              "Parses code blocks and programming language syntax locally."
            )}
            infoBody={t(
              "Lädt beim ersten Start ein lokales Docling-Spezialmodell herunter — nur aktivieren, wenn Studiendateien Quellcode enthalten.",
              "Downloads Docling's local code enrichment weights on first run — enable when analyzing developer tools or scripts."
            )}
          />

          <SettingSwitchRow
            checked={cfg.do_formula_enrichment}
            onChange={(v) => onUpdateConversion({ do_formula_enrichment: v })}
            title={t("Formel- & LaTeX-Erkennung (do_formula_enrichment)", "Formula / LaTeX Enrichment")}
            badge={t("Zusatzmodell", "Extra Model")}
            subtitle={t(
              "Wandelt abgesetzte mathematische Ausdrücke und Statistik-Formeln in strukturiertes LaTeX um.",
              "Transcribes mathematical equations in PDFs into structured LaTeX."
            )}
            infoBody={t(
              "Lädt beim ersten Start ein lokales Formel-Modell herunter — nützlich für wissenschaftliche Auswertungsformeln und Methodenkapitel.",
              "Downloads local formula weights on first run — helpful for scientific method documents and equations."
            )}
          />

          <label className="lx-field" style={{ paddingTop: 4 }}>
            <div className="lx-between">
              <span className="lx-field-label">
                {t(
                  "Seiten- & Abbildungs-Auflösung (images_scale: 0.5 – 4.0)",
                  "Page & Figure Render Scale (0.5 – 4.0)"
                )}
              </span>
              <InfoPopover title={t("Bildauflösung im Inspektor", "Render Resolution")}>
                <p>
                  {t(
                    "1.0 entspricht 72 DPI (kompakt), 2.0 entspricht 144 DPI (gestochen scharf für kleine UI-Labels in Screenshots und Folien).",
                    "1.0 = standard 72 DPI; 1.5–2.0 renders sharper page crops for tiny UI labels in screenshots and slides."
                  )}
                </p>
              </InfoPopover>
            </div>
            <input
              type="number"
              step="0.25"
              min="0.5"
              max="4.0"
              className="lx-input lx-input-sm tabular"
              value={numDrafts.images_scale}
              onChange={(e) => setNumDrafts((p) => ({ ...p, images_scale: e.target.value }))}
              onBlur={() => commitNumber("images_scale", 1.0, 0.5, 4.0)}
              onKeyDown={(e) => e.key === "Enter" && commitNumber("images_scale", 1.0, 0.5, 4.0)}
            />
          </label>
        </section>

        {/* CARD 4: Hardware Accelerator & Safeguards */}
        <section className="lx-card lx-form-stack">
          <div className="lx-between">
            <div className="lx-row-gap">
              <Cpu size={15} className="lx-icon-muted" />
              <h3 className="lx-card-title">
                {t("4. Lokale Hardware & Laufzeitschutz", "4. Hardware Accelerator & Timeout")}
              </h3>
            </div>
            <InfoPopover title={t("Hardware-Beschleunigung", "Accelerator Options")}>
              <p>
                {t(
                  "Steuert Doclings AcceleratorOptions direkt: ‚Auto‘ nutzt vorhandene GPU-Beschleunigung (CUDA / Apple MPS) und fällt sonst sauber auf mehrkernige CPU-Ausführung zurück.",
                  "Maps directly to Docling's AcceleratorOptions: 'Auto' uses CUDA/MPS GPUs if available, otherwise multi-threaded CPU."
                )}
              </p>
            </InfoPopover>
          </div>

          <label className="lx-field">
            <span className="lx-field-label">
              {t("Rechengerät (accelerator_device)", "Accelerator Device")}
            </span>
            <Select
              size="sm"
              value={cfg.accelerator_device}
              onValueChange={(v) => onUpdateConversion({ accelerator_device: v })}
              options={[
                ["auto", t("Auto · Beste verfügbare Hardware (GPU/CPU)", "Auto · Best available (GPU/CPU)")],
                ["cpu", "CPU"],
                ["cuda", "NVIDIA CUDA (GPU)"],
                ["mps", "Apple Metal / MPS"],
              ]}
            />
          </label>

          <div className="lx-grid-2">
            <label className="lx-field">
              <div className="lx-between">
                <span className="lx-field-label">
                  {t("CPU-Threads (1 – 64)", "CPU Threads (1 – 64)")}
                </span>
                <InfoPopover title={t("Parallel-Threads", "CPU Threads")}>
                  <p>
                    {t(
                      "Anzahl lokaler Arbeitsthreads für Layout-Analyse, OCR und TableFormer (Standard: 4).",
                      "Number of local worker threads for layout parsing, OCR, and TableFormer (default: 4)."
                    )}
                  </p>
                </InfoPopover>
              </div>
              <input
                type="number"
                min="1"
                max="64"
                className="lx-input lx-input-sm tabular"
                value={numDrafts.num_threads}
                onChange={(e) => setNumDrafts((p) => ({ ...p, num_threads: e.target.value }))}
                onBlur={() => commitNumber("num_threads", 4, 1, 64)}
                onKeyDown={(e) => e.key === "Enter" && commitNumber("num_threads", 4, 1, 64)}
              />
            </label>

            <label className="lx-field">
              <div className="lx-between">
                <span className="lx-field-label">
                  {t("Max. Dokument-Timeout (s)", "Document Timeout (s)")}
                </span>
                <InfoPopover title={t("Dokument-Timeout", "Document Timeout")}>
                  <p>
                    {t(
                      "Optionales Zeitlimit pro Datei in Sekunden. Leer = kein künstliches Zeitlimit (empfohlen für große Studienmappen).",
                      "Optional safeguard timeout in seconds per file. Leave empty for no artificial cap."
                    )}
                  </p>
                </InfoPopover>
              </div>
              <input
                type="number"
                min="5"
                max="7200"
                className="lx-input lx-input-sm tabular"
                value={numDrafts.document_timeout}
                onChange={(e) => setNumDrafts((p) => ({ ...p, document_timeout: e.target.value }))}
                onBlur={() => commitNumber("document_timeout", null, 5, 7200, true)}
                onKeyDown={(e) => e.key === "Enter" && commitNumber("document_timeout", null, 5, 7200, true)}
                placeholder={t("Unbegrenzt (Standard)", "Unlimited (default)")}
              />
            </label>
          </div>
        </section>
      </div>
    </div>
  );
}
