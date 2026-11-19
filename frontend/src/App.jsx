import React, { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Toaster, toast } from "sonner";
import {
  Cpu,
  FileText,
  FolderOpen,
  GitBranch,
  Layers,
  Moon,
  PanelLeft,
  Plus,
  Search,
  Settings,
  Sparkles,
  Sun,
  Terminal,
  UserCheck,
} from "lucide-react";
import { usePrefs } from "./lib/i18n.jsx";
import { api } from "./lib/api.js";
import { Kbd, Modal, StatusDot } from "./components/ui.jsx";
import { RunMonitor } from "./components/RunMonitor.jsx";
import { CommandPalette } from "./components/CommandPalette.jsx";
import { CorpusView } from "./views/CorpusView.jsx";
import { PipelineView } from "./views/PipelineView.jsx";
import { SynthesisView } from "./views/SynthesisView.jsx";
import { observationKey } from "./components/EvidenceCard.jsx";

const GraphView = lazy(() =>
  import("./views/GraphView.jsx").then((m) => ({ default: m.GraphView }))
);
const InspectorView = lazy(() =>
  import("./views/InspectorView.jsx").then((m) => ({ default: m.InspectorView }))
);
const TerminalView = lazy(() =>
  import("./views/TerminalView.jsx").then((m) => ({ default: m.TerminalView }))
);
const SettingsView = lazy(() =>
  import("./views/SettingsView.jsx").then((m) => ({ default: m.SettingsView }))
);

