import React from "react";
import { RefreshCw } from "lucide-react";
import { usePrefs } from "../../lib/i18n.jsx";
import { InfoPopover, Select } from "../../components/ui.jsx";

function translateBackendPreview(text, lang) {
  if (!text || lang !== "en") return text || "";
  return String(text)
    .replace("Dokumentierte FAU-Referenz", "Documented FAU Reference")
    .replace("Lokale Vorschau ohne Verzeichnisabfrage", "Local preview without endpoint probe")
    .replace("Manueller Profilwert", "Manual profile override")
    .replace("Anbieterverzeichnis", "Provider endpoint metadata")
    .replace("Standard", "Default");
}

export function StageRolesCard({ workflowSettings, profiles, onUpdateWorkflowConfig }) {
  const { t } = usePrefs();
  return (
    <section className="lx-card lx-form-stack">
      <div>
        <div className="lx-row-gap">
          <h2 className="lx-card-title">
            {t("3. Aktive Stufenrollen & Ausgabesprache", "3. Active Stage Roles & Language")}
          </h2>
          <InfoPopover title={t("Warum getrennte Stufenrollen?", "Why separate stage roles?")}>
            <p>
              {t(
                "Du kannst für alle Stufen dasselbe Modell nutzen oder gezielt kombinieren — z. B. ein schnelles Modell mit großem Kontextfenster für Stufe A (Dokumentextraktion) und ein starkes Reasoning-Modell für Stufe C (Finding-Synthese & Gegenprüfung).",
                "Use one model across all stages or mix specialized models — e.g. a fast long-context model for Stage A and a strong reasoning model for Stage C synthesis."
              )}
            </p>
          </InfoPopover>
        </div>
        <p className="lx-card-sub">
          {t(
            "Ordne deinen gespeicherten Profilen die fachlichen Stufen der Analyse-Pipeline zu.",
            "Assign your saved profiles to each analytical stage of the pipeline."
          )}
        </p>
      </div>

      {[
        {
          step: "A",
          label: t("Stufe A · Evidenzextraktion", "Stage A · Evidence Extraction"),
          info: t(
            "Liest jedes Dokument einzeln (als doclang-geo) und extrahiert wörtlich belegte Beobachtungen, Sprecherrollen und Messwerte. Empfehlung: Modell mit großem Kontextfenster und stabiler JSON-Schema-Unterstützung.",
            "Reads each document individually (as doclang-geo) to extract verbatim-anchored observations, speaker roles, and metrics. Recommended: Long-context model with reliable JSON schema support."
          ),
          inheritsA: false,
        },
        {
          step: "B",
          label: t("Stufe B · Dokumentübergreifende Beziehungen", "Stage B · Cross-Document Relations"),
          info: t(
            "Vergleicht alle verankerten A-Beobachtungen der ausgewählten Studiendateien auf Stützung, Widerspruch, Abfolge und Selbstkorrektur. Leer = übernimmt automatisch das Profil von Stufe A.",
            "Compares anchored Stage A observations across all selected study files for corroboration, contradiction, sequence, and recovery. Empty = inherits Stage A profile."
          ),
          inheritsA: true,
        },
        {
          step: "C",
          label: t("Stufe C · Finding-Synthese", "Stage C · Finding Synthesis"),
          info: t(
            "Verdichtet A-Belege und B-Relationen zu prüfbaren Usability-Findings inklusive Gegenbelegen, Nielsen-/ISO-9241-110-Heuristik und Verbesserungshypothese. Empfehlung: Starkes Reasoning-Modell.",
            "Synthesizes A observations and B relations into auditable UX Findings with counterevidence, Nielsen/ISO heuristics, and improvement hypotheses. Recommended: Strong reasoning model."
          ),
          inheritsA: true,
        },
        {
          step: "vision",
          label: t("Visuelle Analyse (Vision-Modell)", "Visual Analysis (Vision Model)"),
          info: t(
            "Beschreibt eingebettete Screenshots, Diagramme und gerenderte 72-DPI-Präsentationsfolien. Erfordert zwingend ein Mischmodell (Multimodal: Text + Vision, z. B. Qwen3.6, Gemma-4, Gemini, GPT-4o).",
            "Describes embedded screenshots, charts, and rendered 72-DPI slides. Requires a multimodal model (Text + Vision, e.g. Qwen3.6, Gemma-4, Gemini, GPT-4o)."
          ),
          inheritsA: false,
        },
      ].map(({ step, label, info, inheritsA }) => (
        <div key={step} className="lx-field">
          <div className="lx-between">
            <span className="lx-field-label">{label}</span>
            <InfoPopover title={label} align="end">
              <p>{info}</p>
            </InfoPopover>
          </div>
          <Select
            value={workflowSettings?.profiles?.[step] || ""}
            onValueChange={(v) => onUpdateWorkflowConfig({ profiles: { [step]: v } })}
            options={[
              [
                "",
                inheritsA
                  ? t("Automatisch wie Stufe A", "Same as Stage A (auto)")
                  : t("Kein Profil zugeordnet", "No profile assigned"),
              ],
              ...profiles.map((p) => [p.name, `${p.name} · ${p.options?.model || ""}`]),
            ]}
          />
        </div>
      ))}

      <div className="lx-divider" />

      <div className="lx-field">
        <div className="lx-between">
          <span className="lx-field-label">
            {t("Ausgabesprache für Synthese (Vision / A / B / C)", "Synthesis Output Language (Vision / A / B / C)")}
          </span>
          <InfoPopover title={t("Ausgabesprache vs. Originalzitat", "Output Language vs. Verbatim Quote")} align="end">
            <p>
              {t(
                "Steuert durchgängig die Sprache für Vision-Beschreibungen (bei Standardprompt), Aussagen und Finding-Synthesen. Wörtliche Originalzitate (quote) bleiben für das Re-Grounding immer exakt in der Originalsprache des Dokuments.",
                "Controls the language of VLM descriptions (when using default prompt), statements, and Finding syntheses. Verbatim quotes always remain untouched in the source document's original language."
              )}
            </p>
          </InfoPopover>
        </div>
        <Select
          value={workflowSettings?.output_language || "auto"}
          onValueChange={(v) => onUpdateWorkflowConfig({ output_language: v })}
          options={[
            ["auto", t("Automatisch (folgt Dokumentsprache)", "Auto (follow source language)")],
            ["de", t("Deutsch (Originalzitate bleiben unverändert)", "German (verbatim quotes stay original)")],
            ["en", t("Englisch (Originalzitate bleiben unverändert)", "English (verbatim quotes stay original)")],
          ]}
        />
      </div>
    </section>
  );
}

