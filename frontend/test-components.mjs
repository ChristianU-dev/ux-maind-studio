import { JSDOM } from "jsdom";
import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";

const dom = new JSDOM("<!doctype html><body><div id='root'></div></body>", {
  url: "http://127.0.0.1/",
});
for (const key of [
  "window",
  "document",
  "HTMLElement",
  "Element",
  "Node",
  "Document",
  "DocumentFragment",
  "ShadowRoot",
  "customElements",
  "Event",
  "CustomEvent",
  "MouseEvent",
  "CSSStyleSheet",
]) {
  globalThis[key] = dom.window[key];
}
globalThis.requestAnimationFrame = (fn) => setTimeout(fn, 0);

// 1. Verify bundled @docling/docling-components & @docling/docling-core
const module = await import("../ux_maind/app/web/generated/components.js");
assert(
  Object.keys(module.docling).length > 0,
  "exported native components retained despite sideEffects:false"
);
for (const name of [
  "docling-img",
  "docling-img-page",
  "docling-tooltip",
  "docling-item-text",
  "docling-item-provenance",
]) {
  assert(customElements.get(name), name + " registration");
}

const doc = {
  schema_name: "DoclingDocument",
  version: "1.10.0",
  name: "synthetic",
  body: {
    self_ref: "#/body",
    children: [{ $ref: "#/texts/0" }, { $ref: "#/texts/1" }],
  },
  furniture: { self_ref: "#/furniture", children: [] },
  groups: [],
  texts: [1, 2].map((n) => ({
    self_ref: "#/texts/" + (n - 1),
    parent: { $ref: "#/body" },
    children: [],
    label: "text",
    text: n === 1 ? "<script>literal()</script>" : "Page two",
    prov: [
      {
        page_no: n,
        bbox: { l: 10, t: 10, r: 80, b: 30, coord_origin: "TOPLEFT" },
        charspan: [0, 8],
      },
    ],
  })),
  pictures: [],
  tables: [],
  pages: Object.fromEntries(
    [1, 2].map((n) => [
      n,
      {
        page_no: n,
        size: { width: 100, height: 100 },
        image: {
          uri: "/document/1/resource?kind=page&index=" + n,
          mimetype: "image/png",
          dpi: 72,
          size: { width: 100, height: 100 },
        },
      },
    ])
  ),
};

const v = document.createElement("docling-img");
assert.equal(module.resolveDocumentItem(doc, { $ref: "#/texts/1" }), doc.texts[1]);
v.src = doc;
v.items = "#/pages/1";
const tt = document.createElement("docling-tooltip");
tt.append(
  document.createElement("docling-item-text"),
  document.createElement("docling-item-provenance")
);
v.append(tt);
document.body.append(v);
const tick = () => new Promise((r) => setTimeout(r, 20));
await v.updateComplete;
await tick();
await v.updateComplete;
let p = v.shadowRoot.querySelector("docling-img-page");
assert(p);
await p.updateComplete;
let rect = p.shadowRoot.querySelector("rect[part]");
assert(rect);
let clicked;
v.onClickItem = (_, page, item) => (clicked = { page: page.page_no, ref: item.self_ref });
await v.updateComplete;
await p.updateComplete;
rect = p.shadowRoot.querySelector("rect[part]");
rect.dispatchEvent(new MouseEvent("click", { bubbles: true }));
assert.deepEqual(clicked, { page: 1, ref: "#/texts/0" });

const text = document.createElement("docling-item-text");
text.item = doc.texts[0];
text.page = doc.pages[1];
document.body.append(text);
await text.updateComplete;
assert(!text.shadowRoot.querySelector("script"));
assert(text.shadowRoot.textContent.includes("<script>"));

// 2. Verify React Studio helper utilities (api.js)
const { pictureSourceLabel } = await import("./src/lib/api.js");
assert.equal(
  pictureSourceLabel({ kind: "slide_context" }, (de, _en) => de),
  "Gerenderte Ganzfolie"
);
assert.equal(
  pictureSourceLabel({ kind: "slide_context" }, (_de, en) => en),
  "Rendered Full Slide"
);

// 3. Verify built React Studio bundle, Anti-AI-Look CSS & OSI License Manifest
const generatedUrl = (name) => new URL(`../ux_maind/app/web/generated/${name}`, import.meta.url);
const mainJsStat = await stat(generatedUrl("main.js"));
assert(mainJsStat.size > 100_000, "main.js React bundle built");

const mainCss = await readFile(generatedUrl("main.css"), "utf8");
assert(mainCss.includes("--bg-canvas:"), "Linear Zinc canvas token present");
assert(mainCss.includes("--primary-bg:"), "Linear monochrome primary token present");
assert(!mainCss.toLowerCase().includes("#4f46e5"), "Zero cliché indigo #4f46e5");
assert(!mainCss.toLowerCase().includes("#6366f1"), "Zero cliché purple #6366f1");

const licenses = await readFile(generatedUrl("LICENSES.txt"), "utf8");
for (const requiredPkg of ["react ", "@xyflow/react ", "@radix-ui/react-select ", "vaul ", "sonner ", "cmdk "]) {
  assert(licenses.includes(requiredPkg), `LICENSES.txt includes ${requiredPkg}`);
}

console.log(
  "PASS: bundled Docling components, XSS escaping, React Studio helpers, Anti-AI-Look CSS & OSI LICENSES verified."
);