export function App() {
  const { lang, setLang, theme, toggleTheme, t } = usePrefs();

  // Navigation & global UI state
  const [screen, setScreen] = useState("documents"); // documents | pipeline | results | graph | review | settings
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [cmdkOpen, setCmdkOpen] = useState(false);
  const [runDrawerOpen, setRunDrawerOpen] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [settingsRequestedTab, setSettingsRequestedTab] = useState(null);

  // Corpus state
  const [filesData, setFilesData] = useState({ total: 0, items: [] });
  const [fileSearch, setFileSearch] = useState("");
  const [fileSort, setFileSort] = useState("newest");
  const [fileArchived, setFileArchived] = useState(false);
  const [fileOffset, setFileOffset] = useState(0);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const didAutoSelectRef = useRef(false);

  // Profiles & Workflow settings
  const [profilesData, setProfilesData] = useState({ profiles: [], presets: {}, env_status: {} });
  const [workflowSettings, setWorkflowSettings] = useState(null);

  // Live Job Status
  const [jobStatus, setJobStatus] = useState(null);
  const prevBusyRef = useRef(false);
  const [workflowModalRequest, setWorkflowModalRequest] = useState(null);

  // Research Workspace (A-basis + B/C graph & objects)
  const [evidenceRuns, setEvidenceRuns] = useState({}); // { [docId]: runId }
  const [customResultRuns, setCustomResultRuns] = useState({}); // { [scopeKey]: { B, C } }
  const [workspace, setWorkspace] = useState(null);
  const [loadingWorkspace, setLoadingWorkspace] = useState(false);

  // Synthesis & Graph navigation state
  const [synthesisTab, setSynthesisTab] = useState("findings");
  const [selectedProposal, setSelectedProposal] = useState({});
  const [onlyOpenEvidence, setOnlyOpenEvidence] = useState(false);
  const [graphFocusRequest, setGraphFocusRequest] = useState(null);

  // Inspector (Dual-View) state & back-history
  const [inspectorSelection, setInspectorSelection] = useState({
    document: null,
    version: null,
    page: null,
    ref: null,
    occurrence: null,
    runId: null,
  });
  const [backStack, setBackStack] = useState([]);
  const [synthesisFilters, setSynthesisFilters] = useState({
    search: "",
    reviewFilter: "*",
    valenceFilter: "*",
  });
  const [graphUiState, setGraphUiState] = useState({
    quickMode: "findings",
    search: "",
    docFilter: "all",
    showIsolated: false,
    isolateSubgraph: true,
    selectedNodeId: null,
  });

  // Load files
  const loadFiles = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        offset: String(fileOffset),
        search: fileSearch,
        archived: fileArchived ? "1" : "0",
        sort: fileSort,
      });
      const data = await api(`files?${params}`);
      setFilesData(data);
      if (!didAutoSelectRef.current && !fileArchived && !fileSearch && data.items?.length > 0) {
        didAutoSelectRef.current = true;
        setSelectedIds(
          new Set(
            data.items
              .filter((f) => (f.corpus_role || "evidence") !== "reference")
              .map((f) => f.id)
          )
        );
      }
    } catch (err) {
      toast.error(err.message);
    }
  }, [fileOffset, fileSearch, fileArchived, fileSort]);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  // Load settings & profiles
  const [researcherState, setResearcherState] = useState({
    active: { id: "default", display_name: "Standard-Prüfer", role: "UX-Forscher" },
    profiles: [],
    oidc: { enabled: false },
  });
  const [reviewerModalOpen, setReviewerModalOpen] = useState(false);
  const [newReviewerName, setNewReviewerName] = useState("");
  const [newReviewerRole, setNewReviewerRole] = useState("UX-Forscher");

  const loadSettings = useCallback(async () => {
    try {
      const [prof, wf, rev] = await Promise.all([
        api("profiles"),
        api("workflow-settings"),
        api("researchers").catch(() => null),
      ]);
      setProfilesData(prof);
      setWorkflowSettings(wf);
      if (rev?.active) setResearcherState(rev);
    } catch (err) {
      toast.error(err.message);
    }
  }, []);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  // Compute active study scope
  const scopeIds = useMemo(() => {
    if (selectedIds.size > 0) return [...selectedIds].sort((a, b) => a - b);
    if (inspectorSelection.document) return [inspectorSelection.document];
    return [];
  }, [selectedIds, inspectorSelection.document]);

  // Load research workspace (A-basis + ux-graph) with single-roundtrip bundle + AbortController
  const workspaceAbortRef = useRef(null);
  const loadWorkspace = useCallback(async () => {
    if (workspaceAbortRef.current) {
      workspaceAbortRef.current.abort();
    }
    if (!scopeIds.length) {
      setWorkspace(null);
      return;
    }
    const ctrl = new AbortController();
    workspaceAbortRef.current = ctrl;
    setLoadingWorkspace(true);
    try {
      const bundleQuery = new URLSearchParams({
        documents: JSON.stringify(scopeIds),
      });
      const fileBundles = await api(`workspace-bundle?${bundleQuery.toString()}`, undefined, {
        signal: ctrl.signal,
      });

      const basis = {};
      const scopeIdsArr = scopeIds;
      scopeIdsArr.forEach((id, idx) => {
        const chosen = Number(evidenceRuns[id] || 0);
        const candidates = (fileBundles[idx]?.runs || []).filter(
          (r) => !r.historical && r.result?.observations?.length
        );
        if (chosen && candidates.some((r) => r.id === chosen)) {
          basis[id] = chosen;
        } else if (candidates.length) {
          basis[id] = candidates[0].id;
        }
      });

      const scopeKey = JSON.stringify([scopeIds, basis]);
      const baseQuery = new URLSearchParams({
        documents: JSON.stringify(scopeIds),
        basis: JSON.stringify(basis),
      });

      const initialResult = await api(
        `ux-graph?${baseQuery.toString()}&result_runs=${encodeURIComponent("{}")}`,
        undefined,
        { signal: ctrl.signal }
      );

      const stages = initialResult?.analysis?.stages || { B: [], C: [], legacy: [] };
      const compatible = (r) => r.status !== "STALE" && r.result_status !== "ERROR";
      const newestB = stages.B.find(compatible);
      const newestC = stages.C.find(compatible);
      const legacy = stages.legacy.find(compatible);
      const chosenC =
        newestC && (!newestB || newestC.id > newestB.id || newestC.b_run === newestB.id)
          ? newestC
          : null;

      const defaultRuns = {
        B: chosenC ? chosenC.b_run ?? null : newestB?.id ?? legacy?.id ?? null,
        C: chosenC?.id ?? (!newestB ? legacy?.id : null) ?? null,
      };
      const activeRuns = customResultRuns[scopeKey] || defaultRuns;

      const finalResult =
        activeRuns.B != null || activeRuns.C != null
          ? await api(
              `ux-graph?${baseQuery.toString()}&result_runs=${encodeURIComponent(
                JSON.stringify(activeRuns)
              )}`,
              undefined,
              { signal: ctrl.signal }
            )
          : initialResult;

      if (ctrl.signal.aborted) return;
      setWorkspace({
        documents: scopeIds,
        files: fileBundles,
        basis,
        scopeKey,
        runs: activeRuns,
        result: finalResult,
      });
    } catch (err) {
      if (err?.name !== "AbortError") {
        toast.error(err.message);
      }
    } finally {
      if (workspaceAbortRef.current === ctrl) {
        setLoadingWorkspace(false);
      }
    }
  }, [scopeIds, evidenceRuns, customResultRuns]);

  useEffect(() => {
    loadWorkspace();
  }, [loadWorkspace]);

  // Poll /api/status reactively
  const pollStatus = useCallback(async () => {
    try {
      const st = await api("status");
      setJobStatus(st);
      const wasBusy = prevBusyRef.current;
      prevBusyRef.current = Boolean(st?.busy);

      if (wasBusy && !st?.busy) {
        if (st?.state === "WAITING_REVIEW") {
          toast.warning(
            t(
              "Pipeline pausiert: Offene Quellenstellen zur Prüfung bereit",
              "Pipeline paused: Open source anchors ready for review"
            )
          );
          setRunDrawerOpen(true);
        } else if (st?.state === "ERROR") {
          toast.error(st?.message || t("Auftrag mit Fehler beendet", "Job ended with error"));
        } else {
          toast.success(t("Analyse-Auftrag abgeschlossen", "Pipeline job completed"));
        }
        loadFiles();
        loadWorkspace();
      }
      return st;
    } catch {
      return null;
    }
  }, [loadFiles, loadWorkspace, t]);

  useEffect(() => {
    pollStatus();
  }, []);

  useEffect(() => {
    if (!jobStatus?.busy) return;
    const id = setInterval(pollStatus, 1400);
    return () => clearInterval(id);
  }, [jobStatus?.busy, pollStatus]);

  // Keyboard shortcuts 1..6 when not typing in an input
  useEffect(() => {
    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = document.activeElement?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || document.activeElement?.isContentEditable) {
        return;
      }
      const map = {
        "1": "documents",
        "2": "pipeline",
        "3": "results",
        "4": "graph",
        "5": "review",
        "6": "terminal",
        "7": "settings",
      };
      if (map[e.key]) {
        setScreen(map[e.key]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Handlers
  const handleOpenDocument = useCallback((doc) => {
    setInspectorSelection({
      document: doc.id,
      version: null,
      page: null,
      ref: null,
      occurrence: null,
      runId: null,
    });
    setScreen("review");
  }, []);

  const handleOpenDocumentById = useCallback((id) => {
    setInspectorSelection({
      document: Number(id),
      version: null,
      page: null,
      ref: null,
      occurrence: null,
      runId: null,
    });
    setScreen("review");
  }, []);

  const handleShowSource = useCallback(
    async (obsRef, anchor, findingContext = null) => {
      if (!obsRef?.document) return;
      setBackStack((prev) => [...prev.slice(-9), { screen, inspectorSelection }]);
      let targetVersion = obsRef.version || null;
      try {
        if (!targetVersion && obsRef.run) {
          const runs = await api(`results?id=${obsRef.document}`);
          targetVersion = runs.find((r) => r.id === obsRef.run)?.result?.document_version || null;
        }
      } catch {}
      const uniquePages = [
        ...new Set((anchor?.prov || []).map((p) => p?.page_no).filter((p) => p != null)),
      ];
      const page = uniquePages.length === 1 ? uniquePages[0] : null;
      setInspectorSelection({
        document: obsRef.document,
        version: targetVersion,
        page,
        ref: anchor?.ref || null,
        occurrence: anchor || null,
        runId: obsRef.run || null,
        findingContext: findingContext || null,
      });
      setScreen("review");
    },
    [screen, inspectorSelection]
  );

  const handleGoBack = useCallback(() => {
    setBackStack((prev) => {
      if (!prev.length) return prev;
      const last = prev[prev.length - 1];
      setInspectorSelection(last.inspectorSelection);
      setScreen(last.screen);
      return prev.slice(0, -1);
    });
  }, []);

  const activeStageAModel = useMemo(() => {
    const aName = workflowSettings?.profiles?.A;
    const found = profilesData?.profiles?.find((p) => p.name === aName);
    return found?.options?.model || t("Modell wählen", "Assign Model");
  }, [workflowSettings, profilesData, t]);

  const findingsTotal = (workspace?.result?.objects || []).filter(
    (o) => o.kind === "finding"
  ).length;

  const navItems = [
    {
      id: "documents",
      icon: FolderOpen,
      label: t("Studienkorpus", "Study Corpus"),
      count: filesData.total || null,
    },
    {
      id: "pipeline",
      icon: Layers,
      label: t("Analyse-Pipeline", "Pipeline"),
      count: scopeIds.length || null,
    },
    {
      id: "results",
      icon: Sparkles,
      label: t("Synthese & Findings", "Synthesis"),
      count: findingsTotal || null,
    },
    {
      id: "graph",
      icon: GitBranch,
      label: t("Wissensgraph", "Evidence Graph"),
      count: workspace?.result?.graph?.nodes?.length || null,
    },
    {
      id: "review",
      icon: FileText,
      label: t("Quelleninspektor", "Source Inspector"),
      count: null,
    },
    {
      id: "terminal",
      icon: Terminal,
      label: t("Terminal & Verlauf", "Terminal & Log"),
      count: jobStatus?.events?.length || null,
    },
    {
      id: "settings",
      icon: Settings,
      label: t("Einstellungen", "Settings"),
      count: null,
    },
  ];

  return (
    <div className={`lx-app-shell${sidebarCollapsed ? " is-sidebar-collapsed" : ""}`}>
      {/* Left Navigation Sidebar */}
      <aside className="lx-sidebar" aria-label={t("Hauptnavigation", "Primary Navigation")}>
        <div className="lx-brand-row">
          <div className="lx-brand-mark" aria-hidden="true">
            <span>UX</span>
          </div>
          {!sidebarCollapsed && (
            <div className="min-w-0">
              <div className="lx-brand-name truncate">UX-mAInd</div>
              <div className="lx-brand-sub truncate">
                {t("Quellengebundene Synthese", "Evidence-Bound Studio")}
              </div>
            </div>
          )}
        </div>

        <nav className="lx-nav-list">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = screen === item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={`lx-nav-item${active ? " is-active" : ""}`}
                onClick={() => setScreen(item.id)}
                title={sidebarCollapsed ? item.label : undefined}
              >
                <Icon size={15} strokeWidth={1.85} className="lx-nav-icon" />
                {!sidebarCollapsed && (
                  <>
                    <span className="lx-nav-label truncate">{item.label}</span>
                    {item.count != null && (
                      <span className="lx-nav-count tabular">{item.count}</span>
                    )}
                  </>
                )}
              </button>
            );
          })}
        </nav>

        {!sidebarCollapsed && (
          <div className="lx-sidebar-footer">
            <div className="lx-scope-box">
              <div className="lx-between">
                <span className="lx-muted lx-text-xs">{t("Studienumfang", "Active Scope")}</span>
                <StatusDot tone={selectedIds.size > 0 ? "success" : "neutral"} />
              </div>
              <strong className="lx-text-xs tabular">
                {selectedIds.size === 0
                  ? t("Keine Auswahl", "None selected")
                  : `${selectedIds.size} ${
                      selectedIds.size === 1 ? t("Datei", "file") : t("Dateien", "files")
                    }`}
              </strong>
              <span className="lx-muted lx-text-xs truncate" title={activeStageAModel}>
                {activeStageAModel}
              </span>
            </div>
          </div>
        )}
      </aside>

      {/* Main Content Area */}
      <div className="lx-main-column">
        {/* Top Chrome Bar */}
        <header className="lx-topbar">
          <div className="lx-topbar-left min-w-0">
            <button
              type="button"
              className="lx-icon-btn"
              onClick={() => setSidebarCollapsed((c) => !c)}
              aria-label={t("Seitenleiste umschalten", "Toggle sidebar")}
            >
              <PanelLeft size={15} />
            </button>

            <button
              type="button"
              className="lx-cmdk-trigger"
              onClick={() => setCmdkOpen(true)}
            >
              <Search size={13} className="lx-icon-muted" />
              <span className="truncate">
                {t("Suchen oder springen …", "Search or jump…")}
              </span>
              <Kbd>Ctrl K</Kbd>
            </button>
          </div>

          <div className="lx-topbar-right">
            <button
              type="button"
              className="lx-top-chip"
              onClick={() => setReviewerModalOpen(true)}
              title={t("Aktives Prüfer-Profil für Revisionsprotokoll", "Active Researcher Profile for Audit Log")}
            >
              <UserCheck size={13} className="lx-icon-muted" />
              <span className="truncate" style={{ maxWidth: 120 }}>
                {researcherState?.active?.display_name || t("Prüfer", "Reviewer")}
              </span>
            </button>

            <button
              type="button"
              className="lx-top-chip"
              onClick={() => setScreen("settings")}
              title={t("Aktives Sprachmodell", "Active LLM Profile")}
            >
              <Cpu size={13} className="lx-icon-muted" />
              <span className="truncate" style={{ maxWidth: 165 }}>
                {activeStageAModel}
              </span>
            </button>

            <RunMonitor
              status={jobStatus}
              open={runDrawerOpen}
              onOpenChange={setRunDrawerOpen}
              onNavigate={setScreen}
              onResumeWorkflow={(review) => {
                setScreen("pipeline");
                setWorkflowModalRequest(review);
              }}
              onEndWorkflow={async (resumeToken) => {
                try {
                  await api("workflow-end", { resume: resumeToken });
                  setRunDrawerOpen(false);
                  await pollStatus();
                } catch (err) {
                  toast.error(err.message);
                }
              }}
            />

            <div className="lx-segmented lx-seg-compact" role="group" aria-label="Language">
              <button
                type="button"
                className={`lx-seg-btn${lang === "de" ? " is-active" : ""}`}
                onClick={() => setLang("de")}
              >
                DE
              </button>
              <button
                type="button"
                className={`lx-seg-btn${lang === "en" ? " is-active" : ""}`}
                onClick={() => setLang("en")}
              >
                EN
              </button>
            </div>

            <button
              type="button"
              className="lx-icon-btn"
              onClick={toggleTheme}
              aria-label={t("Erscheinungsbild wechseln", "Toggle color theme")}
              title={theme === "dark" ? "Light Mode" : "Dark Mode"}
            >
              {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
            </button>

            <button
              type="button"
              className="lx-btn lx-btn-sm lx-btn-primary"
              onClick={() => {
                setScreen("documents");
                setImportModalOpen(true);
              }}
            >
              <Plus size={13} />
              <span>{t("Import", "Import")}</span>
            </button>
          </div>
        </header>

        {/* Active View Surface */}
        <main className="lx-viewport">
          <Suspense fallback={<div className="lx-pane-placeholder">Ansicht wird geladen …</div>}>
          {screen === "documents" && (
            <CorpusView
              filesData={filesData}
              search={fileSearch}
              onSearchChange={(v) => {
                setFileOffset(0);
                setFileSearch(v);
              }}
              sort={fileSort}
              onSortChange={setFileSort}
              archived={fileArchived}
              onArchivedChange={(v) => {
                setFileOffset(0);
                setFileArchived(v);
              }}
              offset={fileOffset}
              onOffsetChange={setFileOffset}
              selectedIds={selectedIds}
              onToggleSelect={(id, checked) => {
                setSelectedIds((prev) => {
                  const next = new Set(prev);
                  if (checked) next.add(id);
                  else next.delete(id);
                  return next;
                });
              }}
              onSelectVisible={() => {
                setSelectedIds((prev) => {
                  const next = new Set(prev);
                  for (const it of filesData.items || []) {
                    if ((it.corpus_role || "evidence") !== "reference") {
                      next.add(it.id);
                    }
                  }
                  return next;
                });
              }}
              onClearSelection={() => setSelectedIds(new Set())}
              onOpenDocument={handleOpenDocument}
              onNavigate={setScreen}
              onRefreshFiles={async () => {
                await loadFiles();
                await pollStatus();
              }}
              importModalOpen={importModalOpen}
              onImportModalChange={setImportModalOpen}
            />
          )}

          {screen === "pipeline" && (
            <PipelineView
              scopeIds={scopeIds}
              workspace={workspace}
              loadingWorkspace={loadingWorkspace}
              workflowSettings={workflowSettings}
              profiles={profilesData.profiles || []}
              jobStatus={jobStatus}
              evidenceRuns={evidenceRuns}
              onChangeEvidenceRun={(docId, runId) =>
                setEvidenceRuns((prev) => ({ ...prev, [docId]: runId }))
              }
              onOpenDocumentById={handleOpenDocumentById}
              onNavigate={setScreen}
              onJobStarted={async () => {
                prevBusyRef.current = true;
                setRunDrawerOpen(true);
                await pollStatus();
              }}
              onOpenJumpToOpenEvidence={(obsRef) => {
                setSynthesisTab("observations");
                setOnlyOpenEvidence(true);
                setSelectedProposal((prev) => ({
                  ...prev,
                  observations: observationKey(obsRef),
                }));
                setScreen("results");
              }}
              workflowModalRequest={workflowModalRequest}
              onClearWorkflowModalRequest={() => setWorkflowModalRequest(null)}
            />
          )}

          {screen === "results" && (
            <SynthesisView
              scopeIds={scopeIds}
              workspace={workspace}
              loadingWorkspace={loadingWorkspace}
              activeTab={synthesisTab}
              onTabChange={setSynthesisTab}
              selectedProposal={selectedProposal}
              onSelectProposal={(tab, id) =>
                setSelectedProposal((prev) => ({ ...prev, [tab]: id }))
              }
              onlyOpenEvidence={onlyOpenEvidence}
              onOnlyOpenEvidenceChange={setOnlyOpenEvidence}
              filters={synthesisFilters}
              onChangeFilters={setSynthesisFilters}
              onChangeResultRuns={(nextRuns) => {
                if (!workspace?.scopeKey) return;
                setCustomResultRuns((prev) => ({
                  ...prev,
                  [workspace.scopeKey]: nextRuns,
                }));
              }}
              onRestoreHistoricalRun={(stage, runObj) => {
                const rawBasis = runObj?.basis_by_doc || runObj?.basis || workspace?.basis || {};
                const orderedBasis = {};
                scopeIds.forEach((id) => {
                  const val = rawBasis[id] ?? rawBasis[String(id)] ?? workspace?.basis?.[id];
                  if (val != null) orderedBasis[id] = Number(val);
                });
                if (Object.keys(orderedBasis).length > 0) {
                  setEvidenceRuns((prev) => ({ ...prev, ...orderedBasis }));
                }
                const targetKey = JSON.stringify([scopeIds, orderedBasis]);
                const nextRuns =
                  stage === "C"
                    ? { B: runObj.b_run ?? null, C: runObj.id }
                    : { B: runObj.id, C: null };
                setCustomResultRuns((prev) => ({ ...prev, [targetKey]: nextRuns }));
                setSynthesisTab(stage === "C" ? "findings" : "relations");
              }}
              onRefreshWorkspace={loadWorkspace}
              onShowSource={handleShowSource}
              onFocusInGraph={(kind, target) => {
                setGraphFocusRequest({ kind, target });
                setScreen("graph");
              }}
              onNavigate={setScreen}
            />
          )}

          {screen === "graph" && (
            <GraphView
              workspace={workspace}
              focusRequest={graphFocusRequest}
              onClearFocusRequest={() => setGraphFocusRequest(null)}
              uiState={graphUiState}
              onChangeUiState={setGraphUiState}
              onShowSource={handleShowSource}
              onOpenProposalInSynthesis={(tab, id) => {
                setSynthesisTab(tab);
                setSelectedProposal((prev) => ({ ...prev, [tab]: id }));
                setScreen("results");
              }}
              onRefreshWorkspace={loadWorkspace}
              onNavigate={setScreen}
            />
          )}

          {screen === "review" && (
            <InspectorView
              files={filesData.items || []}
              workspace={workspace}
              selection={inspectorSelection}
              onChangeSelection={setInspectorSelection}
              canGoBack={backStack.length > 0}
              onGoBack={handleGoBack}
              onNavigate={setScreen}
            />
          )}

          {screen === "terminal" && <TerminalView jobStatus={jobStatus} />}

          {screen === "settings" && (
            <SettingsView
              profilesData={profilesData}
              workflowSettings={workflowSettings}
              onReloadSettings={loadSettings}
              requestedTab={settingsRequestedTab}
              onClearRequestedTab={() => setSettingsRequestedTab(null)}
            />
          )}
          </Suspense>
        </main>
      </div>

      {/* Global Command Palette (Ctrl+K / ⌘K) */}
      <CommandPalette
        open={cmdkOpen}
        onOpenChange={setCmdkOpen}
        onNavigate={setScreen}
        onOpenSynthesisTab={(subTab) => {
          setSynthesisTab(subTab);
          setScreen("results");
        }}
        onOpenSettingsTab={(sTab) => {
          setSettingsRequestedTab(sTab);
          setScreen("settings");
        }}
        files={filesData.items || []}
        onOpenDocument={handleOpenDocument}
        onSelectAll={() =>
          setSelectedIds(
            new Set(
              (filesData.items || [])
                .filter((f) => (f.corpus_role || "evidence") !== "reference")
                .map((f) => f.id)
            )
          )
        }
        onClearSelection={() => setSelectedIds(new Set())}
        onOpenImport={() => {
          setScreen("documents");
          setImportModalOpen(true);
        }}
      />

      {/* Researcher Profile & Optional OIDC Switcher Modal (`US-74`) */}
      <Modal
        open={reviewerModalOpen}
        onOpenChange={setReviewerModalOpen}
        title={t("Prüfer-Profil & Revisionsidentität", "Researcher Identity & Audit Profile")}
        subtitle={t(
          "Jede menschliche Prüfentscheidung (Bestätigen, Korrigieren, Verwerfen) protokolliert das aktive Forscher-Profil revisionssicher in ux_decisions.",
          "Every human review decision stamps the active researcher identity into the append-only ux_decisions ledger."
        )}
      >
        <div className="lx-form-stack">
          <div className="lx-card lx-card-subtle">
            <div className="lx-eyebrow" style={{ marginBottom: 6 }}>
              {t("Gespeicherte Prüfer-Profile", "Saved Researcher Profiles")}
            </div>
            <div className="lx-form-stack" style={{ gap: 6 }}>
              {(researcherState?.profiles || []).map((p) => {
                const isAct = researcherState?.active?.id === p.id;
                return (
                  <div key={p.id} className="lx-between">
                    <div className="lx-row-gap min-w-0">
                      <StatusDot tone={isAct ? "success" : "neutral"} />
                      <strong className="lx-text-xs truncate">{p.display_name}</strong>
                      {p.role && <span className="lx-muted lx-text-xs">· {p.role}</span>}
                    </div>
                    <button
                      type="button"
                      className={`lx-btn lx-btn-xs ${isAct ? "lx-btn-primary" : ""}`}
                      disabled={isAct}
                      onClick={async () => {
                        try {
                          const next = await api("researcher-select", { id: p.id });
                          setResearcherState(next);
                          toast.success(`${t("Aktiver Prüfer", "Active reviewer")}: ${p.display_name}`);
                        } catch (err) {
                          toast.error(err.message);
                        }
                      }}
                    >
                      {isAct ? t("Aktiv", "Active") : t("Wechseln", "Switch")}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="lx-grid-2">
            <label className="lx-field">
              <span className="lx-field-label">{t("Neues Prüfer-Profil", "New Reviewer Name")}</span>
              <input
                type="text"
                className="lx-input lx-input-sm"
                placeholder={t("z. B. Chris oder Zweitprüfer B …", "e.g. Chris or Co-Coder B…")}
                value={newReviewerName}
                onChange={(e) => setNewReviewerName(e.target.value)}
              />
            </label>
            <label className="lx-field">
              <span className="lx-field-label">{t("Rolle", "Role")}</span>
              <input
                type="text"
                className="lx-input lx-input-sm"
                value={newReviewerRole}
                onChange={(e) => setNewReviewerRole(e.target.value)}
              />
            </label>
          </div>
          <div className="lx-between">
            <span className="lx-muted lx-text-xs">
              {researcherState?.oidc?.enabled
                ? `${t("Optionales OIDC aktiv", "Optional OIDC enabled")}: ${researcherState.oidc.provider_label}`
                : t(
                    "Lokaler Offline-Modus aktiv (optionales OIDC/Google-OAuth über UX_MAIND_OIDC_CLIENT_ID konfigurierbar).",
                    "Local offline mode active (optional OIDC/Google OAuth available via UX_MAIND_OIDC_CLIENT_ID)."
                  )}
            </span>
            <button
              type="button"
              className="lx-btn lx-btn-sm lx-btn-primary"
              disabled={!newReviewerName.trim()}
              onClick={async () => {
                try {
                  const next = await api("researcher-save", {
                    display_name: newReviewerName.trim(),
                    role: newReviewerRole.trim() || "UX-Forscher",
                  });
                  setResearcherState(next);
                  setNewReviewerName("");
                  toast.success(t("Prüfer-Profil gespeichert & aktiviert", "Reviewer profile saved & activated"));
                } catch (err) {
                  toast.error(err.message);
                }
              }}
            >
              {t("Anlegen & aktivieren", "Create & Activate")}
            </button>
          </div>
        </div>
      </Modal>

      <Toaster
        position="bottom-right"
        theme={theme}
        toastOptions={{
          style: {
            fontFamily: "var(--font-sans)",
            fontSize: "13px",
          },
        }}
      />
    </div>
  );
}
