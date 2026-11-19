import { Position } from "@xyflow/react";
import dagre from "@dagrejs/dagre";

export const CARD_W = 276;
export const CARD_H = 104;

/**
 * Splits graph into connected components, lays out each multi-node component via Dagre LR,
 * and packs components onto a 16:9 widescreen shelf grid (plus a neat 4-column grid for singletons)
 * so fitView() always renders cards at crisp, readable scale.
 */
export function computeWidescreenLayout(rawNodes, rawEdges) {
  if (!rawNodes.length) return [];

  const nodeById = new Map(rawNodes.map((n) => [n.id, n]));
  const adj = new Map(rawNodes.map((n) => [n.id, new Set()]));
  for (const e of rawEdges) {
    if (adj.has(e.source) && adj.has(e.target)) {
      adj.get(e.source).add(e.target);
      adj.get(e.target).add(e.source);
    }
  }

  const visited = new Set();
  const multiComponents = [];
  const singletons = [];

  for (const n of rawNodes) {
    if (visited.has(n.id)) continue;
    const queue = [n.id];
    visited.add(n.id);
    const compIds = [];
    while (queue.length) {
      const cur = queue.shift();
      compIds.push(cur);
      for (const nb of adj.get(cur) || []) {
        if (!visited.has(nb)) {
          visited.add(nb);
          queue.push(nb);
        }
      }
    }
    if (compIds.length === 1) {
      singletons.push(nodeById.get(compIds[0]));
    } else {
      multiComponents.push(compIds);
    }
  }

  multiComponents.sort((a, b) => b.length - a.length);

  const positioned = new Map();
  const MAX_SHELF_WIDTH = 1760;
  const GAP_X = 88;
  const GAP_Y = 64;

  let cursorX = 0;
  let cursorY = 0;
  let rowHeight = 0;

  for (const compIds of multiComponents) {
    const idSet = new Set(compIds);
    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({
      rankdir: "LR",
      ranksep: 88,
      nodesep: 20,
      marginx: 0,
      marginy: 0,
    });

    for (const id of compIds) {
      g.setNode(id, { width: CARD_W, height: CARD_H });
    }
    for (const e of rawEdges) {
      if (idSet.has(e.source) && idSet.has(e.target)) {
        g.setEdge(e.source, e.target);
      }
    }
    dagre.layout(g);

    const MAX_PER_COL = 5;
    const rawCoords = compIds.map((id) => {
      const p = g.node(id);
      return { id, x: p?.x ?? 0, y: p?.y ?? 0 };
    });
    rawCoords.sort((a, b) => a.x - b.x || a.y - b.y);

    const rankGroups = [];
    for (const item of rawCoords) {
      const last = rankGroups[rankGroups.length - 1];
      if (last && Math.abs(item.x - last.baseX) < 40) {
        last.items.push(item);
      } else {
        rankGroups.push({ baseX: item.x, items: [item] });
      }
    }

    const adjusted = new Map();
    let extraShiftX = 0;
    for (const rg of rankGroups) {
      const count = rg.items.length;
      const subCols = Math.ceil(count / MAX_PER_COL);
      const rowsInGroup = Math.ceil(count / subCols);
      rg.items.forEach((it, idx) => {
        const sc = Math.floor(idx / rowsInGroup);
        const sr = idx % rowsInGroup;
        const xVal = rg.baseX + extraShiftX + sc * (CARD_W + 34);
        const yVal = subCols > 1 ? sr * (CARD_H + 20) + CARD_H / 2 : it.y;
        adjusted.set(it.id, { x: xVal, y: yVal });
      });
      if (subCols > 1) {
        extraShiftX += (subCols - 1) * (CARD_W + 34);
      }
    }

    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const id of compIds) {
      const p = adjusted.get(id);
      const x0 = (p?.x ?? 0) - CARD_W / 2;
      const y0 = (p?.y ?? 0) - CARD_H / 2;
      minX = Math.min(minX, x0);
      minY = Math.min(minY, y0);
      maxX = Math.max(maxX, x0 + CARD_W);
      maxY = Math.max(maxY, y0 + CARD_H);
    }
    const compW = Math.max(CARD_W, maxX - minX);
    const compH = Math.max(CARD_H, maxY - minY);

    if (cursorX > 0 && cursorX + compW > MAX_SHELF_WIDTH) {
      cursorX = 0;
      cursorY += rowHeight + GAP_Y;
      rowHeight = 0;
    }

    for (const id of compIds) {
      const p = adjusted.get(id);
      const localX = (p?.x ?? 0) - CARD_W / 2 - minX;
      const localY = (p?.y ?? 0) - CARD_H / 2 - minY;
      positioned.set(id, { x: cursorX + localX, y: cursorY + localY });
    }

    cursorX += compW + GAP_X;
    rowHeight = Math.max(rowHeight, compH);
  }

  if (multiComponents.length > 0 && singletons.length > 0) {
    cursorY += rowHeight + GAP_Y;
  }

  const COLS = 4;
  singletons.forEach((n, idx) => {
    const col = idx % COLS;
    const row = Math.floor(idx / COLS);
    positioned.set(n.id, {
      x: col * (CARD_W + 28),
      y: cursorY + row * (CARD_H + 22),
    });
  });

  return rawNodes.map((n) => ({
    ...n,
    width: CARD_W,
    height: CARD_H,
    initialWidth: CARD_W,
    initialHeight: CARD_H,
    position: positioned.get(n.id) || { x: 0, y: 0 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
  }));
}
