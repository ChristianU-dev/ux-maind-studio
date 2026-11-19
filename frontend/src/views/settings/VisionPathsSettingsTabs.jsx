import React, { useEffect, useState } from "react";
import { Eye, RotateCcw, Save } from "lucide-react";
import { toast } from "sonner";
import { usePrefs } from "../../lib/i18n.jsx";
import { api } from "../../lib/api.js";
import { InfoPopover, Select, Switch } from "../../components/ui.jsx";

export function VisionSettingsTab({
  workflowSettings,
  profiles,
  onUpdateWorkflowConfig,
  onOpenPromptsTab,
}) {
  const { t } = usePrefs();
  const vis = workflowSettings?.vision || {};
  const [visionCheckText, setVisionCheckText] = useState("");
  const [scaleDraft, setScaleDraft] = useState(String(vis.scale ?? 2.0));
  const [areaDraft, setAreaDraft] = useState(String(vis.picture_area_threshold ?? 0));
  const [timeoutDraft, setTimeoutDraft] = useState(vis.timeout == null ? "" : String(vis.timeout));

  useEffect(() => {
    setScaleDraft(String(vis.scale ?? 2.0));
    setAreaDraft(String(vis.picture_area_threshold ?? 0));
    setTimeoutDraft(vis.timeout == null ? "" : String(vis.timeout));
  }, [vis.scale, vis.picture_area_threshold, vis.timeout]);

  const checkVisionEndpoint = async () => {
    try {
      const vName = workflowSettings?.profiles?.vision;
      const prof = profiles.find((p) => p.name === vName)?.options;
      if (!prof) {
        setVisionCheckText(t("Kein Vision-Profil zugeordnet.", "No Vision profile assigned."));
        return;
      }
      if (vis.mode === "inline") {
        setVisionCheckText(`${t("Lokales Modell", "Local inline model")}: ${prof.model}`);
        return;
      }
      const p = await api("model-preview", { ...prof, vision_check: true });
      setVisionCheckText(
        `${prof.model} · ${p.vision_url || "—"} · ${
          p.vision_ready ? t("Schlüssel bereit", "Key ready") : t("Schlüssel fehlt", "Key missing")
        }`
      );
    } catch (err) {
      setVisionCheckText(err.message);
    }
  };

  return (
    <section className="lx-card lx-form-stack" style={{ maxWidth: 840 }}>
      <div className="lx-row-gap">
        <h2 className="lx-card-title">
          {t(
            "Docling-Bildanreicherung & Folienkontext",
            "Docling Visual Enrichment & Slide Context"
          )}
        </h2>
        <InfoPopover
          title={t("Lokale vs. Modell-Bildanalyse", "Local vs. VLM Visual Analysis")}
        >
          <p>
            {t(
              "Klassifizierung und Diagramm-Tabellenextraktion laufen lokal über Docling. Erst wenn ‚Bildbeschreibung über Vision-Modell‘ aktiv ist, werden nach deiner Freigabe im Pipeline-Dialog Bildpixel an das gewählte Vision-Profil übermittelt.",
              "Figure classification and chart table extraction run locally in Docling. Image pixels are only sent to your Vision model when VLM descriptions are enabled and explicitly authorized in the pipeline consent dialog."
            )}
          </p>
        </InfoPopover>
      </div>
      <p className="lx-card-sub">
        {t(
          "Steuert lokale Abbildungserkennung, Diagramm-Datenextraktion, Bildauflösung und den frei anpassbaren VLM-Systemprompt für Screenshots und Präsentationsfolien.",
          "Configure local figure classification, chart data extraction, render scale, and the customizable VLM instruction prompt for screenshots and slides."
        )}
      </p>

      <label className="lx-inline-switch">
        <Switch
          checked={Boolean(vis.enabled)}
          onCheckedChange={(v) => onUpdateWorkflowConfig({ vision: { enabled: v } })}
        />
        <span>
          {t(
            "Visuelle Analyse im Gesamtauftrag berücksichtigen",
            "Include visual enrichment stage in full pipeline"
          )}
        </span>
      </label>

      <label className="lx-inline-switch">
        <Switch
          checked={Boolean(vis.classification)}
          onCheckedChange={(v) => onUpdateWorkflowConfig({ vision: { classification: v } })}
        />
        <span>
          {t(
            "Lokale Docling-Bildklassifizierung (erkennt Diagramme, Screenshots, Fotos lokal)",
            "Local Docling figure classification (identifies charts, UI screenshots, photos locally)"
          )}
        </span>
      </label>

      <label className="lx-inline-switch">
        <Switch
          checked={Boolean(vis.chart)}
          onCheckedChange={(v) => onUpdateWorkflowConfig({ vision: { chart: v } })}
        />
        <span>
          {t(
            "Tabellarische Diagrammextraktion (liest Zahlenwerte aus Balken-/Liniendiagrammen; aktiviert Klassifizierung automatisch mit)",
            "Tabular chart extraction (extracts structured data tables from charts; automatically enables figure classification)"
          )}
        </span>
      </label>

      <label className="lx-inline-switch">
        <Switch
          checked={Boolean(vis.description)}
          onCheckedChange={(v) => onUpdateWorkflowConfig({ vision: { description: v } })}
        />
        <span>
          {t(
            "Semantische Bildbeschreibung über Vision-Modell erzeugen (benötigt Vision-Profil)",
            "Generate semantic VLM image descriptions (requires assigned Vision profile)"
          )}
        </span>
      </label>

      <div className="lx-grid-2">
        <label className="lx-field">
          <span className="lx-field-label">{t("Ausführungsmodus", "Execution Mode")}</span>
          <Select
            value={vis.mode || "api"}
            onValueChange={(v) => onUpdateWorkflowConfig({ vision: { mode: v } })}
            options={[
              ["api", t("OpenAI-kompatibler API-Endpunkt", "OpenAI-compatible remote API")],
              ["inline", t("Lokale Docling-Inline-Pipeline", "Local Docling inline VLM")],
            ]}
          />
        </label>

        <label className="lx-field">
          <div className="lx-between">
            <span className="lx-field-label">{t("Antwortfrist (s)", "Timeout (s)")}</span>
            <InfoPopover title={t("Vision-Antwortfrist", "Vision Timeout")}>
              <p>
                {t(
                  "Maximale Wartezeit pro Bildanfrage in Sekunden (Standard: 120 s). Leer = kein künstliches Limit.",
                  "Maximum wait time per image request in seconds (default: 120s). Empty = unlimited."
                )}
              </p>
            </InfoPopover>
          </div>
          <input
            type="number"
            className="lx-input tabular"
            value={timeoutDraft}
            onChange={(e) => setTimeoutDraft(e.target.value)}
            onBlur={() =>
              onUpdateWorkflowConfig({
                vision: {
                  timeout: timeoutDraft.trim() === "" ? null : Math.max(5, Number(timeoutDraft)),
                },
              })
            }
          />
        </label>

        <label className="lx-field">
          <div className="lx-between">
            <span className="lx-field-label">
              {t("Mindest-Bildfläche (0.00 – 1.00)", "Min. Picture Area (0.00 – 1.00)")}
            </span>
            <InfoPopover title={t("Mindest-Bildfläche", "Picture Area Threshold")}>
              <p>
                {t(
                  "Überspringt winzige Deko-Icons (z. B. 0.03 = mindestens 3 % der Seitenfläche). 0.00 analysiert alle erkannten Abbildungen.",
                  "Skips tiny decorative icons (e.g. 0.03 = at least 3% of page area). 0.00 inspects all figures."
                )}
              </p>
            </InfoPopover>
          </div>
          <input
            type="number"
            step="0.01"
            min="0"
            max="1"
            className="lx-input tabular"
            value={areaDraft}
            onChange={(e) => setAreaDraft(e.target.value)}
            onBlur={() =>
              onUpdateWorkflowConfig({
                vision: {
                  picture_area_threshold:
                    areaDraft.trim() === ""
                      ? 0
                      : Math.max(0, Math.min(1, Number(areaDraft) || 0)),
                },
              })
            }
          />
        </label>

        <label className="lx-field">
          <div className="lx-between">
            <span className="lx-field-label">
              {t("Vision-Bildskalierung (0.5 – 4.0)", "Vision Render Scale (0.5 – 4.0)")}
            </span>
            <InfoPopover title={t("Vision-Auflösung", "Vision Scale")}>
              <p>
                {t(
                  "Auflösungsfaktor für den Bildzuschnitt vor dem Versand an das Vision-Modell (Standard 2.0 für gut lesbare UI-Beschriftungen und Diagrammachsen).",
                  "Scale factor for cropped images sent to the VLM (default 2.0 for crisp UI labels and chart axes)."
                )}
              </p>
            </InfoPopover>
          </div>
          <input
            type="number"
            step="0.25"
            min="0.5"
            max="4"
            className="lx-input tabular"
            value={scaleDraft}
            onChange={(e) => setScaleDraft(e.target.value)}
            onBlur={() =>
              onUpdateWorkflowConfig({
                vision: {
                  scale:
                    scaleDraft.trim() === ""
                      ? 2.0
                      : Math.max(0.5, Math.min(4.0, Number(scaleDraft) || 2.0)),
                },
              })
            }
          />
        </label>
      </div>

      <div className="lx-io-box lx-between" style={{ flexWrap: "wrap", gap: 10 }}>
        <div className="lx-row-gap" style={{ flexWrap: "wrap" }}>
          <strong className="lx-text-xs">
            {t("Vision-Prompt & Zusatzinstruktionen:", "Vision Prompt & Instructions:")}
          </strong>
          <span className="lx-text-xs lx-muted">
            {vis.prompt
              ? t("Eigener Prompt aktiv", "Custom prompt active")
              : t("Original-Standard aktiv", "Factory default active")}
          </span>
          {onOpenPromptsTab && (
            <button
              type="button"
              className="lx-btn lx-btn-xs lx-btn-primary"
              onClick={onOpenPromptsTab}
            >
              <span>{t("Im Tab ‚Stufen-Prompts‘ bearbeiten", "Edit in 'Stage Prompts' Tab")}</span>
            </button>
          )}
        </div>
        <div className="lx-row-gap">
          <button type="button" className="lx-btn lx-btn-xs" onClick={checkVisionEndpoint}>
            <Eye size={12} />
            <span>{t("Vision-Bereitschaft prüfen", "Check Vision Readiness")}</span>
          </button>
          {visionCheckText && <span className="lx-muted lx-text-xs">{visionCheckText}</span>}
        </div>
      </div>
    </section>
  );
}

