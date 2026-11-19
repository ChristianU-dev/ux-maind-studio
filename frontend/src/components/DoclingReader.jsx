import React, { useEffect, useMemo, useRef, useState } from "react";
import { Image as ImageIcon, Layers, Search, Table as TableIcon, Type } from "lucide-react";
import { resolveDocumentItem } from "../../components.js";
import { usePrefs } from "../lib/i18n.jsx";
import { InfoPopover, Switch } from "./ui.jsx";

function formatSeconds(sec) {
  if (sec == null || !Number.isFinite(Number(sec))) return null;
  const total = Math.max(0, Math.floor(Number(sec)));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function collectReadingOrder(webDoc) {
  if (!webDoc) return [];
  const out = [];
  const visited = new Set();

  const walk = (refObj) => {
    const cref = typeof refObj === "string" ? refObj : refObj?.$ref || refObj?.cref;
    if (!cref || visited.has(cref)) return;
    visited.add(cref);
    let node = null;
    try {
      node = resolveDocumentItem(webDoc, { $ref: cref });
    } catch {
      node = null;
    }
    if (!node) return;

    const isContainer =
      cref.startsWith("#/groups/") || cref === "#/body" || cref === "#/furniture";
    if (!isContainer && node.self_ref) {
      out.push(node);
    }
    if (Array.isArray(node.children)) {
      for (const child of node.children) {
        walk(child);
      }
    }
  };

  if (Array.isArray(webDoc.body?.children)) {
    for (const ch of webDoc.body.children) walk(ch);
  }
  if (Array.isArray(webDoc.furniture?.children)) {
    for (const ch of webDoc.furniture.children) walk(ch);
  }
  for (const group of ["texts", "tables", "pictures", "key_value_items", "form_items"]) {
    for (const item of webDoc[group] || []) {
      if (item?.self_ref && !visited.has(item.self_ref)) {
        visited.add(item.self_ref);
        out.push(item);
      }
    }
  }
  return out;
}

function decorateInlineStrikes(str, strikeSpans) {
  if (!Array.isArray(strikeSpans) || !strikeSpans.length || !str) return str;
  const target = strikeSpans.find((s) => s && str.includes(s));
  if (!target) return str;
  const idx = str.indexOf(target);
  return (
    <>
      {str.slice(0, idx)}
      <span className="lx-inline-strike">{target}</span>
      {decorateInlineStrikes(str.slice(idx + target.length), strikeSpans)}
    </>
  );
}

function renderHighlightedText(text, occurrence, strikeSpans) {
  const str = String(text || "");
  if (
    occurrence &&
    Number.isInteger(occurrence.start) &&
    Number.isInteger(occurrence.end) &&
    occurrence.start >= 0 &&
    occurrence.end > occurrence.start
  ) {
    const cps = Array.from(str);
    if (occurrence.end <= cps.length) {
      const before = cps.slice(0, occurrence.start).join("");
      const hit = cps.slice(occurrence.start, occurrence.end).join("");
      const after = cps.slice(occurrence.end).join("");
      return (
        <>
          {decorateInlineStrikes(before, strikeSpans)}
          <mark className="lx-reader-mark">{hit}</mark>
          {decorateInlineStrikes(after, strikeSpans)}
        </>
      );
    }
  }
  const quote = occurrence?.quote;
  if (!quote || typeof quote !== "string") {
    return decorateInlineStrikes(str, strikeSpans);
  }
  const idx = str.indexOf(quote);
  if (idx < 0) return decorateInlineStrikes(str, strikeSpans);
  return (
    <>
      {decorateInlineStrikes(str.slice(0, idx), strikeSpans)}
      <mark className="lx-reader-mark">{str.slice(idx, idx + quote.length)}</mark>
      {decorateInlineStrikes(str.slice(idx + quote.length), strikeSpans)}
    </>
  );
}

function renderVisionMarkdown(text, quote) {
  const str = String(text || "");
  if (quote && str.includes(quote)) {
    const idx = str.indexOf(quote);
    return (
      <>
        {str.slice(0, idx)}
        <mark className="lx-reader-mark">{str.slice(idx, idx + quote.length)}</mark>
        {str.slice(idx + quote.length)}
      </>
    );
  }
  const parts = str.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? (
      <strong key={i}>{p.slice(2, -2)}</strong>
    ) : (
      p
    )
  );
}

