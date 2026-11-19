import React, { useEffect, useMemo, useState } from "react";
import { BarChart3, Coins, Download, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { usePrefs } from "../lib/i18n.jsx";
import { api } from "../lib/api.js";
import { InfoPopover, StatusBadge } from "./ui.jsx";

function formatUsd(val) {
  if (val == null || Number.isNaN(Number(val))) return "—";
  const num = Number(val);
  if (num === 0) return "$0.00";
  if (num < 0.01) return `$${num.toFixed(4)}`;
  return `$${num.toFixed(2)}`;
}

export function StudyAnalyticsView({
  mode = "charts", // "charts" | "telemetry"
  workspace,
  onJumpToFinding,
}) {
  const { t } = usePrefs();
  const [telemetry, setTelemetry] = useState(null);
  const [loadingTel, setLoadingTel] = useState(false);

  const data = workspace?.result;
  const docs = data?.documents || [];
  const observations = data?.observations || [];
  const findings = useMemo(
    () => (data?.objects || []).filter((o) => o.kind === "finding"),
    [data]
  );

  const fetchTelemetry = async () => {
    if (!workspace?.documents?.length) return;
    setLoadingTel(true);
    try {
      const params = new URLSearchParams({
        documents: JSON.stringify(workspace.documents),
        basis: JSON.stringify(workspace.basis || {}),
        result_runs: JSON.stringify(workspace.runs || {}),
      });
      const res = await api(`ux-telemetry?${params.toString()}`);
      setTelemetry(res);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoadingTel(false);
    }
  };

  useEffect(() => {
    if (mode === "telemetry") {
      fetchTelemetry();
    }
  }, [mode, workspace?.scopeKey, JSON.stringify(workspace?.runs)]);

  // Compute chart breakdowns from workspace.result (excluding HUMAN_REJECTED from active synthesis charts)
  const activeFindings = useMemo(
    () => findings.filter((f) => f.review !== "HUMAN_REJECTED"),
    [findings]
  );

  const chartStats = useMemo(() => {
    const valCounts = { problem: 0, strength: 0, mixed: 0, unclear: 0, neutral: 0 };
    const revCounts = { confirmed: 0, unreviewed: 0, rejected: 0 };
    for (const f of findings) {
      if (f.review === "HUMAN_CONFIRMED" || f.review === "HUMAN_CORRECTED") revCounts.confirmed++;
      else if (f.review === "HUMAN_REJECTED") revCounts.rejected++;
      else revCounts.unreviewed++;

      if (f.review === "HUMAN_REJECTED") continue;
      const v = String(f.effective?.valence || "").toLowerCase();
      if (v === "problem" || v === "negative") valCounts.problem++;
      else if (v === "strength" || v === "positive") valCounts.strength++;
      else if (v === "mixed") valCounts.mixed++;
      else if (v === "unclear") valCounts.unclear++;
      else valCounts.neutral++;
    }

    const modCounts = { text: 0, table: 0, visual: 0, track: 0, open: 0 };
    for (const obs of observations) {
      const matches = obs.source_check?.matches || [];
      if (!matches.length) {
        modCounts.open++;
        continue;
      }
      const m0 = matches[0];
      if (m0.picture_source || String(m0.ref || "").startsWith("#/pictures/")) modCounts.visual++;
      else if (m0.row != null || String(m0.ref || "").startsWith("#/tables/")) modCounts.table++;
      else if (m0.track || m0.voice) modCounts.track++;
      else modCounts.text++;
    }

    // Triangulation matrix: Active Finding x Document (including supports, opposes, qualifies, improvement_evidence)
    const matrixRows = activeFindings.map((f) => {
      const p = f.effective || {};
      const byDoc = new Map();
      for (const d of docs) {
        byDoc.set(d.document, { sup: 0, opp: 0, ctx: 0 });
      }
      for (const ref of p.supports || []) {
        if (ref?.document && byDoc.has(ref.document)) byDoc.get(ref.document).sup++;
      }
      for (const ref of p.opposes || []) {
        if (ref?.document && byDoc.has(ref.document)) byDoc.get(ref.document).opp++;
      }
      for (const ref of [...(p.qualifies || []), ...(p.improvement_evidence || [])]) {
        if (ref?.document && byDoc.has(ref.document)) byDoc.get(ref.document).ctx++;
      }
      const docBreadth = [...byDoc.values()].filter(
        (c) => c.sup > 0 || c.opp > 0 || c.ctx > 0
      ).length;
      return {
        id: String(f.id),
        title: p.title || `Finding #${f.id}`,
        valence: String(p.valence || "").toLowerCase(),
        heuristic: p.usability_heuristic || "",
        docBreadth,
        byDoc,
      };
    });

    return { valCounts, revCounts, modCounts, matrixRows };
  }, [findings, activeFindings, observations, docs]);

  const downloadTelemetryCsv = () => {
    if (!telemetry?.runs?.length) return;
    const headers = [
      "stage",
      "run_id",
      "active",
      "timestamp",
      "scope",
      "provider",
      "model",
      "status",
      "api_calls",
      "prompt_tokens",
      "completion_tokens",
      "total_tokens",
      "items_yielded",
      "tokens_per_item",
      "billed_usd",
      "cloud_reference_usd",
    ];
    const escapeCsv = (v) => {
      const s = v == null ? "" : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const lines = [
      headers.join(","),
      ...telemetry.runs.map((r) =>
        [
          r.kind,
          r.run_id,
          r.active ? "1" : "0",
          r.at,
          r.scope_label,
          r.provider,
          r.model,
          r.status,
          r.calls,
          r.prompt_tokens,
          r.completion_tokens,
          r.total_tokens,
          r.items_count,
          r.tokens_per_item ?? "",
          r.billed_usd ?? "",
          r.cloud_reference_usd ?? "",
        ]
          .map(escapeCsv)
          .join(",")
      ),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ux-maind-telemetry-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (mode === "charts") {
    const fTotal = Math.max(1, activeFindings.length);
    const oTotal = Math.max(1, observations.length);
    const { valCounts, revCounts, modCounts, matrixRows } = chartStats;

    return (
      <div className="lx-analytics-scroll">
        <div className="lx-grid-2">
          {/* Valence & Review Distribution */}
          <section className="lx-card lx-form-stack">
            <div className="lx-between">
              <div className="lx-row-gap">
                <BarChart3 size={15} style={{ color: "var(--dot-active)" }} />
                <h2 className="lx-card-title">
                  {t("Finding-Valenz & Prüfstatus", "Finding Valence & Review Breakdown")}
                </h2>
                <InfoPopover title={t("Valenz- & Review-Verteilung", "Valence & Review Distribution")}>
                  <p>
                    {t(
                      "Zeigt das Verhältnis von Nutzungsproblemen, Stärken und ambivalenten Befunden sowie den Stand der menschlichen Forscher-Prüfung.",
                      "Shows the balance of usability problems, strengths, and mixed findings alongside human researcher verification status."
                    )}
                  </p>
                </InfoPopover>
              </div>
              <span className="lx-mono-tag tabular">{findings.length} Findings</span>
            </div>

            {findings.length === 0 ? (
              <p className="lx-muted lx-text-xs">
                {t("Noch keine Findings (Stufe C) berechnet.", "No Stage C findings computed yet.")}
              </p>
            ) : (
              <>
                <div className="lx-bar-stack" aria-hidden="true">
                  <div
                    style={{
                      width: `${(valCounts.problem / fTotal) * 100}%`,
                      background: "var(--dot-danger)",
                    }}
                  />
                  <div
                    style={{
                      width: `${(valCounts.mixed / fTotal) * 100}%`,
                      background: "var(--dot-warning)",
                    }}
                  />
                  <div
                    style={{
                      width: `${(valCounts.strength / fTotal) * 100}%`,
                      background: "var(--dot-success)",
                    }}
                  />
                  <div
                    style={{
                      width: `${(valCounts.neutral / fTotal) * 100}%`,
                      background: "var(--dot-neutral)",
                    }}
                  />
                </div>

                {[
                  [t("Nutzungsprobleme", "Usability Problems"), valCounts.problem, "var(--dot-danger)"],
                  [t("Ambivalent / Gemischt", "Mixed / Ambivalent"), valCounts.mixed, "var(--dot-warning)"],
                  [t("Stärken / Positiv", "Strengths / Positive"), valCounts.strength, "var(--dot-success)"],
                  [t("Neutral / Kontext", "Neutral / Context"), valCounts.neutral, "var(--dot-neutral)"],
                  ...(valCounts.unclear > 0
                    ? [[t("Unklare Valenz", "Unclear Valence"), valCounts.unclear, "#0284c7"]]
                    : []),
                ].map(([lbl, cnt, col]) => (
                  <div key={lbl} className="lx-bar-row">
                    <span className="truncate">{lbl}</span>
                    <div className="lx-bar-track">
                      <div
                        className="lx-bar-fill"
                        style={{ width: `${(cnt / fTotal) * 100}%`, background: col }}
                      />
                    </div>
                    <span className="tabular lx-muted" style={{ textAlign: "right" }}>
                      {cnt} ({Math.round((cnt / fTotal) * 100)}%)
                    </span>
                  </div>
                ))}

                <div className="lx-divider" />
                <div className="lx-row-wrap">
                  <StatusBadge
                    label={`${t("Bestätigt", "Confirmed")}: ${revCounts.confirmed}`}
                    tone="success"
                  />
                  <StatusBadge
                    label={`${t("Ungeprüft", "Unreviewed")}: ${revCounts.unreviewed}`}
                    tone="warning"
                  />
                  <StatusBadge
                    label={`${t("Verworfen", "Rejected")}: ${revCounts.rejected}`}
                    tone="danger"
                  />
                </div>
              </>
            )}
          </section>

          {/* Modality & Source Resolution */}
          <section className="lx-card lx-form-stack">
            <div className="lx-between">
              <div className="lx-row-gap">
                <h2 className="lx-card-title">
                  {t("Quellenmodalitäten (Stufe A)", "Evidence Modalities (Stage A)")}
                </h2>
                <InfoPopover title={t("Quellenverankerung nach Modalität", "Source Grounding by Modality")}>
                  <p>
                    {t(
                      "Aufschlüsselung aller extrahierten Beobachtungen nach nativer Docling-Quellenart: Textabsatz, Tabellenzelle, Bild/Folie oder Zeitspur.",
                      "Breakdown of extracted observations by native Docling anchor type: text span, table cell, figure/slide, or audio/VTT track."
                    )}
                  </p>
                </InfoPopover>
              </div>
              <span className="lx-mono-tag tabular">
                {observations.length} {t("Beobachtungen", "obs.")}
              </span>
            </div>

            {[
              [t("Textspannen & Absätze", "Text Spans & Paragraphs"), modCounts.text, "var(--stage-a)"],
              [t("Tabellenzellen & -zeilen", "Table Cells & Rows"), modCounts.table, "var(--stage-b)"],
              [t("Bilder, Folien & Charts", "Figures, Slides & Charts"), modCounts.visual, "var(--stage-vision)"],
              [t("Transkript-Zeitspuren (VTT)", "Transcript Tracks (VTT)"), modCounts.track, "var(--stage-c)"],
              [t("Offene / ungeklärte Anker", "Unresolved / Open Anchors"), modCounts.open, "var(--dot-danger)"],
            ].map(([lbl, cnt, col]) => (
              <div key={lbl} className="lx-bar-row">
                <span className="truncate">{lbl}</span>
                <div className="lx-bar-track">
                  <div
                    className="lx-bar-fill"
                    style={{ width: `${(cnt / oTotal) * 100}%`, background: col }}
                  />
                </div>
                <span className="tabular lx-muted" style={{ textAlign: "right" }}>
                  {cnt} ({observations.length ? Math.round((cnt / oTotal) * 100) : 0}%)
                </span>
              </div>
            ))}
          </section>
        </div>

        {/* Cross-Document Triangulation Matrix */}
        <section className="lx-table-card">
          <header className="lx-card-header">
            <div className="lx-row-gap">
              <div>
                <h2 className="lx-card-title">
                  {t(
                    "Dokumentübergreifende Triangulations-Matrix (Finding × Dokument)",
                    "Cross-Document Triangulation Matrix (Finding × Document)"
                  )}
                </h2>
                <p className="lx-card-sub">
                  {t(
                    "Zeigt auf einen Blick, welche Primärdokumente ein Finding stützen (+N) oder einschränken/widerlegen (−N). Klicke auf ein Finding zur Detailprüfung.",
                    "Shows at a glance which study artifacts support (+N) or counter (−N) each Finding. Click any Finding row to inspect."
                  )}
                </p>
              </div>
            </div>
          </header>

          {matrixRows.length === 0 ? (
            <div className="lx-pane-placeholder">
              {t("Noch keine Findings für die Matrix vorhanden.", "No findings available yet.")}
            </div>
          ) : (
            <div className="lx-table-scroll">
              <table className="lx-matrix-table">
                <thead>
                  <tr>
                    <th>Finding</th>
                    <th style={{ width: 92 }}>{t("Abdeckung", "Breadth")}</th>
                    {docs.map((d) => (
                      <th key={d.document} title={d.name}>
                        <span className="truncate" style={{ display: "inline-block", maxWidth: 115 }}>
                          {d.name}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matrixRows.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <button
                          type="button"
                          className="lx-doc-link"
                          onClick={() => onJumpToFinding?.(row.id)}
                        >
                          <span className="lx-mono-tag tabular" style={{ marginRight: 6 }}>
                            C #{row.id}
                          </span>
                          <span>{row.title}</span>
                        </button>
                      </td>
                      <td className="lx-matrix-cell">
                        {row.docBreadth}/{docs.length} {t("Dok.", "docs")}
                      </td>
                      {docs.map((d) => {
                        const cell = row.byDoc.get(d.document) || { sup: 0, opp: 0, ctx: 0 };
                        const cls =
                          cell.opp > 0
                            ? "lx-matrix-cell has-counter"
                            : cell.sup > 0 || cell.ctx > 0
                            ? "lx-matrix-cell has-support"
                            : "lx-matrix-cell lx-muted";
                        return (
                          <td key={d.document} className={cls}>
                            {cell.sup === 0 && cell.opp === 0 && cell.ctx === 0
                              ? "·"
                              : [
                                  cell.sup > 0 ? `+${cell.sup}` : null,
                                  cell.opp > 0 ? `−${cell.opp}` : null,
                                  cell.ctx > 0 ? `~${cell.ctx}` : null,
                                ]
                                  .filter(Boolean)
                                  .join(" / ")}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    );
  }

  // TELEMETRY MODE ("Token & Kosten")
  const sum = telemetry?.summary || {};
  const stageRows = telemetry?.stages || [];
  const maxStageTokens = Math.max(1, ...stageRows.map((s) => s.total_tokens || 0));
  const convTotalSec = (telemetry?.documents || []).reduce(
    (acc, d) => acc + (Number(d.conversion_seconds) || 0),
    0
  );

  return (
    <div className="lx-analytics-scroll">
      <div className="lx-kpi-grid">
        <div className="lx-kpi-card">
          <div className="lx-between">
            <span className="lx-kpi-label">{t("Gesamt-Tokens (Aktive Basis)", "Total Tokens (Active Scope)")}</span>
            <InfoPopover title={t("Token-Verbrauch", "Token Consumption")}>
              <p>
                {t(
                  "Summe der protokollierten Prompt- und Completion-Tokens über die gewählten Läufe von Stufe A, B und C.",
                  "Sum of protocolled prompt and completion tokens across the active Stage A, B, and C runs."
                )}
              </p>
            </InfoPopover>
          </div>
          <strong className="lx-kpi-value tabular">
            {(sum.total_tokens || 0).toLocaleString()}
          </strong>
          <span className="lx-kpi-sub tabular">
            {(sum.prompt_tokens || 0).toLocaleString()} In · {(sum.completion_tokens || 0).toLocaleString()} Out
            {sum.reasoning_tokens > 0 ? ` · ${sum.reasoning_tokens.toLocaleString()} Think` : ""} ·{" "}
            {sum.api_calls || 0} {t("Aufrufe", "calls")}
          </span>
        </div>

        <div className="lx-kpi-card">
          <div className="lx-between">
            <span className="lx-kpi-label">{t("Reale API-Kosten", "Actual API Cost")}</span>
            <InfoPopover title={t("Ehrliche Kostenberechnung", "Genuine API Pricing")}>
              <p>
                {t(
                  "Berechnet ausschließlich verifizierte API-Tarife aus LiteLLM. Hochschul- und Lokal-Endpunkte (FAU NHR, Ollama) werden ehrlich mit 0,00 $ berechnet. Es werden niemals fiktive Schätzpreise erfunden.",
                  "Uses strictly verified LiteLLM model tariffs. Academic/local endpoints (FAU NHR, Ollama) are genuinely $0.00. Unlisted open-weight models show 'Unlisted' rather than invented rates."
                )}
              </p>
            </InfoPopover>
          </div>
          <strong className="lx-kpi-value tabular">{formatUsd(sum.billed_usd ?? 0)}</strong>
          <span className="lx-kpi-sub tabular">
            {sum.cloud_reference_usd != null && sum.cloud_reference_usd > 0
              ? `${t("Verifizierter Cloud-Tarif", "Verified tariff")}: ${formatUsd(sum.cloud_reference_usd)}`
              : t("0,00 € (Lokal/FAU) · Keine Schätzpreise", "$0.00 (Local/FAU) · Zero guessed tariffs")}
          </span>
        </div>

        <div className="lx-kpi-card">
          <span className="lx-kpi-label">{t("Token-Effizienz", "Token Efficiency")}</span>
          <strong className="lx-kpi-value tabular">
            {sum.tokens_per_finding != null
              ? `${Math.round(sum.tokens_per_finding).toLocaleString()}`
              : "—"}
            <span className="lx-kpi-denom"> / Finding</span>
          </strong>
          <span className="lx-kpi-sub tabular">
            {sum.tokens_per_observation != null
              ? `Ø ${Math.round(sum.tokens_per_observation).toLocaleString()} Tokens / ${t("Beobachtung", "Obs.")}`
              : t("Noch keine Token-Belege", "No token receipts yet")}
          </span>
        </div>

        <div className="lx-kpi-card">
          <span className="lx-kpi-label">{t("Lokale Docling-Zeit", "Local Docling Parse Time")}</span>
          <strong className="lx-kpi-value tabular">
            {convTotalSec > 0 ? `${convTotalSec.toFixed(1)} s` : "—"}
          </strong>
          <span className="lx-kpi-sub tabular">
            {sum.documents || 0} {t("Dokumente lokal strukturiert", "documents locally structured")}
          </span>
        </div>
      </div>

      {/* Stage Token Breakdown Chart */}
      <section className="lx-card lx-form-stack">
        <div className="lx-between">
          <div className="lx-row-gap">
            <Coins size={15} style={{ color: "var(--dot-active)" }} />
            <h2 className="lx-card-title">
              {t("Token- & Kostenverteilung nach Pipeline-Stufe", "Token & Cost Breakdown by Stage")}
            </h2>
          </div>
          <div className="lx-btn-row">
            <button
              type="button"
              className="lx-btn lx-btn-xs"
              disabled={loadingTel}
              onClick={fetchTelemetry}
            >
              <RefreshCw size={11} />
              <span>{t("Aktualisieren", "Refresh")}</span>
            </button>
            <button
              type="button"
              className="lx-btn lx-btn-xs lx-btn-primary"
              disabled={!telemetry?.runs?.length}
              onClick={downloadTelemetryCsv}
            >
              <Download size={11} />
              <span>{t("CSV für Evaluation", "Export CSV")}</span>
            </button>
          </div>
        </div>

        {stageRows.map((st) => {
          const stageName =
            st.stage === "vision"
              ? t("Stufe 02 · Vision (Schätzwert)", "Stage 02 · Vision (Est.)")
              : st.stage === "A"
              ? t("Stufe A · Evidenz", "Stage A · Evidence")
              : st.stage === "B"
              ? t("Stufe B · Relationen", "Stage B · Relations")
              : t("Stufe C · Findings", "Stage C · Findings");
          const color =
            st.stage === "vision"
              ? "var(--stage-vision)"
              : st.stage === "A"
              ? "var(--stage-a)"
              : st.stage === "B"
              ? "var(--stage-b)"
              : "var(--stage-c)";
          return (
            <div key={st.stage} className="lx-bar-row">
              <span className="truncate">
                <strong>{stageName}</strong>
              </span>
              <div className="lx-bar-track">
                <div
                  className="lx-bar-fill"
                  style={{
                    width: `${((st.total_tokens || 0) / maxStageTokens) * 100}%`,
                    background: color,
                  }}
                />
              </div>
              <span className="tabular lx-muted" style={{ textAlign: "right" }}>
                {(st.total_tokens || 0).toLocaleString()} Tok.
              </span>
            </div>
          );
        })}
      </section>

      {/* Empirical Multi-Model Evaluation Matrix for Thesis Evaluation */}
      {telemetry?.model_comparison?.length > 0 && (
        <section className="lx-table-card">
          <header className="lx-card-header">
            <div className="lx-row-gap">
              <div>
                <h2 className="lx-card-title">
                  {t(
                    "Modell-Evaluationsmatrix (Vergleich nach Stufe, Ertrag, Verankerungsquote & Tokens)",
                    "Multi-Model Evaluation Matrix (Stage, Yield, Anchor Rate & Token Efficiency)"
                  )}
                </h2>
                <p className="lx-card-sub">
                  {t(
                    "Aggregiert alle gespeicherten Läufe im gewählten Studienumfang pro Modell — ideal für Modellvergleiche in der Bachelorarbeit.",
                    "Aggregates all recorded runs in scope by model — designed for empirical model comparisons in your thesis."
                  )}
                </p>
              </div>
            </div>
          </header>
          <div className="lx-table-scroll">
            <table className="lx-table">
              <thead>
                <tr>
                  <th style={{ width: 90 }}>{t("Stufe", "Stage")}</th>
                  <th>{t("Modell & Anbieter", "Model & Provider")}</th>
                  <th style={{ width: 76 }}>{t("Läufe", "Runs")}</th>
                  <th style={{ width: 110 }}>{t("Ertrag", "Yield")}</th>
                  <th style={{ width: 135 }}>{t("Verankerung", "Anchored %")}</th>
                  <th style={{ width: 120 }}>{t("Ø Tok./Item", "Tok./Item")}</th>
                  <th style={{ width: 120 }}>{t("Gesamt-Tok.", "Total Tok.")}</th>
                  <th style={{ width: 125 }}>{t("Kosten (Ref.)", "Cost (Ref.)")}</th>
                </tr>
              </thead>
              <tbody>
                {telemetry.model_comparison.map((mc, idx) => (
                  <tr key={`${mc.stage}-${mc.provider}-${mc.model}-${idx}`}>
                    <td className="tabular">
                      <strong>{mc.stage === "vision" ? "Vision" : `Stufe ${mc.stage}`}</strong>
                    </td>
                    <td className="truncate" title={`${mc.provider} · ${mc.model}`}>
                      <strong>{mc.model}</strong>
                      <div className="lx-muted lx-text-xs">{mc.provider || "—"}</div>
                    </td>
                    <td className="tabular">
                      {mc.runs}
                      {mc.truncated_runs > 0 && (
                        <span className="lx-cap-pill" style={{ marginLeft: 4, color: "var(--dot-warning)" }}>
                          {mc.truncated_runs} cut
                        </span>
                      )}
                    </td>
                    <td className="tabular">{mc.items_total}</td>
                    <td className="tabular">
                      {mc.anchor_rate_pct != null ? (
                        <StatusBadge
                          label={`${mc.resolved_total}/${mc.items_total} (${mc.anchor_rate_pct}%)`}
                          tone={mc.anchor_rate_pct >= 95 ? "success" : mc.anchor_rate_pct >= 80 ? "warning" : "danger"}
                        />
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="tabular">
                      {mc.tokens_per_item != null ? Math.round(mc.tokens_per_item).toLocaleString() : "—"}
                    </td>
                    <td className="tabular">
                      {(mc.total_tokens || 0).toLocaleString()}
                      {mc.token_origin === "vision_estimate" && (
                        <span className="lx-muted lx-text-xs"> ~</span>
                      )}
                    </td>
                    <td className="tabular">
                      {formatUsd(mc.billed_usd)}
                      {mc.cloud_reference_usd != null && mc.cloud_reference_usd > 0 ? (
                        <span className="lx-muted lx-text-xs">
                          {" "}
                          ({formatUsd(mc.cloud_reference_usd)})
                        </span>
                      ) : mc.billed_usd === 0 ? (
                        <span className="lx-muted lx-text-xs"> ({t("0 € FAU/Lokal", "$0 Local")})</span>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Complete Run Telemetry Table */}
      <section className="lx-table-card">
        <header className="lx-card-header">
          <div>
            <h2 className="lx-card-title">
              {t("Einzellauf-Telemetrie (Alle gespeicherten Läufe im Umfang)", "Per-Run Telemetry Ledger")}
            </h2>
            <p className="lx-card-sub">
              {t(
                "Exakte Aufruf-, Token- und Kostendaten pro Modelllauf — direkt exportierbar für Kapitel 5 der Bachelorarbeit.",
                "Exact call, token, and cost metrics per model run — directly exportable for thesis evaluation."
              )}
            </p>
          </div>
        </header>
        <div className="lx-table-scroll">
          <table className="lx-table">
            <thead>
              <tr>
                <th style={{ width: 90 }}>{t("Stufe / ID", "Stage")}</th>
                <th>{t("Umfang / Dokument", "Scope / Document")}</th>
                <th>{t("Modell", "Model")}</th>
                <th style={{ width: 130 }}>{t("Prompt / Output", "In / Out")}</th>
                <th style={{ width: 110 }}>{t("Gesamt", "Total")}</th>
                <th style={{ width: 95 }}>{t("Ertrag", "Yield")}</th>
                <th style={{ width: 130 }}>{t("Kosten (Ref.)", "Cost (Ref.)")}</th>
              </tr>
            </thead>
            <tbody>
              {!telemetry?.runs?.length ? (
                <tr>
                  <td colSpan={7} className="lx-table-empty">
                    {loadingTel
                      ? t("Lade Telemetrie …", "Loading telemetry…")
                      : t("Noch keine protokollierten Modellläufe.", "No model runs recorded yet.")}
                  </td>
                </tr>
              ) : (
                telemetry.runs.map((r) => (
                  <tr key={`${r.kind}-${r.run_id}`}>
                    <td className="tabular">
                      <strong>
                        {r.kind} #{r.run_id}
                      </strong>
                      {r.active && (
                        <span className="lx-cap-pill" style={{ marginLeft: 5 }}>
                          {t("Aktiv", "Active")}
                        </span>
                      )}
                    </td>
                    <td className="truncate" title={r.scope_label}>
                      {r.scope_label}
                    </td>
                    <td className="truncate" title={`${r.provider} · ${r.model}`}>
                      {r.model || "—"}
                    </td>
                    <td className="tabular lx-muted">
                      {(r.prompt_tokens || 0).toLocaleString()} /{" "}
                      {(r.completion_tokens || 0).toLocaleString()}
                    </td>
                    <td className="tabular">
                      <strong>{(r.total_tokens || 0).toLocaleString()}</strong>
                    </td>
                    <td className="tabular">{r.items_count ?? 0}</td>
                    <td className="tabular">
                      {formatUsd(r.billed_usd)}
                      {r.cloud_reference_usd != null && r.cloud_reference_usd > 0 ? (
                        <span className="lx-muted lx-text-xs">
                          {" "}
                          ({formatUsd(r.cloud_reference_usd)})
                        </span>
                      ) : r.billed_usd === 0 ? (
                        <span className="lx-muted lx-text-xs"> ({t("0 €", "$0")})</span>
                      ) : null}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
