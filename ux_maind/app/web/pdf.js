// Mozilla's public component integration: no own canvas, text layer or highlight geometry.
import * as pdfjs from "./generated/pdfjs/build/pdf.mjs";
import {
  EventBus,
  PDFLinkService,
  PDFFindController,
  PDFViewer,
} from "./generated/pdfjs/web/pdf_viewer.mjs";
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "./generated/pdfjs/build/pdf.worker.mjs",
  import.meta.url,
).href;
const $ = (id) => document.getElementById(id),
  params = new URLSearchParams(location.search);
const documentId = params.get("document"),
  kind = params.get("kind");
document.documentElement.dataset.theme =
  params.get("theme") === "dark" ? "dark" : "light";
const eventBus = new EventBus(),
  linkService = new PDFLinkService({
    eventBus,
    externalLinkTarget: 2,
    externalLinkRel: "noopener noreferrer",
  });
const findController = new PDFFindController({ eventBus, linkService });
const viewer = new PDFViewer({
  container: $("viewerContainer"),
  eventBus,
  linkService,
  findController,
  annotationMode: pdfjs.AnnotationMode.DISABLE,
});
window.addEventListener("unhandledrejection", (e) => {
  $("status").textContent = "PDF.js: " + String(e.reason?.message || e.reason);
});
linkService.setViewer(viewer);
let ready = false,
  pending = null,
  quote = "",
  anchorRef = null,
  anchorRequest = null,
  boundPage = null,
  preview = null,
  layoutRequest = 0,
  suppressPageEmit = false;
const surface = $("viewerContainer");
function find(query, type, previous, highlightAll) {
  eventBus.dispatch("find", {
    source: viewer,
    type,
    query,
    caseSensitive: false,
    entireWord: false,
    highlightAll,
    findPrevious: previous,
    matchDiacritics: false,
  });
}
function matchControls(total) {
  $("find-next").disabled = $("find-previous").disabled = !total;
}
function search(type = "", previous = false) {
  if (!ready) return;
  if (type !== "again") matchControls(0);
  $("status").textContent =
    "PDF-Textsuche läuft … keine verifizierte Pixelzuordnung.";
  find(quote, type, previous, !boundPage);
  if (!quote)
    $("status").textContent =
      "Information rechts ansteuern, um ihre Belegstelle hervorzuheben.";
}
function showSearch(open) {
  $("find-form").hidden = !open;
  $("find-toggle").setAttribute("aria-expanded", String(open));
}
function request(value) {
  if (!ready) {
    pending = value;
    return;
  }
  preview = null;
  boundPage =
    value.fixedPage && value.page <= viewer.pagesCount ? value.page : null;
  quote = typeof value.quote === "string" ? value.quote : "";
  anchorRef = typeof value.ref === "string" ? value.ref : null;
  anchorRequest = value.request;
  $("find-query").value = quote;
  $("viewerContainer").classList.toggle("unbound", Boolean(boundPage));
  if (quote) showSearch(true);
  cancelAnimationFrame(layoutRequest);
  layoutRequest = requestAnimationFrame(() => {
    suppressPageEmit = true;
    try {
      if (value.page && value.page <= viewer.pagesCount)
        viewer.scrollPageIntoView({ pageNumber: value.page });
      viewer.update();
      if (value.page && value.page <= viewer.pagesCount)
        viewer.currentPageNumber = value.page;
    } finally {
      queueMicrotask(() => {
        suppressPageEmit = false;
      });
    }
    search("source");
    if (!quote && value.page)
      $("status").textContent =
        `Seite ${value.page} · kein gespeichertes PDF-Textzitat.`;
  });
}
function previewSource(value) {
  if (!ready || quote) return;
  if (!value.quote) {
    if (preview) {
      preview = null;
      find("", "source", false, false);
    }
    return;
  }
  const page = viewer.currentPageNumber;
  if (value.page && value.page !== page) return;
  preview = { page, top: surface.scrollTop, left: surface.scrollLeft };
  surface.classList.add("unbound");
  find(value.quote, "source", false, false);
}
window.addEventListener("message", (e) => {
  if (e.origin !== location.origin || e.source !== parent) return;
  if (e.data?.type === "set-theme") {
    document.documentElement.dataset.theme =
      e.data.theme === "dark" ? "dark" : "light";
    return;
  }
  if (
    !["search-quote", "preview-quote"].includes(e.data?.type) ||
    String(e.data.document) !== documentId ||
    e.data.kind !== kind ||
    !Number.isInteger(e.data.request)
  )
    return;
  if (e.data.type === "preview-quote") previewSource(e.data);
  else request(e.data);
});
$("find-start").onclick = () => {
  cancelAnimationFrame(layoutRequest);
  preview = null;
  quote = $("find-query").value;
  anchorRef = null;
  boundPage = null;
  $("viewerContainer").classList.remove("unbound");
  search();
};
$("find-toggle").onclick = () => {
  showSearch($("find-form").hidden);
  if (!$("find-form").hidden) $("find-query").focus();
};
$("find-query").onkeydown = (event) => {
  if (event.key === "Enter") $("find-start").click();
};
for (const [id, previous] of [
  ["find-next", false],
  ["find-previous", true],
])
  $(id).onclick = () => {
    boundPage = null;
    anchorRef = null;
    $("viewerContainer").classList.remove("unbound");
    search("again", previous);
  };