export function WorkspacePathsTab() {
  const { t } = usePrefs();
  const [pathsInfo, setPathsInfo] = useState(null);

  useEffect(() => {
    api("paths")
      .then(setPathsInfo)
      .catch((e) => toast.error(e.message));
  }, []);

  const pickOutputFolder = async () => {
    try {
      const p = await api("output-pick", {});
      setPathsInfo(p);
      toast.success(t("Ausgabeordner aktualisiert", "Output folder updated"));
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <section className="lx-card lx-form-stack" style={{ maxWidth: 740 }}>
      <h2 className="lx-card-title">
        {t("Arbeitsbereich, Originale & Ausgabeordner", "Workspace, Originals & Output Directory")}
      </h2>
      <p className="lx-card-sub">
        {t(
          "Strikte Trennung zwischen internem SQLite/Docling-Arbeitsbereich, unveränderten Originaldateien und abgelegten Berichten/Handouts.",
          "Strict separation between internal workspace storage, immutable originals, and exported study reports/handouts."
        )}
      </p>

      <div className="lx-kv-item">
        <span className="lx-muted lx-text-xs">
          {t("Tatsächlich geöffneter Arbeitsordner", "Actually Opened Workspace Folder")}
        </span>
        <div className="lx-row-gap" style={{ flexWrap: "wrap" }}>
          <code className="lx-mono-tag" data-testid="settings-workspace-path">
            {pathsInfo?.workspace || "—"}
          </code>
          <span className="lx-mono-tag">
            {pathsInfo?.is_default_workspace
              ? t("Dauerhafter Standardpfad", "Permanent Default Path")
              : t("Explizites --workspace", "Explicit --workspace Override")}
          </span>
        </div>
      </div>

      {pathsInfo?.default_workspace && !pathsInfo?.is_default_workspace && (
        <div className="lx-kv-item">
          <span className="lx-muted lx-text-xs">
            {t("Regulärer Standardpfad", "Standard Application Path")}
          </span>
          <code className="lx-mono-tag">{pathsInfo.default_workspace}</code>
        </div>
      )}

      {pathsInfo?.legacy_workspace?.found && (
        <div
          className="lx-review-guide"
          data-testid="settings-legacy-r12-notice"
          style={{ marginTop: 4 }}
        >
          <strong className="lx-text-xs">
            {t(
              `Vorhandener Altbestand in workspace-r12 erkannt (${pathsInfo.legacy_workspace.documents} Dok., ${pathsInfo.legacy_workspace.runs} A-Läufe, ${pathsInfo.legacy_workspace.findings} Findings)`,
              `Existing workspace-r12 detected (${pathsInfo.legacy_workspace.documents} docs, ${pathsInfo.legacy_workspace.runs} Stage-A runs, ${pathsInfo.legacy_workspace.findings} findings)`
            )}
          </strong>
          <p className="lx-text-xs" style={{ marginTop: 4 }}>
            <code>{pathsInfo.legacy_workspace.path}</code>
          </p>
          <p className="lx-text-xs lx-muted" style={{ marginTop: 4 }}>
            {t(
              "Übernahme bei geschlossenem Studio: Kopiere den Inhalt von workspace-r12 in den neuen Ordner workspace (nicht verschieben). So bleibt workspace-r12 unverändert als überprüfbare Rückfallebene erhalten.",
              "Safe migration while Studio is closed: Copy the contents of workspace-r12 into workspace (do not move), keeping workspace-r12 intact as a verifiable fallback."
            )}
          </p>
        </div>
      )}

      <div className="lx-kv-item">
        <span className="lx-muted lx-text-xs">
          {t("Export- & Handout-Ablageordner", "Report & Handout Output Folder")}
        </span>
        <div className="lx-row-gap">
          <code className="lx-mono-tag">{pathsInfo?.output || "—"}</code>
          <button type="button" className="lx-btn lx-btn-xs" onClick={pickOutputFolder}>
            {t("Ordner wählen …", "Change Folder…")}
          </button>
        </div>
      </div>
    </section>
  );
}
