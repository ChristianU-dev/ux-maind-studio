import React, { useEffect, useState } from "react";
import { ArrowRightLeft, FileCode2, RotateCcw, Save } from "lucide-react";
import { usePrefs } from "../../lib/i18n.jsx";
import { InfoPopover, StatusBadge } from "../../components/ui.jsx";

const STAGE_ORDER = ["vision", "A", "B", "C"];

export function PromptsSettingsTab({ workflowSettings, onSavePrompts }) {
  const { lang, t } = usePrefs();
  const catalog = workflowSettings?.stage_prompt_catalog || {};
  const savedAddenda = workflowSettings?.stage_prompts || {};
  const savedBases = workflowSettings?.base_prompts || {};

  const getFactoryPrompt = (stageKey) =>
    catalog[stageKey]?.default_prompt ||
    (stageKey === "vision" ? workflowSettings?.vision?.default_prompt || "" : "");

  const [baseDrafts, setBaseDrafts] = useState({ vision: "", A: "", B: "", C: "" });
  const [addendumDrafts, setAddendumDrafts] = useState({ vision: "", A: "", B: "", C: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setBaseDrafts({
      vision: savedBases.vision || getFactoryPrompt("vision"),
      A: savedBases.A || getFactoryPrompt("A"),
      B: savedBases.B || getFactoryPrompt("B"),
      C: savedBases.C || getFactoryPrompt("C"),
    });
    setAddendumDrafts({
      vision: savedAddenda.vision || "",
      A: savedAddenda.A || "",
      B: savedAddenda.B || "",
      C: savedAddenda.C || "",
    });
  }, [
    savedBases.vision,
    savedBases.A,
    savedBases.B,
    savedBases.C,
    savedAddenda.vision,
    savedAddenda.A,
    savedAddenda.B,
    savedAddenda.C,
    catalog.vision?.default_prompt,
    catalog.A?.default_prompt,
    catalog.B?.default_prompt,
    catalog.C?.default_prompt,
  ]);

  const buildPayload = (nextBases, nextAddenda) => {
    const cleanBases = {};
    const cleanAddenda = {};
    for (const k of STAGE_ORDER) {
      const factory = (getFactoryPrompt(k) || "").trim();
      const bVal = (nextBases[k] || "").trim();
      cleanBases[k] = !bVal || bVal === factory ? "" : bVal;
      cleanAddenda[k] = (nextAddenda[k] || "").trim();
    }
    return {
      base_prompts: cleanBases,
      stage_prompts: cleanAddenda,
      vision: {
        prompt: cleanBases.vision || cleanAddenda.vision || "",
      },
    };
  };

  const handleSaveAll = async () => {
    setSaving(true);
    try {
      await onSavePrompts(buildPayload(baseDrafts, addendumDrafts));
    } finally {
      setSaving(false);
    }
  };

  const resetOne = async (stageKey) => {
    const factory = getFactoryPrompt(stageKey);
    const nextBases = { ...baseDrafts, [stageKey]: factory };
    const nextAddenda = { ...addendumDrafts, [stageKey]: "" };
    setBaseDrafts(nextBases);
    setAddendumDrafts(nextAddenda);
    setSaving(true);
    try {
      await onSavePrompts(buildPayload(nextBases, nextAddenda));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="lx-form-stack">
      <section className="lx-card lx-form-stack">
        <div className="lx-between" style={{ flexWrap: "wrap", gap: 12 }}>
          <div style={{ maxWidth: 880 }}>
            <div className="lx-row-gap">
              <FileCode2 size={15} style={{ color: "var(--dot-active)" }} />
              <h2 className="lx-card-title">
                {t(
                  "Stufen-Prompts, Datenübergabe & Schema-Verträge (Vollständig editierbar)",
                  "Stage Prompts, Data Handoff & Schema Contracts (Fully Editable)"
                )}
              </h2>
              <InfoPopover
                title={t(
                  "Haupt-Prompt überarbeiten vs. Zusatz-Instruktionen ergänzen",
                  "Editing Base Prompts vs. Adding Supplementary Instructions"
                )}
              >
                <p style={{ marginBottom: 6 }}>
                  {t(
                    "1. Haupt-Prompt überarbeiten: Du kannst den Standard-Systemprompt jeder Stufe direkt im oberen Textfeld umschreiben. Klicke jederzeit auf ‚Original-Standard laden‘, um den geprüften Werkstext wiederherzustellen.",
                    "1. Edit Base Prompt: Directly modify the core system instruction of any stage in the top textarea. Click 'Restore Factory Default' anytime to reload the verified original prompt."
                  )}
                </p>
                <p>
                  {t(
                    "2. Zusatz-Instruktionen: Im zweiten Feld kannst du studienspezifische Zusatzregeln (z. B. Domänenbegriffe oder Fokusfragen) anhängen, ohne den Haupt-Prompt zu verändern. Das deterministische Quellen-Grounding (evidence.py) bleibt immer geschützt.",
                    "2. Additional Instructions: Append study-specific rules (domain vocabulary, focus areas) in the second box without altering the base prompt. Deterministic re-grounding stays enforced."
                  )}
                </p>
              </InfoPopover>
            </div>
            <p className="lx-card-sub">
              {t(
                "Sieh für Vision, Stufe A, Stufe B und Stufe C ohne Blick in den Programmcode exakt ein, welche Daten eingehen, was ausgegeben wird, überarbeite bei Bedarf den Standard-Prompt oder ergänze Zusatz-Instruktionen.",
                "Inspect exact inputs, outputs, and base prompts for Vision, Stage A, Stage B, and Stage C — directly edit standard prompts, add supplementary rules, or reset to factory defaults."
              )}
            </p>
          </div>
          <button
            type="button"
            disabled={saving}
            className="lx-btn lx-btn-primary"
            onClick={handleSaveAll}
          >
            <Save size={13} />
            <span>{t("Alle Stufen-Prompts speichern", "Save All Stage Prompts")}</span>
          </button>
        </div>
      </section>

      <div className="lx-grid-2">
        {STAGE_ORDER.map((stageKey) => {
          const info = catalog[stageKey] || {};
          const title = (lang === "en" ? info.title_en : info.title_de) || `Stage ${stageKey}`;
          const inputTxt = (lang === "en" ? info.input_en : info.input_de) || "";
          const outputTxt = (lang === "en" ? info.output_en : info.output_de) || "";
          const schemaSummary =
            (lang === "en" ? info.schema_summary_en : info.schema_summary_de) || "";
          const factory = (getFactoryPrompt(stageKey) || "").trim();
          const currentBase = (baseDrafts[stageKey] || "").trim();
          const currentAdd = (addendumDrafts[stageKey] || "").trim();
          const baseModified = Boolean(currentBase && currentBase !== factory);
          const hasAnyCustom = baseModified || Boolean(currentAdd);

          return (
            <section key={stageKey} className="lx-prompt-card">
              <div className="lx-between" style={{ flexWrap: "wrap", gap: 6 }}>
                <div className="lx-row-gap">
                  <strong className="lx-card-title">{title}</strong>
                  <StatusBadge
                    label={
                      baseModified && currentAdd
                        ? t("Haupt- & Zusatz-Prompt angepasst", "Base & Addendum Modified")
                        : baseModified
                        ? t("Haupt-Prompt angepasst", "Base Modified")
                        : currentAdd
                        ? t("+ Zusatz-Instruktion", "+ Addendum")
                        : t("Original-Standard", "Factory Default")
                    }
                    tone={hasAnyCustom ? "active" : "neutral"}
                  />
                  {schemaSummary && (
                    <InfoPopover title={t("Aktiver Schema-Vertrag", "Active Schema Contract")}>
                      <p style={{ marginBottom: info.item_docstring ? 6 : 0 }}>{schemaSummary}</p>
                      {info.item_docstring && (
                        <p className="lx-muted" style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}>
                          {info.item_docstring}
                        </p>
                      )}
                    </InfoPopover>
                  )}
                </div>
                <button
                  type="button"
                  disabled={saving}
                  className="lx-btn lx-btn-xs"
                  onClick={() => resetOne(stageKey)}
                  title={t("Original-Standardprompt wiederherstellen", "Reload original default prompt")}
                >
                  <RotateCcw size={11} />
                  <span>{t("Original-Standard laden", "Load Default Prompt")}</span>
                </button>
              </div>

              {/* Input / Output Transparency Boxes */}
              {(inputTxt || outputTxt) && (
                <div className="lx-io-grid">
                  <div className="lx-io-box">
                    <div className="lx-eyebrow" style={{ marginBottom: 2 }}>
                      {t("Eingabe (Was geht rein?)", "Stage Input")}
                    </div>
                    <div>{inputTxt}</div>
                  </div>
                  <div className="lx-io-box">
                    <div className="lx-eyebrow" style={{ marginBottom: 2 }}>
                      <ArrowRightLeft size={10} style={{ display: "inline", marginRight: 4 }} />
                      {t("Ausgabe (Was kommt raus?)", "Stage Output")}
                    </div>
                    <div>{outputTxt}</div>
                  </div>
                </div>
              )}

              {/* 1. Directly Editable Standard / Base Prompt */}
              <label className="lx-field">
                <div className="lx-between">
                  <span className="lx-field-label">
                    {t(
                      "1. Haupt-Prompt (Standard-Systemprompt direkt bearbeiten)",
                      "1. Base Prompt (Directly edit standard system prompt)"
                    )}
                  </span>
                  <span className="lx-text-xs lx-muted tabular">
                    {(baseDrafts[stageKey] || "").length} / 8000
                  </span>
                </div>
                <textarea
                  rows={4}
                  className="lx-textarea"
                  style={{ fontFamily: "var(--font-mono)", fontSize: "11.5px" }}
                  value={baseDrafts[stageKey] ?? ""}
                  onChange={(e) =>
                    setBaseDrafts((prev) => ({ ...prev, [stageKey]: e.target.value }))
                  }
                />
              </label>

              {/* 2. Supplementary Researcher Instructions */}
              <label className="lx-field">
                <div className="lx-between">
                  <span className="lx-field-label">
                    {t(
                      "2. Eigene Zusatz-Instruktionen (optional · wird ergänzend angehängt)",
                      "2. Additional Researcher Instructions (optional · appended to base)"
                    )}
                  </span>
                  <span className="lx-text-xs lx-muted tabular">
                    {(addendumDrafts[stageKey] || "").length} / 8000
                  </span>
                </div>
                <textarea
                  rows={3}
                  className="lx-textarea"
                  value={addendumDrafts[stageKey] || ""}
                  onChange={(e) =>
                    setAddendumDrafts((prev) => ({ ...prev, [stageKey]: e.target.value }))
                  }
                  placeholder={t(
                    "Optional: Domänen-Kontext, Fachvokabular oder Evaluationsfokus ergänzen, ohne den Haupt-Prompt oben zu verändern …",
                    "Optional: Add domain context, vocabulary, or evaluation focus without altering the base prompt above…"
                  )}
                />
              </label>
            </section>
          );
        })}
      </div>
    </div>
  );
}