function buildTableMatrix(tableData, maxRows = 40, maxCols = 14) {
  if (!tableData) return null;
  const numRows = Number(tableData.num_rows || tableData.grid?.length || 0);
  const numCols = Number(tableData.num_cols || tableData.grid?.[0]?.length || 0);
  const rLimit = Math.min(numRows, maxRows);
  const cLimit = Math.min(numCols, maxCols);
  if (rLimit <= 0 || cLimit <= 0) return null;

  if (Array.isArray(tableData.grid) && tableData.grid.length > 0) {
    const rows = tableData.grid.slice(0, rLimit).map((row) =>
      (row || []).slice(0, cLimit).map((cell) => ({
        text: cell?.text ?? "",
        header: Boolean(cell?.column_header || cell?.row_header),
      }))
    );
    return { rows, numRows, numCols, truncated: numRows > rLimit || numCols > cLimit };
  }

  const cells = tableData.table_cells || [];
  if (!cells.length) return null;
  const matrix = Array.from({ length: rLimit }, () =>
    Array.from({ length: cLimit }, () => ({ text: "", header: false }))
  );
  for (const c of cells) {
    const r = c.start_row_offset_idx ?? 0;
    const col = c.start_col_offset_idx ?? 0;
    if (r >= 0 && r < rLimit && col >= 0 && col < cLimit) {
      matrix[r][col] = {
        text: c.text ?? "",
        header: Boolean(c.column_header || c.row_header),
      };
    }
  }
  return { rows: matrix, numRows, numCols, truncated: numRows > rLimit || numCols > cLimit };
}

function extractStructuredPairs(item) {
  const cells = item?.graph?.cells || [];
  const links = item?.graph?.links || [];
  if (cells.length) {
    const byId = new Map(cells.map((c) => [c.cell_id, c.text || c.orig || ""]));
    if (links.length) {
      return links
        .map((lk) => [byId.get(lk.source_cell_id) || "", byId.get(lk.target_cell_id) || ""])
        .filter(([k, v]) => k || v);
    }
    return cells.map((c) => [c.label || `#${c.cell_id}`, c.text || c.orig || ""]);
  }
  return [];
}