$("previous").onclick = () => {
  viewer.currentPageNumber = Math.max(1, viewer.currentPageNumber - 1);
};
$("next").onclick = () => {
  viewer.currentPageNumber = Math.min(
    viewer.pagesCount,
    viewer.currentPageNumber + 1,
  );
};
$("page").onchange = () => {
  viewer.currentPageNumber = Math.max(
    1,
    Math.min(viewer.pagesCount, +$("page").value || 1),
  );
};
$("zoom").onchange = () => {
  viewer.currentScaleValue =
    $("zoom").value === "custom"
      ? String(+$("zoom-percent").value / 100)
      : $("zoom").value;
};
$("zoom-percent").onchange = () => {
  if (!$("zoom-percent").reportValidity()) return;
  $("zoom").value = "custom";
  $("zoom").onchange();
};
eventBus.on("pagechanging", (e) => {
  $("page").value = e.pageNumber;
  if (!suppressPageEmit && ready && Number.isInteger(e.pageNumber)) {
    parent.postMessage(
      {
        type: "pdf-page-changed",
        document: documentId,
        kind,
        page: e.pageNumber,
      },
      location.origin,
    );
  }
});
function showMatches(e) {
  if (!quote || !e.matchesCount?.total) return;
  const { current, total } = e.matchesCount;
  const { pageIdx } = findController.selected;
  const onBoundPageCount = boundPage
    ? findController.pageMatches[boundPage - 1]?.length || 0
    : 0;
  const bound = Boolean(
    boundPage && pageIdx + 1 === boundPage && onBoundPageCount === 1,
  );
  if (boundPage && onBoundPageCount === 0 && anchorRef) {
    parent.postMessage(
      {
        type: "pdf-no-text-match",
        document: documentId,
        kind,
        ref: anchorRef,
        request: anchorRequest,
      },
      location.origin,
    );
  }
  matchControls(total);
  $("viewerContainer").classList.toggle(
    "unbound",
    Boolean(boundPage && !bound),
  );
  if (boundPage && !bound && viewer.currentPageNumber !== boundPage)
    viewer.currentPageNumber = boundPage;
  $("status").textContent = `PDF-Texttreffer ${current}/${total} · ${
    bound
      ? "eindeutiger Treffer auf Quellenseite " + boundPage
      : boundPage
        ? "kein eindeutiger Treffer auf Quellenseite " + boundPage
        : total > 1
          ? "mehrere mögliche Suchtreffer"
          : "Suchhilfe"
  } · keine verifizierte Docling-Pixelzuordnung.`;
}
eventBus.on("updatefindmatchescount", (e) =>
  queueMicrotask(() => showMatches(e)),
);
eventBus.on("updatefindcontrolstate", (e) => {
  if (preview && e.state !== 3) {
    const active = preview;
    queueMicrotask(() => {
      if (active !== preview) return;
      const { pageIdx } = findController.selected;
      const found =
        e.state !== 1 &&
        pageIdx + 1 === active.page &&
        findController.pageMatches[pageIdx]?.length === 1;
      surface.classList.toggle("unbound", !found);
      if (viewer.currentPageNumber !== active.page)
        viewer.currentPageNumber = active.page;
      surface.scrollTo(active.left, active.top);
    });
    return;
  }
  if (!quote) return;
  if (e.state === 1) {
    matchControls(0);
    $("status").textContent =
      "NO_TEXT_MATCH · kein PDF-Texttreffer. Darstellung bleibt verfügbar.";
    parent.postMessage(
      {
        type: "pdf-no-text-match",
        document: documentId,
        kind,
        ref: anchorRef,
        request: anchorRequest,
      },
      location.origin,
    );
  } else if (e.state !== 3) queueMicrotask(() => showMatches(e));
});
const container = $("viewerContainer");
let lastVisibleWidth = 0;
let repaintTimer = 0;
$("label")?.classList.toggle("is-derivative", kind === "office-pdf");

