import React from "react";
import { Drawer } from "vaul";
import { Activity, AlertTriangle, CheckCircle2, Clock, ExternalLink, Play, Square, X } from "lucide-react";
import { usePrefs, statusInfo } from "../lib/i18n.jsx";
import { StatusDot } from "./ui.jsx";
import {
  formatLocalDateTime,
  SafeJobConsole,
  useFluidRuntimeProgress,
} from "./PipelineFlowConsole.jsx";

const STAGE_ORDER = [
  ["conversion", "Konvertierung", "Conversion"],
  ["vision", "Visuelle Analyse", "Visual Analysis"],
  ["A", "Evidenz A", "Evidence A"],
  ["B", "Beziehungen B", "Relations B"],
  ["C", "Findings C", "Findings C"],
];

export function RunMonitor({
  status,
  open,
  onOpenChange,
  onNavigate,
  onResumeWorkflow,
  onEndWorkflow,
}) {
  const { lang, t } = usePrefs();
  const fluid = useFluidRuntimeProgress(status);

  const busy = Boolean(status?.busy);
  const parked = status?.state === "WAITING_REVIEW" ? status : status?.parked_workflow || null;
  const waitingReview = !busy && Boolean(parked?.report?.review);
  const review = waitingReview ? parked.report.review : null;
  const resumeToken = parked?.ended || null;
  const safeMessage =
    typeof status?.message === "string"
      ? status.message
      : status?.message && typeof status.message === "object"
      ? [status.message.kind, status.message.document_name, status.message.status]
          .filter(Boolean)
          .join(" · ")
      : "";

  const wf = status?.workflow || null;
  const finishedCount = wf
    ? STAGE_ORDER.filter(([k]) =>
        ["success", "skipped", "UNREVIEWED", "NO_PROPOSALS"].includes(wf[k]?.status)
      ).length
    : 0;

  const elapsed = status?.started ? fluid.elapsed : "—";
  const liveProgressPct = busy
    ? fluid.overallPct
    : wf
    ? Math.round((finishedCount / 5) * 100)
    : status?.state === "FINISHED"
    ? 100
    : 0;

  let pillTone = "neutral";
  let pillLabel = t("Bereit", "Idle");
  if (busy) {
    pillTone = "active";
    pillLabel = wf
      ? `${t("Pipeline", "Pipeline")} ${Math.round(liveProgressPct)}% · ${elapsed}`
      : `${safeMessage || t("Aktiv", "Running")} · ${Math.round(liveProgressPct)}% · ${elapsed}`;
  } else if (waitingReview) {
    pillTone = "warning";
    pillLabel = t("Prüfung erforderlich", "Review Required");
  } else if (status?.state === "ERROR") {
    pillTone = "danger";
    pillLabel = t("Letzter Lauf fehlerhaft", "Last Run Failed");
  } else if (wf || status?.state === "FINISHED") {
    pillTone = "success";
    pillLabel = status?.started
      ? `${t("Abgeschlossen", "Completed")} · ${elapsed}`
      : t("Abgeschlossen", "Completed");
  }

  return (
    <Drawer.Root direction="right" open={open} onOpenChange={onOpenChange}>
      <Drawer.Trigger asChild>
        <button
          type="button"
          data-testid="run-monitor-pill"
          className={`lx-run-pill${busy ? " is-busy" : ""}${waitingReview ? " is-review" : ""}`}
          title={t("Pipeline-Aktivitätsmonitor öffnen", "Open Pipeline Activity Monitor")}
        >
          <StatusDot tone={pillTone} pulse={busy} />
          <span className="tabular truncate">{pillLabel}</span>
        </button>
      </Drawer.Trigger>
      <Drawer.Portal>
        <Drawer.Overlay className="lx-drawer-overlay" />
        <Drawer.Content className="lx-drawer-content" aria-describedby={undefined}>
          <div className="lx-drawer-header">
            <div className="lx-row-gap min-w-0">
              <Activity size={16} className="lx-icon-muted" />
              <Drawer.Title className="lx-drawer-title truncate">
                {t("Pipeline-Aktivitätsmonitor", "Pipeline Activity Monitor")}
              </Drawer.Title>
            </div>
            <Drawer.Close asChild>
              <button type="button" className="lx-icon-btn" aria-label="Close">
                <X size={15} />
              </button>
            </Drawer.Close>
          </div>

          <div className="lx-drawer-body">
            {/* Summary status card */}
            <div className="lx-card lx-card-subtle">
              <div className="lx-between">
                <div className="lx-row-gap min-w-0">
                  <StatusDot tone={pillTone} pulse={busy} />
                  <strong className="truncate">
                    {busy
                      ? safeMessage || t("Verarbeitung läuft …", "Processing…")
                      : waitingReview
                      ? t("Wartet auf Quellenprüfung", "Paused for Source Review")
                      : safeMessage || t("Kein aktiver Auftrag", "No Active Job")}
                  </strong>
                </div>
                <span className="lx-mono-tag tabular">{elapsed}</span>
              </div>
              {(wf || busy) && (
                <div className="lx-progress-track" aria-hidden="true">
                  <div
                    className={`lx-progress-fill${busy ? " is-fluid" : ""}`}
                    style={{ width: `${liveProgressPct}%` }}
                  />
                </div>
              )}
              {status?.started && (
                <div className="lx-meta-line tabular" data-testid="run-monitor-timestamps">
                  <span data-testid="run-monitor-started" title={`UTC: ${status.started}`}>
                    {t("Start", "Started")}: {formatLocalDateTime(status.started, lang)}
                  </span>
                  {status.ended && (
                    <span data-testid="run-monitor-ended" title={`UTC: ${status.ended}`}>
                      {t("Ende", "Ended")}: {formatLocalDateTime(status.ended, lang)}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Review Pause Callout */}
            {waitingReview && review && (
              <div className="lx-callout-box lx-callout-warning">
                <div className="lx-row-gap">
                  <AlertTriangle size={15} />
                  <strong>
                    {t(
                      `Angehalten vor Folgestufe (${review.phase || "Prüfung"})`,
                      `Paused at stage (${review.phase || "Review"})`
                    )}
                  </strong>
                </div>
                <p className="lx-text-sm">
                  {t(
                    "Einige Primärquellen oder Laufbelege sind noch offen. Du kannst sie prüfen, erneut ausführen oder den Gesamtauftrag hier sauber abschließen.",
                    "Some primary anchors or stage receipts remain open. Inspect them, retry open items, or finalize the workflow at this stage."
                  )}
                </p>
                <div className="lx-btn-row">
                  <button
                    type="button"
                    className="lx-btn lx-btn-sm lx-btn-primary"
                    onClick={() => {
                      onOpenChange(false);
                      onResumeWorkflow?.({ ...review, resume: resumeToken });
                    }}
                  >
                    <Play size={13} />
                    <span>{t("Fortsetzen / Prüfen", "Resume / Retry")}</span>
                  </button>
                  <button
                    type="button"
                    className="lx-btn lx-btn-sm"
                    onClick={() => onEndWorkflow?.(resumeToken)}
                  >
                    <Square size={13} />
                    <span>{t("Hier abschließen", "End Workflow Here")}</span>
                  </button>
                </div>
              </div>
            )}

            {/* 5-Stage Timeline */}
            <div className="lx-section-block">
              <h3 className="lx-eyebrow">{t("Stufenfortschritt", "Stage Timeline")}</h3>
              <ol className="lx-timeline">
                {STAGE_ORDER.map(([key, labelDe, labelEn]) => {
                  const step = wf?.[key] || { status: "planned" };
                  const rawStatus = step.status || "planned";
                  const isRunning = busy && rawStatus === "running";
                  const isDone = ["success", "UNREVIEWED", "NO_PROPOSALS"].includes(rawStatus);
                  const isSkipped = rawStatus === "skipped";
                  const tone = isRunning
                    ? "active"
                    : isDone
                    ? "success"
                    : rawStatus === "ERROR" || rawStatus === "PARTIAL"
                    ? "warning"
                    : "neutral";

                  const details = [
                    isRunning
                      ? t("Aktiv", "Running")
                      : isDone
                      ? t("Abgeschlossen", "Completed")
                      : isSkipped
                      ? t("Übersprungen", "Skipped")
                      : statusInfo(rawStatus, t).label,
                    step.total > 0 ? `${step.completed ?? 0}/${step.total}` : null,
                    Number.isInteger(step.proposed)
                      ? `${step.proposed} ${t("Vorschläge", "proposals")}`
                      : null,
                    key === "vision" && step.pictures > 0
                      ? `${step.described || 0}/${step.pictures} ${t("Bilder", "images")}`
                      : null,
                    isRunning && step.event?.document_name ? step.event.document_name : null,
                  ]
                    .filter(Boolean)
                    .join(" · ");

                  return (
                    <li key={key} className={`lx-timeline-item${isRunning ? " is-active" : ""}`}>
                      <div className="lx-timeline-dot">
                        <StatusDot tone={tone} pulse={isRunning} />
                      </div>
                      <div className="lx-timeline-content min-w-0">
                        <div className="lx-between">
                          <span className="lx-timeline-title">{t(labelDe, labelEn)}</span>
                          <span className="lx-muted tabular">{key}</span>
                        </div>
                        <p className="lx-timeline-sub truncate" title={details}>
                          {details}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </div>

            {/* Per-document status list */}
            {Array.isArray(status?.documents) && status.documents.length > 0 && (
              <div className="lx-section-block">
                <h3 className="lx-eyebrow">
                  {t("Dokumentprotokoll", "Document Ledger")} ({status.documents.length})
                </h3>
                <div className="lx-doc-ledger">
                  {status.documents.map((d, idx) => {
                    const si = statusInfo(d.status, t);
                    return (
                      <div key={d.document || idx} className="lx-doc-ledger-row">
                        <StatusDot tone={si.tone} pulse={busy && d.status === "running"} />
                        <div className="min-w-0 flex-1">
                          <div className="lx-doc-ledger-name truncate" title={d.document_name}>
                            {d.document_name || `#${d.document}`}
                          </div>
                          <div className="lx-muted truncate">
                            {[si.label, d.detail, d.observations != null ? `${d.observations} Obs.` : null]
                              .filter(Boolean)
                              .join(" · ")}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Live Safe Console inside Slide-Over Drawer */}
            <div className="lx-card" style={{ padding: 0, overflow: "hidden" }}>
              <SafeJobConsole
                events={status?.events || []}
                status={status}
                defaultOpen
                compact
              />
            </div>

            {/* Quick navigation footer */}
            <div className="lx-drawer-footer">
              <button
                type="button"
                className="lx-btn lx-btn-sm"
                onClick={() => {
                  onOpenChange(false);
                  onNavigate?.("pipeline");
                }}
              >
                <Clock size={13} />
                <span>{t("Zur Pipeline", "Open Pipeline")}</span>
              </button>
              <button
                type="button"
                className="lx-btn lx-btn-sm lx-btn-primary"
                onClick={() => {
                  onOpenChange(false);
                  onNavigate?.("results");
                }}
              >
                <CheckCircle2 size={13} />
                <span>{t("Ergebnisse prüfen", "Inspect Synthesis")}</span>
                <ExternalLink size={12} />
              </button>
            </div>
          </div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
