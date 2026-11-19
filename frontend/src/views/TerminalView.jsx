import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Copy,
  RefreshCw,
  Search,
  Terminal,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { usePrefs, statusInfo } from "../lib/i18n.jsx";
import { api } from "../lib/api.js";
import { InfoPopover, StatusBadge, StatusDot } from "../components/ui.jsx";

function formatEventLocalClock(isoUtc) {
  if (!isoUtc) return "--:--:--";
  const ms = Date.parse(isoUtc);
  if (!Number.isFinite(ms)) return String(isoUtc).slice(11, 19) || "--:--:--";
  return new Intl.DateTimeFormat("de-DE", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(ms));
}

export function formatRichTerminalEvent(ev, t) {
  const ts = formatEventLocalClock(ev.at);
  const rawStage = ev.workflow_step || ev.workflow_stage || ev.kind || ev.stage || ev.phase || "job";
  const stageGroup =
    {
      inventory: "IMPORT",
      import_paths: "IMPORT",
      conversion: "DOCLING",
      convert: "DOCLING",
      vision: "VISION",
      enrich: "VISION",
      A: "STUFE A",
      extract: "STUFE A",
      B: "STUFE B",
      C: "STUFE C",
      workflow: "PIPELINE",
      model_access: "MODELL",
    }[rawStage] || String(rawStage).toUpperCase().slice(0, 9);

  const status = ev.result_status || ev.status || "";
  const phase = ev.phase || "";
  const httpCode = Number(ev.http_status || 0);
  const isError =
    status === "ERROR" ||
    status === "failure" ||
    status === "error" ||
    phase === "api_error" ||
    httpCode >= 500 ||
    Boolean(ev.error);
  const isWarn =
    !isError &&
    (status === "PARTIAL" ||
      status === "WARN" ||
      status === "partial_success" ||
      status === "NO_PROPOSALS" ||
      status === "WAITING_REVIEW" ||
      ["model_timeout", "stream_stalled", "model_retry", "structured_fallback"].includes(phase) ||
      httpCode >= 400 ||
      Boolean(ev.unresolved) ||
      Boolean(ev.issues && ev.issues > 0 && status !== "UNREVIEWED"));

  const parts = [];
  if (ev.document_name) parts.push(ev.document_name);
  else if (ev.document) parts.push(`#${ev.document}`);

  if (phase && !["conversion", "enrich", rawStage].includes(phase)) {
    parts.push(phase);
  }
  if (status && status !== "WARN") {
    parts.push(statusInfo(status, t).label || status);
  }
  if (ev.attempt && ev.max_attempts && ev.max_attempts > 1) {
    parts.push(`${t("Versuch", "Attempt")} ${ev.attempt}/${ev.max_attempts}`);
  }
  if (ev.completed != null && ev.total != null && ev.total > 0) {
    parts.push(`${ev.completed}/${ev.total}`);
  }
  if (ev.completed_pages != null && ev.total_pages != null && ev.total_pages > 0) {
    parts.push(`${t("Seite", "p.")} ${ev.completed_pages}/${ev.total_pages}`);
  }
  if (ev.duration_s != null) {
    parts.push(`${ev.duration_s}s`);
  } else if (ev.timeout_s != null && phase === "model_request") {
    parts.push(`Limit ${ev.timeout_s}s`);
  }
  if (ev.items_count != null) {
    parts.push(`${ev.items_count} ${t("Blöcke", "blocks")}`);
  }
  if (ev.confidence_grade) {
    parts.push(`${t("Güte", "Quality")}: ${ev.confidence_grade}`);
  }
  if (ev.observations != null) {
    if (ev.resolved != null) {
      parts.push(`${t("Belege", "Grounded")} ${ev.resolved}/${ev.observations}`);
    } else {
      parts.push(`${ev.observations} ${t("Beobachtungen", "obs.")}`);
    }
  }
  if (ev.proposed != null) {
    parts.push(`${ev.proposed} ${t("Vorschläge", "proposals")}`);
  }
  if (ev.unresolved) {
    parts.push(`${ev.unresolved} ${t("offen", "open")}`);
  }
  if (ev.described != null && ev.pictures != null) {
    parts.push(`${ev.described}/${ev.pictures} ${t("Bilder", "images")}`);
  }
  if (ev.total_tokens) {
    const rTok = ev.reasoning_tokens ? ` (${Number(ev.reasoning_tokens).toLocaleString()} Reasoning)` : "";
    parts.push(`${Number(ev.total_tokens).toLocaleString()} Tokens${rTok}`);
  }
  if (ev.model) {
    parts.push(ev.model);
  }
  if (ev.contract) {
    parts.push(`contract=${ev.contract}`);
  }
  if (ev.http_status) {
    parts.push(`HTTP ${ev.http_status}`);
  }
  if (ev.detail) {
    parts.push(ev.detail);
  } else if (ev.reason) {
    parts.push(`${t("Hinweis", "Note")}: ${ev.reason}`);
  }
  if (ev.error && ev.error !== ev.reason) {
    parts.push(`${t("Fehler", "Error")}: ${ev.error}`);
  }

  return {
    ts,
    stageGroup,
    text: parts.join(" · ") || t("Schritt aktiv", "Step active"),
    isError,
    isWarn,
    raw: ev,
  };
}

