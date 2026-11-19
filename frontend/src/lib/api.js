/**
 * Loopback API helper & deterministic source-highlighting utilities.
 */

export function getWorkspaceToken() {
  return document.querySelector('meta[name="workspace-token"]')?.content || "";
}

export async function api(path, body = undefined, options = {}) {
  const isPost = body !== undefined;
  const headers = {};
  if (isPost) {
    headers["Content-Type"] = "application/json";
    headers["X-Workspace-Token"] = getWorkspaceToken();
  }
  const resp = await fetch(`/api/${path}`, {
    method: isPost ? "POST" : "GET",
    headers,
    body: isPost ? JSON.stringify(body) : undefined,
    signal: options.signal,
  });
  let payload = null;
  const ct = resp.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    payload = await resp.json();
  } else {
    payload = await resp.text();
  }
  if (!resp.ok) {
    const msg =
      (payload && typeof payload === "object" && payload.error) ||
      (typeof payload === "string" && payload) ||
      `HTTP ${resp.status}`;
    throw new Error(msg);
  }
  return payload;
}

export async function apiUploadBinary(path, fileOrBytes) {
  const resp = await fetch(`/api/${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/octet-stream",
      "X-Workspace-Token": getWorkspaceToken(),
    },
    body: fileOrBytes,
  });
  const ct = resp.headers.get("content-type") || "";
  const payload = ct.includes("application/json") ? await resp.json() : await resp.text();
  if (!resp.ok) {
    const msg =
      (payload && typeof payload === "object" && payload.error) ||
      (typeof payload === "string" && payload) ||
      `HTTP ${resp.status}`;
    throw new Error(msg);
  }
  return payload;
}

export async function fetchObservationEntry(ref) {
  const params = new URLSearchParams({
    documents: JSON.stringify([ref.document]),
    ref: JSON.stringify(ref),
  });
  return api(`ux-observation?${params}`);
}

export function pictureSourceLabel(source, t) {
  const names = {
    slide_context: t("Gerenderte Ganzfolie", "Rendered Full Slide"),
    page_context: t("Gerenderte Ganzseite", "Rendered Full Page"),
    embedded: t("Eingebettetes Bild", "Embedded Image"),
    page_region: t("Native Bildregion", "Native Page Region"),
  };
  return names[source?.kind] || t("Bildquelle", "Visual Source");
}

function uniqueOffset(text, quote) {
  if (!quote) return -1;
  const start = text.indexOf(quote);
  return start < 0 || text.indexOf(quote, start + 1) >= 0 ? -1 : start;
}

export function markPlainTextFrame(frame, item, anchor, { preview = false, scroll = false } = {}) {
  const doc = frame?.contentDocument;
  const block = doc?.getElementById("original-text");
  const win = doc?.defaultView;
  if (!block || !win?.CSS?.highlights) return false;
  const highlights = win.CSS.highlights;
  const name = preview ? "ux-preview" : "ux-source";
  highlights.delete(name);
  if (!anchor?.quote || !item?.text || !block.firstChild) return false;
  const quote = anchor.quote;
  const codepoints = Array.from(item.text);
  if (codepoints.slice(anchor.start, anchor.end).join("") !== quote) return false;
  const text = block.textContent;
  const base = uniqueOffset(text, item.text);
  const start =
    base < 0
      ? uniqueOffset(text, quote)
      : base + codepoints.slice(0, anchor.start).join("").length;
  if (start < 0 || text.slice(start, start + quote.length) !== quote) return false;
  const range = doc.createRange();
  range.setStart(block.firstChild, start);
  range.setEnd(block.firstChild, start + quote.length);
  highlights.set(name, new win.Highlight(range));
  if (scroll) {
    win.scrollBy(0, range.getBoundingClientRect().top - win.innerHeight / 3);
  }
  return true;
}
