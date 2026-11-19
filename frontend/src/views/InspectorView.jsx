import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  BookOpen,
  Code2,
  Download,
  FileText,
  Layers,
  Maximize2,
  Minimize2,
  Minus,
  Plus,
  RotateCcw,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { toast } from "sonner";
import * as _doclingComponents from "../../components.js";
import { resolveDocumentItem } from "../../components.js";
import { usePrefs, statusInfo } from "../lib/i18n.jsx";
import { api, markPlainTextFrame } from "../lib/api.js";
import { InfoPopover, Modal, Select, StatusBadge } from "../components/ui.jsx";
import { DoclingReader } from "../components/DoclingReader.jsx";
import { observationKey } from "../components/EvidenceCard.jsx";

void _doclingComponents;

const shortHash = (h) => (h ? h.slice(0, 10) : "—");

export function InspectorView({
  files = [],
  workspace = null,
  selection,
  onChangeSelection,
  canGoBack,
  onGoBack,
  onNavigate,
}) {
  const { theme, t } = usePrefs();
  const [docBundle, setDocBundle] = useState(null); // { file, summary, runs, webDoc }
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("compare"); // "compare" | "original" | "structure" | "native"
  const [rightSubMode, setRightSubMode] = useState("reader"); // "reader" | "geometry" | "cells"
  const [zoom, setZoom] = useState(100);
  const [splitPct, setSplitPct] = useState(50);
  const [focusMode, setFocusMode] = useState(false);

  // Modals / Drawers
  const [elementsModalOpen, setElementsModalOpen] = useState(false);
  const [elementsQuery, setElementsQuery] = useState("");
  const [elementsOffset, setElementsOffset] = useState(0);
  const [elementsData, setElementsData] = useState(null);

  const [modelInputOpen, setModelInputOpen] = useState(false);
  const [modelInputData, setModelInputData] = useState(null);
  const [modelInputRunId, setModelInputRunId] = useState("");
  const [anchorsModalOpen, setAnchorsModalOpen] = useState(false);
  const [ocrFallbackNotice, setOcrFallbackNotice] = useState("");

  // Table cells window state
  const [cellsData, setCellsData] = useState(null);
  const [cellRowStart, setCellRowStart] = useState(0);
  const [cellColStart, setCellColStart] = useState(0);
  const [cellSearch, setCellSearch] = useState("");

  const originalFrameRef = useRef(null);
  const viewerRef = useRef(null);
  const pdfReqCounter = useRef(0);
  const lastPdfReportedPageRef = useRef(null);
  const draggingSplit = useRef(false);

  const docId = selection?.document || null;
  const version = selection?.version || "";

  // Load document metadata, summary, runs, and native web JSON
  useEffect(() => {
    if (!docId) {
      setDocBundle(null);
      return;
    }
    let cancelled = false;
    setLoading(true);

    (async () => {
      try {
        const [file, baseSummary, runs] = await Promise.all([
          api(`file?id=${docId}`),
          api(`summary?id=${docId}`),
          api(`results?id=${docId}`),
        ]);
        const targetVer = selection?.version || baseSummary?.preferred_version || "";
        const summary =
          targetVer && targetVer !== baseSummary?.version
            ? await api(`summary?${new URLSearchParams({ id: docId, version: targetVer })}`)
            : baseSummary;

        let webDoc = null;
        if (file?.native) {
          const vParam = targetVer ? `?version=${encodeURIComponent(targetVer)}` : "";
          const resp = await fetch(`/document/${docId}/web${vParam}`);
          if (resp.ok) {
            webDoc = await resp.json();
          }
        }
        if (cancelled) return;

        setDocBundle({ file, summary, runs, webDoc });

        // Set sensible initial page & mode if opening fresh
        const hasPages = summary?.pages?.some((p) => p.image);
        if (!selection?.page && hasPages) {
          let initialPage = summary.pages.find((p) => p.image)?.page_no || null;
          if (selection?.ref && webDoc) {
            const item = resolveDocumentItem(webDoc, { $ref: selection.ref });
            const provPages = [
              ...new Set(
                (item?.prov || [])
                  .filter((p) => summary.pages.some((sp) => sp.image && sp.page_no === p.page_no))
                  .map((p) => p.page_no)
              ),
            ];
            if (provPages.length === 1) initialPage = provPages[0];
          }
          if (initialPage) {
            onChangeSelection((prev) =>
              prev?.document === docId ? { ...prev, page: initialPage, version: targetVer } : prev
            );
          }
        }

        if (file?.native && file?.stored) {
          setMode((m) => (m === "native" && !hasPages ? "compare" : m));
        } else if (file?.stored) {
          setMode("original");
        } else {
          setMode("structure");
        }
      } catch (err) {
        if (!cancelled) toast.error(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [docId, version]);

  const file = docBundle?.file;
  const summary = docBundle?.summary;
  const webDoc = docBundle?.webDoc;
  const hasPages = Boolean(summary?.pages?.some((p) => p.image));
  const isOffice = Boolean(file && /\.(docx|odt|pptx)$/i.test(file.name));
  const usesPdfViewer = Boolean(
    file && (/\.pdf$/i.test(file.name) || (isOffice && summary?.office_renderer))
  );
  const isPlainTxt = Boolean(file && /\.(txt|vtt|md)$/i.test(file.name));
  const nativeConfidence = summary?.diagnostics?.confidence || null;
  const tableSelected = Boolean(selection?.ref?.startsWith("#/tables/"));

  const showNativeGeometryInRightPane =
    mode === "native" ||
    (mode === "compare" && rightSubMode === "geometry" && hasPages && Boolean(selection?.page));

  // Sync theme live into PDF.js iframe without reloading PDF state
  useEffect(() => {
    if (!usesPdfViewer || !originalFrameRef.current?.contentWindow) return;
    originalFrameRef.current.contentWindow.postMessage(
      { type: "set-theme", theme },
      window.location.origin
    );
  }, [theme, usesPdfViewer]);

  // Sync <docling-img> custom element
  useEffect(() => {
    const el = viewerRef.current;
    if (!el || !showNativeGeometryInRightPane || !webDoc || !selection?.page) return;
    el.src = webDoc;
    el.items = `#/pages/${selection.page}`;
    el.itemStyle = (_, item) =>
      item.self_ref === selection?.ref
        ? "stroke:#0f766e;stroke-width:3;fill:#14b8a6;fill-opacity:.18"
        : item.meta?.ux_maind__slide_context || item.meta?.ux_maind__page_context
        ? "pointer-events:none;stroke:none"
        : "";
    el.onClickItem = (_, page, item) => {
      if (item?.self_ref) {
        onChangeSelection((prev) => ({
          ...prev,
          ref: item.self_ref,
          page: page?.page_no || prev.page,
          occurrence: item.text ? { quote: item.text } : null,
          presentation: null,
          runId: null,
        }));
      }
    };
  }, [showNativeGeometryInRightPane, webDoc, selection?.page, selection?.ref]);

  // Send search-quote postMessage to pdf.html
  const dispatchPdfSearch = useCallback(() => {
    const frame = originalFrameRef.current;
    if (!frame || !usesPdfViewer || !docBundle) return;
    let quote = selection?.occurrence?.quote || "";
    if (!quote && selection?.ref && webDoc) {
      const item = resolveDocumentItem(webDoc, { $ref: selection.ref });
      quote = item?.text || "";
    }
    const kind = isOffice ? "office-pdf" : "pdf";
    const reqId = ++pdfReqCounter.current;
    frame.contentWindow?.postMessage(
      {
        type: "search-quote",
        document: docId,
        kind,
        request: reqId,
        quote: typeof quote === "string" ? quote : "",
        page:
          kind === "pdf" || /\.pptx$/i.test(file?.name || "") ? selection?.page || null : null,
        fixedPage: kind === "pdf" && Boolean(selection?.occurrence && selection?.page),
        ref: selection?.ref || null,
      },
      window.location.origin
    );
  }, [usesPdfViewer, docBundle, selection, webDoc, isOffice, docId, file]);

  useEffect(() => {
    const onMessage = (e) => {
      if (e.origin !== window.location.origin) return;
      if (e.source !== originalFrameRef.current?.contentWindow) return;
      if (String(e.data?.document) !== String(docId)) return;
      if (e.data?.type === "pdf-ready") {
        originalFrameRef.current?.contentWindow?.postMessage(
          { type: "set-theme", theme },
          window.location.origin
        );
        dispatchPdfSearch();
      } else if (
        e.data?.type === "pdf-page-changed" &&
        Number.isInteger(e.data?.page)
      ) {
        const nextPage = e.data.page;
        lastPdfReportedPageRef.current = nextPage;
        onChangeSelection((prev) =>
          prev?.page === nextPage ? prev : { ...prev, page: nextPage }
        );
      } else if (
        e.data?.type === "pdf-no-text-match" &&
        e.data?.ref &&
        e.data?.ref === selection?.ref &&
        webDoc &&
        hasPages
      ) {
        const item = resolveDocumentItem(webDoc, { $ref: selection.ref });
        const pages = [
          ...new Set(
            (item?.prov || [])
              .filter((p) => summary?.pages?.some((sp) => sp.image && sp.page_no === p.page_no))
              .map((p) => p.page_no)
          ),
        ];
        if (pages.length === 1) {
          onChangeSelection((prev) => ({ ...prev, page: pages[0] }));
          if (mode === "compare") setRightSubMode("geometry");
          else setMode("native");
          setOcrFallbackNotice(
            t(
              "OCR-Fundstelle im nativen Docling-Seitenbild markiert (kein PDF-Textlayer-Treffer).",
              "OCR span highlighted via native Docling bounding box (no PDF text-layer match)."
            )
          );
        }
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [docId, dispatchPdfSearch, selection?.ref, webDoc, hasPages, summary, mode, t]);

  useEffect(() => {
    if (usesPdfViewer && (mode === "compare" || mode === "original")) {
      if (lastPdfReportedPageRef.current === selection?.page) {
        lastPdfReportedPageRef.current = null;
        return;
      }
      dispatchPdfSearch();
    }
  }, [usesPdfViewer, mode, selection?.ref, selection?.page, selection?.occurrence, dispatchPdfSearch]);

  // Highlight .txt original frame
  const handleOriginalLoad = useCallback(() => {
    if (!isPlainTxt || !originalFrameRef.current || !webDoc) return;
    if (selection?.ref && selection?.occurrence) {
      const item = resolveDocumentItem(webDoc, { $ref: selection.ref });
      markPlainTextFrame(originalFrameRef.current, item, selection.occurrence, {
        preview: false,
        scroll: true,
      });
    }
  }, [isPlainTxt, webDoc, selection]);

  useEffect(() => {
    handleOriginalLoad();
  }, [handleOriginalLoad]);

  // Load table cells when a table ref is selected
  useEffect(() => {
    if (!docId || !tableSelected || !selection?.ref) {
      setCellsData(null);
      return;
    }
    const r0 = selection?.occurrence?.row ?? cellRowStart;
    const c0 = selection?.occurrence?.column ?? cellColStart;
    const params = new URLSearchParams({
      id: docId,
      ref: selection.ref,
      start: r0,
      column: c0,
      search: cellSearch,
      offset: 0,
    });
    if (summary?.version) params.set("version", summary.version);
    api(`cells?${params}`)
      .then(setCellsData)
      .catch((err) => toast.error(err.message));
  }, [docId, tableSelected, selection?.ref, selection?.occurrence, cellRowStart, cellColStart, cellSearch, summary?.version]);

  // Drag split handle
  useEffect(() => {
    const onMove = (e) => {
      if (!draggingSplit.current) return;
      const host = document.getElementById("lx-split-host");
      if (!host) return;
      const rect = host.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      setSplitPct(Math.max(24, Math.min(76, pct)));
    };
    const onUp = () => {
      draggingSplit.current = false;
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, []);

  // Load elements directory when modal opens
  useEffect(() => {
    if (!elementsModalOpen || !docId) return;
    const params = new URLSearchParams({
      id: docId,
      search: elementsQuery,
      offset: elementsOffset,
    });
    if (summary?.version) params.set("version", summary.version);
    api(`elements?${params}`)
      .then(setElementsData)
      .catch((e) => toast.error(e.message));
  }, [elementsModalOpen, docId, elementsQuery, elementsOffset, summary?.version]);

  // Load model-input ledger
  useEffect(() => {
    if (!modelInputOpen || !docId) return;
    const targetRun = modelInputRunId || docBundle?.runs?.[0]?.id || "";
    const params = new URLSearchParams({ id: docId });
    if (targetRun) params.set("run", targetRun);
    api(`model-input?${params}`)
      .then(setModelInputData)
      .catch((e) => toast.error(e.message));
  }, [modelInputOpen, docId, modelInputRunId, docBundle?.runs]);

  const versionOptions = useMemo(() => {
    if (!summary) return [];
    const seen = new Map();
    for (const v of summary.versions || []) {
      if (v.version !== summary.base_version) seen.set(v.version, v);
    }
    return [
      ["", `${t("Basis", "Base")} · ${shortHash(summary.base_version)}`],
      ...[...seen.values()].map((v) => [
        v.version,
        `${v.configuration?.model || "Docling"} · ${shortHash(v.version)}`,
      ]),
    ];
  }, [summary, t]);

  const pageOptions = useMemo(() => {
    if (!summary?.pages) return [];
    return [
      ["", t("Seite wählen", "Pick Page")],
      ...summary.pages
        .filter((p) => p.image)
        .map((p) => [String(p.page_no), `${t("Seite", "Page")} ${p.page_no}`]),
    ];
  }, [summary, t]);

  if (!docId) {
    return (
      <div className="lx-page">
        <div className="lx-empty-state">
          <FileText size={28} strokeWidth={1.5} className="lx-icon-muted" />
          <h2>{t("Kein Dokument im Quelleninspektor geöffnet", "No Document Open in Source Inspector")}</h2>
          <p>
            {t(
              "Wähle ein Dokument aus dem Korpus oder klicke in einem Finding auf ‚Original prüfen‘, um Originaldatei und Docling-Struktur synchron zu vergleichen.",
              "Pick a document below or click 'Inspect Original' on any Finding to compare original artifact and Docling structure side-by-side."
            )}
          </p>
          {files.length > 0 ? (
            <div style={{ width: 320 }}>
              <Select
                value=""
                placeholder={t("Dokument direkt öffnen …", "Open a document directly…")}
                onValueChange={(v) => {
                  if (v) {
                    onChangeSelection({
                      document: Number(v),
                      version: null,
                      page: null,
                      ref: null,
                      occurrence: null,
                    });
                  }
                }}
                options={files.map((f) => [String(f.id), f.name])}
              />
            </div>
          ) : (
            <button
              type="button"
              className="lx-btn lx-btn-primary"
              onClick={() => onNavigate("documents")}
            >
              {t("Zum Studienkorpus", "Open Study Corpus")}
            </button>
          )}
        </div>
      </div>
    );
  }

  const originalSrc = usesPdfViewer
    ? `/assets/pdf.html?document=${docId}&kind=${isOffice ? "office-pdf" : "pdf"}`
    : `/document/${docId}/original-view?theme=${theme}`;

  const structureQuery = new URLSearchParams();
  if (summary?.version && summary.version !== summary.base_version) {
    structureQuery.set("version", summary.version);
  }
  if (selection?.ref) structureQuery.set("ref", selection.ref);
  if (selection?.presentation) structureQuery.set("presentation", selection.presentation);
  const structureSrc = `/document/${docId}/view?${structureQuery.toString()}`;

  const matchingDocRuns = (docBundle?.runs || []).filter(
    (r) => r.result?.document_version === summary?.version && r.result?.observations?.length
  );
  const activeAnchorRun =
    matchingDocRuns.find((r) => r.id === selection?.runId) || matchingDocRuns[0] || null;
  const selectedPicItem =
    selection?.ref?.startsWith("#/pictures/") && webDoc
      ? resolveDocumentItem(webDoc, { $ref: selection.ref })
      : null;

  const saveNativeExport = async (exportKind = "native") => {
    try {
      const res = await api("save-export", {
        kind: exportKind,
        document: docId,
        version: summary?.version || null,
      });
      toast.success(
        res?.path
          ? `${t("Gespeichert unter", "Saved to")} ${res.path}`
          : t("Im Ausgabeordner abgelegt", "Saved to output folder")
      );
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <div className={`lx-inspector-shell${focusMode ? " is-fullscreen" : ""}`}>
      <h1 className="sr-only">{t("Quelleninspektor", "Source Inspector")}</h1>
      {/* Crisp Single-Row Inspector Bar */}
      <header className="lx-inspector-bar">
        <div className="lx-toolbar-left min-w-0">
          {canGoBack && (
            <button type="button" className="lx-btn lx-btn-xs" onClick={onGoBack}>
              <ArrowLeft size={13} />
              <span>{t("Zurück", "Back")}</span>
            </button>
          )}

          <div style={{ width: 230, minWidth: 150 }}>
            <Select
              size="sm"
              value={String(docId)}
              onValueChange={(v) =>
                onChangeSelection({
                  document: Number(v),
                  version: null,
                  page: null,
                  ref: null,
                  occurrence: null,
                })
              }
              options={files.map((f) => [String(f.id), f.name])}
            />
          </div>

          <div className="lx-segmented">
            {[
              ["compare", t("Dual-View", "Dual-View"), !(file?.stored && file?.native)],
              ["original", t("Original", "Original"), !file?.stored],
              ["structure", t("Struktur", "Structure"), !file?.native],
              ["native", t("Geometrie", "Geometry"), !hasPages],
            ].map(([k, lbl, dis]) => (
              <button
                key={k}
                type="button"
                disabled={dis}
                className={`lx-seg-btn${mode === k ? " is-active" : ""}`}
                onClick={() => setMode(k)}
              >
                {lbl}
              </button>
            ))}
          </div>

          {hasPages && (mode === "native" || mode === "compare") && (
            <div style={{ width: 130 }}>
              <Select
                size="sm"
                value={String(selection?.page || "")}
                onValueChange={(v) =>
                  onChangeSelection((prev) => ({ ...prev, page: v ? Number(v) : null }))
                }
                options={pageOptions}
              />
            </div>
          )}

          {versionOptions.length > 1 && (
            <div style={{ width: 170 }}>
              <Select
                size="sm"
                value={
                  summary?.version === summary?.base_version ? "" : summary?.version || ""
                }
                onValueChange={(v) =>
                  onChangeSelection((prev) => ({ ...prev, version: v || null }))
                }
                options={versionOptions}
              />
            </div>
          )}
        </div>

        <div className="lx-toolbar-right">
          {nativeConfidence?.mean_grade && (
            <span className="lx-tag tabular">
              <span>
                Docling: {nativeConfidence.mean_grade}
                {nativeConfidence.mean_score != null
                  ? ` (${Math.round(nativeConfidence.mean_score * 100)}%)`
                  : ""}
              </span>
              <InfoPopover
                title={t("Docling Konvertierungs-Güte", "Docling Conversion Confidence")}
                align="end"
              >
                <p>
                  {t(
                    "Lokale Struktur- und Erkennungsgüte aus Docling ConversionResult:",
                    "Local layout and recognition confidence reported by Docling:"
                  )}
                </p>
                <p className="tabular">
                  {[
                    nativeConfidence.layout_score != null
                      ? `Layout: ${Math.round(nativeConfidence.layout_score * 100)}%`
                      : null,
                    nativeConfidence.parse_score != null
                      ? `Parse: ${Math.round(nativeConfidence.parse_score * 100)}%`
                      : null,
                    nativeConfidence.table_score != null
                      ? `Tabellen: ${Math.round(nativeConfidence.table_score * 100)}%`
                      : null,
                    nativeConfidence.ocr_score != null
                      ? `OCR: ${Math.round(nativeConfidence.ocr_score * 100)}%`
                      : null,
                  ]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </p>
              </InfoPopover>
            </span>
          )}
          {selection?.ref && (
            <button
              type="button"
              className="lx-btn lx-btn-xs"
              onClick={() =>
                onChangeSelection((prev) => ({
                  ...prev,
                  ref: null,
                  occurrence: null,
                  runId: null,
                }))
              }
              title={selection.ref}
            >
              <RotateCcw size={11} />
              <span className="tabular">{selection.ref}</span>
            </button>
          )}

          {mode !== "original" && (
            <div className="lx-zoom-pill tabular">
              <button
                type="button"
                className="lx-icon-btn"
                onClick={() => setZoom((z) => Math.max(60, z - 15))}
                aria-label="Zoom out"
              >
                <Minus size={12} />
              </button>
              <span>{zoom}%</span>
              <button
                type="button"
                className="lx-icon-btn"
                onClick={() => setZoom((z) => Math.min(220, z + 15))}
                aria-label="Zoom in"
              >
                <Plus size={12} />
              </button>
            </div>
          )}

          {selectedPicItem && (
            <div className="lx-segmented">
              <button
                type="button"
                className={`lx-seg-btn${selection?.presentation === "picture" ? " is-active" : ""}`}
                onClick={() => {
                  if (mode === "compare") {
                    setRightSubMode("reader");
                  } else if (mode !== "structure") {
                    setMode("structure");
                  }
                  onChangeSelection((prev) => ({
                    ...prev,
                    presentation: prev.presentation === "picture" ? null : "picture",
                  }));
                }}
              >
                {t("Bildfokus", "Image")}
              </button>
              {selectedPicItem.meta?.tabular_chart && (
                <button
                  type="button"
                  className={`lx-seg-btn${selection?.presentation === "chart" ? " is-active" : ""}`}
                  onClick={() => {
                    if (mode === "compare") {
                      setRightSubMode("reader");
                    } else if (mode !== "structure") {
                      setMode("structure");
                    }
                    onChangeSelection((prev) => ({
                      ...prev,
                      presentation: prev.presentation === "chart" ? null : "chart",
                    }));
                  }}
                >
                  {t("Diagrammdaten", "Chart Table")}
                </button>
              )}
            </div>
          )}

          {file?.native && (
            <>
              {activeAnchorRun && (
                <button
                  type="button"
                  className="lx-btn lx-btn-xs"
                  onClick={() => setAnchorsModalOpen(true)}
                >
                  <BookOpen size={12} />
                  <span>
                    {t("Belege", "Anchors")} ({activeAnchorRun.result?.observations?.length || 0})
                  </span>
                </button>
              )}
              <button
                type="button"
                className="lx-btn lx-btn-xs"
                onClick={() => setElementsModalOpen(true)}
              >
                <Layers size={12} />
                <span>{t("Elemente", "Elements")}</span>
              </button>
              <button
                type="button"
                className="lx-btn lx-btn-xs"
                disabled={!docBundle?.runs?.length}
                title={
                  docBundle?.runs?.length
                    ? t("Protokollierten Modell-Input anzeigen", "Inspect protocolled LLM input")
                    : t("Zuerst Stufe A ausführen, um den Modell-Input zu prüfen", "Run Stage A first to inspect LLM input")
                }
                onClick={() => setModelInputOpen(true)}
              >
                <Code2 size={12} />
                <span>{t("Modell-Input", "LLM Input")}</span>
              </button>
              <a
                className="lx-btn lx-btn-xs lx-btn-ghost"
                href={`/document/${docId}/markdown${
                  summary?.version ? `?version=${encodeURIComponent(summary.version)}` : ""
                }`}
                target="_blank"
                rel="noreferrer"
                title={t("DoclingDocument als Markdown (.md) herunterladen", "Download DoclingDocument as Markdown (.md)")}
              >
                <Download size={12} />
                <span>.MD</span>
              </a>
              <a
                className="lx-btn lx-btn-xs lx-btn-ghost"
                href={`/document/${docId}/native${
                  summary?.version ? `?version=${encodeURIComponent(summary.version)}` : ""
                }`}
                target="_blank"
                rel="noreferrer"
                title={t("DoclingDocument JSON herunterladen", "Download DoclingDocument JSON")}
              >
                <Download size={12} />
                <span>JSON</span>
              </a>
              <button
                type="button"
                className="lx-btn lx-btn-xs lx-btn-ghost"
                onClick={() => saveNativeExport("markdown")}
                title={t("Docling Markdown im Ausgabeordner ablegen", "Save Docling Markdown to output folder")}
              >
                <span>{t("MD-Ablage", "Save MD")}</span>
              </button>
              <button
                type="button"
                className="lx-btn lx-btn-xs lx-btn-ghost"
                onClick={() => saveNativeExport("native")}
                title={t("Docling JSON im Ausgabeordner ablegen", "Save Docling JSON to output folder")}
              >
                <span>{t("JSON-Ablage", "Save JSON")}</span>
              </button>
            </>
          )}

          {file?.stored && (
            <a
              className="lx-btn lx-btn-xs lx-btn-ghost"
              href={`/document/${docId}/original`}
              target="_blank"
              rel="noreferrer"
              title={t("Original herunterladen", "Download original")}
            >
              <Download size={12} />
              <span>Original</span>
            </a>
          )}

          <button
            type="button"
            className="lx-btn lx-btn-xs"
            onClick={() => setFocusMode((f) => !f)}
          >
            {focusMode ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
          </button>
        </div>
      </header>

      {/* Provenance Info Strip */}
      <div className="lx-provenance-bar">
        <span className="truncate">
          {loading
            ? t("Dokumentdaten werden geladen …", "Loading document provenance…")
            : [
                file?.name,
                summary?.version ? `Docling ${shortHash(summary.version)}` : null,
                selection?.runId ? `${t("Lauf", "Run")} #${selection.runId}` : null,
                selection?.ref || null,
                selection?.page ? `${t("Seite", "Page")} ${selection.page}` : null,
                ocrFallbackNotice || null,
                isOffice && summary?.office_renderer
                  ? t(
                      "Links: abgeleitetes LibreOffice-PDF · Rechts: native Docling-Struktur/Boxen",
                      "Left: derived LibreOffice PDF · Right: native Docling structure/boxes"
                    )
                  : t(
                      "Synchroner Vergleich von unverändertem Original und Docling-Repräsentation",
                      "Synchronous comparison of immutable original and Docling structure"
                    ),
              ]
                .filter(Boolean)
                .join(" · ")}
        </span>
      </div>

      {/* Active Finding / Relation Context Strip when inspecting from Synthesis or Graph */}
      {selection?.findingContext && (
        <div className="lx-finding-context-strip">
          <div className="lx-row-wrap" style={{ minWidth: 0, flex: 1 }}>
            <span className="lx-mono-tag tabular" style={{ background: "var(--brand)", color: "#fff" }}>
              <Sparkles size={11} style={{ display: "inline", marginRight: 4 }} />
              {selection.findingContext.kind === "finding" ? "C" : "B"} #{selection.findingContext.id}
            </span>
            <strong className="truncate" style={{ maxWidth: 360 }}>
              {selection.findingContext.title}
            </strong>
            <span className="lx-muted lx-text-xs">· {t("Belegkette:", "Evidence chain:")}</span>
            {(selection.findingContext.anchors || []).map((ancItem, idx) => {
              const obsEntry = (workspace?.result?.observations || []).find(
                (o) => observationKey(o.ref) === observationKey(ancItem.ref)
              );
              const resolvedMatch = ancItem.match || obsEntry?.source_check?.matches?.[0] || null;
              const isCurrent =
                Number(ancItem.ref?.document) === Number(docId) &&
                resolvedMatch?.ref === selection?.ref &&
                Number(ancItem.ref?.run || 0) === Number(selection?.runId || 0);
              const chipDocName =
                ancItem.docName ||
                obsEntry?.name ||
                files.find((f) => f.id === ancItem.ref?.document)?.name ||
                `Dok #${ancItem.ref?.document}`;
              return (
                <button
                  key={`${observationKey(ancItem.ref)}-${idx}`}
                  type="button"
                  className={`lx-finding-anchor-chip${isCurrent ? " is-active" : ""}`}
                  title={ancItem.statement || obsEntry?.effective?.statement || ""}
                  onClick={() => {
                    if (!resolvedMatch) return;
                    lastPdfReportedPageRef.current = null;
                    setOcrFallbackNotice("");
                    onChangeSelection((prev) => ({
                      ...prev,
                      document: ancItem.ref.document,
                      version: ancItem.ref.version || null,
                      page: resolvedMatch.prov?.length === 1 ? resolvedMatch.prov[0].page_no : null,
                      ref: resolvedMatch.ref || null,
                      occurrence: resolvedMatch,
                      runId: ancItem.ref.run || null,
                      findingContext: prev.findingContext,
                    }));
                  }}
                >
                  <span>{ancItem.role ? `${ancItem.role}: ` : ""}</span>
                  <span className="truncate" style={{ maxWidth: 140 }}>
                    {chipDocName}
                  </span>
                  {resolvedMatch?.ref && <span className="tabular">({resolvedMatch.ref})</span>}
                </button>
              );
            })}
          </div>
          <button
            type="button"
            className="lx-icon-btn"
            onClick={() =>
              onChangeSelection((prev) => ({ ...prev, findingContext: null }))
            }
            title={t("Finding-Fokusleiste schließen", "Dismiss Finding context strip")}
          >
            <X size={13} />
          </button>
        </div>
      )}

      {/* Resizable Split-Pane Surface */}
      <div id="lx-split-host" className="lx-split-surface">
        {(mode === "original" || mode === "compare") && file?.stored && (
          <section
            className="lx-split-pane"
            style={{
              width: mode === "compare" ? `${splitPct}%` : "100%",
              flex: mode === "compare" ? "none" : 1,
            }}
          >
            <div className="lx-pane-label">
              <span>{t("Originaldokument", "Original Artifact")}</span>
              <span className="lx-muted">{usesPdfViewer ? "PDF.js" : "Native"}</span>
            </div>
            <iframe
              ref={originalFrameRef}
              title={t("Originalansicht", "Original View")}
              src={originalSrc}
              sandbox={
                usesPdfViewer ? "allow-scripts allow-same-origin" : "allow-same-origin"
              }
              onLoad={handleOriginalLoad}
              className="lx-doc-frame"
            />
          </section>
        )}

        {mode === "compare" && file?.stored && file?.native && (
          <div
            className="lx-split-divider"
            role="separator"
            aria-orientation="vertical"
            onPointerDown={() => {
              draggingSplit.current = true;
            }}
          />
        )}

        {mode !== "original" && file?.native && (
          <section className="lx-split-pane" style={{ flex: 1 }}>
            <div className="lx-pane-label">
              <span>
                {showNativeGeometryInRightPane
                  ? t("Native Docling-Seitengeometrie", "Native Docling Page Geometry")
                  : tableSelected && rightSubMode === "cells"
                  ? `${t("Zellen-Inspektor", "Cell Inspector")} ${selection?.ref}`
                  : t("Strukturierte Docling-Lesefassung", "Structured Docling Reading Order")}
              </span>
              <div className="lx-row-gap">
                {mode === "compare" && hasPages && (
                  <div className="lx-segmented" style={{ transform: "scale(0.92)", transformOrigin: "right center" }}>
                    <button
                      type="button"
                      className={`lx-seg-btn${rightSubMode === "reader" ? " is-active" : ""}`}
                      onClick={() => setRightSubMode("reader")}
                    >
                      {t("Lesefassung", "Structure")}
                    </button>
                    <button
                      type="button"
                      className={`lx-seg-btn${rightSubMode === "geometry" ? " is-active" : ""}`}
                      onClick={() => setRightSubMode("geometry")}
                    >
                      {t("Geometrie", "Geometry")}
                    </button>
                  </div>
                )}
                <span className="lx-muted tabular">{shortHash(summary?.version)}</span>
              </div>
            </div>

            {showNativeGeometryInRightPane ? (
              <div className="lx-docling-scroll">
                <div style={{ width: `${zoom}%`, margin: "0 auto" }}>
                  <docling-img ref={viewerRef} />
                </div>
              </div>
            ) : tableSelected && rightSubMode === "cells" && cellsData ? (
              <div className="lx-cells-inspector">
                <div className="lx-cells-toolbar">
                  <button
                    type="button"
                    className="lx-btn lx-btn-xs"
                    onClick={() => setRightSubMode("reader")}
                  >
                    <ArrowLeft size={11} />
                    <span>{t("Zur Lesefassung", "Back to Structure")}</span>
                  </button>
                  <span className="lx-muted lx-text-xs tabular">
                    {cellsData.rows} × {cellsData.columns} {t("Zellen", "cells")}
                  </span>
                  <input
                    type="search"
                    className="lx-input lx-input-sm"
                    style={{ width: 200 }}
                    value={cellSearch}
                    onChange={(e) => setCellSearch(e.target.value)}
                    placeholder={t("Zelle suchen …", "Search cell…")}
                  />
                  <button
                    type="button"
                    className="lx-btn lx-btn-xs"
                    onClick={() => setCellRowStart((r) => Math.max(0, r - 30))}
                  >
                    −30 {t("Zeilen", "Rows")}
                  </button>
                  <button
                    type="button"
                    className="lx-btn lx-btn-xs"
                    onClick={() => setCellRowStart((r) => r + 30)}
                  >
                    +30 {t("Zeilen", "Rows")}
                  </button>
                </div>
                <div className="lx-cells-list">
                  {(cellsData.cells || []).map((c, idx) => {
                    const occ = selection?.occurrence;
                    const isHit =
                      occ?.row === c.start_row_offset_idx &&
                      (occ?.column === c.start_col_offset_idx ||
                        (occ?.modality === "table_row" &&
                          c.start_col_offset_idx < (occ?.column_end ?? 999)));
                    return (
                      <div key={idx} className={`lx-cell-row${isHit ? " is-hit" : ""}`}>
                        <span className="lx-mono-tag tabular">
                          Z.{c.start_row_offset_idx + 1} · Sp.{c.start_col_offset_idx + 1}
                        </span>
                        <span className="lx-cell-text">{c.text}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : webDoc ? (
              <DoclingReader
                webDoc={webDoc}
                selection={selection}
                zoom={zoom}
                onSelectItem={(item, pageNo) => {
                  setOcrFallbackNotice("");
                  onChangeSelection((prev) => ({
                    ...prev,
                    ref: item.self_ref,
                    page: pageNo || prev.page,
                    occurrence: item.text ? { quote: item.text } : null,
                    presentation: null,
                    runId: null,
                  }));
                }}
                onOpenLargeTable={(tableRef) => {
                  onChangeSelection((prev) => ({
                    ...prev,
                    ref: tableRef,
                    presentation: null,
                    runId: null,
                  }));
                  setRightSubMode("cells");
                }}
              />
            ) : (
              <iframe
                title={t("Docling-Struktur", "Docling Structure")}
                src={structureSrc}
                sandbox="allow-same-origin"
                className="lx-doc-frame"
                style={{ zoom: zoom / 100 }}
              />
            )}
          </section>
        )}
      </div>

      {/* Document Stage A Anchors Modal */}
      <Modal
        open={anchorsModalOpen}
        onOpenChange={setAnchorsModalOpen}
        title={`${t("Verankerte A-Beobachtungen", "Anchored Stage A Observations")}${
          activeAnchorRun ? ` · #${activeAnchorRun.id}` : ""
        }`}
        subtitle={file?.name}
        width={680}
      >
        <div className="lx-elements-scroll">
          {(activeAnchorRun?.result?.observations || []).map((obs) => {
            const anchors = (obs.source_ids || [])
              .map((sid) => activeAnchorRun.result?.sources?.[sid])
              .filter(Boolean);
            if (!anchors.length) return null;
            return (
              <div key={obs.id} className="lx-card lx-card-subtle" style={{ marginBottom: 8 }}>
                <div className="lx-between" style={{ marginBottom: 4 }}>
                  <span className="lx-mono-tag tabular">{obs.id}</span>
                  <span className="lx-muted lx-text-xs tabular">
                    {anchors.map((a) => a.ref).join(", ")}
                  </span>
                </div>
                <p className="lx-text-xs" style={{ marginBottom: 6 }}>
                  {obs.statement}
                </p>
                <div className="lx-btn-row">
                  {anchors.map((anc, aIdx) => (
                    <button
                      key={aIdx}
                      type="button"
                      className="lx-btn lx-btn-xs"
                      onClick={() => {
                        setAnchorsModalOpen(false);
                        setOcrFallbackNotice("");
                        onChangeSelection((prev) => ({
                          ...prev,
                          ref: anc.ref,
                          page: anc.prov?.length === 1 ? anc.prov[0].page_no : prev.page,
                          occurrence: anc,
                          runId: activeAnchorRun.id,
                        }));
                      }}
                    >
                      <span>
                        {anc.ref}
                        {anc.prov?.length === 1 ? ` · S.${anc.prov[0].page_no}` : ""}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </Modal>

      {/* Elements Browser Modal */}
      <Modal
        open={elementsModalOpen}
        onOpenChange={setElementsModalOpen}
        title={t("Native Docling-Elemente", "Native Docling Elements")}
        subtitle={file?.name}
        width={640}
      >
        <div className="lx-form-stack">
          <input
            type="search"
            className="lx-input"
            value={elementsQuery}
            onChange={(e) => {
              setElementsOffset(0);
              setElementsQuery(e.target.value);
            }}
            placeholder={t("Text, Label oder #/texts/ suchen …", "Filter text, label, or ref…")}
          />
          <div className="lx-elements-scroll">
            {(elementsData?.items || []).map((it) => (
              <button
                key={it.ref}
                type="button"
                className="lx-element-row"
                onClick={() => {
                  setElementsModalOpen(false);
                  onChangeSelection((prev) => ({
                    ...prev,
                    ref: it.ref,
                    page: it.pages?.length === 1 ? it.pages[0] : prev.page,
                    occurrence: it.text ? { quote: it.text } : null,
                  }));
                }}
              >
                <span className="lx-mono-tag tabular">{it.ref}</span>
                <span className="lx-muted lx-text-xs">{it.label}</span>
                <span className="truncate flex-1" style={{ textAlign: "left" }}>
                  {it.text}
                </span>
              </button>
            ))}
          </div>
        </div>
      </Modal>

      {/* Protocolled Model Input Modal */}
      <Modal
        open={modelInputOpen}
        onOpenChange={setModelInputOpen}
        title={t("Protokollierte Modellanfrage (Stufe A)", "Protocolled Stage A Model Input")}
        subtitle={t(
          "Exakter Eingabetext und Parameter, die an das Sprachmodell gesendet wurden.",
          "Exact serialized document representation and parameters sent to the LLM."
        )}
        width={720}
      >
        <div className="lx-form-stack">
          {docBundle?.runs?.length > 1 && (
            <Select
              size="sm"
              value={String(modelInputRunId || docBundle.runs[0].id)}
              onValueChange={setModelInputRunId}
              options={docBundle.runs.map((r) => [
                String(r.id),
                `A #${r.id} · ${r.result?.model || "Lauf"}`,
              ])}
            />
          )}
          <pre className="lx-code-pre">
            {modelInputData
              ? typeof modelInputData === "string"
                ? modelInputData
                : JSON.stringify(modelInputData, null, 2)
              : t("Lade Protokoll …", "Loading receipt…")}
          </pre>
        </div>
      </Modal>
    </div>
  );
}
