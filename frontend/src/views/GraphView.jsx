import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import {
  ArrowUpRight,
  Focus,
  LayoutGrid,
  Maximize2,
  Minimize2,
  RotateCcw,
  Search,
  Sparkles,
  Unlink,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { usePrefs } from "../lib/i18n.jsx";
import { api, pictureSourceLabel } from "../lib/api.js";
import { computeWidescreenLayout } from "../lib/graphLayout.js";
import {
  EpistemicFlagsRow,
  InfoPopover,
  ResearcherReviewBlock,
  Select,
  StatusDot,
  Switch,
} from "../components/ui.jsx";
import { EvidenceCard, observationKey } from "../components/EvidenceCard.jsx";

function CustomGraphCard({ data, selected }) {
  const dimmed = data.dimmed && !selected;
  return (
    <div
      className={`lx-rf-card lx-rf-${data.kindClass}${selected ? " is-selected" : ""}${
        dimmed ? " is-dimmed" : ""
      }`}
    >
      <Handle type="target" position={Position.Left} className="lx-rf-handle" />
      <div className="lx-rf-card-head">
        <span className="lx-rf-badge tabular">
          <StatusDot tone={data.tone} />
          <span>{data.eyebrow}</span>
        </span>
        {data.pill && <span className="lx-rf-meta truncate">{data.pill}</span>}
      </div>
      <div className="lx-rf-card-body">{data.title}</div>
      {data.footer && <div className="lx-rf-card-foot truncate">{data.footer}</div>}
      <Handle type="source" position={Position.Right} className="lx-rf-handle" />
    </div>
  );
}

const NODE_TYPES = {
  uxCard: CustomGraphCard,
};

function GraphCanvasInner({
  workspace,
  focusRequest,
  onClearFocusRequest,
  uiState = null,
  onChangeUiState = null,
  onShowSource,
  onOpenProposalInSynthesis,
  onRefreshWorkspace,
  onNavigate,
}) {
  const { theme, t } = usePrefs();
  const rf = useReactFlow();

  const result = workspace?.result;
  const graph = result?.graph || { nodes: [], edges: [] };
  const hasFindings = useMemo(
    () => Boolean(graph.nodes?.some((n) => n.__class__ === "FindingNode")),
    [graph.nodes]
  );

  const [localSearch, setLocalSearch] = useState("");
  const [localQuickMode, setLocalQuickMode] = useState("findings"); // "findings" | "all" | "counter" | "visual"
  const [localDocFilter, setLocalDocFilter] = useState("all");
  const [localShowIsolated, setLocalShowIsolated] = useState(false);
  const [localIsolateSubgraph, setLocalIsolateSubgraph] = useState(true);
  const [localSelectedNodeId, setLocalSelectedNodeId] = useState(null);

  const search = uiState ? uiState.search ?? "" : localSearch;
  const quickMode = uiState ? uiState.quickMode ?? "findings" : localQuickMode;
  const docFilter = uiState ? uiState.docFilter ?? "all" : localDocFilter;
  const showIsolated = uiState ? Boolean(uiState.showIsolated) : localShowIsolated;
  const isolateSubgraph = uiState ? uiState.isolateSubgraph ?? true : localIsolateSubgraph;
  const selectedNodeId = uiState ? uiState.selectedNodeId ?? null : localSelectedNodeId;

  const updateUi = useCallback(
    (key, fallbackSetter) => (val) => {
      if (onChangeUiState) {
        onChangeUiState((prev) => ({
          ...prev,
          [key]: typeof val === "function" ? val(prev[key]) : val,
        }));
      } else {
        fallbackSetter(val);
      }
    },
    [onChangeUiState]
  );
  const setSearch = useMemo(() => updateUi("search", setLocalSearch), [updateUi]);
  const setQuickMode = useMemo(() => updateUi("quickMode", setLocalQuickMode), [updateUi]);
  const setDocFilter = useMemo(() => updateUi("docFilter", setLocalDocFilter), [updateUi]);
  const setShowIsolated = useMemo(() => updateUi("showIsolated", setLocalShowIsolated), [updateUi]);
  const setIsolateSubgraph = useMemo(
    () => updateUi("isolateSubgraph", setLocalIsolateSubgraph),
    [updateUi]
  );
  const setSelectedNodeId = useMemo(
    () => updateUi("selectedNodeId", setLocalSelectedNodeId),
    [updateUi]
  );
  const [fullscreen, setFullscreen] = useState(false);
  const [userPositions, setUserPositions] = useState({});

  const handleNodesChange = useCallback((changes) => {
    const posUpdates = {};
    let hasPos = false;
    for (const ch of changes || []) {
      if (ch.type === "position" && ch.position && ch.id) {
        posUpdates[ch.id] = { x: ch.position.x, y: ch.position.y };
        hasPos = true;
      }
    }
    if (hasPos) {
      setUserPositions((prev) => ({ ...prev, ...posUpdates }));
    }
  }, []);

  // Sync sensible default mode when workspace loads
  useEffect(() => {
    if (!hasFindings && quickMode === "findings") {
      setQuickMode("all");
    }
  }, [hasFindings]);

  const obsByKey = useMemo(() => {
    const m = new Map();
    for (const e of result?.observations || []) {
      m.set(observationKey(e.ref), e);
    }
    return m;
  }, [result]);

  const objById = useMemo(() => {
    const m = new Map();
    for (const o of result?.objects || []) {
      m.set(`${o.kind}:${o.id}`, o);
    }
    return m;
  }, [result]);

  const edgeRoleLabel = useCallback(
    (role) => {
      const map = {
        SUPPORTS: t("Stützt", "Supports"),
        COUNTEREVIDENCE: t("Gegenbeleg", "Counter"),
        QUALIFIES: t("Kontext", "Qualifies"),
        SUGGESTED_BY: t("Vorschlag", "Suggested"),
        SOURCE: t("Quelle", "Source"),
        TARGET: t("Ziel", "Target"),
        USES_RELATION: t("Nutzt B", "Uses B"),
        HAS_PICTURE_SOURCE: t("Bildquelle", "Visual"),
        HAS_DOCUMENT_SOURCE: t("Dokument", "Doc"),
      };
      return map[role] || role;
    },
    [t]
  );

  const severRelation = useCallback(
    async (relObj) => {
      try {
        await api("ux-decision", {
          target_type: "relation",
          target: relObj.id,
          action: "rejected",
          reason: t(
            "Verbindung im Wissensgraphen manuell gelöst",
            "Connection severed manually in Evidence Graph"
          ),
        });
        toast.success(t("Relation im Graphen gelöst & verworfen", "Relation severed & rejected"));
        setSelectedNodeId(null);
        await onRefreshWorkspace();
      } catch (err) {
        toast.error(err.message);
      }
    },
    [onRefreshWorkspace, t]
  );

  const unlinkFromFinding = useCallback(
    async (findingObj, listKey, removeTarget) => {
      const cur = findingObj?.effective || {};
      const nextInterp = { ...cur };
      if (listKey === "relations") {
        nextInterp.relations = (cur.relations || []).filter(
          (rid) => String(rid) !== String(removeTarget)
        );
      } else {
        const rmKey = observationKey(removeTarget);
        const filtered = (cur[listKey] || []).filter((r) => observationKey(r) !== rmKey);
        if (listKey === "supports" && filtered.length === 0) {
          toast.error(
            t(
              "Ein Finding benötigt mindestens einen Stützbeleg. Nutze ‚Verwerfen‘, um das gesamte Finding zu entfernen.",
              "A Finding requires at least one supporting anchor. Use 'Reject' to discard the entire Finding."
            )
          );
          return;
        }
        nextInterp[listKey] = filtered;
      }
      try {
        await api("ux-decision", {
          target_type: "finding",
          target: findingObj.id,
          action: "corrected",
          reason: t(
            `Verknüpfung (${listKey}) im Wissensgraphen gelöst`,
            `Unlinked (${listKey}) in Evidence Graph`
          ),
          payload: { interpretation: nextInterp },
        });
        toast.success(t("Verknüpfung gelöst", "Connection unlinked"));
        await onRefreshWorkspace();
      } catch (err) {
        toast.error(err.message);
      }
    },
    [onRefreshWorkspace, t]
  );

  const { layoutedNodes, styledEdges, allNodeMap, findingQuickList } = useMemo(() => {
    const baseRawNodes = (graph.nodes || []).filter((n) => {
      if (n.__class__ === "FindingNode") {
        return objById.get(`finding:${n.record_id}`)?.review !== "HUMAN_REJECTED";
      }
      if (n.__class__ === "RelationNode") {
        return objById.get(`relation:${n.record_id}`)?.review !== "HUMAN_REJECTED";
      }
      return true;
    });
    const nodeIdAllow = new Set(baseRawNodes.map((n) => n.id));
    const baseRawEdges = (graph.edges || []).filter(
      (e) => nodeIdAllow.has(e.source) && nodeIdAllow.has(e.target)
    );

    const effectiveMode = !hasFindings && quickMode === "findings" ? "all" : quickMode;

    // Project DocumentSource hub cards in "all" mode so text/table observations connect visibly to their source files
    const rawNodes = [...baseRawNodes];
    const rawEdges = [...baseRawEdges];
    if (effectiveMode === "all") {
      const docMetaById = new Map((result?.documents || []).map((d) => [d.document, d]));
      const hasPicEdge = new Set();
      for (const e of baseRawEdges) {
        const roles = e.roles?.length ? e.roles : [e.label];
        if (roles.includes("HAS_PICTURE_SOURCE")) {
          hasPicEdge.add(e.source);
          hasPicEdge.add(e.target);
        }
      }
      const docHubCounts = new Map();
      for (const n of baseRawNodes) {
        if (n.__class__ === "ObservationNode" && n.document != null && !hasPicEdge.has(n.id)) {
          docHubCounts.set(n.document, (docHubCounts.get(n.document) || 0) + 1);
        }
      }
      for (const [dId, count] of docHubCounts.entries()) {
        const dMeta = docMetaById.get(dId);
        const hubId = `docsrc:${dId}`;
        rawNodes.push({
          id: hubId,
          __class__: "DocumentSourceNode",
          document: dId,
          doc_name: dMeta?.name || `Dokument #${dId}`,
          obs_count: count,
        });
      }
      for (const n of baseRawNodes) {
        if (n.__class__ === "ObservationNode" && n.document != null && !hasPicEdge.has(n.id)) {
          rawEdges.push({
            source: n.id,
            target: `docsrc:${n.document}`,
            label: "HAS_DOCUMENT_SOURCE",
            roles: ["HAS_DOCUMENT_SOURCE"],
          });
        }
      }
    }

    const deg = new Map();
    for (const e of rawEdges) {
      deg.set(e.source, (deg.get(e.source) || 0) + 1);
      deg.set(e.target, (deg.get(e.target) || 0) + 1);
    }

    const includeIsolated = showIsolated || rawEdges.length === 0;

    // Quick-mode reachability (2 hops so Finding -> Relation/Observation -> PictureSource all stay connected)
    const quickKeepNodes = new Set();
    const matchingEdgeSet = new Set();

    if (effectiveMode === "counter") {
      rawEdges.forEach((e, idx) => {
        const roles = e.roles?.length ? e.roles : [e.label];
        if (roles.includes("COUNTEREVIDENCE")) {
          matchingEdgeSet.add(idx);
          quickKeepNodes.add(e.source);
          quickKeepNodes.add(e.target);
        }
      });
    } else if (effectiveMode === "visual") {
      rawNodes.forEach((n) => {
        if (n.__class__ === "PictureSourceNode") quickKeepNodes.add(n.id);
      });
      for (let hop = 0; hop < 2; hop++) {
        rawEdges.forEach((e, idx) => {
          if (quickKeepNodes.has(e.source) || quickKeepNodes.has(e.target)) {
            matchingEdgeSet.add(idx);
            quickKeepNodes.add(e.source);
            quickKeepNodes.add(e.target);
          }
        });
      }
    } else if (effectiveMode === "findings") {
      rawNodes.forEach((n) => {
        if (n.__class__ === "FindingNode") quickKeepNodes.add(n.id);
      });
      for (let hop = 0; hop < 2; hop++) {
        rawEdges.forEach((e, idx) => {
          if (quickKeepNodes.has(e.source) || quickKeepNodes.has(e.target)) {
            matchingEdgeSet.add(idx);
            quickKeepNodes.add(e.source);
            quickKeepNodes.add(e.target);
          }
        });
      }
    }

    const q = search.trim().toLowerCase();

    const baseKeptNodes = rawNodes.filter((n) => {
      if (selectedNodeId === n.id) return true;
      if (!includeIsolated && (deg.get(n.id) || 0) === 0 && n.__class__ !== "FindingNode") {
        return false;
      }
      if (docFilter !== "all" && n.document != null && String(n.document) !== docFilter) {
        return false;
      }
      if (effectiveMode !== "all" && !quickKeepNodes.has(n.id)) {
        return false;
      }
      if (q) {
        const entry = obsByKey.get(observationKey(n));
        const hay = [
          n.text,
          n.title,
          n.kind,
          n.observation,
          entry?.name,
          entry?.raw?.quote,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    const baseKeptIds = new Set(baseKeptNodes.map((n) => n.id));
    const baseKeptEdges = rawEdges.filter(
      (e, idx) =>
        baseKeptIds.has(e.source) &&
        baseKeptIds.has(e.target) &&
        (effectiveMode === "all" || matchingEdgeSet.size === 0 || matchingEdgeSet.has(idx))
    );

    // 2-hop neighborhood around selectedNodeId
    const neighborhood = new Set();
    if (selectedNodeId && baseKeptIds.has(selectedNodeId)) {
      neighborhood.add(selectedNodeId);
      for (let hop = 0; hop < 2; hop++) {
        for (const e of baseKeptEdges) {
          if (neighborhood.has(e.source)) neighborhood.add(e.target);
          if (neighborhood.has(e.target)) neighborhood.add(e.source);
        }
      }
    }

    const visibleNodes =
      neighborhood.size > 0 && isolateSubgraph
        ? baseKeptNodes.filter((n) => neighborhood.has(n.id))
        : baseKeptNodes;
    const visibleIds = new Set(visibleNodes.map((n) => n.id));
    const visibleEdges = baseKeptEdges.filter(
      (e) => visibleIds.has(e.source) && visibleIds.has(e.target)
    );

    const buildCardData = (n) => {
      const entry = obsByKey.get(observationKey(n));
      let kindClass = "obs";
      let eyebrow = `A · ${entry?.ref?.observation || n.observation || ""}`;
      let tone = "neutral";
      let pill = "";
      let footer = entry?.name || "";

      if (n.__class__ === "FindingNode") {
        kindClass = "finding";
        const obj = objById.get(`finding:${n.record_id}`);
        const val = String(obj?.effective?.valence || n.valence || "").toLowerCase();
        eyebrow = `C · Finding #${n.record_id}`;
        tone =
          obj?.review === "HUMAN_CONFIRMED"
            ? "success"
            : val === "problem" || val === "negative"
            ? "danger"
            : val === "strength" || val === "positive"
            ? "success"
            : "warning";
        pill = val || "";
        const sup = (obj?.effective?.supports || []).length;
        const opp = (obj?.effective?.opposes || []).length;
        footer = `${sup} ${t("Belege", "supports")}${opp ? ` · ${opp} ${t("Gegen", "counter")}` : ""}`;
      } else if (n.__class__ === "RelationNode") {
        kindClass = "relation";
        const obj = objById.get(`relation:${n.record_id}`);
        eyebrow = `B · #${n.record_id}`;
        tone = obj?.review === "HUMAN_CONFIRMED" ? "success" : "neutral";
        pill = (obj?.effective?.kind || n.kind || "").replaceAll("_", " ");
        const sameDoc =
          obj?.effective?.source?.document != null &&
          obj?.effective?.source?.document === obj?.effective?.target?.document;
        footer = sameDoc
          ? t("Dokumentinterne Relation", "Within-document relation")
          : t("Dokumentübergreifende Relation", "Cross-document relation");
      } else if (n.__class__ === "PictureSourceNode") {
        kindClass = "visual";
        eyebrow = t("Bildquelle", "Visual Source");
        tone = "active";
        footer = n.ref || "";
      } else if (n.__class__ === "DocumentSourceNode") {
        kindClass = "docsource";
        eyebrow = t("Dokumentquelle", "Document Source");
        tone = "info";
        const ext = String(n.doc_name || "").split(".").pop()?.toUpperCase() || "";
        pill = ext && ext.length <= 5 ? ext : "";
        footer = `${n.obs_count || 0} ${t("Text-/Tabellenbelege", "text/table anchors")}`;
      } else {
        tone = entry?.source_check?.matches?.length ? "success" : "warning";
      }

      const rawTitle =
        n.__class__ === "PictureSourceNode"
          ? pictureSourceLabel(n.picture_source, t)
          : n.__class__ === "DocumentSourceNode"
          ? String(n.doc_name || `Dokument #${n.document}`)
          : String(n.text || n.title || n.kind || n.__class__);

      return {
        raw: n,
        entry,
        kindClass,
        eyebrow,
        tone,
        pill,
        title: rawTitle,
        footer,
        dimmed: !isolateSubgraph && neighborhood.size > 0 && !neighborhood.has(n.id),
      };
    };

    const nodeMap = new Map();
    for (const n of rawNodes) {
      nodeMap.set(n.id, { id: n.id, type: "uxCard", data: buildCardData(n) });
    }

    const rfNodes = visibleNodes.map((n) => nodeMap.get(n.id));

    const strokeBase = theme === "dark" ? "#475569" : "#94a3b8";
    const strokeActive = theme === "dark" ? "#2dd4bf" : "#0f766e";
    const strokeCounter = "#ef4444";

    const rfEdges = visibleEdges.map((e, idx) => {
      const roles = e.roles?.length ? e.roles : [e.label];
      const isCounter = roles.includes("COUNTEREVIDENCE");
      const inSpotlight =
        neighborhood.size === 0 || (neighborhood.has(e.source) && neighborhood.has(e.target));
      const stroke = isCounter
        ? strokeCounter
        : neighborhood.size > 0 && inSpotlight
        ? strokeActive
        : strokeBase;

      return {
        id: `e-${idx}-${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        label:
          visibleEdges.length <= 24 || (neighborhood.size > 0 && inSpotlight)
            ? roles.map(edgeRoleLabel).join(" · ")
            : undefined,
        style: {
          stroke,
          strokeWidth: neighborhood.size > 0 && inSpotlight ? 1.8 : 1.35,
          strokeDasharray: isCounter ? "5 4" : undefined,
          opacity: !isolateSubgraph && !inSpotlight ? 0.16 : 1,
        },
        labelStyle: {
          fill: theme === "dark" ? "#d4d4d8" : "#3f3f46",
          fontSize: 10,
          fontWeight: 500,
        },
        labelBgStyle: {
          fill: theme === "dark" ? "#111113" : "#ffffff",
          fillOpacity: 0.92,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 14,
          height: 14,
          color: stroke,
        },
      };
    });

    const positioned = computeWidescreenLayout(rfNodes, rfEdges);
    const findingsList = rawNodes
      .filter((n) => n.__class__ === "FindingNode")
      .map((n) => nodeMap.get(n.id));

    return {
      layoutedNodes: positioned,
      styledEdges: rfEdges,
      allNodeMap: nodeMap,
      findingQuickList: findingsList,
    };
  }, [
    graph,
    hasFindings,
    showIsolated,
    isolateSubgraph,
    docFilter,
    quickMode,
    search,
    selectedNodeId,
    obsByKey,
    objById,
    theme,
    t,
    edgeRoleLabel,
  ]);

  const interactiveNodes = useMemo(
    () =>
      layoutedNodes.map((n) =>
        userPositions[n.id] ? { ...n, position: userPositions[n.id] } : n
      ),
    [layoutedNodes, userPositions]
  );
  const hasCustomPositions = Object.keys(userPositions).length > 0;

  // Fit view smoothly whenever visible topology changes
  useEffect(() => {
    if (!layoutedNodes.length) return;
    const timer = setTimeout(() => {
      rf.fitView({ padding: 0.14, duration: 220, maxZoom: 1.0 });
    }, 50);
    return () => clearTimeout(timer);
  }, [layoutedNodes.length, selectedNodeId, isolateSubgraph, quickMode, docFilter, showIsolated, fullscreen]);

  // Handle incoming focus request from SynthesisView without dumping isolated nodes
  useEffect(() => {
    if (!focusRequest || !graph.nodes?.length) return;
    const match = graph.nodes.find((n) => {
      if (focusRequest.kind === "finding") {
        return n.__class__ === "FindingNode" && String(n.record_id) === String(focusRequest.target);
      }
      if (focusRequest.kind === "relation") {
        return n.__class__ === "RelationNode" && String(n.record_id) === String(focusRequest.target);
      }
      if (focusRequest.kind === "observation") {
        return observationKey(n) === observationKey(focusRequest.target);
      }
      return false;
    });
    if (match) {
      if (focusRequest.kind !== "finding") {
        setQuickMode("all");
      }
      setIsolateSubgraph(true);
      setSelectedNodeId(match.id);
    }
    onClearFocusRequest?.();
  }, [focusRequest, graph.nodes]);

  const selectedNode = selectedNodeId ? allNodeMap.get(selectedNodeId) : null;

  if (!workspace?.documents?.length) {
    return (
      <div className="lx-page">
        <div className="lx-empty-state">
          <Sparkles size={28} strokeWidth={1.5} className="lx-icon-muted" />
          <h2>{t("Keine Studienauswahl für den Wissensgraphen", "No Study Scope Selected")}</h2>
          <p>
            {t(
              "Wähle Dokumente im Korpus aus, um die gesamte Belegkette von Bild- und Textankern über Beziehungen bis zu Findings visuell zu explorieren.",
              "Select documents in Corpus to explore the visual evidence graph from source anchors to findings."
            )}
          </p>
          <button type="button" className="lx-btn lx-btn-primary" onClick={() => onNavigate("documents")}>
            {t("Zum Studienkorpus", "Open Study Corpus")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`lx-graph-shell${fullscreen ? " is-fullscreen" : ""}`}>
      <h1 className="sr-only">{t("Wissensgraph", "Evidence Graph")}</h1>
      {/* Clean Single-Row Graph Toolbar */}
      <header className="lx-graph-toolbar">
        <div className="lx-toolbar-left">
          <div className="lx-search-wrap" style={{ width: 210 }}>
            <Search size={13} className="lx-search-icon" />
            <input
              type="search"
              className="lx-input lx-input-sm lx-search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("Knoten oder Zitat suchen …", "Search nodes or quotes…")}
            />
          </div>

          <div className="lx-segmented">
            {[
              ["findings", t("Findings-Ketten", "Finding Chains"), !hasFindings],
              ["all", t("Gesamtnetz", "All Linked"), false],
              ["counter", t("Gegenbelege", "Counter"), false],
              ["visual", t("Visuell", "Visual"), false],
            ].map(([k, lbl, dis]) => (
              <button
                key={k}
                type="button"
                disabled={dis}
                className={`lx-seg-btn${quickMode === k ? " is-active" : ""}`}
                onClick={() => setQuickMode(k)}
              >
                {lbl}
              </button>
            ))}
          </div>

          <InfoPopover
            title={t("Graphen-Modi, Ziehen & Verbindungen lösen", "Graph Modes, Dragging & Unlinking")}
          >
            <p>
              <strong>{t("Findings-Ketten", "Finding Chains")}:</strong>{" "}
              {t(
                "Zeigt synthetisierte Findings (Stufe C) mitsamt ihren verknüpften B-Relationen, A-Beobachtungen und Bildquellen (benötigt einen abgeschlossenen Stufe-C-Lauf).",
                "Shows Stage C Findings with their linked Stage B relations, Stage A observations, and visual sources (requires a completed Stage C run)."
              )}
            </p>
            <p>
              <strong>{t("Gesamtnetz", "All Linked")}:</strong>{" "}
              {t(
                "Zeigt alle Dokumente im Umfang: Text- und Tabellenbelege gruppiert an ihrer Dokumentquelle sowie Bildbelege an ihrer Bildquelle (plus B/C-Knoten, falls berechnet).",
                "Shows all documents in scope: text & table anchors grouped by Document Source and visual anchors by Visual Source (plus Stage B/C nodes if computed)."
              )}
            </p>
            <p>
              <strong>{t("Gegenbelege / Visuell", "Counter / Visual")}:</strong>{" "}
              {t(
                "Filtert gezielt widersprüchliche Kanten (rot gestrichelt) bzw. alle aus Screenshots, Charts und Folien stammenden Belegketten.",
                "Filters specifically contradictory edges (dashed red) or visual slide/chart evidence chains."
              )}
            </p>
            <p>
              <strong>{t("Interaktion", "Interaction")}:</strong>{" "}
              {t(
                "Jede Karte lässt sich frei per Drag & Drop verschieben (‚Layout neu ordnen‘ setzt zurück). Im rechten Inspektor kannst du fehlerhafte KI-Verknüpfungen gezielt lösen.",
                "Every card is freely draggable ('Auto-Layout' resets). In the right inspector you can sever faulty AI links."
              )}
            </p>
          </InfoPopover>

          <div style={{ width: 175 }}>
            <Select
              size="sm"
              value={docFilter}
              onValueChange={setDocFilter}
              options={[
                ["all", t("Alle Dokumente", "All Documents")],
                ...(result?.documents || []).map((d) => [String(d.document), d.name]),
              ]}
            />
          </div>

          {selectedNodeId ? (
            <label className="lx-inline-switch lx-text-xs">
              <Switch checked={isolateSubgraph} onCheckedChange={setIsolateSubgraph} />
              <span>{t("Teilgraph isolieren", "Isolate Subgraph")}</span>
            </label>
          ) : (
            <label className="lx-inline-switch lx-text-xs">
              <Switch checked={showIsolated} onCheckedChange={setShowIsolated} />
              <span>{t("Isolierte A-Knoten", "Isolated Nodes")}</span>
            </label>
          )}
        </div>

        <div className="lx-toolbar-right">
          <span className="lx-muted lx-text-xs tabular">
            {layoutedNodes.length} {t("Karten", "cards")} · {styledEdges.length}{" "}
            {t("Kanten", "edges")}
          </span>
          <InfoPopover
            title={t("Graphen-Legende", "Evidence Graph Legend")}
            align="end"
          >
            <p>
              <strong>C · Finding:</strong>{" "}
              {t("Synthetisierter UX-Befund (Stufe C).", "Synthesized UX Finding (Stage C).")}
            </p>
            <p>
              <strong>B · Relation:</strong>{" "}
              {t("Dokumentübergreifende Verknüpfung (Stufe B).", "Cross-document relation (Stage B).")}
            </p>
            <p>
              <strong>A · Beobachtung:</strong>{" "}
              {t("Wörtlich verankerte Einzelbeobachtung im Original.", "Verbatim-grounded observation in source.")}
            </p>
            <p>
              <strong>{t("Gestrichelte rote Kante", "Dashed red edge")}:</strong>{" "}
              {t("Gegenbeleg / Widerspruch.", "Counterevidence / contradiction.")}
            </p>
          </InfoPopover>
          {selectedNodeId && (
            <button
              type="button"
              className="lx-btn lx-btn-xs"
              onClick={() => setSelectedNodeId(null)}
            >
              <RotateCcw size={12} />
              <span>{t("Fokus lösen", "Clear Focus")}</span>
            </button>
          )}
          {hasCustomPositions && (
            <button
              type="button"
              className="lx-btn lx-btn-xs"
              onClick={() => {
                setUserPositions({});
                setTimeout(() => rf.fitView({ padding: 0.16, duration: 240, maxZoom: 1.0 }), 30);
              }}
              title={t("Manuell gezogene Karten wieder automatisch anordnen", "Reset dragged cards to automatic layout")}
            >
              <LayoutGrid size={12} />
              <span>{t("Layout neu ordnen", "Auto-Layout")}</span>
            </button>
          )}
          <button
            type="button"
            className="lx-btn lx-btn-xs"
            onClick={() => rf.fitView({ padding: 0.16, duration: 240, maxZoom: 1.0 })}
          >
            <Focus size={12} />
            <span>{t("Einpassen", "Fit")}</span>
          </button>
          <button
            type="button"
            className="lx-btn lx-btn-xs"
            onClick={() => setFullscreen((f) => !f)}
          >
            {fullscreen ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
            <span>{fullscreen ? t("Normal", "Exit") : t("Vollbild", "Fullscreen")}</span>
          </button>
        </div>
      </header>

      {!hasFindings && (
        <div className="lx-graph-notice-banner">
          <span>
            {t(
              "Hinweis: Für diese Auswahl wurden Stufe B (Beziehungen) und Stufe C (Findings) noch nicht ausgeführt. Das ‚Gesamtnetz‘ gruppiert aktuell alle Stufe-A-Beobachtungen nach Dokument- und Bildquellen.",
              "Note: Stage B (Relations) and Stage C (Findings) have not run yet for this scope. 'All Linked' currently groups all Stage A observations by Document and Visual Sources."
            )}
          </span>
          <button
            type="button"
            className="lx-btn lx-btn-xs lx-btn-primary"
            onClick={() => onNavigate("pipeline")}
          >
            <span>{t("Stufe B & C in Pipeline starten", "Run Stage B & C in Pipeline")}</span>
            <ArrowUpRight size={12} />
          </button>
        </div>
      )}

      {/* Main Split: React Flow Canvas + Inspector Sidebar */}
      <div className="lx-graph-body">
        <div className="lx-graph-canvas-wrap">
          <ReactFlow
            nodes={interactiveNodes}
            edges={styledEdges}
            nodeTypes={NODE_TYPES}
            nodesDraggable={true}
            onNodesChange={handleNodesChange}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            onPaneClick={() => setSelectedNodeId(null)}
            minZoom={0.22}
            maxZoom={1.6}
            proOptions={{ hideAttribution: false }}
            fitView
          >
            <Background
              gap={20}
              size={1}
              color={theme === "dark" ? "#27272a" : "#e4e4e7"}
            />
            <Controls showInteractive={false} className="lx-rf-controls" />
            {layoutedNodes.length >= 1 && (
              <MiniMap
                pannable
                zoomable
                className="lx-rf-minimap"
                bgColor={theme === "dark" ? "#11141c" : "#f8fafc"}
                maskColor={theme === "dark" ? "rgba(15,23,42,0.72)" : "rgba(226,232,240,0.68)"}
                nodeStrokeWidth={3}
                nodeColor={(n) => {
                  const kc = n.data?.kindClass;
                  if (kc === "finding") return "#059669";
                  if (kc === "relation") return "#d97706";
                  if (kc === "visual") return "#0891b2";
                  if (kc === "docsource") return "#0284c7";
                  return theme === "dark" ? "#64748b" : "#94a3b8";
                }}
                nodeStrokeColor={(n) => {
                  const kc = n.data?.kindClass;
                  if (kc === "finding") return "#10b981";
                  if (kc === "relation") return "#f59e0b";
                  if (kc === "visual") return "#06b6d4";
                  if (kc === "docsource") return "#38bdf8";
                  return theme === "dark" ? "#94a3b8" : "#475569";
                }}
              />
            )}
          </ReactFlow>
        </div>

        {/* Right-Hand Node Inspector */}
        <aside className="lx-graph-inspector">
          {!selectedNode ? (
            <div className="lx-inspector-idle">
              <div className="lx-section-block">
                <h3 className="lx-eyebrow">{t("Evidenzgraph-Inspektor", "Graph Inspector")}</h3>
                <p className="lx-text-xs lx-muted">
                  {t(
                    "Klicke auf eine Karte im Graphen oder wähle unten direkt ein Finding, um seine vollständige Belegkette im Teilgraph-Fokus zu prüfen.",
                    "Click any card on the canvas or pick a Finding below to isolate and inspect its full cross-document evidence chain."
                  )}
                </p>
              </div>

              {findingQuickList.length > 0 && (
                <div className="lx-section-block">
                  <h4 className="lx-eyebrow">
                    {t("Findings direkt fokussieren", "Quick-Focus Findings")} ({findingQuickList.length})
                  </h4>
                  <div className="lx-quick-finding-list">
                    {findingQuickList.map((fn) => (
                      <button
                        key={fn.id}
                        type="button"
                        className="lx-master-item"
                        onClick={() => {
                          setIsolateSubgraph(true);
                          setSelectedNodeId(fn.id);
                        }}
                      >
                        <div className="lx-master-item-top">
                          <StatusDot tone={fn.data.tone} />
                          <span className="lx-master-item-title">{fn.data.title}</span>
                        </div>
                        <span className="lx-master-item-sub">{fn.data.footer}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            (() => {
              const n = selectedNode.data.raw;
              const entry = selectedNode.data.entry;
              const obj =
                n.__class__ === "FindingNode"
                  ? objById.get(`finding:${n.record_id}`)
                  : n.__class__ === "RelationNode"
                  ? objById.get(`relation:${n.record_id}`)
                  : null;

              return (
                <div className="lx-inspector-detail">
                  <div className="lx-between">
                    <span className="lx-mono-tag tabular">{selectedNode.data.eyebrow}</span>
                    <button
                      type="button"
                      className="lx-icon-btn"
                      onClick={() => setSelectedNodeId(null)}
                      aria-label="Close inspector"
                    >
                      <X size={14} />
                    </button>
                  </div>

                  <h3 className="lx-inspector-title">{selectedNode.data.title}</h3>

                  {obj && (
                    <>
                      <EpistemicFlagsRow
                        record={{
                          ...obj,
                          epistemic_flags: n.epistemic_flags || [],
                          independence: n.independence,
                        }}
                      />
                      <ResearcherReviewBlock
                        compact
                        targetType={obj.kind}
                        target={obj.id}
                        decisions={obj.decisions}
                        apiCall={api}
                        onSaved={() => {
                          toast.success(t("Entscheidung gespeichert", "Decision saved"));
                          return onRefreshWorkspace();
                        }}
                      />
                      <p className="lx-text-xs" style={{ lineHeight: 1.55 }}>
                        {obj.effective?.rationale || ""}
                      </p>

                      {obj.kind === "relation" && obj.review !== "HUMAN_REJECTED" && (
                        <button
                          type="button"
                          className="lx-btn lx-btn-xs"
                          style={{ color: "var(--dot-danger)", borderColor: "var(--dot-danger)" }}
                          onClick={() => severRelation(obj)}
                        >
                          <Unlink size={12} />
                          <span>
                            {t("Verbindung lösen (Relation verwerfen)", "Sever Connection (Reject Relation)")}
                          </span>
                        </button>
                      )}

                      {obj.kind === "finding" && (
                        <div className="lx-form-stack" style={{ marginTop: 6 }}>
                          <h4 className="lx-eyebrow">
                            {t(
                              "Verknüpfte Kanten prüfen & lösen",
                              "Inspect & Unlink Graph Connections"
                            )}
                          </h4>
                          {[
                            ["supports", t("Stützbeleg", "Supports")],
                            ["opposes", t("Gegenbeleg", "Counter")],
                            ["qualifies", t("Einschränkend", "Qualifies")],
                          ].map(([lKey, roleTitle]) =>
                            (obj.effective?.[lKey] || []).map((ref) => {
                              const rk = observationKey(ref);
                              const linkedEntry = obsByKey.get(rk);
                              const canUnlink =
                                lKey !== "supports" || (obj.effective?.supports || []).length > 1;
                              const match0 = linkedEntry?.source_check?.matches?.[0] || null;
                              return (
                                <div
                                  key={`${lKey}-${rk}`}
                                  className="lx-exclusion-item lx-between"
                                  style={{ gap: 6 }}
                                >
                                  <div className="min-w-0" style={{ flex: 1 }}>
                                    <div className="lx-muted tabular" style={{ fontSize: "10.5px" }}>
                                      {roleTitle} · {linkedEntry?.name || `Dok #${ref.document}`} ·{" "}
                                      {ref.observation}
                                    </div>
                                    <div className="truncate lx-text-xs">
                                      {linkedEntry?.effective?.statement || rk}
                                    </div>
                                  </div>
                                  <div className="lx-btn-row" style={{ flexShrink: 0 }}>
                                    {match0 && (
                                      <button
                                        type="button"
                                        className="lx-btn lx-btn-xs lx-btn-ghost"
                                        onClick={() =>
                                          onShowSource(ref, match0, {
                                            kind: "finding",
                                            id: obj.id,
                                            title: selectedNode.data.title,
                                            anchors: [
                                              ...(obj.effective?.supports || []).map((r) => ({
                                                ref: r,
                                                role: t("Stützt", "Supports"),
                                              })),
                                              ...(obj.effective?.opposes || []).map((r) => ({
                                                ref: r,
                                                role: t("Gegen", "Counter"),
                                              })),
                                            ],
                                          })
                                        }
                                        title={t("Im Original zeigen", "Inspect in Original")}
                                      >
                                        <ArrowUpRight size={11} />
                                      </button>
                                    )}
                                    <button
                                      type="button"
                                      className="lx-btn lx-btn-xs lx-btn-ghost"
                                      disabled={!canUnlink}
                                      onClick={() => unlinkFromFinding(obj, lKey, ref)}
                                      title={
                                        canUnlink
                                          ? t("Diese Kante vom Finding lösen", "Unlink edge from Finding")
                                          : t("Letzter Stützbeleg kann nicht gelöst werden", "Cannot unlink sole support")
                                      }
                                    >
                                      <Unlink size={11} />
                                    </button>
                                  </div>
                                </div>
                              );
                            })
                          )}
                          {(obj.effective?.relations || []).map((relId) => (
                            <div
                              key={`rel-${relId}`}
                              className="lx-exclusion-item lx-between"
                              style={{ gap: 6 }}
                            >
                              <span className="lx-text-xs tabular">Relation B #{relId}</span>
                              <button
                                type="button"
                                className="lx-btn lx-btn-xs lx-btn-ghost"
                                onClick={() => unlinkFromFinding(obj, "relations", relId)}
                                title={t("B-Relation vom Finding lösen", "Unlink Stage B relation")}
                              >
                                <Unlink size={11} />
                                <span>{t("Lösen", "Unlink")}</span>
                              </button>
                            </div>
                          ))}
                        </div>
                      )}

                      <button
                        type="button"
                        className="lx-btn lx-btn-xs"
                        onClick={() =>
                          onOpenProposalInSynthesis(
                            obj.kind === "finding" ? "findings" : "relations",
                            String(obj.id)
                          )
                        }
                      >
                        <span>{t("In Synthese-Ansicht öffnen", "Open in Synthesis View")}</span>
                        <ArrowUpRight size={12} />
                      </button>
                    </>
                  )}

                  {entry && (
                    <>
                      <EpistemicFlagsRow record={entry} />
                      <ResearcherReviewBlock
                        compact
                        targetType="observation"
                        target={entry.ref}
                        decisions={entry.decisions}
                        apiCall={api}
                        onSaved={() => {
                          toast.success(t("Entscheidung gespeichert", "Decision saved"));
                          return onRefreshWorkspace();
                        }}
                      />
                      <EvidenceCard compact entry={entry} onShowSource={onShowSource} />
                    </>
                  )}

                  {n.__class__ === "PictureSourceNode" && (
                    <div className="lx-form-stack">
                      <p className="lx-text-xs lx-muted">
                        {t("Dokument", "Document")} #{n.document} · {n.ref}
                      </p>
                      <button
                        type="button"
                        className="lx-btn lx-btn-sm lx-btn-primary"
                        onClick={() =>
                          onShowSource(
                            { document: n.document, version: n.version || null },
                            {
                              ref: n.ref,
                              picture_source: n.picture_source,
                              prov: n.pages?.length ? [{ page_no: n.pages[0] }] : [],
                            }
                          )
                        }
                      >
                        <span>{t("Bildquelle im Inspektor öffnen", "Inspect Visual Source")}</span>
                        <ArrowUpRight size={13} />
                      </button>
                    </div>
                  )}

                  {n.__class__ === "DocumentSourceNode" && (
                    <div className="lx-form-stack">
                      <p className="lx-text-xs lx-muted">
                        {t("Primärdokument", "Primary Document")} #{n.document} ·{" "}
                        {selectedNode.data.footer}
                      </p>
                      <button
                        type="button"
                        className="lx-btn lx-btn-sm lx-btn-primary"
                        onClick={() => onShowSource({ document: n.document }, null)}
                      >
                        <span>
                          {t("Dokument im Quelleninspektor öffnen", "Open Document in Inspector")}
                        </span>
                        <ArrowUpRight size={13} />
                      </button>
                    </div>
                  )}
                </div>
              );
            })()
          )}
        </aside>
      </div>
    </div>
  );
}

export function GraphView(props) {
  return (
    <ReactFlowProvider>
      <GraphCanvasInner {...props} />
    </ReactFlowProvider>
  );
}
