import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  Terminal,
} from "lucide-react";
import { toast } from "sonner";
import { usePrefs } from "../lib/i18n.jsx";
import { InfoPopover, StatusDot } from "./ui.jsx";
import { formatRichTerminalEvent } from "../views/TerminalView.jsx";

function safeMessageText(rawMsg) {
  if (!rawMsg) return "";
  if (typeof rawMsg === "string") return rawMsg;
  if (typeof rawMsg === "object") {
    return [rawMsg.workflow_step || rawMsg.kind, rawMsg.document_name, rawMsg.status]
      .filter(Boolean)
      .join(" · ");
  }
  return String(rawMsg);
}

const LIVE_STAGE_ORDER = ["conversion", "vision", "A", "B", "C"];
const STAGE_TAU_SEC = {
  conversion: 8,
  vision: 18,
  A: 26,
  B: 30,
  C: 30,
};

function resolveActionStageKey(action) {
  if (!action) return null;
  if (action === "import" || action === "analysis_convert") return "conversion";
  if (action === "analysis_enrich") return "vision";
  if (action === "analysis_A") return "A";
  if (action === "analysis_B") return "B";
  if (action === "analysis_C") return "C";
  return null;
}

export function formatRuntimeElapsed(started, ended, nowTick) {
  if (!started) return "00:00";
  const t0 = Date.parse(started);
  const t1 = ended ? Date.parse(ended) : nowTick;
  if (!Number.isFinite(t0) || !Number.isFinite(t1)) return "00:00";
  const sec = Math.max(0, Math.floor((t1 - t0) / 1000));
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function useFluidRuntimeProgress(jobStatus) {
  const busy = Boolean(jobStatus?.busy);
  const [nowTick, setNowTick] = useState(() => Date.now());
  const subStepRef = useRef({ sig: "", runKey: "", startedAt: Date.now() });
  const maxPctRef = useRef({ runKey: "", pct: 0 });

  useEffect(() => {
    setNowTick(Date.now());
    if (!busy) return;
    const id = setInterval(() => setNowTick(Date.now()), 1000);
    return () => clearInterval(id);
  }, [busy, jobStatus?.started]);

  return useMemo(() => {
    const wf = jobStatus?.workflow || null;
    const evs = jobStatus?.events || [];
    const lastEv = evs.length ? evs[evs.length - 1] : jobStatus?.last_event || null;
    const elapsed = formatRuntimeElapsed(jobStatus?.started, jobStatus?.ended, nowTick);

    if (!busy) {
      const doneStages = wf
        ? LIVE_STAGE_ORDER.filter((k) =>
            ["success", "skipped", "UNREVIEWED", "NO_PROPOSALS"].includes(wf[k]?.status)
          ).length
        : 0;
      const idlePct =
        jobStatus?.state === "FINISHED" && (!wf || doneStages >= 5)
          ? 100
          : wf
          ? Math.round((doneStages / 5) * 100)
          : 0;
      return {
        busy: false,
        nowTick,
        elapsed,
        overallPct: idlePct,
        activeWfKey: null,
        activeStagePct: 0,
        streamChunks: 0,
      };
    }

    const runKey = `${jobStatus?.started || "active"}|${jobStatus?.action || "job"}`;
    let activeWfKey =
      (wf && LIVE_STAGE_ORDER.find((k) => wf[k]?.status === "running")) ||
      resolveActionStageKey(jobStatus?.action) ||
      (wf &&
        LIVE_STAGE_ORDER.find(
          (k) => !["success", "skipped", "UNREVIEWED", "NO_PROPOSALS"].includes(wf[k]?.status)
        )) ||
      "A";

    const wfStep = wf?.[activeWfKey] || null;
    const unitDone = Math.max(0, Number(wfStep?.completed || 0));
    const unitTotal = Math.max(1, Number(wfStep?.total || 1));
    const docSig = wfStep?.event?.document_name || lastEv?.document_name || "";
    const sig = `${runKey}|${activeWfKey}|${unitDone}/${unitTotal}|${docSig}`;

    if (subStepRef.current.sig !== sig) {
      const isInitialForRun = subStepRef.current.runKey !== runKey;
      const parsedStart = Date.parse(jobStatus?.started || "");
      subStepRef.current = {
        sig,
        runKey,
        startedAt: isInitialForRun && Number.isFinite(parsedStart) ? parsedStart : nowTick,
      };
    }

    const stepElapsedSec = Math.max(0, (nowTick - subStepRef.current.startedAt) / 1000);
    const streamChunks = Math.max(0, Number(lastEv?.chunks || wfStep?.event?.chunks || 0));
    const tau = STAGE_TAU_SEC[activeWfKey] || 24;
    const subUnitFrac = Math.min(
      0.92,
      1 - Math.exp(-(stepElapsedSec / tau) - streamChunks / 1400)
    );
    const activeStagePct = Math.min(
      97,
      Math.max(5, ((unitDone + subUnitFrac) / unitTotal) * 100)
    );

    let rawOverall = activeStagePct;
    if (wf) {
      let totalWeight = 0;
      for (const k of LIVE_STAGE_ORDER) {
        const st = wf[k]?.status;
        if (["success", "skipped", "UNREVIEWED", "NO_PROPOSALS"].includes(st)) {
          totalWeight += 1;
        } else if (k === activeWfKey) {
          totalWeight += activeStagePct / 100;
        }
      }
      rawOverall = Math.min(99.2, Math.max(2.5, (totalWeight / 5) * 100));
    } else {
      rawOverall = Math.min(98.8, Math.max(3, activeStagePct));
    }

    if (maxPctRef.current.runKey !== runKey) {
      maxPctRef.current = { runKey, pct: rawOverall };
    } else {
      maxPctRef.current.pct = Math.max(maxPctRef.current.pct, rawOverall);
    }

    return {
      busy: true,
      nowTick,
      elapsed,
      overallPct: Number(maxPctRef.current.pct.toFixed(1)),
      activeWfKey,
      activeStagePct: Math.round(activeStagePct),
      streamChunks,
    };
  }, [busy, jobStatus, nowTick]);
}

function formatEventLine(ev, t) {
  const rich = formatRichTerminalEvent(ev, t);
  return {
    ts: rich.ts,
    stageLabel: rich.stageGroup,
    text: rich.text,
    isError: rich.isError,
    isWarn: rich.isWarn,
  };
}

export function SafeJobConsole({ events = [], status, defaultOpen = false, compact = false }) {
  const { t } = usePrefs();
  const [open, setOpen] = useState(defaultOpen);
  const [onlyIssues, setOnlyIssues] = useState(false);
  const logRef = useRef(null);

  const busy = Boolean(status?.busy);
  const hasFailed = status?.state === "ERROR" || status?.state === "WAITING_REVIEW";
  const safeMsg = safeMessageText(status?.message);

  useEffect(() => {
    if (busy || hasFailed) setOpen(true);
  }, [busy, hasFailed]);

  const formatted = useMemo(() => {
    const base = (events || []).map((ev) => formatEventLine(ev, t));
    if (status?.state === "ERROR" && safeMsg) {
      if (!base.some((b) => b.text.includes(safeMsg))) {
        base.push({
          ts: (status.ended || status.started || "").slice(11, 19) || "—",
          stageLabel: "FEHLER",
          text: safeMsg,
          isError: true,
          isWarn: false,
        });
      }
    }
    return onlyIssues ? base.filter((b) => b.isError || b.isWarn) : base;
  }, [events, onlyIssues, status, safeMsg, t]);

  const issueCount = useMemo(
    () =>
      (events || [])
        .map((ev) => formatEventLine(ev, t))
        .filter((b) => b.isError || b.isWarn).length +
      (status?.state === "ERROR" ? 1 : 0),
    [events, status?.state, t]
  );

  useEffect(() => {
    if (open && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [formatted.length, open]);

  const copyLog = async () => {
    const txt = formatted.map((l) => `[${l.ts}] [${l.stageLabel}] ${l.text}`).join("\n");
    try {
      await navigator.clipboard.writeText(txt || safeMsg || "");
      toast.success(t("Protokoll in Zwischenablage kopiert", "Safe console log copied"));
    } catch {
      toast.error(t("Kopieren nicht verfügbar", "Clipboard unavailable"));
    }
  };

  return (
    <div className="lx-console-panel">
      <div className="lx-console-bar">
        <button
          type="button"
          className="lx-btn-ghost"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 7,
            border: "none",
            padding: "2px 4px",
            borderRadius: 5,
            cursor: "pointer",
            fontWeight: 600,
            fontSize: "11.5px",
          }}
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
        >
          <Terminal size={13} className="lx-icon-muted" />
          <span>{t("Echtzeit-Laufkonsole", "Live Safe Job Console")}</span>
          <span className="lx-mono-tag tabular">{(events || []).length}</span>
          {issueCount > 0 && (
            <span className="lx-badge lx-tag-warn tabular">
              <AlertTriangle size={11} />
              <span>
                {issueCount} {t("Hinweise/Fehler", "warnings/errors")}
              </span>
            </span>
          )}
          {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>

        <div className="lx-row-gap">
          <InfoPopover
            title={t("Sicheres Auftragsprotokoll", "Safe Execution Protocol")}
            align="end"
          >
            <p>
              {t(
                "Zeigt Konvertierungs-, Modell- und Quellenprüfungsereignisse in Echtzeit. Roh-Prompts, Dokumentvolltexte und API-Schlüssel bleiben gemäß Datenschutz-Grundsatz außerhalb der sichtbaren Konsole.",
                "Streams real-time conversion, model, and grounding events. Raw prompts, full document text, and API secrets are never exposed in the visible console."
              )}
            </p>
          </InfoPopover>
          {open && (
            <>
              <div className="lx-segmented">
                <button
                  type="button"
                  className={`lx-seg-btn${!onlyIssues ? " is-active" : ""}`}
                  onClick={() => setOnlyIssues(false)}
                >
                  {t("Alle", "All")}
                </button>
                <button
                  type="button"
                  className={`lx-seg-btn${onlyIssues ? " is-active" : ""}`}
                  onClick={() => setOnlyIssues(true)}
                >
                  {t("Fehler/Warn.", "Issues")}
                </button>
              </div>
              {!compact && formatted.length > 0 && (
                <button
                  type="button"
                  className="lx-btn lx-btn-xs lx-btn-ghost"
                  onClick={copyLog}
                  title={t("Protokoll kopieren", "Copy safe log")}
                >
                  <Copy size={11} />
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {open && (
        <div
          ref={logRef}
          className="lx-console-log"
          style={compact ? { maxHeight: 165 } : undefined}
          role="log"
          aria-live="polite"
        >
          {formatted.length === 0 ? (
            <div className="lx-muted" style={{ padding: "6px 4px" }}>
              {onlyIssues
                ? t("Keine Warnungen oder Fehler im letzten Lauf.", "No warnings or errors recorded.")
                : safeMsg
                ? `[${(status?.ended || status?.started || "").slice(11, 19) || "READY"}] ${safeMsg}`
                : t(
                    "Bereit — sobald ein Konvertierungs- oder Modellauftrag startet, erscheinen hier Live-Statusmeldungen.",
                    "Idle — live stage telemetry and error diagnostics appear here as soon as a job starts."
                  )}
            </div>
          ) : (
            formatted.map((line, idx) => (
              <div
                key={idx}
                className={`lx-console-line${
                  line.isError ? " is-error" : line.isWarn ? " is-warn" : ""
                }`}
              >
                <span className="lx-console-ts tabular">{line.ts}</span>
                <span className="lx-console-stage truncate">{line.stageLabel}</span>
                <span style={{ overflowWrap: "anywhere" }}>{line.text}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export function PipelineFlowConsole({ stages, jobStatus, workspace, onOpenTerminal }) {
  const { t } = usePrefs();
  const busy = Boolean(jobStatus?.busy);
  const wf = busy ? jobStatus?.workflow || null : null;
  const safeMsg = safeMessageText(jobStatus?.message);
  const fluid = useFluidRuntimeProgress(jobStatus);
  const lastEvent = useMemo(() => {
    const evs = jobStatus?.events || [];
    return evs.length ? evs[evs.length - 1] : jobStatus?.last_event || null;
  }, [jobStatus?.events, jobStatus?.last_event]);

  const stageStates = useMemo(() => {
    const docs = workspace?.files || [];
    const convertedDocs = docs.filter(
      (b) => b.file?.status === "success" || b.file?.status === "partial_success"
    ).length;
    const enrichedDocs = docs.filter((b) =>
      (b.summary?.pictures || []).some((p) => p.description_status === "ENRICHED" || p.chart)
    ).length;
    const totalPics = docs.reduce((acc, b) => acc + (b.summary?.pictures?.length || 0), 0);
    const describedPics = docs.reduce(
      (acc, b) =>
        acc +
        (b.summary?.pictures || []).filter((p) => p.description_status === "ENRICHED").length,
      0
    );
    const obsCount = workspace?.result?.observations?.length || 0;
    const relCount = (workspace?.result?.objects || []).filter((o) => o.kind === "relation").length;
    const findCount = (workspace?.result?.objects || []).filter((o) => o.kind === "finding").length;

    return stages.map((st) => {
      const wfStep = wf?.[st.wfKey] || null;
      const raw = wfStep?.status || "idle";
      const isRunning = busy && (raw === "running" || jobStatus?.action === `analysis_${st.key}`);
      const isDoneFromWf = ["success", "UNREVIEWED", "NO_PROPOSALS"].includes(raw);
      const isError = raw === "ERROR" || raw === "failure";

      let fallbackPct = 0;
      let metricLabel = "";
      if (st.key === "convert") {
        fallbackPct = docs.length ? Math.round((convertedDocs / docs.length) * 100) : 0;
        metricLabel = docs.length
          ? `${convertedDocs}/${docs.length} ${t("konvertiert", "converted")}`
          : "";
      } else if (st.key === "enrich") {
        const pics = wfStep?.pictures || totalPics;
        const desc = wfStep?.described ?? describedPics;
        fallbackPct = isDoneFromWf
          ? 100
          : totalPics > 0
          ? Math.round((desc / totalPics) * 100)
          : enrichedDocs > 0
          ? 100
          : 0;
        metricLabel =
          pics > 0
            ? `${desc}/${pics} ${t("Bilder beschrieben", "images described")}`
            : t("Keine Bilder / Optional", "No images / Optional");
      } else if (st.key === "A") {
        const withA = (workspace?.result?.documents || []).filter((d) => d.selected_run).length;
        fallbackPct = docs.length ? Math.round((withA / docs.length) * 100) : 0;
        metricLabel =
          obsCount > 0
            ? `${obsCount} ${t("Beobachtungen", "obs.")} (${withA}/${docs.length} Dok.)`
            : t("Noch kein A-Lauf", "Not extracted yet");
      } else if (st.key === "B") {
        fallbackPct = workspace?.runs?.B ? 100 : 0;
        metricLabel =
          relCount > 0
            ? `${relCount} ${t("Relationen", "relations")} · B #${workspace?.runs?.B || ""}`
            : workspace?.runs?.B
            ? `B #${workspace.runs.B} (0 Relationen)`
            : t("Noch kein B-Lauf für Auswahl", "No B run for current scope");
      } else if (st.key === "C") {
        fallbackPct = workspace?.runs?.C ? 100 : 0;
        metricLabel =
          findCount > 0
            ? `${findCount} Findings · C #${workspace?.runs?.C || ""}`
            : workspace?.runs?.C
            ? `C #${workspace.runs.C} (0 Findings)`
            : t("Noch kein C-Lauf für Auswahl", "No C run for current scope");
      }

      if (isRunning && wfStep?.event?.document_name) {
        metricLabel = `▶ ${wfStep.event.document_name}${
          wfStep.event.completed_pages && wfStep.event.total_pages
            ? ` (${wfStep.event.completed_pages}/${wfStep.event.total_pages})`
            : ""
        }`;
      }

      let pct = fallbackPct;
      if (isRunning && fluid.activeWfKey === st.wfKey) {
        pct = fluid.activeStagePct;
      } else if (wfStep && wfStep.total > 0) {
        pct = Math.round(((wfStep.completed || 0) / wfStep.total) * 100);
      } else if (isDoneFromWf) {
        pct = 100;
      } else if (isRunning) {
        pct = Math.max(fluid.activeStagePct || 15, fallbackPct);
      }

      const isDone = !isRunning && !isError && (isDoneFromWf || pct === 100);
      const tone = isRunning
        ? "active"
        : isError
        ? "danger"
        : isDone
        ? "success"
        : "neutral";

      return {
        ...st,
        isRunning,
        isDone,
        isError,
        pct,
        tone,
        metricLabel,
      };
    });
  }, [stages, wf, busy, jobStatus?.action, workspace, fluid, t]);

  const completedStages = stageStates.filter((s) => s.isDone).length;
  const idleRailPct =
    completedStages === 0
      ? 0
      : completedStages >= 5
      ? 100
      : Math.min(100, Math.max(4, Math.round(((completedStages - 0.5) / 4) * 100)));
  const railFillPct = busy ? fluid.overallPct : idleRailPct;
  const runtimeBarPct = busy
    ? fluid.overallPct
    : completedStages > 0
    ? Math.round((completedStages / 5) * 100)
    : 0;

  return (
    <section
      className="lx-flow-shell"
      aria-label={t("Pipeline-Status & Konsole", "Pipeline Status & Console")}
    >
      {/* Top Fluid Status Banner */}
      <div className="lx-flow-top">
        <div className="lx-row-gap min-w-0">
          <Activity size={15} style={{ color: "var(--dot-active)", flexShrink: 0 }} />
          <strong className="lx-text-sm truncate">
            {busy
              ? safeMsg || t("Pipeline wird ausgeführt …", "Pipeline executing…")
              : jobStatus?.state === "ERROR"
              ? `${t("Letzter Auftrag mit Fehler", "Last job reported an error")}: ${safeMsg}`
              : t("Mehrstufiger Synthese-Fluss", "Multi-Stage Synthesis Flow")}
          </strong>
          <InfoPopover title={t("Wie arbeitet die ABC-Pipeline?", "How does the ABC Pipeline work?")}>
            <p>
              <strong>01 Docling:</strong>{" "}
              {t(
                "Zerlegt PDF, Office, Tabellen und Transkripte lokal in adressierbare Strukturblöcke & Koordinaten.",
                "Locally parses PDF, Office, tables, and transcripts into addressable blocks & coordinates."
              )}
            </p>
            <p>
              <strong>02 Vision:</strong>{" "}
              {t(
                "Klassifiziert Abbildungen/Folien lokal und erzeugt optional Bildbeschreibungen.",
                "Classifies figures/slides locally and optionally generates VLM image descriptions."
              )}
            </p>
            <p>
              <strong>03–05 (A → B → C):</strong>{" "}
              {t(
                "Extrahiert zuerst wörtlich belegte Einzelbeobachtungen (A), verknüpft sie dokumentübergreifend (B) und verdichtet sie zu prüfbaren UX-Findings (C).",
                "Extracts verbatim-grounded observations (A), links them across documents (B), and synthesizes auditable UX Findings (C)."
              )}
            </p>
          </InfoPopover>
        </div>

        <div className="lx-row-wrap">
          {lastEvent?.document_name && (
            <span className="lx-cap-pill truncate" style={{ maxWidth: 220 }} title={lastEvent.document_name}>
              {busy ? "▶ " : "Letztes Dok.: "}
              {lastEvent.document_name}
            </span>
          )}
          {lastEvent?.total_tokens > 0 && (
            <span className="lx-cap-pill tabular">
              {Number(lastEvent.total_tokens).toLocaleString()} Tok.
            </span>
          )}
          <span className="lx-mono-tag tabular">
            {completedStages}/5 {t("Stufen bereit", "stages ready")}
          </span>
        </div>
      </div>

      {/* Fluid Second-by-Second Runtime Progress Bar */}
      <div
        className={`lx-fluid-runtime-wrap${busy ? " is-busy" : ""}${
          jobStatus?.state === "ERROR" ? " is-error" : ""
        }`}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(runtimeBarPct)}
        aria-label={t("Laufzeitfortschritt der Pipeline", "Pipeline runtime progress")}
      >
        <div className="lx-fluid-runtime-meta">
          <span className="lx-fluid-runtime-label truncate">
            {busy
              ? `${t("Laufzeitfortschritt", "Live Runtime")}: ${fluid.elapsed}${
                  fluid.streamChunks > 0 ? ` · ${fluid.streamChunks} Stream-Chunks` : ""
                }`
              : jobStatus?.started
              ? `${t("Letzte Laufzeit", "Last Runtime")}: ${fluid.elapsed}`
              : t("Bereitschaftsfortschritt", "Readiness")}
          </span>
          <strong className="lx-fluid-runtime-pct tabular">
            {busy ? `${runtimeBarPct.toFixed(1)} %` : `${Math.round(runtimeBarPct)} %`}
          </strong>
        </div>
        <div className="lx-fluid-runtime-track">
          <div
            className="lx-fluid-runtime-fill"
            style={{ width: `${runtimeBarPct}%` }}
          />
        </div>
      </div>

      {/* Crisp Perfectly Circular HTML/CSS Stepper Track (Never Squished!) */}
      <div className="lx-stepper-wrap" aria-hidden="true">
        <div className="lx-stepper-track">
          <div className="lx-stepper-rail">
            <div
              className="lx-stepper-rail-fill"
              style={{ width: `${railFillPct}%` }}
            />
            {busy && <div className="lx-stepper-rail-pulse" />}
          </div>
          {stageStates.map((s) => (
            <div key={s.key} className="lx-stepper-cell">
              <div
                className={`lx-stepper-orb${s.isDone ? " is-done" : ""}${
                  s.isRunning ? " is-running" : ""
                }${s.isError ? " is-error" : ""}`}
              >
                {s.isDone ? <Check size={14} strokeWidth={2.5} /> : s.isError ? "!" : s.step}
              </div>
              <span className="lx-stepper-caption">{s.title.split("·").pop().trim()}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 5 Stage Cards */}
      <div className="lx-flow-grid">
        {stageStates.map((st) => (
          <div
            key={st.key}
            data-stage={st.key}
            className={`lx-flow-node${st.isRunning ? " is-running" : ""}${
              st.isDone ? " is-done" : ""
            }`}
          >
            <div className="lx-between">
              <div className="lx-row-gap">
                <StatusDot tone={st.tone} pulse={st.isRunning} />
                <span className="lx-stage-num tabular">{st.step}</span>
                {st.infoBody && <InfoPopover title={st.title}>{st.infoBody}</InfoPopover>}
              </div>
              <button
                type="button"
                className="lx-btn lx-btn-xs"
                disabled={busy}
                onClick={st.onRun}
              >
                {st.actionLabel}
              </button>
            </div>
            <strong className="lx-stage-title truncate">{st.title}</strong>
            <span className="lx-stage-model truncate" title={st.sub}>
              {st.sub}
            </span>
            <div className="lx-flow-node-bar" aria-hidden="true">
              <span style={{ width: `${st.pct}%` }} />
            </div>
            {st.metricLabel && (
              <span className="lx-muted lx-text-xs tabular truncate" title={st.metricLabel}>
                {st.metricLabel}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Compact 1-Line Live Status Strip + Direct Terminal Link (`US-51`: zero duplicate console clutter) */}
      <div className="lx-compact-terminal-strip">
        <div className="lx-row-gap min-w-0">
          <Terminal size={13} className="lx-icon-muted" />
          <span className="lx-text-xs truncate">
            {busy
              ? `${t("Aktiv", "Active")}: ${safeMsg || t("Pipeline arbeitet …", "Pipeline running…")}`
              : safeMsg
              ? `${t("Letzter Status", "Last status")}: ${safeMsg}`
              : t(
                  "Bereit · Vollständige Auftrags- & Stufenprotokolle im Terminal-Verlauf.",
                  "Ready · Complete chronological stage logs available in Terminal & Ledger."
                )}
          </span>
        </div>
        {onOpenTerminal && (
          <button type="button" className="lx-btn lx-btn-xs" onClick={onOpenTerminal}>
            <Terminal size={12} />
            <span>{t("Terminal & Verlauf öffnen (6)", "Open Terminal & Ledger (6)")}</span>
          </button>
        )}
      </div>
    </section>
  );
}