function syncVisibleLayout(reTriggerFind = false) {
  if (!container || container.clientWidth <= 20 || container.clientHeight <= 20) return false;
  const widthChanged =
    lastVisibleWidth === 0 || Math.abs(container.clientWidth - lastVisibleWidth) > 4;
  lastVisibleWidth = container.clientWidth;
  if (!viewer.pagesCount) return true;
  if (widthChanged) {
    const mode = $("zoom").value;
    if (mode !== "custom") viewer.currentScaleValue = mode;
    viewer.update();
    if (reTriggerFind && ready && $("find-query")?.value) {
      window.setTimeout(() => {
        if (!$("find-start").disabled) $("find-start").click();
      }, 60);
    }
  }
  return true;
}

if (typeof ResizeObserver === "function" && container) {
  new ResizeObserver(() => {
    window.cancelAnimationFrame(repaintTimer);
    repaintTimer = window.requestAnimationFrame(() => syncVisibleLayout(true));
  }).observe(container);
}

eventBus.on("pagesinit", () => {
  $("pages").textContent = "/ " + viewer.pagesCount;
  $("page").max = viewer.pagesCount;
  if (syncVisibleLayout(false)) {
    if ($("zoom").value !== "custom") viewer.currentScaleValue = $("zoom").value;
  }
});
eventBus.on("pagerendered", () => {
  const painted =
    container &&
    container.clientWidth > 20 &&
    Array.from(container.querySelectorAll("canvas")).some(
      (c) => c.width > 0 && c.height > 0,
    );
  if (!painted) return;
  if (document.documentElement.dataset.state === "ready") return;
  Object.assign(document.documentElement.dataset, {
    state: "ready",
    document: documentId,
    version: params.get("version") || "",
  });
  parent.postMessage(
    {
      type: "pdf-ready",
      document: documentId,
      kind,
      version: params.get("version") || "",
      url: location.href,
    },
    location.origin,
  );
});
try {
  if (!/^\d+$/.test(documentId) || !["pdf", "office-pdf"].includes(kind))
    throw Error("Ungültige Dokumentauswahl");
  const pdf = await pdfjs.getDocument({
    url: `/document/${documentId}/${kind}`,
    cMapUrl: "/assets/generated/pdfjs/cmaps/",
    cMapPacked: true,
    standardFontDataUrl: "/assets/generated/pdfjs/standard_fonts/",
    wasmUrl: "/assets/generated/pdfjs/wasm/",
    enableXfa: false,
    isEvalSupported: false,
  }).promise;
  $("label").textContent =
    kind === "pdf"
      ? "Unverändertes Original-PDF"
      : "LibreOffice-Anzeige-PDF · Derivat, keine Originalquelle";
  viewer.setDocument(pdf);
  linkService.setDocument(pdf, null);
  // Bind through the public API even when the iframe first rendered while hidden.
  await viewer.pagesPromise;
  findController.setDocument(pdf);
  ready = true;
  $("find-query").disabled = $("find-start").disabled = false;
  syncVisibleLayout(false);
  if (pending) request(pending);
} catch (e) {
  $("status").textContent = "PDF-Darstellung fehlgeschlagen: " + e.message;
}