export function TerminalView({ jobStatus }) {
  const { t } = usePrefs();
  const [historyData, setHistoryData] = useState({ history: [], active: null });
  const [selectedRunIdx, setSelectedRunIdx] = useState("all"); // "live" | "all" | index
  const [stageFilter, setStageFilter] = useState("ALL");
  const [onlyIssues, setOnlyIssues] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const logContainerRef = useRef(null);

  const loadHistory = useCallback(async () => {
    try {
      const res = await api("job-history");
      setHistoryData(res || { history: [], active: null });
    } catch {
      /* ignore transient */
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory, jobStatus?.busy, jobStatus?.ended]);

  useEffect(() => {
    if (!jobStatus?.busy) return;
    setSelectedRunIdx("live");
  }, [jobStatus?.busy]);

  const clearHistory = async () => {
    try {
      await api("job-history-clear", {});
      setHistoryData({ history: [], active: null });
      setSelectedRunIdx("live");
      toast.success(t("Auftragsverlauf geleert", "Job history cleared"));
    } catch (err) {
      toast.error(err.message);
    }
  };

  const historyList = historyData.history || [];
  const hasLiveOrLatest = Boolean(jobStatus?.events?.length || jobStatus?.busy);

  const activeEventsSource = useMemo(() => {
    if (selectedRunIdx === "live") {
      return (jobStatus?.events || []).map((ev) => ({
        ...ev,
        _jobLabel: jobStatus?.action || "live",
      }));
    }
    if (selectedRunIdx === "all") {
      const chronologicalJobs = [...historyList].reverse();
      const merged = [];
      for (const j of chronologicalJobs) {
        for (const ev of j.events || []) {
          merged.push({
            ...ev,
            _jobLabel: `${j.action || "job"} (${(j.started || "").slice(11, 16)})`,
          });
        }
      }
      if (jobStatus?.busy && jobStatus?.events?.length) {
        for (const ev of jobStatus.events) {
          merged.push({ ...ev, _jobLabel: "LIVE" });
        }
      } else if (!merged.length && jobStatus?.events?.length) {
        for (const ev of jobStatus.events) {
          merged.push({ ...ev, _jobLabel: jobStatus.action || "latest" });
        }
      }
      return merged;
    }
    const chosen = historyList[Number(selectedRunIdx)];
    return (chosen?.events || []).map((ev) => ({
      ...ev,
      _jobLabel: chosen?.action || "job",
    }));
  }, [selectedRunIdx, jobStatus, historyList]);

  const formattedLines = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return activeEventsSource
      .map((ev) => ({ ...formatRichTerminalEvent(ev, t), jobLabel: ev._jobLabel }))
      .filter((line) => {
        if (onlyIssues && !line.isError && !line.isWarn) return false;
        if (stageFilter !== "ALL" && line.stageGroup !== stageFilter) return false;
        if (q && !`${line.stageGroup} ${line.text} ${line.jobLabel}`.toLowerCase().includes(q)) {
          return false;
        }
        return true;
      });
  }, [activeEventsSource, onlyIssues, stageFilter, searchQuery, t]);

  const totalTokensLogged = useMemo(() => {
    const seenRunKeys = new Set();
    let sum = 0;
    activeEventsSource.forEach((ev, idx) => {
      const tok = Number(ev.total_tokens) || 0;
      if (!tok) return;
      const runKey =
        ev.run != null ? `${ev.kind || ev.stage || "run"}:${ev.run}` : `idx:${idx}`;
      if (seenRunKeys.has(runKey)) return;
      seenRunKeys.add(runKey);
      sum += tok;
    });
    return sum;
  }, [activeEventsSource]);

  const issueLinesCount = useMemo(
    () =>
      activeEventsSource
        .map((ev) => formatRichTerminalEvent(ev, t))
        .filter((l) => l.isError || l.isWarn).length,
    [activeEventsSource, t]
  );

  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [formattedLines.length, autoScroll]);

  const copyTranscript = async () => {
    const text = formattedLines
      .map(
        (l) =>
          `[${l.ts}] [${l.stageGroup.padEnd(9, " ")}] ${
            selectedRunIdx === "all" && l.jobLabel ? `(${l.jobLabel}) ` : ""
          }${l.text}`
      )
      .join("\n");
    try {
      await navigator.clipboard.writeText(text);
      toast.success(t("Terminal-Verlauf in Zwischenablage kopiert", "Terminal log copied"));
    } catch {
      toast.error(t("Kopieren nicht verfügbar", "Clipboard unavailable"));
    }
  };

  return (
    <div className="lx-page">
      <header className="lx-page-header">
        <div>
          <div className="lx-row-gap">
            <h1 className="lx-page-title">
              {t("Terminal & Kompletter Auftragsverlauf", "Terminal & Complete Run Ledger")}
            </h1>
            <InfoPopover title={t("Terminal im Browser & in der Shell", "Web & CLI Terminal")}>
              <p>
                {t(
                  "Hier siehst du lückenlos jeden Schritt deiner aktuellen Sitzung und vergangener Läufe: Docling-Konvertierungszeit, Blockanzahl, Konfidenzgüte, Vision-Status, verankerte Belege in Stufe A, Synthese-Vorschläge in B/C, verwendete Modellkennung und Token-Zähler.",
                  "Provides a chronological audit stream of every active and past run: Docling conversion timing, parsed block counts, confidence grades, Vision status, Stage A grounded anchors, Stage B/C proposals, model IDs, and token counts."
                )}
              </p>
              <p>
                {t(
                  "Auch im System-Terminal (PowerShell/Bash) gibt ‚ux-maind‘ diese Schritte live aus (mit ‚ux-maind --verbose‘ zusätzlich alle HTTP-Requests). Roh-Prompts, Dokumentvolltexte und API-Keys werden niemals im Klartext protokolliert.",
                  "Running 'ux-maind' in your shell also streams these events live ('ux-maind --verbose' adds HTTP access logs). Raw prompts, full texts, and API keys are never exposed."
                )}
              </p>
              <p>
                {t(
                  "Persistenz & Deployment-Fähigkeit: Sollte der Server neu gestartet oder als Container bereitgestellt werden, rekonstruiert UX-mAInd den kompletten Verlauf aller Konvertierungs-, Vision-, A-, B- und C-Läufe automatisch aus der lokalen SQLite-Datenbank. Für Mehrbenutzer-Web-Deployments lässt sich der Hintergrund-Worker sauber über eine externe Job-Queue (Redis/PostgreSQL) entkoppeln (siehe Handbuch & Systemgrenzen).",
                  "Persistence & Web Deployment: Across server restarts or container deployments, UX-mAInd automatically reconstructs historical Conversion, Vision, Stage A, B, and C runs from SQLite. For multi-tenant web deployments, background workers can be decoupled via Redis/PostgreSQL (see Manual & System Limits)."
                )}
              </p>
            </InfoPopover>
          </div>
          <p className="lx-page-sub">
            {t(
              "Chronologisches Echtzeit-Protokoll über Konvertierung, Bildanreicherung und KI-Stufen A · B · C inklusive gespeicherter Laufhistorie.",
              "Real-time chronological execution log across Docling conversion, Vision enrichment, and LLM Stages A · B · C."
            )}
          </p>
        </div>

        <div className="lx-row-gap">
          <button type="button" className="lx-btn lx-btn-sm" onClick={loadHistory}>
            <RefreshCw size={13} />
            <span>{t("Aktualisieren", "Refresh")}</span>
          </button>
          <button
            type="button"
            className="lx-btn lx-btn-sm"
            disabled={!formattedLines.length}
            onClick={copyTranscript}
          >
            <Copy size={13} />
            <span>{t("Protokoll kopieren", "Copy Log")}</span>
          </button>
        </div>
      </header>

      {/* Summary KPI Strip */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
          gap: 12,
          marginBottom: 16,
        }}
      >
        <div className="lx-card lx-card-subtle" style={{ padding: "12px 14px" }}>
          <span className="lx-muted lx-text-xs">{t("Aktueller Laufstatus", "Current State")}</span>
          <div className="lx-row-gap" style={{ marginTop: 4 }}>
            <StatusDot
              tone={
                jobStatus?.busy
                  ? "info"
                  : jobStatus?.state === "ERROR"
                  ? "danger"
                  : jobStatus?.state === "WAITING_REVIEW"
                  ? "warning"
                  : "success"
              }
            />
            <strong className="lx-text-sm">
              {jobStatus?.busy
                ? t("Auftrag läuft live …", "Job running live…")
                : jobStatus?.state || t("Bereit", "Idle / Ready")}
            </strong>
          </div>
        </div>

        <div className="lx-card lx-card-subtle" style={{ padding: "12px 14px" }}>
          <span className="lx-muted lx-text-xs">
            {t("Gespeicherte Aufträge im Verlauf", "Recorded Runs in Ledger")}
          </span>
          <div style={{ marginTop: 4, fontSize: "16px", fontWeight: 700 }} className="tabular">
            {historyList.length}
          </div>
        </div>

        <div className="lx-card lx-card-subtle" style={{ padding: "12px 14px" }}>
          <span className="lx-muted lx-text-xs">
            {t("Angezeigte Protokollzeilen", "Visible Log Events")}
          </span>
          <div style={{ marginTop: 4, fontSize: "16px", fontWeight: 700 }} className="tabular">
            {formattedLines.length}{" "}
            <span className="lx-muted lx-text-xs" style={{ fontWeight: 400 }}>
              / {activeEventsSource.length}
            </span>
          </div>
        </div>

        <div className="lx-card lx-card-subtle" style={{ padding: "12px 14px" }}>
          <span className="lx-muted lx-text-xs">
            {t("Erfasste Tokens (Auswahl)", "Logged Tokens (Selection)")}
          </span>
          <div style={{ marginTop: 4, fontSize: "16px", fontWeight: 700 }} className="tabular">
            {totalTokensLogged > 0 ? totalTokensLogged.toLocaleString() : "—"}
          </div>
        </div>
      </div>

      {/* Main Split: Left Run Ledger + Right Chronological Terminal */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(250px, 300px) minmax(0, 1fr)",
          gap: 16,
          alignItems: "start",
        }}
      >
        {/* Left: Run History Ledger */}
        <section className="lx-card lx-form-stack" style={{ padding: 12, gap: 8 }}>
          <div className="lx-between">
            <span className="lx-eyebrow">{t("Auftrags-Verlauf", "Job Ledger")}</span>
            {historyList.length > 0 && (
              <button
                type="button"
                className="lx-btn lx-btn-xs lx-btn-ghost"
                onClick={clearHistory}
                title={t("Gespeicherten Verlauf leeren", "Clear saved ledger")}
              >
                <Trash2 size={11} />
                <span>{t("Leeren", "Clear")}</span>
              </button>
            )}
          </div>

          <button
            type="button"
            className={`lx-catalog-row${selectedRunIdx === "all" ? " is-active" : ""}`}
            onClick={() => setSelectedRunIdx("all")}
          >
            <div>
              <div className="lx-text-xs" style={{ fontWeight: 600 }}>
                {t("Kompletter Gesamtverlauf", "Complete Chronological Stream")}
              </div>
              <div className="lx-muted" style={{ fontSize: "11px" }}>
                {t("Alle Läufe chronologisch vereint", "All runs merged chronologically")}
              </div>
            </div>
          </button>

          {hasLiveOrLatest && (
            <button
              type="button"
              className={`lx-catalog-row${selectedRunIdx === "live" ? " is-active" : ""}`}
              onClick={() => setSelectedRunIdx("live")}
            >
              <div className="min-w-0" style={{ flex: 1 }}>
                <div className="lx-row-gap">
                  <Activity size={12} />
                  <span className="lx-text-xs truncate" style={{ fontWeight: 600 }}>
                    {jobStatus?.busy
                      ? t("Aktiver Live-Auftrag", "Active Live Run")
                      : t("Letzter Sitzungsauftrag", "Latest Session Run")}
                  </span>
                </div>
                <div className="lx-muted tabular" style={{ fontSize: "11px" }}>
                  {jobStatus?.action || "job"} · {(jobStatus?.events || []).length}{" "}
                  {t("Ereignisse", "events")}
                </div>
              </div>
              <StatusBadge status={jobStatus?.state || "RUNNING"} />
            </button>
          )}

          {historyList.length > 0 && <div className="lx-divider" />}

          <div style={{ maxHeight: 420, overflowY: "auto", display: "flex", flexDirection: "column", gap: 4 }}>
            {historyList.map((h, idx) => {
              const isSelected = String(selectedRunIdx) === String(idx);
              const tsLabel = h.started ? `${h.started.slice(0, 10)} ${h.started.slice(11, 19)}` : "—";
              return (
                <button
                  key={`${h.started}-${idx}`}
                  type="button"
                  className={`lx-catalog-row${isSelected ? " is-active" : ""}`}
                  onClick={() => setSelectedRunIdx(idx)}
                >
                  <div className="min-w-0" style={{ flex: 1, textAlign: "left" }}>
                    <div className="lx-text-xs truncate" style={{ fontWeight: 600 }}>
                      {h.action || "job"}
                    </div>
                    <div className="lx-muted tabular" style={{ fontSize: "10.5px" }}>
                      <Clock size={10} style={{ display: "inline", marginRight: 4 }} />
                      {tsLabel} · {(h.documents || []).length} {t("Dok.", "docs")}
                    </div>
                  </div>
                  <StatusBadge status={h.state || "FINISHED"} />
                </button>
              );
            })}
            {!historyList.length && !hasLiveOrLatest && (
              <p className="lx-muted lx-text-xs" style={{ padding: "8px 4px" }}>
                {t(
                  "Noch keine Aufträge ausgeführt. Starte einen Import oder Pipeline-Lauf, um das Echtzeit-Terminal zu sehen.",
                  "No runs recorded yet. Start an import or pipeline run to inspect live events."
                )}
              </p>
            )}
          </div>
        </section>

        {/* Right: Structured Monospace Terminal Surface */}
        <section className="lx-console-panel" style={{ margin: 0 }}>
          <div className="lx-console-bar" style={{ flexWrap: "wrap", gap: 8 }}>
            <div className="lx-row-wrap" style={{ gap: 6 }}>
              {[
                ["ALL", t("Alle", "All")],
                ["DOCLING", "Docling"],
                ["VISION", "Vision"],
                ["STUFE A", t("Stufe A", "Stage A")],
                ["STUFE B", t("Stufe B", "Stage B")],
                ["STUFE C", t("Stufe C", "Stage C")],
              ].map(([code, label]) => (
                <button
                  key={code}
                  type="button"
                  className={`lx-btn lx-btn-xs${stageFilter === code ? " lx-btn-primary" : " lx-btn-ghost"}`}
                  onClick={() => setStageFilter(code)}
                >
                  {label}
                </button>
              ))}
              <button
                type="button"
                className={`lx-btn lx-btn-xs${onlyIssues ? " lx-btn-primary" : " lx-btn-ghost"}`}
                onClick={() => setOnlyIssues((v) => !v)}
              >
                <AlertTriangle size={11} />
                <span>
                  {t("Warnungen/Fehler", "Issues")} ({issueLinesCount})
                </span>
              </button>
            </div>

            <div className="lx-row-gap">
              <div className="lx-search-wrap" style={{ width: 210 }}>
                <Search size={12} className="lx-search-icon" />
                <input
                  type="search"
                  className="lx-input lx-input-sm lx-search-input"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder={t("Im Terminal filtern …", "Filter log…")}
                />
              </div>
              <button
                type="button"
                className={`lx-btn lx-btn-xs${autoScroll ? " is-active" : " lx-btn-ghost"}`}
                onClick={() => setAutoScroll((v) => !v)}
                title={t("Automatisch ans Ende scrollen", "Auto-scroll to newest line")}
              >
                <CheckCircle2 size={11} />
                <span>Auto-Scroll</span>
              </button>
            </div>
          </div>

          <div
            ref={logContainerRef}
            className="lx-console-log"
            style={{ minHeight: 440, maxHeight: "66vh", padding: "12px 14px" }}
          >
            {formattedLines.length === 0 ? (
              <div className="lx-muted" style={{ padding: "18px 6px" }}>
                <Terminal size={16} style={{ display: "inline", marginRight: 8, verticalAlign: "text-bottom" }} />
                {t(
                  "Keine passenden Protokollzeilen für den gewählten Filter.",
                  "No log entries match the current filter."
                )}
              </div>
            ) : (
              formattedLines.map((line, idx) => (
                <div
                  key={idx}
                  className={`lx-console-line${
                    line.isError ? " is-error" : line.isWarn ? " is-warn" : ""
                  }`}
                >
                  <span className="lx-console-ts tabular">{line.ts}</span>
                  <span className="lx-console-stage">{line.stageGroup}</span>
                  <span className="lx-console-msg">
                    {selectedRunIdx === "all" && line.jobLabel ? (
                      <span className="lx-muted" style={{ marginRight: 6 }}>
                        [{line.jobLabel}]
                      </span>
                    ) : null}
                    {line.text}
                  </span>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