export function DoclingReader({
  webDoc,
  selection,
  zoom = 100,
  onSelectItem,
  onOpenLargeTable,
}) {
  const { t } = usePrefs();
  const [filterKind, setFilterKind] = useState("all"); // all | text | table | picture | notes
  const [pageSyncFilter, setPageSyncFilter] = useState(false);
  const [expandedTables, setExpandedTables] = useState({});
  const [query, setQuery] = useState("");
  const [showChartForRef, setShowChartForRef] = useState({});
  const itemRefs = useRef(new Map());

  const allItems = useMemo(() => collectReadingOrder(webDoc), [webDoc]);

  const counts = useMemo(() => {
    let text = 0;
    let table = 0;
    let picture = 0;
    let notes = 0;
    for (const it of allItems) {
      const ref = it.self_ref || "";
      if (it.content_layer === "notes") notes++;
      if (ref.startsWith("#/tables/")) table++;
      else if (ref.startsWith("#/pictures/")) picture++;
      else text++;
    }
    return { all: allItems.length, text, table, picture, notes };
  }, [allItems]);

  const visibleItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    return allItems.filter((it) => {
      const ref = it.self_ref || "";
      if (selection?.ref === ref) return true;
      if (pageSyncFilter && selection?.page) {
        const itemPages = (it.prov || []).map((p) => p.page_no);
        if (itemPages.length > 0 && !itemPages.includes(selection.page)) {
          return false;
        }
      }
      if (filterKind === "notes" && it.content_layer !== "notes") return false;
      if (filterKind === "table" && !ref.startsWith("#/tables/")) return false;
      if (filterKind === "picture" && !ref.startsWith("#/pictures/")) return false;
      if (
        filterKind === "text" &&
        (ref.startsWith("#/tables/") || ref.startsWith("#/pictures/"))
      ) {
        return false;
      }
      if (!q) return true;
      const desc = it.meta?.description?.text || "";
      const hay = `${ref} ${it.label || ""} ${it.text || ""} ${desc}`.toLowerCase();
      return hay.includes(q);
    });
  }, [allItems, filterKind, pageSyncFilter, selection?.page, query, selection?.ref]);

  // Smoothly scroll selected item into view, or scroll to active page's first item on PDF scroll
  useEffect(() => {
    if (selection?.ref) {
      const node = itemRefs.current.get(selection.ref);
      if (node && typeof node.scrollIntoView === "function") {
        node.scrollIntoView({ block: "center", behavior: "smooth" });
      }
      return;
    }
    if (selection?.page) {
      const firstOnPage = visibleItems.find((it) =>
        (it.prov || []).some((p) => p.page_no === selection.page)
      );
      if (firstOnPage?.self_ref) {
        const node = itemRefs.current.get(firstOnPage.self_ref);
        if (node && typeof node.scrollIntoView === "function") {
          node.scrollIntoView({ block: "start", behavior: "smooth" });
        }
      }
    }
  }, [selection?.ref, selection?.page, visibleItems.length]);

  return (
    <div className="lx-reader-wrap">
      <div className="lx-reader-toolbar">
        <div className="lx-row-wrap">
          <div className="lx-segmented">
            {[
              ["all", `${t("Alle", "All")} (${counts.all})`, Layers],
              ["text", `${t("Text", "Text")} (${counts.text})`, Type],
              ["table", `${t("Tabellen", "Tables")} (${counts.table})`, TableIcon],
              ["picture", `${t("Bilder/Folien", "Visuals")} (${counts.picture})`, ImageIcon],
              ...(counts.notes > 0
                ? [["notes", `${t("Notizen", "Notes")} (${counts.notes})`, Type]]
                : []),
            ].map(([k, lbl]) => (
              <button
                key={k}
                type="button"
                className={`lx-seg-btn${filterKind === k ? " is-active" : ""}`}
                onClick={() => setFilterKind(k)}
              >
                {lbl}
              </button>
            ))}
          </div>

          {selection?.page && (
            <label className="lx-inline-switch lx-text-xs">
              <Switch checked={pageSyncFilter} onCheckedChange={setPageSyncFilter} />
              <span>
                {t(`Nur S. ${selection.page}`, `Only p. ${selection.page}`)}
              </span>
            </label>
          )}

          <InfoPopover
            title={t("Vollständige Docling-Lesefassung", "Complete Docling Document View")}
          >
            <p>
              {t(
                "Zeigt das gesamte lokal strukturierte DoclingDocument (inkl. Word-Absätzen, Formatierungen/Streichungen, Tabellen, PowerPoint-Vortragsnotizen, Formularfeldern und Vision-Beschreibungen) zum direkten Vergleich.",
                "Renders the complete locally parsed DoclingDocument (including Word paragraphs, inline strikethroughs, full tables, PowerPoint speaker notes, form fields, and Vision descriptions) for side-by-side comparison."
              )}
            </p>
          </InfoPopover>
        </div>

        <div className="lx-search-wrap" style={{ width: 196 }}>
          <Search size={12} className="lx-search-icon" />
          <input
            type="search"
            className="lx-input lx-input-sm lx-search-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("Struktur filtern …", "Filter blocks…")}
          />
        </div>
      </div>

      <div className="lx-reader-scroll">
        <div
          className="lx-reader-paper"
          style={zoom !== 100 ? { fontSize: `${zoom}%` } : undefined}
        >
          {visibleItems.length === 0 ? (
            <div className="lx-pane-placeholder">
              {t("Keine Strukturblöcke für diesen Filter.", "No blocks match current filter.")}
            </div>
          ) : (
            visibleItems.map((item) => {
              const ref = item.self_ref;
              const isSelected = selection?.ref === ref;
              const pages = [
                ...new Set((item.prov || []).map((p) => p.page_no).filter(Boolean)),
              ];
              const track = (item.source || []).find(
                (s) => s?.voice || s?.start_time != null
              );
              const isHeading =
                item.label === "title" || item.label === "section_header";
              const isStruck = Boolean(item.formatting?.strikethrough);
              const inlineStrikes = item.meta?.ux_maind__strikethrough_spans || null;
              const tableStrikes = item.meta?.ux_maind__table_strikethrough || [];
              const isTable = ref.startsWith("#/tables/");
              const isPicture = ref.startsWith("#/pictures/");
              const isStructuredForm =
                ref.startsWith("#/key_value_items/") || ref.startsWith("#/form_items/");
              const activeOcc = isSelected ? selection?.occurrence : null;

              const isExpanded = Boolean(expandedTables[ref]);
              const tableMatrix = isTable
                ? buildTableMatrix(item.data, isExpanded ? 400 : 40, isExpanded ? 24 : 14)
                : null;
              const chartMatrix =
                isPicture && item.meta?.tabular_chart?.chart_data
                  ? buildTableMatrix(item.meta.tabular_chart.chart_data)
                  : null;
              const structuredPairs = isStructuredForm ? extractStructuredPairs(item) : [];
              const isSlideCtx = Boolean(
                item.meta?.ux_maind__slide_context || item.meta?.ux_maind__page_context
              );
              const vlmText = item.meta?.description?.text?.trim() || "";
              const picClass =
                item.meta?.classification?.predictions?.[0]?.class_name || "";

              return (
                <article
                  key={ref}
                  ref={(el) => {
                    if (el) itemRefs.current.set(ref, el);
                    else itemRefs.current.delete(ref);
                  }}
                  className={`lx-reader-item${isSelected ? " is-selected" : ""}`}
                  onClick={() => onSelectItem?.(item, pages[0] || null)}
                >
                  <div className="lx-reader-item-meta">
                    <div className="lx-row-wrap">
                      <span>{ref}</span>
                      {item.label && <span>· {item.label}</span>}
                      {item.content_layer === "notes" && (
                        <span className="lx-cap-pill" style={{ color: "var(--dot-active)" }}>
                          {t("Vortragsnotiz", "Speaker Note")}
                        </span>
                      )}
                      {item.content_layer === "furniture" && (
                        <span className="lx-cap-pill">
                          {t("Kopf-/Fußzeile", "Header/Footer")}
                        </span>
                      )}
                      {isSlideCtx && (
                        <span className="lx-cap-pill is-vision">
                          {t("Folien-/Seitenkontext", "Slide/Page Render")}
                        </span>
                      )}
                      {picClass && <span className="lx-cap-pill">{picClass}</span>}
                      {(isStruck || inlineStrikes?.length > 0) && (
                        <span className="lx-cap-pill" style={{ color: "var(--dot-warning)" }}>
                          {t("Streichung erkannt", "Strikethrough")}
                        </span>
                      )}
                      {track && (
                        <span className="lx-cap-pill">
                          {[
                            track.voice,
                            track.start_time != null
                              ? `${formatSeconds(track.start_time)}–${
                                  formatSeconds(track.end_time) || ""
                                }`
                              : null,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      )}
                    </div>
                    {pages.length > 0 && (
                      <span>
                        {t("S.", "p.")} {pages.join(", ")}
                      </span>
                    )}
                  </div>

                  {/* Structured Key-Value / Form Item */}
                  {isStructuredForm && (
                    <div className="lx-reader-table-wrap">
                      {structuredPairs.length > 0 ? (
                        <table className="lx-reader-table">
                          <tbody>
                            {structuredPairs.map(([k, v], pIdx) => (
                              <tr key={pIdx}>
                                <th style={{ width: "38%" }}>{k}</th>
                                <td>{v}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <div className="lx-reader-text">
                          {item.text || t("Strukturiertes Formularfeld", "Structured form item")}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Heading or Text Block */}
                  {!isTable && !isPicture && !isStructuredForm && (
                    <div
                      className={
                        isHeading
                          ? "lx-reader-heading"
                          : `lx-reader-text${isStruck ? " is-struck" : ""}`
                      }
                      style={{
                        fontWeight: !isHeading && item.formatting?.bold ? 600 : undefined,
                        fontStyle: item.formatting?.italic ? "italic" : undefined,
                        textDecoration: item.formatting?.underline && !isStruck ? "underline" : undefined,
                      }}
                    >
                      {renderHighlightedText(
                        item.text || item.orig || "",
                        activeOcc,
                        inlineStrikes
                      )}
                    </div>
                  )}

                  {/* Structured Table Block */}
                  {isTable && (
                    <div>
                      {tableMatrix ? (
                        <>
                          <div className="lx-reader-table-wrap">
                            <table className="lx-reader-table">
                              <tbody>
                                {tableMatrix.rows.map((r, rIdx) => (
                                  <tr key={rIdx}>
                                    {r.map((cell, cIdx) => {
                                      const occ = activeOcc;
                                      const rowEnd = occ?.row_end ?? (occ?.row != null ? occ.row + 1 : -1);
                                      const colEnd =
                                        occ?.column_end ??
                                        (occ?.column != null ? occ.column + 1 : 9999);
                                      const inRowRange =
                                        occ?.row != null && rIdx >= occ.row && rIdx < rowEnd;
                                      const inColRange =
                                        occ?.modality === "table_row"
                                          ? cIdx >= (occ.column ?? 0) && cIdx < colEnd
                                          : occ?.column != null && cIdx >= occ.column && cIdx < colEnd;
                                      const isHit = Boolean(occ && inRowRange && inColRange);
                                      const cellStrike = tableStrikes.find(
                                        (ts) => ts.row === rIdx && ts.column === cIdx
                                      );
                                      const Tag = cell.header || rIdx === 0 ? "th" : "td";
                                      return (
                                        <Tag
                                          key={cIdx}
                                          className={isHit ? "is-hit" : undefined}
                                        >
                                          {cellStrike
                                            ? decorateInlineStrikes(cell.text, cellStrike.struck)
                                            : cell.text}
                                        </Tag>
                                      );
                                    })}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          {(tableMatrix.truncated || isExpanded) && (
                            <div className="lx-between" style={{ marginTop: 6 }}>
                              <span className="lx-muted lx-text-xs tabular">
                                {t(
                                  `${tableMatrix.rows.length} von ${tableMatrix.numRows} Zeilen (${tableMatrix.numCols} Spalten)`,
                                  `${tableMatrix.rows.length} of ${tableMatrix.numRows} rows (${tableMatrix.numCols} cols)`
                                )}
                              </span>
                              <div className="lx-btn-row">
                                {tableMatrix.numRows > 40 && (
                                  <button
                                    type="button"
                                    className="lx-btn lx-btn-xs"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setExpandedTables((prev) => ({
                                        ...prev,
                                        [ref]: !prev[ref],
                                      }));
                                    }}
                                  >
                                    {isExpanded
                                      ? t("Kompaktansicht (40 Zeilen)", "Compact (40 rows)")
                                      : t(
                                          `Alle ${Math.min(400, tableMatrix.numRows)} Zeilen ausklappen`,
                                          `Expand all ${Math.min(400, tableMatrix.numRows)} rows`
                                        )}
                                  </button>
                                )}
                                {onOpenLargeTable && (
                                  <button
                                    type="button"
                                    className="lx-btn lx-btn-xs lx-btn-ghost"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      onOpenLargeTable(ref);
                                    }}
                                  >
                                    {t("Zellen-Suche", "Cell Search")}
                                  </button>
                                )}
                              </div>
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="lx-between">
                          <span className="lx-muted lx-text-xs">
                            {t("Große Tabelle (Zellen-Ansicht verfügbar)", "Large table (Cell Inspector available)")}
                          </span>
                          {onOpenLargeTable && (
                            <button
                              type="button"
                              className="lx-btn lx-btn-xs"
                              onClick={(e) => {
                                e.stopPropagation();
                                onOpenLargeTable(ref);
                              }}
                            >
                              {t("Zellen durchsuchen", "Browse Cells")}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Picture / Slide Render / Chart Block */}
                  {isPicture && (() => {
                    const isPicFocus = isSelected && selection?.presentation === "picture";
                    const chartExpanded = Boolean(
                      showChartForRef[ref] ??
                        (activeOcc?.chart_cell || (isSelected && selection?.presentation === "chart"))
                    );
                    return (
                      <div className={`lx-reader-figure${isPicFocus ? " is-picture-focus" : ""}`}>
                        {item.image?.uri && (
                          <img
                            src={item.image.uri}
                            alt={ref}
                            loading="lazy"
                            className="lx-reader-img"
                          />
                        )}
                        {vlmText && (
                          <div className="lx-reader-vlm-box">
                            <div className="lx-eyebrow" style={{ marginBottom: 3 }}>
                              {t("Abgeleitete Bildbeschreibung (Vision)", "Derived Vision Description")}
                            </div>
                            <div>{renderVisionMarkdown(vlmText, activeOcc?.quote)}</div>
                          </div>
                        )}
                        {chartMatrix && (
                          <div>
                            <button
                              type="button"
                              className="lx-btn lx-btn-xs"
                              onClick={(e) => {
                                e.stopPropagation();
                                setShowChartForRef((prev) => ({
                                  ...prev,
                                  [ref]: !chartExpanded,
                                }));
                              }}
                            >
                              {chartExpanded
                                ? t("Diagrammtabelle ausblenden", "Hide Chart Table")
                                : t("Abgeleitete Diagrammdaten anzeigen", "Show Extracted Chart Data")}
                            </button>
                            {chartExpanded && (
                              <div className="lx-reader-table-wrap" style={{ marginTop: 6 }}>
                                <table className="lx-reader-table">
                                  <tbody>
                                    {chartMatrix.rows.map((r, rIdx) => (
                                      <tr key={rIdx}>
                                        {r.map((c, cIdx) => {
                                          const chHit =
                                            activeOcc?.chart_cell &&
                                            activeOcc.chart_cell.row === rIdx &&
                                            activeOcc.chart_cell.column === cIdx;
                                          return (
                                            <td key={cIdx} className={chHit ? "is-hit" : undefined}>
                                              {c.text}
                                            </td>
                                          );
                                        })}
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </article>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
