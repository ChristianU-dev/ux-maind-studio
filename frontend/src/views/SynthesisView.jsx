import React, { useCallback, useEffect, useMemo, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import {
  ArrowRight,
  BarChart3,
  Coins,
  Download,
  FileText,
  FolderDown,
  GitBranch,
  History,
  Printer,
  Search,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { usePrefs, statusInfo } from "../lib/i18n.jsx";
import { api } from "../lib/api.js";
import {
  EpistemicFlagsRow,
  InfoPopover,
  Modal,
  ResearcherReviewBlock,
  Select,
  StatusBadge,
  StatusDot,
  Switch,
  latestHumanDecision,
} from "../components/ui.jsx";
import { EvidenceCard, isOpenEvidence, observationKey } from "../components/EvidenceCard.jsx";
import { StudyAnalyticsView } from "../components/StudyAnalyticsView.jsx";

function valenceLabel(v, t) {
  const map = {
    problem: t("Nutzungsproblem", "Usability Problem"),
    negative: t("Negativ / Hürde", "Negative / Friction"),
    strength: t("Stärke / Positiv", "Strength / Positive"),
    positive: t("Positiv", "Positive"),
    mixed: t("Ambivalent / Gemischt", "Mixed / Ambivalent"),
    neutral: t("Neutral / Kontext", "Neutral / Context"),
  };
  return map[String(v || "").toLowerCase()] || v || "";
}

function valenceTone(v) {
  const k = String(v || "").toLowerCase();
  if (k === "problem" || k === "negative") return "danger";
  if (k === "strength" || k === "positive") return "success";
  if (k === "mixed") return "warning";
  return "neutral";
}

function reviewGroupOf(item) {
  if (item.object) {
    const r = item.object.review;
    if (r === "HUMAN_CONFIRMED" || r === "HUMAN_CORRECTED") return "confirmed";
    if (r === "HUMAN_REJECTED") return "rejected";
    return "unreviewed";
  }
  const dec = latestHumanDecision(item.entry?.decisions || []);
  if (dec?.action === "confirmed" || dec?.action === "corrected") return "confirmed";
  if (dec?.action === "rejected") return "rejected";
  return "unreviewed";
}

function buildActionableDiagnostics(kind, record, graphNode, t) {
  const hints = [];
  let hasWarning = false;

  if (kind === "observation") {
    const resolved = record?.source_check?.status === "SOURCE_RESOLVED";
    if (!resolved) {
      hasWarning = true;
      hints.push(
        t(
          "Offene Fundstelle: Das Zitat konnte nicht eindeutig einer einzigen Stelle zugeordnet werden. Wähle unten per 1-Klick eine passende Kandidatenstelle aus oder prüfe das Original im Quelleninspektor.",
          "Unresolved anchor: Quote could not be bound to a single unique span. Pick one of the candidate anchors below in 1 click or inspect the original."
        )
      );
    }
    const openMeas = (record?.measurements || []).filter((m) => !m.sources?.length);
    if (openMeas.length > 0) {
      hasWarning = true;
      hints.push(
        t(
          `${openMeas.length} sekundäre Messstelle(n) ohne exakten Zellen-/Textanker (${openMeas
            .map((m) => m.raw_value)
            .join(", ")}). Prüfe die Tabellenspalte oder korrigiere das Statement.`,
          `${openMeas.length} secondary measurement(s) lack an exact cell/text anchor. Check the table column or refine the statement.`
        )
      );
    }
    const unknownScale = (record?.measurements || []).find(
      (m) =>
        m.numeric_value != null &&
        (!m.scale_direction || m.scale_direction === "unknown") &&
        (m.measurement_kind == null || m.measurement_kind === "rating_scale")
    );
    if (unknownScale) {
      hasWarning = true;
      hints.push(
        t(
          `Skalenpolung für Wert „${unknownScale.raw_value}“ im Dokumenttext nicht explizit belegt (z. B. 1=positiv vs. 7=positiv). Vor Valenzschlüssen Fragebogenkopf im Original prüfen.`,
          `Scale polarity for "${unknownScale.raw_value}" is not explicitly anchored in source text. Verify questionnaire scale labels in Original before interpreting valence.`
        )
      );
    }
    if (record?.effective?.negated_or_struck) {
      hasWarning = true;
      hints.push(
        t(
          "Durchstreichung / Negation erkannt: Stelle sicher, dass eine gestrichene Option nicht als gültige Aussage gewertet wird.",
          "Strikethrough / negation detected: Verify a crossed-out option is not treated as an active statement."
        )
      );
    }
    if (!hints.length) {
      hints.push(
        t(
          "Wörtlicher Originalanker technisch verifiziert. Prüfe kurz Sprecherrolle und Kontext und klicke auf ‚Bestätigen‘ oder ‚Korrigieren‘.",
          "Verbatim source anchor verified. Review speaker attribution and click 'Confirm' or 'Correct'."
        )
      );
    }
    return { hints, hasWarning };
  }

  const p = record?.effective || {};
  const flags = graphNode?.epistemic_flags || [];
  const indep = graphNode?.independence || {};

  if (flags.includes("contains_rejected_support")) {
    hasWarning = true;
    hints.push(
      t(
        "Mindestens ein Stützbeleg dieses Vorschlags wurde als Beobachtung verworfen! Löse den Beleg über ‚Korrigieren‘ / im Wissensgraphen oder verwirf das Finding.",
        "At least one supporting observation of this proposal was rejected! Unlink it or reject the Finding."
      )
    );
  }
  if (flags.includes("unanchored_scale_direction")) {
    hasWarning = true;
    hints.push(
      t(
        "Unbelegte Skalenrichtung in mindestens einem Stützbeleg: Prüfe, ob Zahlenwerte im Fragebogen hoch=gut oder niedrig=gut bedeuten, und passe ggf. Valenz über ‚Korrigieren‘ an.",
        "Unanchored rating scale polarity in supporting evidence: Check questionnaire polarity and adjust Valence via 'Correct' if needed."
      )
    );
  }
  if (flags.includes("contains_negated_or_struck")) {
    hasWarning = true;
    hints.push(
      t(
        "Mindestens ein Beleg enthält eine Durchstreichung oder explizite Verneinung — prüfe im Original, ob die Aussage verworfen wurde.",
        "Supporting evidence includes a strikethrough or explicit negation — inspect the original slide/page."
      )
    );
  }
  if (flags.includes("unresolved_context_reference")) {
    hasWarning = true;
    hints.push(
      t(
        "Offener Rück-/Vorwärtsverweis (z. B. ‚wie oben‘): Prüfe im Quelleninspektor den umgebenden Absatzkontext.",
        "Unresolved backward/forward cue (e.g. 'same as above'): Check surrounding context in Source Inspector."
      )
    );
  }
  if (indep.dependent_visual_overlap) {
    hints.push(
      t(
        `Überlappender Folienbeleg erkannt: ${indep.effective_independent_supports} von ${indep.raw_supports} Belegen sind effektiv unabhängig (Text + Folienrender derselben Seite zählen nicht doppelt).`,
        `Overlapping slide render accounted for: ${indep.effective_independent_supports} of ${indep.raw_supports} supports are effectively independent.`
      )
    );
  }
  if (kind === "finding" && indep.independent_documents === 1 && !(p.opposes || []).length) {
    hints.push(
      t(
        "Einzelquellen-Befund (nur 1 Dokument): Achte über ‚Korrigieren‘ darauf, dass der Geltungsbereich (Scope) eng auf diese Sitzung/Person begrenzt bleibt.",
        "Single-document finding: Ensure Scope remains bounded to this specific participant/artifact via 'Correct'."
      )
    );
  }
  if (record?.review === "UNREVIEWED") {
    hints.push(
      t(
        "Prüfschritt für Übergabe-Handout: Zitate unten per Klick im Original gegenprüfen, dann ‚Bestätigen‘, über ‚Korrigieren‘ präzisieren oder ‚Verwerfen‘ (verworfene Vorschläge werden aus dem aktiven Handout gefiltert).",
        "Handout review step: Verify quotes in Original below, then 'Confirm', refine via 'Correct', or 'Reject' (rejected proposals are filtered out of active handouts)."
      )
    );
  }
  return { hints, hasWarning };
}

export function SynthesisView({
  scopeIds,
  workspace,
  loadingWorkspace,
  activeTab,
  onTabChange,
  selectedProposal,
  onSelectProposal,
  onlyOpenEvidence,
  onOnlyOpenEvidenceChange,
  filters = null,
  onChangeFilters = null,
  onChangeResultRuns,
  onRestoreHistoricalRun,
  onRefreshWorkspace,
  onShowSource,
  onFocusInGraph,
  onNavigate,
}) {
  const { lang, t } = usePrefs();
  const [localSearch, setLocalSearch] = useState("");
  const [localReviewFilter, setLocalReviewFilter] = useState("*");
  const [localValenceFilter, setLocalValenceFilter] = useState("*");
  const search = filters ? filters.search ?? "" : localSearch;
  const reviewFilter = filters ? filters.reviewFilter ?? "*" : localReviewFilter;
  const valenceFilter = filters ? filters.valenceFilter ?? "*" : localValenceFilter;
  const setSearch = useCallback(
    (v) => {
      if (onChangeFilters) {
        onChangeFilters((prev) => ({
          ...prev,
          search: typeof v === "function" ? v(prev.search ?? "") : v,
        }));
      } else {
        setLocalSearch(v);
      }
    },
    [onChangeFilters]
  );
  const setReviewFilter = useCallback(
    (v) => {
      if (onChangeFilters) {
        onChangeFilters((prev) => ({
          ...prev,
          reviewFilter: typeof v === "function" ? v(prev.reviewFilter ?? "*") : v,
        }));
      } else {
        setLocalReviewFilter(v);
      }
    },
    [onChangeFilters]
  );
  const setValenceFilter = useCallback(
    (v) => {
      if (onChangeFilters) {
        onChangeFilters((prev) => ({
          ...prev,
          valenceFilter: typeof v === "function" ? v(prev.valenceFilter ?? "*") : v,
        }));
      } else {
        setLocalValenceFilter(v);
      }
    },
    [onChangeFilters]
  );
  const [runPickerOpen, setRunPickerOpen] = useState(false);
  const [extraObs, setExtraObs] = useState({});
  const [inspectedRunReceipt, setInspectedRunReceipt] = useState(null);
  const [fullHistoryStages, setFullHistoryStages] = useState(null);
  const [savedExports, setSavedExports] = useState({ output: "", items: [] });

  const loadSavedExports = async () => {
    try {
      const res = await api("exports-list");
      setSavedExports(res || { output: "", items: [] });
    } catch {
      setSavedExports({ output: "", items: [] });
    }
  };

  useEffect(() => {
    if (activeTab !== "history") return;
    loadSavedExports();
    if (!workspace?.documents?.length) return;
    const params = new URLSearchParams({
      documents: JSON.stringify(workspace.documents),
      basis: JSON.stringify(workspace.basis || {}),
      history: "1",
    });
    api(`ux-graph?${params.toString()}&result_runs=${encodeURIComponent("{}")}`)
      .then((res) => setFullHistoryStages(res?.analysis?.stages || null))
      .catch(() => setFullHistoryStages(null));
  }, [activeTab, workspace?.documents, workspace?.basis]);

  const data = workspace?.result;
  const runs = workspace?.runs || { B: null, C: null };

  const obsMap = useMemo(() => {
    const m = new Map();
    for (const e of data?.observations || []) {
      m.set(observationKey(e.ref), e);
    }
    for (const [k, v] of Object.entries(extraObs)) {
      if (v) m.set(k, v);
    }
    return m;
  }, [data, extraObs]);

  const items = useMemo(() => {
    if (!data) return [];
    if (activeTab === "observations") {
      return (data.observations || []).map((e) => ({
        id: observationKey(e.ref),
        title: e.effective?.statement || t("Beobachtung", "Observation"),
        subtitle: `${e.name} · A #${e.ref.run}/${e.ref.observation}`,
        entry: e,
        valence: "",
      }));
    }
    if (activeTab === "relations" || activeTab === "findings") {
      const targetKind = activeTab === "relations" ? "relation" : "finding";
      return (data.objects || [])
        .filter((o) => o.kind === targetKind)
        .map((o) => {
          const p = o.effective || {};
          const srcStmt = obsMap.get(observationKey(p.source))?.effective?.statement || "…";
          const tgtStmt = obsMap.get(observationKey(p.target))?.effective?.statement || "…";
          const title =
            targetKind === "relation"
              ? `${srcStmt} → ${tgtStmt}`
              : p.title || p.kind || t("Finding-Vorschlag", "Finding Candidate");
          const supCount = (p.supports || []).length;
          const oppCount = (p.opposes || []).length;
          const subtitle =
            targetKind === "relation"
              ? `B #${o.id} · ${(p.kind || "relation").replaceAll("_", " ")}`
              : [
                  `C #${o.id}`,
                  p.valence ? valenceLabel(p.valence, t) : null,
                  `${supCount} ${t("Belege", "supports")}`,
                  oppCount > 0 ? `${oppCount} ${t("Gegenbelege", "counter")}` : null,
                ]
                  .filter(Boolean)
                  .join(" · ");
          return {
            id: String(o.id),
            title: String(title),
            subtitle,
            object: o,
            valence: String(p.valence || "").toLowerCase(),
          };
        });
    }
    return [];
  }, [data, activeTab, obsMap, t]);

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((item) => {
      if (reviewFilter !== "*" && reviewGroupOf(item) !== reviewFilter) return false;
      if (activeTab === "findings" && valenceFilter !== "*" && item.valence !== valenceFilter) {
        return false;
      }
      if (activeTab === "observations" && onlyOpenEvidence && !isOpenEvidence(item.entry)) {
        return false;
      }
      if (!q) return true;
      const hay = [
        item.title,
        item.subtitle,
        item.entry?.raw?.quote,
        item.object?.effective?.rationale,
        item.object?.effective?.observed_effect,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [items, search, reviewFilter, valenceFilter, activeTab, onlyOpenEvidence]);

  const activeItem = useMemo(() => {
    if (!filteredItems.length) return null;
    const targetId = selectedProposal?.[activeTab];
    return filteredItems.find((i) => i.id === targetId) || filteredItems[0];
  }, [filteredItems, selectedProposal, activeTab]);

  // Fetch any missing observation referenced by a finding or relation
  useEffect(() => {
    if (!activeItem?.object || !scopeIds.length) return;
    const p = activeItem.object.effective || {};
    const refs =
      activeItem.object.kind === "relation"
        ? [p.source, p.target]
        : [
            ...(p.supports || []),
            ...(p.opposes || []),
            ...(p.qualifies || []),
            ...(p.improvement_evidence || []),
          ];
    for (const ref of refs) {
      if (!ref || !scopeIds.includes(ref.document)) continue;
      const k = observationKey(ref);
      if (!obsMap.has(k) && !(k in extraObs)) {
        const params = new URLSearchParams({
          documents: JSON.stringify(scopeIds),
          ref: JSON.stringify(ref),
        });
        api(`ux-observation?${params}`)
          .then((res) => setExtraObs((prev) => ({ ...prev, [k]: res })))
          .catch(() => setExtraObs((prev) => ({ ...prev, [k]: null })));
      }
    }
  }, [activeItem, scopeIds]);

  const valences = useMemo(() => {
    const s = new Set(items.map((i) => i.valence).filter(Boolean));
    return [
      ["*", t("Alle Valenzen", "All Valences")],
      ...[...s].sort().map((v) => [v, valenceLabel(v, t)]),
    ];
  }, [items, t]);

  const exportParams = useMemo(() => {
    if (!workspace) return "";
    const p = new URLSearchParams({
      documents: JSON.stringify(workspace.documents || []),
      basis: JSON.stringify(workspace.basis || {}),
      result_runs: JSON.stringify(workspace.runs || {}),
    });
    return p.toString();
  }, [workspace]);

  const saveExportToOutput = async (kind = "report") => {
    try {
      const res = await api("save-export", {
        kind,
        documents: workspace?.documents || [],
        basis: workspace?.basis || {},
        result_runs: workspace?.runs || {},
        lang,
      });
      toast.success(
        res?.path
          ? `${t("Gespeichert unter", "Saved to")} ${res.path}`
          : t("Im Ausgabeordner abgelegt", "Saved to output folder")
      );
      if (activeTab === "history") loadSavedExports();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const inspectRunReceipt = async (runId) => {
    try {
      const receipt = await api(`ux-run?id=${runId}`);
      setInspectedRunReceipt(receipt);
    } catch (err) {
      toast.error(err.message);
    }
  };

  if (scopeIds.length === 0) {
    return (
      <div className="lx-page">
        <div className="lx-empty-state">
          <Sparkles size={28} strokeWidth={1.5} className="lx-icon-muted" />
          <h2>{t("Keine Studienauswahl aktiv", "No Study Scope Active")}</h2>
          <p>
            {t(
              "Wähle im Studienkorpus Dokumente aus, um synthetisierte Findings, Beziehungen und Originalzitate zu prüfen.",
              "Select documents in the Study Corpus to inspect synthesized findings, relations, and verbatim quotes."
            )}
          </p>
          <button type="button" className="lx-btn lx-btn-primary" onClick={() => onNavigate("documents")}>
            <span>{t("Zum Studienkorpus", "Go to Study Corpus")}</span>
            <ArrowRight size={14} />
          </button>
        </div>
      </div>
    );
  }

  const stages = data?.analysis?.stages || { B: [], C: [], legacy: [] };
  const findingsCount = (data?.objects || []).filter((o) => o.kind === "finding").length;
  const relationsCount = (data?.objects || []).filter((o) => o.kind === "relation").length;
  const obsCount = (data?.observations || []).length;

  return (
    <div className="lx-page lx-page-fill">
      {/* Compact Synthesis Header & Active Run Strip */}
      <header className="lx-page-header lx-header-compact">
        <div className="min-w-0">
          <div className="lx-row-gap">
            <h1 className="lx-page-title">{t("Synthese & Findings", "Synthesis & Findings")}</h1>
            <span className="lx-mono-tag tabular">
              {runs.C ? `C #${runs.C}` : t("Kein C-Stand", "No C Run")} ·{" "}
              {runs.B ? `B #${runs.B}` : t("Direktbasis A", "Direct A")}
            </span>
          </div>
        </div>
        <div className="lx-btn-row">
          <button type="button" className="lx-btn lx-btn-sm" onClick={() => setRunPickerOpen(true)}>
            <SlidersHorizontal size={13} />
            <span>{t("Laufstand", "Run Version")}</span>
          </button>
          {exportParams && (
            <>
              <a
                className="lx-btn lx-btn-sm lx-btn-primary"
                href={`/api/ux-handout?${exportParams}&lang=${lang}`}
                target="_blank"
                rel="noreferrer"
                title={t("Druckbares A4-Studien-Handout öffnen", "Open printable A4 Study Handout")}
              >
                <Printer size={13} />
                <span>{t("Handout (A4)", "Handout (A4)")}</span>
              </a>
              <button
                type="button"
                className="lx-btn lx-btn-sm"
                onClick={() => saveExportToOutput("handout")}
                title={t("Druckbares Handout im Ausgabeordner ablegen", "Archive HTML Handout in output folder")}
              >
                <FolderDown size={13} />
                <span>{t("Handout ablegen", "Save Handout")}</span>
              </button>
              <a
                className="lx-btn lx-btn-sm"
                href={`/api/ux-report?${exportParams}&lang=${lang}`}
                target="_blank"
                rel="noreferrer"
              >
                <FileText size={13} />
                <span>{t("Bericht (.md)", "Report (.md)")}</span>
              </a>
              <button
                type="button"
                className="lx-btn lx-btn-sm lx-btn-ghost"
                onClick={() => saveExportToOutput("report")}
                title={t("Markdown-Bericht im Ausgabeordner ablegen", "Save Markdown report to output folder")}
              >
                <FolderDown size={13} />
                <span>{t("MD ablegen", "Save MD")}</span>
              </button>
              <a
                className="lx-btn lx-btn-sm lx-btn-ghost"
                href={`/api/ux-export?${exportParams}`}
                target="_blank"
                rel="noreferrer"
              >
                <Download size={13} />
                <span>JSON</span>
              </a>
              <InfoPopover
                title={t("Handout, Bericht & Ablage", "Handout, Report & Archiving")}
                align="end"
              >
                <p>
                  <strong>Handout (A4):</strong>{" "}
                  {t(
                    "Öffnet eine druckoptimierte Übersicht aller Findings inklusive Originalzitaten, Quellenankern und Studien-Kennzahlen (Strg+P für PDF/Druck). Mit ‚Handout ablegen‘ wird es direkt in deinem Export-Ordner archiviert.",
                    "Opens a print-ready A4 summary of all Findings with verbatim quotes, anchors, and study KPIs (Ctrl+P to print/PDF). 'Save Handout' archives it directly to your output folder."
                  )}
                </p>
              </InfoPopover>
            </>
          )}
        </div>
      </header>

      <Tabs.Root value={activeTab} onValueChange={onTabChange} className="lx-tabs-fill">
        <Tabs.List className="lx-tabs-list" aria-label={t("Synthese-Ebenen", "Synthesis Layers")}>
          <Tabs.Trigger value="findings" className="lx-tab-trigger">
            <span>{t("Findings C", "Findings C")}</span>
            <span className="lx-tab-count tabular">{findingsCount}</span>
          </Tabs.Trigger>
          <Tabs.Trigger value="observations" className="lx-tab-trigger">
            <span>{t("Beobachtungen A", "Observations A")}</span>
            <span className="lx-tab-count tabular">{obsCount}</span>
          </Tabs.Trigger>
          <Tabs.Trigger value="relations" className="lx-tab-trigger">
            <span>{t("Beziehungen B", "Relations B")}</span>
            <span className="lx-tab-count tabular">{relationsCount}</span>
          </Tabs.Trigger>
          <Tabs.Trigger value="charts" className="lx-tab-trigger">
            <BarChart3 size={13} />
            <span>{t("Diagramme & Abdeckung", "Charts & Coverage")}</span>
          </Tabs.Trigger>
          <Tabs.Trigger value="telemetry" className="lx-tab-trigger">
            <Coins size={13} />
            <span>{t("Token & Kosten", "Tokens & Cost")}</span>
          </Tabs.Trigger>
          <Tabs.Trigger value="history" className="lx-tab-trigger">
            <History size={13} />
            <span>{t("Laufprotokolle & Ablage", "Runs & Saved Reports")}</span>
          </Tabs.Trigger>
        </Tabs.List>

        {/* Master-Detail Workbench for Findings / Observations / Relations */}
        {activeTab === "charts" || activeTab === "telemetry" ? (
          <StudyAnalyticsView
            mode={activeTab}
            workspace={workspace}
            onJumpToFinding={(findingId) => {
              onSelectProposal("findings", String(findingId));
              onTabChange("findings");
            }}
          />
        ) : activeTab !== "history" ? (
          <div className="lx-workbench">
            {/* Left Master List */}
            <aside className="lx-master-pane">
              <div className="lx-master-controls">
                <div className="lx-search-wrap">
                  <Search size={13} className="lx-search-icon" />
                  <input
                    type="search"
                    className="lx-input lx-input-sm lx-search-input"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder={t("Einträge durchsuchen …", "Search entries…")}
                  />
                </div>

                <div className="lx-segmented">
                  {[
                    ["*", t("Alle", "All")],
                    ["unreviewed", t("Offen", "Open")],
                    ["confirmed", t("Bestätigt", "Confirmed")],
                    ["rejected", t("Verworfen", "Rejected")],
                  ].map(([val, lbl]) => (
                    <button
                      key={val}
                      type="button"
                      className={`lx-seg-btn${reviewFilter === val ? " is-active" : ""}`}
                      onClick={() => setReviewFilter(val)}
                    >
                      {lbl}
                    </button>
                  ))}
                </div>

                {activeTab === "findings" && valences.length > 2 && (
                  <Select
                    size="sm"
                    value={valenceFilter}
                    onValueChange={setValenceFilter}
                    options={valences}
                  />
                )}

                {activeTab === "observations" && (
                  <label className="lx-inline-switch lx-text-xs">
                    <Switch
                      checked={onlyOpenEvidence}
                      onCheckedChange={onOnlyOpenEvidenceChange}
                    />
                    <span>{t("Nur offene Quellen / Messstellen", "Only open anchors / metrics")}</span>
                  </label>
                )}

                <div className="lx-muted lx-text-xs tabular">
                  {filteredItems.length} / {items.length} {t("Einträge", "entries")}
                </div>
              </div>

              <div className="lx-master-list">
                {loadingWorkspace && !items.length ? (
                  <div className="lx-pane-placeholder">{t("Lade Synthese …", "Loading synthesis…")}</div>
                ) : filteredItems.length === 0 ? (
                  <div className="lx-pane-placeholder">
                    {t("Keine Einträge für diesen Filter.", "No entries match current filter.")}
                  </div>
                ) : (
                  filteredItems.map((it) => {
                    const isActive = activeItem?.id === it.id;
                    const rg = reviewGroupOf(it);
                    const dotTone =
                      rg === "confirmed"
                        ? "success"
                        : rg === "rejected"
                        ? "danger"
                        : it.valence
                        ? valenceTone(it.valence)
                        : "warning";

                    return (
                      <button
                        key={it.id}
                        type="button"
                        className={`lx-master-item${isActive ? " is-active" : ""}`}
                        onClick={() => onSelectProposal(activeTab, it.id)}
                      >
                        <div className="lx-master-item-top">
                          <StatusDot tone={dotTone} />
                          <span className="lx-master-item-title">{it.title}</span>
                        </div>
                        <span className="lx-master-item-sub truncate">{it.subtitle}</span>
                      </button>
                    );
                  })
                )}
              </div>
            </aside>

            {/* Right Editorial Detail Pane */}
            <article className="lx-detail-pane">
              {!activeItem ? (
                <div className="lx-pane-placeholder">
                  {items.length === 0
                    ? t(
                        "Für diesen Umfang liegt noch kein Lauf auf dieser Stufe vor. Starte die Pipeline unter Analyse.",
                        "No stage output exists yet for this scope. Run the pipeline in Analysis."
                      )
                    : t("Eintrag links auswählen.", "Select an item on the left.")}
                </div>
              ) : activeItem.entry ? (
                /* Observation Detail */
                <div className="lx-detail-stack">
                  <div className="lx-detail-header">
                    <div className="min-w-0">
                      <div className="lx-eyebrow tabular">
                        {activeItem.entry.name} · A #{activeItem.entry.ref.run} /{" "}
                        {activeItem.entry.ref.observation}
                      </div>
                      <h2 className="lx-detail-title">{activeItem.title}</h2>
                    </div>
                    <button
                      type="button"
                      className="lx-btn lx-btn-sm"
                      onClick={() => onFocusInGraph("observation", activeItem.entry.ref)}
                    >
                      <GitBranch size={13} />
                      <span>{t("Im Graphen zeigen", "Show in Graph")}</span>
                    </button>
                  </div>

                  <EpistemicFlagsRow record={activeItem.entry} />

                  {(() => {
                    const diag = buildActionableDiagnostics(
                      "observation",
                      activeItem.entry,
                      null,
                      t
                    );
                    return diag.hints.length > 0 ? (
                      <div className={`lx-review-guide${diag.hasWarning ? " is-warn" : ""}`}>
                        <strong className="lx-text-xs">
                          {t(
                            "Prüf- & Korrekturleitfaden für diese Beobachtung",
                            "Actionable Review Guide for this Observation"
                          )}
                        </strong>
                        <ul className="lx-review-guide-list">
                          {diag.hints.map((h, i) => (
                            <li key={i}>{h}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null;
                  })()}

                  <ResearcherReviewBlock
                    targetType="observation"
                    target={activeItem.entry.ref}
                    decisions={activeItem.entry.decisions}
                    currentEffective={activeItem.entry.effective}
                    apiCall={api}
                    onSaved={() => {
                      toast.success(t("Forschungsentscheidung gespeichert", "Review decision saved"));
                      return onRefreshWorkspace();
                    }}
                  />

                  {(() => {
                    const c = activeItem.entry.effective?.context || {};
                    const ctxParts = [
                      c.actor_or_speaker,
                      c.role,
                      c.task_or_goal,
                      c.condition_or_time,
                    ].filter(Boolean);
                    return ctxParts.length ? (
                      <div className="lx-prose-card">
                        <h3 className="lx-eyebrow">{t("Erhebungskontext", "Study Context")}</h3>
                        <p className="lx-text-sm">{ctxParts.join(" · ")}</p>
                      </div>
                    ) : null;
                  })()}

                  <div className="lx-section-block">
                    <h3 className="lx-eyebrow">{t("Originalbeleg & Anker", "Verbatim Source Anchor")}</h3>
                    <EvidenceCard
                      entry={activeItem.entry}
                      onShowSource={onShowSource}
                      onAnchorConfirmed={onRefreshWorkspace}
                    />
                  </div>
                </div>
              ) : (
                /* Finding or Relation Detail */
                (() => {
                  const obj = activeItem.object;
                  const p = obj.effective || {};
                  const graphNode = (data?.graph?.nodes || []).find(
                    (n) =>
                      (obj.kind === "finding" &&
                        n.__class__ === "FindingNode" &&
                        n.record_id === obj.id) ||
                      (obj.kind === "relation" &&
                        n.__class__ === "RelationNode" &&
                        String(n.record_id) === String(obj.id))
                  );

                  const roleMap = new Map();
                  const endpoints =
                    obj.kind === "relation"
                      ? [
                          [p.source, t("Ausgangsbeleg", "Source Anchor")],
                          [p.target, t("Zielbeleg", "Target Anchor")],
                        ]
                      : [
                          ...(p.supports || []).map((r) => [r, t("Stützbeleg", "Supporting")]),
                          ...(p.opposes || []).map((r) => [r, t("Gegenbeleg", "Counterevidence")]),
                          ...(p.qualifies || []).map((r) => [r, t("Einschränkend", "Qualifying")]),
                          ...(p.improvement_evidence || []).map((r) => [
                            r,
                            t("Verbesserungshinweis", "Improvement Cue"),
                          ]),
                        ];
                  for (const [ref, roleLabel] of endpoints) {
                    if (!ref) continue;
                    const k = observationKey(ref);
                    if (!roleMap.has(k)) roleMap.set(k, { ref, roles: [] });
                    if (!roleMap.get(k).roles.includes(roleLabel)) {
                      roleMap.get(k).roles.push(roleLabel);
                    }
                  }
                  const uniqueDocCount = new Set(
                    [...roleMap.values()].map((x) => x.ref.document)
                  ).size;

                  return (
                    <div className="lx-detail-stack">
                      <div className="lx-detail-header">
                        <div className="min-w-0">
                          <div className="lx-eyebrow tabular">
                            {[
                              `${obj.kind === "finding" ? "C" : "B"} #${obj.id}`,
                              obj.metadata?.model,
                              p.finding_type,
                              p.valence ? valenceLabel(p.valence, t) : null,
                              p.usability_heuristic ? `UX: ${p.usability_heuristic}` : null,
                              p.scope,
                              graphNode?.independence?.distinct_speakers > 0
                                ? `${graphNode.independence.distinct_speakers} ${t("Sprecher", "speakers")}`
                                : null,
                            ]
                              .filter(Boolean)
                              .join(" · ")}
                          </div>
                          <h2 className="lx-detail-title">{activeItem.title}</h2>
                        </div>
                        <button
                          type="button"
                          className="lx-btn lx-btn-sm"
                          onClick={() => onFocusInGraph(obj.kind, obj.id)}
                        >
                          <GitBranch size={13} />
                          <span>{t("Im Graphen zeigen", "Show in Graph")}</span>
                        </button>
                      </div>

                      <EpistemicFlagsRow
                        record={{
                          ...obj,
                          epistemic_flags: graphNode?.epistemic_flags || [],
                          independence: graphNode?.independence,
                        }}
                      />

                      {(() => {
                        const diag = buildActionableDiagnostics(
                          obj.kind,
                          obj,
                          graphNode,
                          t
                        );
                        return diag.hints.length > 0 ? (
                          <div className={`lx-review-guide${diag.hasWarning ? " is-warn" : ""}`}>
                            <strong className="lx-text-xs">
                              {t(
                                "Prüf- & Verbesserungsleitfaden",
                                "Actionable Review & Refinement Guide"
                              )}
                            </strong>
                            <ul className="lx-review-guide-list">
                              {diag.hints.map((h, i) => (
                                <li key={i}>{h}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null;
                      })()}

                      <ResearcherReviewBlock
                        targetType={obj.kind}
                        target={obj.id}
                        decisions={obj.decisions}
                        currentEffective={p}
                        apiCall={api}
                        onSaved={() => {
                          toast.success(
                            t("Forschungsentscheidung gespeichert", "Review decision saved")
                          );
                          return onRefreshWorkspace();
                        }}
                      />

                      {obj.kind === "finding" && Array.isArray(p.relations) && p.relations.length > 0 && (
                        <div className="lx-row-wrap">
                          <span className="lx-muted lx-text-xs">
                            {t("Verknüpfte B-Relationen:", "Linked Stage B Relations:")}
                          </span>
                          {p.relations.map((relId) => (
                            <button
                              key={relId}
                              type="button"
                              className="lx-btn lx-btn-xs"
                              onClick={() => {
                                onSelectProposal("relations", String(relId));
                                onTabChange("relations");
                              }}
                            >
                              <span>B #{relId}</span>
                              <ArrowRight size={11} />
                            </button>
                          ))}
                        </div>
                      )}

                      {/* Structured analytical synthesis */}
                      <div className="lx-prose-card">
                        {obj.kind === "relation" && (
                          <p className="lx-text-xs lx-muted" style={{ marginBottom: 8 }}>
                            {[
                              `${t("Relationstyp", "Relation Kind")}: ${(p.kind || "—").replaceAll("_", " ")}`,
                              p.situation && `${t("Situation", "Situation")}: ${p.situation}`,
                              p.inference_basis && `${t("Basis", "Basis")}: ${p.inference_basis}`,
                            ]
                              .filter(Boolean)
                              .join(" · ")}
                          </p>
                        )}
                        {p.statement && <p className="lx-prose-lead">{p.statement}</p>}
                        <div className="lx-prose-section">
                          <h4>{t("Synthese & Begründung", "Synthesis & Rationale")}</h4>
                          <p>{p.rationale || t("Keine Begründung hinterlegt.", "No rationale stored.")}</p>
                        </div>
                        {p.observed_effect && (
                          <div className="lx-prose-section">
                            <h4>{t("Beobachtete Auswirkung", "Observed User Effect")}</h4>
                            <p>{p.observed_effect}</p>
                          </div>
                        )}
                        {p.improvement_hypothesis && (
                          <div className="lx-prose-section">
                            <h4>
                              {t(
                                "Gestaltungshypothese (ungeprüft)",
                                "Design Hypothesis (Unverified)"
                              )}
                            </h4>
                            <p>{p.improvement_hypothesis}</p>
                          </div>
                        )}
                        <div className="lx-prose-uncertainty">
                          <strong>{t("Epistemische Unsicherheit", "Epistemic Uncertainty")}:</strong>{" "}
                          {p.uncertainty || t("Nicht gesondert ausgewiesen", "None explicitly noted")}
                        </div>
                      </div>

                      {/* Grounded Verbatim Evidence List */}
                      <div className="lx-section-block">
                        <h3 className="lx-eyebrow">
                          {t("Verankerte Originalbelege", "Anchored Verbatim Evidence")} (
                          {roleMap.size} {t("Beobachtungen", "observations")} · {uniqueDocCount}{" "}
                          {uniqueDocCount === 1 ? t("Dokument", "document") : t("Dokumente", "documents")}
                          )
                        </h3>
                        <div className="lx-evidence-stack">
                          {[...roleMap.values()].map(({ ref, roles }) => {
                            const entry = obsMap.get(observationKey(ref));
                            if (!entry) {
                              return (
                                <div key={observationKey(ref)} className="lx-card lx-card-subtle">
                                  <span className="lx-muted lx-text-xs">
                                    {t("Lade Belegreferenz", "Resolving anchor")} {observationKey(ref)} …
                                  </span>
                                </div>
                              );
                            }
                            return (
                              <EvidenceCard
                                key={observationKey(ref)}
                                entry={entry}
                                roles={roles}
                                onShowSource={(oRef, anc) =>
                                  onShowSource(oRef, anc, {
                                    kind: obj.kind,
                                    id: obj.id,
                                    title: activeItem.title,
                                    anchors: [...roleMap.values()].map(({ ref: rItem, roles: rList }) => {
                                      const eItem = obsMap.get(observationKey(rItem));
                                      return {
                                        ref: rItem,
                                        role: rList[0] || "",
                                        docName: eItem?.name || `Dok #${rItem.document}`,
                                        match: eItem?.source_check?.matches?.[0] || null,
                                        statement: eItem?.effective?.statement || "",
                                      };
                                    }),
                                  })
                                }
                                onAnchorConfirmed={onRefreshWorkspace}
                              />
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  );
                })()
              )}
            </article>
          </div>
        ) : (
          /* Run Ledger / History Tab */
          <div className="lx-history-pane">
            <div className="lx-grid-2">
              {["C", "B"].map((st) => (
                <section key={st} className="lx-table-card">
                  <header className="lx-card-header">
                    <div>
                      <h2 className="lx-card-title">
                        {st === "C"
                          ? t("Stufe C · Finding-Läufe", "Stage C · Finding Runs")
                          : t("Stufe B · Beziehungs-Läufe", "Stage B · Relation Runs")}
                      </h2>
                    </div>
                  </header>
                  <div className="lx-table-scroll">
                    <table className="lx-table">
                      <thead>
                        <tr>
                          <th>{t("Lauf", "Run")}</th>
                          <th>{t("Modell", "Model")}</th>
                          <th>{t("Status", "Status")}</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {((fullHistoryStages || stages)[st] || []).length === 0 ? (
                          <tr>
                            <td colSpan={4} className="lx-table-empty">
                              {t("Keine Läufe gespeichert.", "No runs recorded.")}
                            </td>
                          </tr>
                        ) : (
                          ((fullHistoryStages || stages)[st] || []).map((r) => (
                            <tr key={r.id}>
                              <td className="tabular">
                                <strong>#{r.id}</strong>
                                {(r.at || r.created_at) && (
                                  <div className="lx-muted lx-text-xs">
                                    {(r.at || r.created_at).slice(0, 16).replace("T", " ")}
                                  </div>
                                )}
                              </td>
                              <td className="truncate" style={{ maxWidth: 200 }}>
                                {r.model || "—"}
                              </td>
                              <td>
                                <StatusBadge status={r.result_status || r.status} />
                              </td>
                              <td className="lx-cell-right">
                                <div className="lx-btn-row">
                                  {r.result_status !== "ERROR" && (
                                    <button
                                      type="button"
                                      className="lx-btn lx-btn-xs"
                                      onClick={() => onRestoreHistoricalRun?.(st, r)}
                                    >
                                      {t("Öffnen", "Restore")}
                                    </button>
                                  )}
                                  <button
                                    type="button"
                                    className="lx-btn lx-btn-xs lx-btn-ghost"
                                    onClick={() => inspectRunReceipt(r.id)}
                                  >
                                    {t("Beleg", "Receipt")}
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>
              ))}
            </div>

            {/* Stage A & Vision Runs Across Active Scope */}
            <section className="lx-table-card" style={{ marginTop: 14 }}>
              <header className="lx-card-header">
                <div>
                  <h2 className="lx-card-title">
                    {t(
                      "Stufe A & Vision · Dokument-Läufe im Studienumfang",
                      "Stage A & Vision · Document Runs in Study Scope"
                    )}
                  </h2>
                  <p className="lx-card-sub">
                    {t(
                      "Revisionsechte Extraktions- und Bildbeschreibungs-Läufe pro Primärdokument.",
                      "Immutable extraction and image-description runs per primary document."
                    )}
                  </p>
                </div>
              </header>
              <div className="lx-table-scroll">
                <table className="lx-table">
                  <thead>
                    <tr>
                      <th style={{ width: 110 }}>{t("Stufe / Lauf", "Stage / Run")}</th>
                      <th>{t("Dokument", "Document")}</th>
                      <th>{t("Modell", "Model")}</th>
                      <th style={{ width: 150 }}>{t("Ergebnis / Verankerung", "Yield / Grounding")}</th>
                      <th style={{ width: 140 }}>{t("Status", "Status")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(() => {
                      const docRunRows = [];
                      for (const fb of workspace?.files || []) {
                        const docName = fb?.file?.name || `#${fb?.file?.id}`;
                        for (const v of fb?.summary?.versions || []) {
                          if (v.version && v.version !== fb?.summary?.base_version) {
                            docRunRows.push({
                              key: `vis-${fb.file.id}-${v.version}`,
                              badge: `Vision · ${v.version.slice(0, 8)}`,
                              docId: fb.file.id,
                              docName,
                              model: v.configuration?.model || "Vision",
                              yieldText: `${v.described_pictures ?? "—"} ${t("Bilder", "images")}`,
                              status: "FINISHED",
                              at: v.created_at || "",
                            });
                          }
                        }
                        for (const r of fb?.runs || []) {
                          const obsTotal = r.result?.observations?.length || 0;
                          docRunRows.push({
                            key: `a-${fb.file.id}-${r.id}`,
                            badge: `A #${r.id}`,
                            docId: fb.file.id,
                            docName,
                            model: r.result?.model || r.model || "—",
                            yieldText: `${obsTotal} ${t("Beobachtungen", "obs.")}`,
                            status: r.result?.status || r.status || "FINISHED",
                            at: r.created_at || r.at || "",
                          });
                        }
                      }
                      if (!docRunRows.length) {
                        return (
                          <tr>
                            <td colSpan={5} className="lx-table-empty">
                              {t(
                                "Noch keine Stufe-A- oder Vision-Läufe im aktuellen Umfang.",
                                "No Stage A or Vision runs recorded in current scope."
                              )}
                            </td>
                          </tr>
                        );
                      }
                      return docRunRows.map((dr) => (
                        <tr key={dr.key}>
                          <td className="tabular">
                            <strong>{dr.badge}</strong>
                            {dr.at && (
                              <div className="lx-muted lx-text-xs">
                                {String(dr.at).slice(0, 16).replace("T", " ")}
                              </div>
                            )}
                          </td>
                          <td className="truncate">{dr.docName}</td>
                          <td className="truncate">{dr.model}</td>
                          <td className="tabular">{dr.yieldText}</td>
                          <td>
                            <StatusBadge status={dr.status} />
                          </td>
                        </tr>
                      ));
                    })()}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Saved Exports & Printable Handouts Browser inside App */}
            <section className="lx-table-card" style={{ marginTop: 14 }}>
              <header className="lx-card-header">
                <div className="min-w-0">
                  <h2 className="lx-card-title">
                    {t(
                      "Abgelegte Übergabe-Handouts & Studienberichte",
                      "Saved Study Handouts & Exported Reports"
                    )}
                  </h2>
                  <p className="lx-card-sub truncate" title={savedExports.output}>
                    {savedExports.output || t("Standard-Ausgabeordner", "Default output directory")}
                  </p>
                </div>
                <div className="lx-btn-row">
                  <button
                    type="button"
                    className="lx-btn lx-btn-xs lx-btn-primary"
                    onClick={() => saveExportToOutput("handout")}
                  >
                    <Printer size={12} />
                    <span>{t("Aktuelles Handout ablegen", "Archive Current Handout")}</span>
                  </button>
                  <button
                    type="button"
                    className="lx-btn lx-btn-xs"
                    onClick={() => saveExportToOutput("report")}
                  >
                    <FileText size={12} />
                    <span>{t("Aktuellen Bericht (.md) ablegen", "Archive Report (.md)")}</span>
                  </button>
                </div>
              </header>
              <div className="lx-table-scroll">
                <table className="lx-table">
                  <thead>
                    <tr>
                      <th>{t("Datei", "File")}</th>
                      <th style={{ width: 150 }}>{t("Zeitpunkt", "Saved At")}</th>
                      <th style={{ width: 100 }}>{t("Größe", "Size")}</th>
                      <th style={{ width: 180 }} />
                    </tr>
                  </thead>
                  <tbody>
                    {!savedExports.items?.length ? (
                      <tr>
                        <td colSpan={4} className="lx-table-empty">
                          {t(
                            "Noch keine abgelegten Handouts oder Berichte im Ausgabeordner. Klicke oben auf ‚Handout ablegen‘.",
                            "No archived handouts or reports yet. Click 'Save Handout' above to store a snapshot."
                          )}
                        </td>
                      </tr>
                    ) : (
                      savedExports.items.map((ex) => (
                        <tr key={ex.filename}>
                          <td className="truncate" title={ex.path}>
                            <strong>{ex.display_name}</strong>
                            <div className="lx-muted lx-text-xs tabular">{ex.filename}</div>
                          </td>
                          <td className="tabular lx-muted">
                            {(ex.modified_at || "").slice(0, 16).replace("T", " ")}
                          </td>
                          <td className="tabular lx-muted">
                            {(ex.size_bytes / 1024).toFixed(1)} KB
                          </td>
                          <td className="lx-cell-right">
                            <div className="lx-btn-row">
                              {ex.suffix === ".html" && (
                                <a
                                  className="lx-btn lx-btn-xs lx-btn-primary"
                                  href={`/api/export-file?name=${encodeURIComponent(ex.filename)}`}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  <Printer size={11} />
                                  <span>{t("Öffnen / Drucken", "Open / Print")}</span>
                                </a>
                              )}
                              <a
                                className="lx-btn lx-btn-xs"
                                href={`/api/export-file?name=${encodeURIComponent(ex.filename)}&download=1`}
                                target="_blank"
                                rel="noreferrer"
                              >
                                <Download size={11} />
                                <span>{t("Download", "Download")}</span>
                              </a>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}
      </Tabs.Root>

      {/* Run Switcher Modal */}
      <Modal
        open={runPickerOpen}
        onOpenChange={setRunPickerOpen}
        title={t("Gespeicherten B/C-Laufstand wählen", "Select Saved Stage B/C Run")}
        subtitle={t(
          "Historische Syntheseläufe bleiben lesend vergleichbar.",
          "Historical synthesis runs remain inspectable side-by-side."
        )}
      >
        <div className="lx-form-stack">
          <label className="lx-field">
            <span className="lx-field-label">{t("Stufe B (Beziehungen)", "Stage B (Relations)")}</span>
            <Select
              value={String(runs.B ?? "none")}
              onValueChange={(v) =>
                onChangeResultRuns({ ...runs, B: v === "none" ? null : Number(v) })
              }
              options={[
                ["none", t("Ohne B-Lauf (direkt auf A)", "No B run (direct on Stage A)")],
                ...(stages.B || []).map((r) => [
                  String(r.id),
                  `B #${r.id} · ${r.model || ""} (${r.result_status || r.status})`,
                ]),
              ]}
            />
          </label>
          <label className="lx-field">
            <span className="lx-field-label">{t("Stufe C (Findings)", "Stage C (Findings)")}</span>
            <Select
              value={String(runs.C ?? "none")}
              onValueChange={(v) =>
                onChangeResultRuns({ ...runs, C: v === "none" ? null : Number(v) })
              }
              options={[
                ["none", t("Kein C-Lauf ausgewählt", "No C run selected")],
                ...(stages.C || []).map((r) => [
                  String(r.id),
                  `C #${r.id} · ${r.model || ""}${r.b_run ? ` (Basis B #${r.b_run})` : ""}`,
                ]),
              ]}
            />
          </label>
          <div className="lx-modal-actions">
            <button type="button" className="lx-btn lx-btn-primary" onClick={() => setRunPickerOpen(false)}>
              {t("Übernehmen", "Done")}
            </button>
          </div>
        </div>
      </Modal>

      {/* Native Run Receipt Modal */}
      <Modal
        open={Boolean(inspectedRunReceipt)}
        onOpenChange={(v) => !v && setInspectedRunReceipt(null)}
        title={
          inspectedRunReceipt
            ? `${t("Nativer Laufbeleg", "Native Run Receipt")} #${inspectedRunReceipt.id}`
            : ""
        }
        width={680}
      >
        {inspectedRunReceipt && (
          <div className="lx-form-stack">
            <div className="lx-between">
              <span className="lx-muted lx-text-xs tabular">
                {[
                  `Stufe ${inspectedRunReceipt.metadata?.stage || inspectedRunReceipt.stage || "—"}`,
                  inspectedRunReceipt.metadata?.provider,
                  inspectedRunReceipt.metadata?.model || inspectedRunReceipt.model,
                  inspectedRunReceipt.at?.slice(0, 19)?.replace("T", " "),
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
              <a
                className="lx-btn lx-btn-xs"
                href={`/api/ux-run-export?id=${inspectedRunReceipt.id}`}
                target="_blank"
                rel="noreferrer"
              >
                <Download size={12} />
                <span>{t("JSON herunterladen", "Download JSON")}</span>
              </a>
            </div>
            <pre className="lx-code-pre">
              {JSON.stringify(
                inspectedRunReceipt.metadata?.native_graph?.requests ||
                  inspectedRunReceipt.metadata ||
                  inspectedRunReceipt,
                null,
                2
              )}
            </pre>
          </div>
        )}
      </Modal>
    </div>
  );
}