export function ParameterTransparencyCard({ preview, onProbeLimits }) {
  const { lang, t } = usePrefs();
  return (
    <section className="lx-table-card">
      <header className="lx-card-header">
        <div>
          <div className="lx-row-gap">
            <h2 className="lx-card-title">
              {t(
                "4. Parameter-Transparenz: Modellgrenze vs. Chunk-Planung vs. HTTP-Request",
                "4. Parameter Transparency: Model Limit vs. Chunk Plan vs. HTTP Request"
              )}
            </h2>
            <InfoPopover title={t("Wie liest man diese 3 Spalten?", "How to read these 3 columns?")}>
              <p style={{ marginBottom: 6 }}>
                <strong>1. {t("Modell-Hardwarelimit", "Model Hardware Limit")}:</strong>{" "}
                {t(
                  "Was die API bzw. das Modell technisch maximal verarbeiten kann (z. B. 262.144 Tokens).",
                  "What the model/endpoint physically supports (e.g., 262,144 tokens)."
                )}
              </p>
              <p style={{ marginBottom: 6 }}>
                <strong>2. {t("Docling-Graph Planungswert", "Docling-Graph Plan Value")}:</strong>{" "}
                {t(
                  "Nach diesem Wert entscheidet Docling-Graph lokal, ob ein Dokument am Stück (direct) passt oder in Teilblöcke (dense) zerlegt wird.",
                  "Used locally by Docling-Graph to decide whether a document fits in a single pass (direct) or requires chunking (dense)."
                )}
              </p>
              <p>
                <strong>3. {t("Gesendeter Wire-Parameter", "Sent Wire Parameter")}:</strong>{" "}
                {t(
                  "Der exakte JSON-Parameter im HTTP-Aufruf. Bei Gateways mit gemeinsamem Ein-/Ausgabefenster (wie FAU) wird max_tokens im Automatikmodus weggelassen, damit der Server die freie Restkapazität optimal vergibt.",
                  "The exact JSON key sent over HTTP. On shared-window gateways (like FAU), max_tokens is omitted in auto mode so the server dynamically allocates remaining context."
                )}
              </p>
            </InfoPopover>
          </div>
          <p className="lx-card-sub">
            {preview?.endpoint
              ? `${preview.endpoint}${
                  preview.limits_discovery
                    ? ` · ${translateBackendPreview(preview.limits_discovery, lang)}`
                    : ""
                }`
              : t(
                  "Wähle oben ein Modell, um genau zu sehen, welche Parameter geplant und tatsächlich gesendet werden.",
                  "Select a model above to inspect planned vs. actually transmitted parameters."
                )}
          </p>
        </div>
        <button type="button" className="lx-btn lx-btn-xs" onClick={onProbeLimits}>
          <RefreshCw size={12} />
          <span>{t("Endpunkt-Limits live abfragen", "Query Endpoint Limits")}</span>
        </button>
      </header>

      {preview && (
        <div className="lx-table-scroll">
          <table className="lx-table">
            <thead>
              <tr>
                <th>{t("Steuergröße", "Parameter")}</th>
                <th>{t("1. Modell-Hardwarelimit (API)", "1. Model Hardware Limit")}</th>
                <th>{t("2. Docling-Graph Chunk-Planung", "2. Docling-Graph Chunk Plan")}</th>
                <th>{t("3. Im HTTP-Request gesendet (Wire)", "3. Sent in HTTP Request (Wire)")}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <strong>{t("Gesamtes Kontextfenster", "Total Context Window")}</strong>
                </td>
                <td className="tabular">
                  {preview.context_limit ? `${preview.context_limit.toLocaleString()} Tokens` : "—"}
                </td>
                <td className="tabular">
                  {preview.context_limit
                    ? `${preview.context_limit.toLocaleString()} Tokens (${translateBackendPreview(
                        preview.sources?.context_limit || "Standard",
                        lang
                      )})`
                    : t("SDK-Fallback (8.192)", "SDK Fallback (8,192)")}
                </td>
                <td>
                  <code className="lx-mono-tag">
                    {t("Kein Wire-Feld (Server-Eigenschaft)", "Not a wire field (server limit)")}
                  </code>
                </td>
              </tr>
              <tr>
                <td>
                  <strong>{t("Max. Antwortlänge (max_tokens)", "Max Output Budget (max_tokens)")}</strong>
                </td>
                <td className="tabular">
                  {preview.max_output_tokens
                    ? `${preview.max_output_tokens.toLocaleString()} Tokens`
                    : t("Geteiltes Ein-/Ausgabefenster", "Shared input/output window")}
                </td>
                <td className="tabular">
                  {(
                    preview.plan_max_output_tokens ||
                    preview.max_output_tokens ||
                    4096
                  ).toLocaleString()}{" "}
                  Tokens {t("(für Direct/Dense-Wahl)", "(for Direct/Dense split)")}
                </td>
                <td>
                  <code className="lx-mono-tag">
                    {preview.wire_max_tokens != null
                      ? `max_tokens = ${preview.wire_max_tokens}`
                      : t(
                          "Bewusst weggelassen → Server nutzt freie Restkapazität",
                          "Omitted -> Server allocates remaining context"
                        )}
                  </code>
                </td>
              </tr>
              <tr>
                <td>
                  <strong>{t("Sampling-Temperatur", "Sampling Temperature")}</strong>
                </td>
                <td>{t("0.0 – 2.0 unterstützt", "0.0 – 2.0 supported")}</td>
                <td className="tabular">{preview.generation?.temperature ?? "0.1 (Deterministisch)"}</td>
                <td>
                  <code className="lx-mono-tag">
                    {preview.generation?.temperature != null
                      ? `temperature = ${preview.generation.temperature}`
                      : "temperature = 0.1"}
                  </code>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
