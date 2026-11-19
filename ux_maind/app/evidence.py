"""Link UX citations to occurrences in a versioned DoclingDocument."""

import json
import re
from collections import Counter
from contextlib import contextmanager
from hashlib import file_digest as digest_file, sha256
from itertools import groupby
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unicodedata import category

from docling_core.types.doc import (
    BaseMeta,
    ContentLayer,
    CoordOrigin,
    DocItemLabel,
    FloatingMeta,
    FormItem,
    KeyValueItem,
    ListItem,
    PictureItem,
    PictureMeta,
    RefItem,
    RichTableCell,
    TableItem,
    TextItem,
)

SCHEMA_VERSION = "ux-evidence/2"
READABLE_SCHEMAS = {SCHEMA_VERSION, "ux-evidence/1"}
TYPOGRAPHIC_HYPHENS = str.maketrans(
    {
        "‐": "-",
        "‑": "-",
        "−": "-",
    }
)
QUOTE_FOLD = str.maketrans(
    {
        "‐": "-",
        "‑": "-",
        "−": "-",
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‹": "'",
        "›": "'",
        "«": '"',
        "»": '"',
    }
)


_HTML_ENTITIES = (
    ("&amp;", "&"),
    ("&lt;", "<"),
    ("&gt;", ">"),
    ("&quot;", '"'),
    ("&#39;", "'"),
    ("&apos;", "'"),
    ("&nbsp;", " "),
)

_PDF_LIGATURES = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
}

_INVISIBLE_CHARS = frozenset(("\u00ad", "\u200b", "\u200c", "\u200d", "\ufeff"))


def _word_boundary_pattern(literal: str, sample: str, word_boundary: bool) -> str:
    """Build independent left/right boundary assertions; always protect digit boundaries ('5%' != '15%')."""
    if not sample:
        return f"(?={literal})"
    if not word_boundary:
        d_left = r"(?<!\d)" if (sample[0].isdigit() or re.match(r"^[-+\u2212]\d", sample)) else ""
        d_right = r"(?!\d)" if sample[-1].isdigit() else ""
        if d_left or d_right:
            return f"(?={d_left}{literal}{d_right})"
        return f"(?={literal})"
    if re.match(r"^\w", sample):
        left = r"(?<!\w)"
    elif re.match(r"^[-+\u2212]\d", sample):
        left = r"(?<![\w\d])"
    else:
        left = ""
    right = r"(?!\w)" if re.search(r"\w$", sample) else ""
    if left or right:
        return f"{left}{literal}{right}"
    return f"(?={literal})"


def _normalized_spans_pass(text, norm_quote, *, word_boundary=False, fold_line_hyphens=False):
    norm_chars, orig_starts, orig_ends = [], [], []
    in_space = True
    idx = 0
    n_text = len(text)
    while idx < n_text:
        ch = text[idx]
        if ch in _INVISIBLE_CHARS:
            idx += 1
            continue
        if (
            fold_line_hyphens
            and ch in "-‐‑"
            and idx > 0
            and text[idx - 1].isalpha()
            and idx + 2 < n_text
        ):
            nl_step = 0
            if text[idx + 1] == "\n":
                nl_step = 2
            elif text[idx + 1 : idx + 3] == "\r\n":
                nl_step = 3
            if nl_step and idx + nl_step < n_text and text[idx + nl_step].islower():
                idx += nl_step
                continue
        step = 1
        if ch == "&":
            for ent, rep in _HTML_ENTITIES:
                if text.startswith(ent, idx):
                    ch = rep
                    step = len(ent)
                    break
        if ch == "\u2026":
            norm_chars.extend((".", ".", "."))
            orig_starts.extend((idx, idx, idx))
            orig_ends.extend((idx + step, idx + step, idx + step))
            in_space = False
            idx += step
            continue
        if ch in _PDF_LIGATURES:
            lig = _PDF_LIGATURES[ch]
            for lch in lig:
                norm_chars.append(lch)
                orig_starts.append(idx)
                orig_ends.append(idx + step)
            in_space = False
            idx += step
            continue
        folded = ch.translate(QUOTE_FOLD)
        if folded.isspace():
            if not in_space and norm_chars:
                norm_chars.append(" ")
                orig_starts.append(idx)
                orig_ends.append(idx + step)
            in_space = True
        else:
            norm_chars.append(folded)
            orig_starts.append(idx)
            orig_ends.append(idx + step)
            in_space = False
        idx += step
    if norm_chars and norm_chars[-1] == " ":
        norm_chars.pop()
        orig_starts.pop()
        orig_ends.pop()
    norm_text = "".join(norm_chars)
    literal = re.escape(norm_quote)
    pattern = _word_boundary_pattern(literal, norm_quote, word_boundary)
    for found in re.finditer(pattern, norm_text):
        ns = found.start()
        ne = ns + len(norm_quote)
        if ne <= len(orig_ends):
            yield orig_starts[ns], orig_ends[ne - 1]


def _normalized_spans(text, quote, *, word_boundary=False):
    """Map whitespace/typographic/ligature/hyphen/entity quote matches back to exact character indices."""
    q_clean = quote.replace("\u2026", "...")
    for ch_inv in _INVISIBLE_CHARS:
        if ch_inv in q_clean:
            q_clean = q_clean.replace(ch_inv, "")
    for lig_k, lig_v in _PDF_LIGATURES.items():
        if lig_k in q_clean:
            q_clean = q_clean.replace(lig_k, lig_v)
    for ent, rep in _HTML_ENTITIES:
        if ent in q_clean:
            q_clean = q_clean.replace(ent, rep)
    norm_quote = " ".join(q_clean.translate(QUOTE_FOLD).split())
    if not norm_quote:
        return
    matched_any = False
    for span in _normalized_spans_pass(
        text, norm_quote, word_boundary=word_boundary, fold_line_hyphens=False
    ):
        matched_any = True
        yield span
    if not matched_any and ("\n" in text or "\r" in text):
        yield from _normalized_spans_pass(
            text, norm_quote, word_boundary=word_boundary, fold_line_hyphens=True
        )


def file_digest(path):
    with path.open("rb") as stream:
        return digest_file(stream, "sha256").hexdigest()


def _table_headers(item, cell_text):
    columns, rows = {}, {}
    for cell in item.data.table_cells:
        txt = " ".join(cell_text(cell).split())
        if not txt:
            continue
        if cell.column_header or cell.start_row_offset_idx == 0:
            for c in range(cell.start_col_offset_idx, cell.end_col_offset_idx):
                columns.setdefault(c, []).append(txt)
        if cell.row_header or cell.start_col_offset_idx == 0:
            for r in range(cell.start_row_offset_idx, cell.end_row_offset_idx):
                rows.setdefault(r, []).append(txt)
    if not columns and not rows:
        return None
    raw_cols = {c: " / ".join(dict.fromkeys(v)) for c, v in sorted(columns.items())}
    col_counts = {}
    for val in raw_cols.values():
        key = val.casefold()
        col_counts[key] = col_counts.get(key, 0) + 1
    disambiguated_cols = {}
    last_unique = None
    for c, val in sorted(raw_cols.items()):
        if col_counts.get(val.casefold(), 0) > 1 and last_unique:
            disambiguated_cols[str(c)] = f"{val} [{last_unique[:48]}]"
        else:
            disambiguated_cols[str(c)] = val
            if col_counts.get(val.casefold(), 0) == 1:
                last_unique = val
    return {
        "columns": disambiguated_cols,
        "rows": {str(r): " / ".join(dict.fromkeys(v)) for r, v in sorted(rows.items())},
    }


def _item_tracks(item):
    return [
        s.model_dump(mode="json", exclude_none=True)
        for s in getattr(item, "source", ()) or ()
        if getattr(s, "kind", None) == "track"
    ]


def _track_prefix(tracks):
    if not tracks:
        return ""
    first = tracks[0]
    parts = []
    if first.get("voice"):
        parts.append(f"Voice: {first['voice']}")
    if first.get("start_time") is not None and first.get("end_time") is not None:
        parts.append(f"{first['start_time']:.1f}s-{first['end_time']:.1f}s")
    return f"[{' | '.join(parts)}] " if parts else ""


@contextmanager
def model_source(sources, original, input_format="auto"):
    """Offer source identities inside native item metadata on the analysis copy."""
    doc = sources.doc
    has_tracks = any(
        _item_tracks(item)
        for item, _ in doc.iterate_items(
            included_content_layers=set(ContentLayer), traverse_pictures=False
        )
    )
    if (
        input_format == "markdown"
        and not doc.pictures
        and not doc.tables
        and not has_tracks
    ):
        yield original
        return
    with TemporaryDirectory() as root:
        path = Path(root) / original.name
        annotated = doc.model_copy(deep=True)
        table_captions_to_attach = []
        kv_texts_to_attach = []
        for item, _ in annotated.iterate_items(
            included_content_layers=set(ContentLayer), traverse_pictures=True
        ):
            # Sanitize LanguageMetaField (`docling-core 2.106.0` UnboundLocalError protection `US-36`)
            if getattr(item, "meta", None) is not None and getattr(item.meta, "language", None) is not None:
                lang_val = getattr(item.meta.language, "text", None) or str(item.meta.language)
                item.meta.set_custom_field("ux_maind", "language", lang_val)
                item.meta.language = None
            if isinstance(item, PictureItem):
                item.meta = item.meta or PictureMeta()
                item.meta.set_custom_field(
                    "ux_maind", "picture_source", sources.picture_source(item)
                )
                item.meta.set_custom_field("ux_maind", "source_ref", item.self_ref)
                continue
            if isinstance(item, (KeyValueItem, FormItem)):
                cells = getattr(getattr(item, "graph", None), "cells", None) or []
                cell_strs = [c.text.strip() for c in cells if getattr(c, "text", "").strip()]
                if cell_strs:
                    kv_texts_to_attach.append((item.self_ref, " | ".join(cell_strs)))
                continue
            if isinstance(item, TextItem) and item.label == DocItemLabel.GRADING_SCALE:
                item.label = DocItemLabel.TEXT
                item.meta = item.meta or BaseMeta()
                item.meta.set_custom_field("ux_maind", "grading_scale", True)
            tracks = _item_tracks(item) if isinstance(item, TextItem) else []
            if input_format == "markdown":
                if tracks:
                    prefix = _track_prefix(tracks)
                    if prefix and not item.text.startswith(prefix):
                        item.text = prefix + item.text
                if isinstance(item, TableItem):
                    headers = _table_headers(item, sources.cell_text)
                    table_captions_to_attach.append((item, headers))
                continue
            elif isinstance(item, TableItem):
                default_meta = FloatingMeta
            elif isinstance(item, TextItem):
                default_meta = BaseMeta
            else:
                continue
            item.meta = item.meta or default_meta()
            item.meta.set_custom_field("ux_maind", "source_ref", item.self_ref)
            if tracks:
                item.meta.set_custom_field("ux_maind", "track_source", tracks)
            if isinstance(item, TableItem):
                headers = _table_headers(item, sources.cell_text)
                if headers:
                    item.meta.set_custom_field("ux_maind", "table_headers", headers)
                table_captions_to_attach.append((item, headers))
        for kv_ref, kv_body in kv_texts_to_attach:
            annotated.add_text(
                DocItemLabel.TEXT,
                f"[ux_maind: form_source_ref={kv_ref}] {kv_body}",
            )
        for tbl_item, headers in table_captions_to_attach:
            parts = [f"source_ref={tbl_item.self_ref}"]
            if tbl_item.parent:
                try:
                    parent_node = tbl_item.parent.resolve(annotated)
                    sheet_name = getattr(parent_node, "name", None)
                    if sheet_name and sheet_name != "body":
                        parts.append(f"worksheet={sheet_name}")
                except Exception:
                    pass
            cols = (headers or {}).get("columns") or {}
            if cols:
                col_txt = ", ".join(
                    f"{k}={v}" for k, v in cols.items() if v
                )
                if col_txt:
                    parts.append(f"columns: {col_txt}")
            cap = annotated.add_text(
                DocItemLabel.CAPTION,
                f"[ux_maind: {' | '.join(parts)}]",
                parent=tbl_item,
            )
            tbl_item.captions.append(cap.get_ref())
        path.write_text(
            annotated.model_dump_json(by_alias=True, exclude_computed_fields=True),
            encoding="utf-8",
        )
        yield path


def ledger_coverage(sources, ledger):
    chunks = (ledger or {}).get("chunks", {})
    references = {}
    headings = {}
    for block in chunks.values():
        for ref in block["doc_item_refs"]:
            references.setdefault(ref, []).append(block["chunk_id"])
        for heading in block.get("headings", []):
            for page in block.get("page_numbers") or [None]:
                headings.setdefault((page, heading), []).append(block["chunk_id"])
    items = list(sources.items())
    heading_labels = (DocItemLabel.TITLE, DocItemLabel.SECTION_HEADER)
    occurrences = Counter(
        (page, item.text)
        for item in items
        if item.label in heading_labels
        for page in {p.page_no for p in item.prov} or {None}
    )
    inventory = []
    for item in items:
        pages = [p.page_no for p in item.prov]
        text = getattr(item, "text", "")
        matched = references.get(item.self_ref, [])
        as_heading = []
        if not matched and item.label in heading_labels:
            as_heading = [
                cid
                for page in pages or [None]
                if occurrences[page, text] == 1
                for cid in headings.get((page, text), [])
            ]
        inventory.append(
            dict(
                ref=item.self_ref,
                label=item.label.value,
                pages=pages,
                block=bool(matched or as_heading) if chunks else None,
                chunks=sorted(set(matched or as_heading)),
                as_heading=bool(as_heading),
                primary=item.content_layer == ContentLayer.BODY
                and (
                    bool(text.strip())
                    or isinstance(item, TableItem)
                    or (isinstance(item, (KeyValueItem, FormItem)) and bool(matched))
                    or has_visual_content(item)
                ),
            )
        )
    return inventory


def has_visual_content(item):
    if not isinstance(item, PictureItem) or item.meta is None:
        return False
    description = item.meta.description
    return bool((description and description.text.strip()) or item.meta.tabular_chart)


def picture_source(item, configuration=None):
    configuration = configuration or {}
    meta = item.meta
    result = dict(ref=item.self_ref, pages=sorted({p.page_no for p in item.prov}))
    if meta and getattr(meta, "ux_maind__slide_context", False):
        render = getattr(meta, "ux_maind__render_source", None)
        if not isinstance(render, dict):
            render = configuration.get("slide_view") or {}
        result.update(kind="slide_context", origin="renderer_derived")
        result.update(
            {
                key: render[key]
                for key in ("renderer", "source_sha256", "display_sha256")
                if isinstance(render.get(key), str)
            }
        )
    elif meta and getattr(meta, "ux_maind__page_context", False):
        render = getattr(meta, "ux_maind__render_source", None)
        if not isinstance(render, dict):
            render = configuration.get("page_view") or {}
        result.update(kind="page_context", origin="native_page_render")
        result.update(
            {
                key: render[key]
                for key in ("renderer", "source_sha256", "display_sha256")
                if isinstance(render.get(key), str)
            }
        )
    elif item.image and not configuration.get("picture_images"):
        result.update(kind="embedded", origin="original_embedded")
    else:
        result.update(kind="page_region", origin="native_region")
    if meta and meta.description and meta.description.text:
        result["description_origin"] = "derived_picture_description"
    return result


class Sources:
    """Resolve selected quotes, cells and images through native item references."""

    def __init__(
        self, doc, document, version, *, configuration=None, source_sha256=None
    ):
        self.doc = doc
        self.document = document
        self.version = version
        self.configuration = configuration
        self.source_sha256 = source_sha256
        self.rich_serializer = None
        self.outlines = {}
        self.text_shapes = None
        self.description_lists = {}
        self.caption_owners = {}
        for picture in doc.pictures:
            for ref in picture.captions:
                self.caption_owners.setdefault(ref.cref, []).append(picture)

    def items(self, ref=None, *, page=None):
        if ref is not None:
            try:
                item = RefItem(cref=ref).resolve(self.doc)
            except (KeyError, IndexError, AttributeError, ValueError):
                raise ValueError("Unbekannte Docling-Referenz") from None
            if getattr(item, "self_ref", None) != ref:
                raise ValueError("Unbekannte Docling-Referenz")
            if page is None or any(p.page_no == page for p in item.prov):
                yield item
        else:
            for item, _ in self.doc.iterate_items(
                included_content_layers=set(ContentLayer), traverse_pictures=True
            ):
                if page is None or any(p.page_no == page for p in item.prov):
                    yield item

    def cell_text(self, cell):
        if isinstance(cell, RichTableCell):
            if self.rich_serializer is None:
                from docling_core.transforms.serializer.markdown import (
                    MarkdownDocSerializer,
                )

                self.rich_serializer = MarkdownDocSerializer(doc=self.doc)
            return self.rich_serializer.serialize(item=cell.ref.resolve(self.doc)).text
        return cell.text

    def view(self, item, modality, quote="", **coordinates):
        anchor = dict(ref=item.self_ref, modality=modality, **coordinates)
        identity = json.dumps([self.document, self.version, anchor], sort_keys=True)
        view = dict(
            anchor,
            evidence_id=sha256(identity.encode()).hexdigest(),
            quote=quote,
            layer=item.content_layer.value,
            prov=[p.model_dump(mode="json") for p in item.prov],
            label=item.label.value,
            outline=self.outline(item),
        )
        if modality == "picture_enrichment":
            view["derived"] = item.meta.model_dump(mode="json", exclude_none=True)
        if isinstance(item, PictureItem):
            view["picture_source"] = self.picture_source(item)
        if modality == "text" and item.formatting:
            view["formatting"] = item.formatting.model_dump(mode="json")
        if modality == "text" and item.meta:
            struck_spans = getattr(item.meta, "ux_maind__strikethrough_spans", None)
            if struck_spans:
                view["strikethrough_spans"] = list(struck_spans)
        tracks = _item_tracks(item)
        if tracks:
            view["track"] = tracks
        if item.meta and getattr(item.meta, "ux_maind__layout_heading", False):
            view["label_origin"] = "visual_layout"
        if modality in ("cell", "table_row") and isinstance(item, TableItem):
            if modality == "cell":
                sheet = worksheet(self.doc, item, anchor)
                if sheet:
                    view["worksheet"] = sheet
            tbl_hdrs = getattr(self, "_cached_table_headers", None)
            if tbl_hdrs is None:
                tbl_hdrs = {}
                self._cached_table_headers = tbl_hdrs
            if item.self_ref not in tbl_hdrs:
                tbl_hdrs[item.self_ref] = _table_headers(item, self.cell_text) or {}
            hdr = tbl_hdrs[item.self_ref]
            c_idx = coordinates.get("column")
            r_idx = coordinates.get("row")
            if c_idx is not None and (ch := (hdr.get("columns") or {}).get(str(c_idx))):
                view["column_header"] = ch
            if r_idx is not None and r_idx > 0 and (rh := (hdr.get("rows") or {}).get(str(r_idx))):
                view["row_header"] = rh
        return view

    def picture_source(self, item):
        source = picture_source(item, self.configuration)
        source.update(document=self.document, document_version=self.version)
        if self.source_sha256:
            source.setdefault("source_sha256", self.source_sha256)
        return source

    def outline(self, item):
        ref = item.self_ref
        if ref in self.outlines:
            return self.outlines[ref]
        path = []
        seen = {ref}
        while parent := item.parent:
            if parent.cref in seen:
                break
            seen.add(parent.cref)
            item = parent.resolve(self.doc)
            if item.parent is None:
                break
            path.append(
                dict(
                    ref=item.self_ref,
                    label=item.label.value,
                    text=getattr(item, "text", None) or getattr(item, "name", None),
                    level=getattr(item, "level", None),
                )
            )
        self.outlines[ref] = list(reversed(path))
        return self.outlines[ref]

    def candidates(self, item, query):
        quote = query.get("quote")
        modality = query.get("modality")
        if isinstance(item, TextItem) and modality in (None, "text"):
            if quote is None:
                start, end = query.get("start", 0), query.get("end", len(item.text))
                if (
                    type(start) is int
                    and type(end) is int
                    and 0 <= start < end <= len(item.text)
                ):
                    yield self.view(
                        item, "text", item.text[start:end], start=start, end=end
                    )
            elif quote:
                tracks = _item_tracks(item)
                if tracks:
                    prefix = _track_prefix(tracks)
                    if prefix and quote.startswith(prefix) and len(quote) > len(prefix):
                        quote = quote[len(prefix) :]
                # These hyphen variants each occupy one character. Match the
                # spelling while keeping the original text and native offsets.
                literal = re.escape(quote.translate(TYPOGRAPHIC_HYPHENS))
                comparable = item.text.translate(TYPOGRAPHIC_HYPHENS)
                within = query.get("within_span")
                word_bound = bool(query.get("word_boundary"))
                pattern = _word_boundary_pattern(
                    literal, quote.translate(TYPOGRAPHIC_HYPHENS), word_bound
                )
                spans = [
                    (found.start(), found.start() + len(quote))
                    for found in re.finditer(pattern, comparable)
                ]
                if not spans:
                    spans = list(
                        _normalized_spans(item.text, quote, word_boundary=word_bound)
                    )
                if within:
                    w0, w1 = within
                    inside = [(s, e) for s, e in spans if s >= w0 and e <= w1]
                    if inside:
                        spans = inside
                for start, end in spans:
                    yield self.view(
                        item, "text", item.text[start:end], start=start, end=end
                    )
        elif isinstance(item, TableItem):
            if modality == "table_row" or (modality is None and quote):
                if (
                    modality == "table_row"
                    and isinstance(query.get("row"), int)
                    and isinstance(query.get("row_end"), int)
                    and query["row_end"] - query["row"] >= 2
                ):
                    yield from self.table_multi_row_candidates(item, quote)
                else:
                    yield from self.table_row_candidates(item, query)
            if (
                modality in (None, "table")
                and quote is None
                and "row" not in query
                and "column" not in query
            ):
                yield self.view(item, "table")
            elif modality in (None, "cell"):
                ws_filter = str(query.get("worksheet") or "").strip().lower()
                if ws_filter and item.parent:
                    try:
                        p_node = item.parent.resolve(self.doc)
                        p_name = str(getattr(p_node, "name", "") or "").strip().lower()
                        if p_name and p_name != "body" and p_name != ws_filter:
                            return
                    except Exception:
                        pass
                sub_ok = bool(
                    query.get("measurement_substring")
                    and "row" in query
                    and "column" in query
                    and quote
                )
                exact_bounds = "row_end" in query or "column_end" in query
                for cell in item.data.table_cells:
                    coordinates = dict(
                        row=cell.start_row_offset_idx,
                        row_end=cell.end_row_offset_idx,
                        column=cell.start_col_offset_idx,
                        column_end=cell.end_col_offset_idx,
                    )
                    if exact_bounds:
                        coord_ok = all(query.get(k, v) == v for k, v in coordinates.items())
                    else:
                        row_ok = (
                            "row" not in query
                            or cell.start_row_offset_idx <= query["row"] < cell.end_row_offset_idx
                        )
                        col_ok = (
                            "column" not in query
                            or cell.start_col_offset_idx <= query["column"] < cell.end_col_offset_idx
                        )
                        coord_ok = row_ok and col_ok
                    if coord_ok:
                        value = self.cell_text(cell)
                        if quote is None:
                            matched_cell = True
                        elif quote == "":
                            matched_cell = value == ""
                        else:
                            folded_val = " ".join(value.translate(QUOTE_FOLD).split())
                            folded_q = " ".join(quote.translate(QUOTE_FOLD).split())
                            matched_cell = value == quote or (
                                bool(folded_q) and folded_val == folded_q
                            )
                            if not matched_cell and sub_ok:
                                esc = re.escape(folded_q)
                                pat = _word_boundary_pattern(esc, folded_q, True)
                                matched_cell = bool(re.search(pat, folded_val))
                            if not matched_cell and len(quote.strip()) >= 4:
                                matched_cell = next(_normalized_spans(value, quote), None) is not None
                        if matched_cell:
                            occurrence = self.view(item, "cell", value, **coordinates)
                            if cell.bbox is not None:
                                occurrence["cell_bbox"] = cell.bbox.model_dump(
                                    mode="json"
                                )
                            yield occurrence
        elif isinstance(item, PictureItem):
            if modality in (None, "picture") and quote in (None, ""):
                yield self.view(item, "picture")
            if (
                modality == "picture_enrichment"
                and item.meta
                and any(
                    (
                        item.meta.description,
                        item.meta.classification,
                        item.meta.tabular_chart,
                    )
                )
            ):
                v = self.view(item, "picture_enrichment", quote=quote or "")
                if query.get("chart_cell"):
                    v["chart_cell"] = dict(query["chart_cell"])
                yield v
        elif quote in (None, "") and isinstance(item, (KeyValueItem, FormItem)):
            yield self.view(item, "structured")

    def table_row_candidates(self, item, query):
        quote = query.get("quote")
        if not quote:
            return
        rows = {}
        for cell in item.data.table_cells:
            if cell.row_span == 1:
                rows.setdefault(cell.start_row_offset_idx, []).append(cell)
        for row, cells in rows.items():
            if len(cells) < 2 or query.get("row", row) != row:
                continue
            cells.sort(key=lambda cell: cell.start_col_offset_idx)
            values = [self.cell_text(cell) for cell in cells]
            if sum(bool(value.strip()) for value in values) < 2:
                continue
            row_norm = " ".join(" ".join(values).split())
            quote_norm = " ".join(quote.split())
            pipe_norm = " ".join(re.sub(r"\s*\|\s*", " ", quote).split())
            comma_join = " ".join(", ".join(values).split())
            comma_compact = " ".join(", ".join(v for v in values if v.strip()).split())
            if (
                row_norm == quote_norm
                or (pipe_norm and row_norm == pipe_norm)
                or quote_norm in (comma_join, comma_compact)
            ):
                yield self.view(
                    item,
                    "table_row",
                    " ".join(values),
                    row=row,
                    row_end=row + 1,
                    column=cells[0].start_col_offset_idx,
                    column_end=cells[-1].end_col_offset_idx,
                )
            elif len(quote_norm) >= 16 and not any(
                v.strip() and next(_normalized_spans(v, quote), None) is not None
                for v in values
            ):
                cell_spans, parts, off = [], [], 0
                for c, v in zip(cells, values):
                    vt = v.strip()
                    if not vt:
                        continue
                    cell_spans.append((c, off, off + len(vt)))
                    parts.append(vt)
                    off += len(vt) + 1
                joined_row = " ".join(parts)
                q_probe = pipe_norm if "|" in quote and pipe_norm else quote
                seen_cols = set()
                for cs, ce in _normalized_spans(joined_row, q_probe):
                    covered = [c for c, s_o, e_o in cell_spans if cs < e_o and ce > s_o]
                    if len(covered) >= 2:
                        col_pair = (
                            covered[0].start_col_offset_idx,
                            covered[-1].end_col_offset_idx,
                        )
                        if col_pair in seen_cols:
                            continue
                        seen_cols.add(col_pair)
                        yield self.view(
                            item,
                            "table_row",
                            joined_row[cs:ce],
                            row=row,
                            row_end=row + 1,
                            column=col_pair[0],
                            column_end=col_pair[1],
                        )

    def table_multi_row_candidates(self, item, quote):
        if not quote or len(quote.strip()) < 12:
            return
        rows = {}
        for cell in item.data.table_cells:
            rows.setdefault(cell.start_row_offset_idx, []).append(cell)
        sorted_rows = sorted(rows)
        row_entries = []
        offset = 0
        parts = []
        for r in sorted_rows:
            cells = sorted(rows[r], key=lambda c: c.start_col_offset_idx)
            non_empty = [self.cell_text(c) for c in cells if self.cell_text(c).strip()]
            txt = " ".join(non_empty)
            if not txt:
                continue
            start_off = offset
            end_off = offset + len(txt)
            row_entries.append((r, cells, txt, start_off, end_off))
            parts.append(txt)
            offset = end_off + 1
        if len(row_entries) < 2:
            return
        full_joined = "\n".join(parts)
        seen_ranges = set()
        for cs, ce in _normalized_spans(full_joined, quote):
            covered = [
                idx
                for idx, (_, _, _, s_off, e_off) in enumerate(row_entries)
                if cs < e_off and ce > s_off
            ]
            if len(covered) >= 2:
                i0, i1 = covered[0], covered[-1]
                if (i0, i1) in seen_ranges:
                    continue
                seen_ranges.add((i0, i1))
                chunk = row_entries[i0 : i1 + 1]
                all_cells = [c for _, cs_list, _, _, _ in chunk for c in cs_list]
                yield self.view(
                    item,
                    "table_row",
                    "\n".join(t for _, _, t, _, _ in chunk),
                    row=chunk[0][0],
                    row_end=chunk[-1][0] + 1,
                    column=min(c.start_col_offset_idx for c in all_cells),
                    column_end=max(c.end_col_offset_idx for c in all_cells),
                )

    def select(self, query):
        if not isinstance(query, dict) or not isinstance(query.get("ref"), str):
            raise ValueError("Konkreten Docling-Beleg wählen")
        keys = (
            "modality",
            "start",
            "end",
            "row",
            "row_end",
            "column",
            "column_end",
            "evidence_id",
        )
        return unique(
            candidate
            for item in self.items(query["ref"])
            for candidate in self.candidates(item, query)
            if all(candidate.get(k) == query[k] for k in keys if k in query)
        )

    def locate(self, quote, locator, origin="original", *, page=None):
        return unique(self.occurrences(quote, locator, origin, page=page))[0]

    def occurrences(self, quote, locator, origin, *, page=None, **extra_query):
        locator = locator or {}
        ref = locator.get("self_ref")
        grid = {k: locator[k] for k in ("row", "column") if k in locator}
        ws_name = locator.get("worksheet")
        if not quote and (len(grid) != 2 or origin != "original"):
            raise ValueError("Eine leere Zelle benötigt konkrete Koordinaten")
        if origin == "original":
            query = dict(grid, quote=quote, **extra_query)
            if ws_name:
                query["worksheet"] = ws_name
            if "column" in grid:
                query["modality"] = "cell"
            matched = []
            for item in self.items(ref, page=page):
                for match in self.candidates(item, query):
                    if match["modality"] in ("text", "cell", "table_row"):
                        matched.append((match,))
            if not matched and "column" in grid and quote and (" " in quote or "|" in quote):
                row_query = {k: v for k, v in query.items() if k not in ("column", "modality")}
                row_query["modality"] = "table_row"
                for item in self.items(ref, page=page):
                    if isinstance(item, TableItem):
                        for match in self.table_row_candidates(item, row_query):
                            matched.append((match,))
            if matched:
                yield from matched
            elif quote and not grid:
                found_shape = False
                for match in self.same_shape(quote, ref, page):
                    found_shape = True
                    yield match
                if not found_shape and ref and any(ch.isspace() for ch in quote):
                    yield from self.adjacent_spans(quote, ref, page)
                if not found_shape and len(quote.strip()) >= 12:
                    for item in self.items(ref, page=page):
                        if isinstance(item, TableItem):
                            for match in self.table_multi_row_candidates(item, quote):
                                yield (match,)
        else:
            yield from (
                (m,) for m in self.derived_matches(ref, quote, grid, origin, page)
            )

    def adjacent_spans(self, quote, ref, page):
        """Reconcile contiguous TextItem paragraphs starting/anchored at an explicit ref (`US-43`)."""
        if not any(ch.isspace() for ch in quote):
            return
        raw_ordered = [
            it
            for it in self.items(None, page=page)
            if getattr(it, "content_layer", None) != ContentLayer.FURNITURE
            and getattr(it, "label", None) not in (DocItemLabel.PAGE_HEADER, DocItemLabel.PAGE_FOOTER)
        ]
        anchor_idx = next(
            (idx for idx, item in enumerate(raw_ordered) if item.self_ref == ref),
            None,
        )
        if anchor_idx is None:
            return
        anchor = raw_ordered[anchor_idx]
        if not isinstance(anchor, TextItem) or anchor.label in (
            DocItemLabel.SECTION_HEADER,
            DocItemLabel.TITLE,
        ):
            return
        parent_ref = anchor.parent.cref if anchor.parent else None

        def same_block(candidate):
            return (
                isinstance(candidate, TextItem)
                and candidate.label not in (DocItemLabel.SECTION_HEADER, DocItemLabel.TITLE)
                and (candidate.parent.cref if candidate.parent else None) == parent_ref
            )

        lo = anchor_idx
        while lo > 0 and anchor_idx - lo < 6 and same_block(raw_ordered[lo - 1]):
            lo -= 1
        hi = anchor_idx + 1
        while hi < len(raw_ordered) and hi - anchor_idx < 8 and same_block(raw_ordered[hi]):
            hi += 1
        window = raw_ordered[lo:hi]
        if len(window) < 2:
            return
        combined = " ".join(item.text for item in window)
        found_any = False
        for cs, ce in _normalized_spans(combined, quote):
            spans, offset = [], 0
            for item in window:
                limit = offset + len(item.text)
                if cs < limit and ce > offset:
                    spans.append((item, max(0, cs - offset), min(limit, ce) - offset))
                offset = limit + 1
            if len(spans) > 1 and any(item.self_ref == ref for item, _, _ in spans):
                found_any = True
                yield tuple(
                    self.view(item, "text", item.text[start:end], start=start, end=end)
                    for item, start, end in spans
                )
        if not found_any and "." in quote:
            parts, ranges, offset = [], [], 0
            for idx_w, item in enumerate(window):
                t_val = item.text
                sep = (
                    ". "
                    if idx_w < len(window) - 1
                    and t_val
                    and t_val[-1].isalnum()
                    else " "
                    if idx_w < len(window) - 1
                    else ""
                )
                ranges.append((item, offset, offset + len(t_val)))
                parts.append(t_val + sep)
                offset += len(t_val) + len(sep)
            punct_combined = "".join(parts)
            for cs, ce in _normalized_spans(punct_combined, quote):
                spans = [
                    (item, max(0, cs - s_o), min(e_o, ce) - s_o)
                    for item, s_o, e_o in ranges
                    if cs < e_o and ce > s_o
                ]
                if len(spans) > 1 and any(item.self_ref == ref for item, _, _ in spans):
                    yield tuple(
                        self.view(item, "text", item.text[start:end], start=start, end=end)
                        for item, start, end in spans
                    )

    def same_shape(self, quote, ref, page):
        if " " not in quote:
            return
        if self.text_shapes is None:
            self.text_shapes = [
                items
                for key, group in groupby(self.items(), shape_key)
                if key and len(items := list(group)) > 1
            ]
        for items in self.text_shapes:
            if page is not None and items[0].prov[0].page_no != page:
                continue
            for spans in contiguous_spans(items, quote, ref):
                yield tuple(
                    self.view(item, "text", item.text[start:end], start=start, end=end)
                    for item, start, end in spans
                )

    def derived_matches(self, ref, quote, grid, origin, page):
        candidates = []
        for item in self.items(ref, page=page):
            if not isinstance(item, PictureItem) or not item.meta:
                continue
            if origin == "picture_description" and item.meta.description:
                if self.description_matches(item, quote):
                    candidates.append(
                        (item, self.view(item, "picture_enrichment", quote=quote or ""))
                    )
            if origin == "chart_enrichment" and item.meta.tabular_chart:
                for cell in item.meta.tabular_chart.chart_data.table_cells:
                    c_val = self.cell_text(cell)
                    folded_c = " ".join(c_val.translate(QUOTE_FOLD).split())
                    folded_q = " ".join((quote or "").translate(QUOTE_FOLD).split())
                    cell_ok = (
                        c_val == quote
                        or (bool(folded_q) and folded_c == folded_q)
                        or (
                            bool(folded_q)
                            and next(
                                _normalized_spans(c_val, quote, word_boundary=True),
                                None,
                            )
                            is not None
                        )
                    )
                    if (
                        cell_ok
                        and grid.get("row", cell.start_row_offset_idx)
                        == cell.start_row_offset_idx
                        and grid.get("column", cell.start_col_offset_idx)
                        == cell.start_col_offset_idx
                    ):
                        v = self.view(
                            item,
                            "picture_enrichment",
                            quote=c_val or quote or "",
                        )
                        v["chart_cell"] = dict(
                            row=cell.start_row_offset_idx,
                            column=cell.start_col_offset_idx,
                            text=c_val,
                        )
                        candidates.append((item, v))
        if ref is None and len(candidates) > 1:
            primary_pages = {
                p.page_no
                for item, _ in candidates
                if not getattr(item.meta, "ux_maind__slide_context", False)
                and not getattr(item.meta, "ux_maind__page_context", False)
                for p in item.prov
            }
            if primary_pages:
                candidates = [
                    (item, view)
                    for item, view in candidates
                    if not (
                        (
                            getattr(item.meta, "ux_maind__slide_context", False)
                            or getattr(item.meta, "ux_maind__page_context", False)
                        )
                        and item.prov
                        and {p.page_no for p in item.prov}.issubset(primary_pages)
                    )
                ]
        for _, view in candidates:
            yield view

    def description_matches(self, item, quote):
        text = item.meta.description.text
        if re.search(rf"(?<!\w){re.escape(quote)}(?!\w)", text):
            return True
        if next(_normalized_spans(text, quote, word_boundary=True), None) is not None:
            return True
        if "\n" not in text or " " not in quote:
            return False
        if item.self_ref not in self.description_lists:
            self.description_lists[item.self_ref] = quoted_lists(text)
        return any(
            any(contiguous_spans(lines, quote, None))
            for lines in self.description_lists[item.self_ref]
        )

    def picture_sources(self, matches):
        pictures = {}
        for anchor in matches:
            for item in self.items(anchor["ref"]):
                if isinstance(item, PictureItem):
                    pictures[item.self_ref] = anchor
                else:
                    for picture in self.caption_owners.get(item.self_ref, ()):
                        pictures.setdefault(
                            picture.self_ref, self.view(picture, "picture")
                        )
        return list(pictures.values())


class _SimpleLine:
    __slots__ = ("text", "self_ref")

    def __init__(self, text: str):
        self.text = text
        self.self_ref = None


def _is_quoted_bullet(content: str) -> bool:
    if len(content) < 3:
        return False
    first, last = content[0], content[-1]
    if first == last and first in ("'", '"'):
        return True
    if category(first) in ("Pi", "Ps") and category(last) in ("Pf", "Pe"):
        return True
    if first in "„“”«»‚‘’" and last in "“”«»‘’\"'":
        return True
    return False


def quoted_lists(text):
    """Parse consecutive quoted list items without instantiating DocumentConverter (`US-42`)."""
    groups = []
    current = []
    bullet_re = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+(.*\S)\s*$")
    for raw_line in text.splitlines():
        m = bullet_re.match(raw_line)
        body = m.group(1) if m else ""
        if body and _is_quoted_bullet(body):
            current.append(_SimpleLine(body[1:-1]))
        else:
            if len(current) > 1:
                groups.append(current)
            current = []
    if len(current) > 1:
        groups.append(current)
    return groups


def shape_key(item):
    if isinstance(item, TextItem) and item.text and item.parent and len(item.prov) == 1:
        prov = item.prov[0]
        return (
            item.parent.cref,
            prov.page_no,
            prov.bbox.coord_origin,
            prov.bbox.as_tuple(),
        )
    return None


def contiguous_spans(items, quote, ref):
    text = " ".join(item.text for item in items)
    span_list = [
        (found.start(), found.start() + len(quote))
        for found in re.finditer(f"(?={re.escape(quote)})", text)
    ] or list(_normalized_spans(text, quote))
    for start, end in span_list:
        spans, offset = [], 0
        for item in items:
            limit = offset + len(item.text)
            if start < limit and end > offset:
                spans.append((item, max(0, start - offset), min(limit, end) - offset))
            offset = limit + 1
        if len(spans) > 1 and (
            ref is None or any(item.self_ref == ref for item, _, _ in spans)
        ):
            yield spans


def unique(occurrences):
    matches = iter(occurrences)
    match = next(matches, None)
    if match is None:
        raise ValueError("Wörtlicher Beleg an der angegebenen Quelle fehlt")
    if next(matches, None) is not None:
        raise ValueError("Wörtlicher Beleg kommt an mehreren Fundstellen vor")
    return match


def worksheet(doc, item, anchor):
    """Resolve native spreadsheet table offsets in the containing sheet."""
    if not doc.origin or doc.origin.mimetype not in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.oasis.opendocument.spreadsheet",
    ):
        return None
    if len(item.prov) != 1 or not item.parent:
        return None
    prov = item.prov[0]
    box = prov.bbox
    if (
        box.coord_origin != CoordOrigin.TOPLEFT
        or box.r - box.l != item.data.num_cols
        or box.b - box.t != item.data.num_rows
        or not all(float(value).is_integer() for value in (box.t, box.l))
    ):
        return None
    sheet = item.parent.resolve(doc)
    if not getattr(sheet, "name", None):
        return None
    return dict(
        name=sheet.name,
        page=prov.page_no,
        row=int(box.t) + anchor["row"],
        row_end=int(box.t) + anchor["row_end"],
        column=int(box.l) + anchor["column"],
        column_end=int(box.l) + anchor["column_end"],
    )


def extraction_pages(native, document):
    """Use native one-to-one trace ordinals to scope otherwise identical quotes."""
    pages = sorted(document.pages)
    page_events = [
        e["payload"]
        for e in native["trace"]
        if e["event_type"] == "extraction_completed"
        and e["payload"]["source_type"] == "page"
        and e["payload"]["parsed_model"] is not None
    ]
    if [e["parsed_model"] for e in page_events] == native["extracted"] and all(
        0 <= e["source_id"] < len(pages) for e in page_events
    ):
        return [pages[e["source_id"]] for e in page_events]
    return [None] * len(native["extracted"])


def observation_view(native, sources):
    """Link literal UX proposals to their exact native source occurrences."""
    observations, anchors, issues = [], {}, []
    seen_obs = set()

    def bind(
        quote,
        locator,
        origin,
        observation,
        page,
        *,
        issue_status="UNRESOLVED",
        **extra_query,
    ):
        try:
            matches = unique(
                sources.occurrences(quote, locator, origin, page=page, **extra_query)
            )
        except ValueError as error:
            if extra_query:
                return [], str(error)
            issues.append(
                dict(
                    status=issue_status,
                    observation=observation,
                    quote=quote,
                    origin=origin,
                    ref=locator.get("self_ref"),
                    reason=str(error),
                )
            )
            return [], str(error)
        for match in matches:
            anchors[match["evidence_id"]] = match
        return [match["evidence_id"] for match in matches], None

    def try_origin_reconcile(quote, locator, declared_origin, page):
        ref = locator.get("self_ref")
        if not ref:
            return None, []
        try:
            resolved_items = list(sources.items(ref, page=page))
        except ValueError:
            return None, []
        if not resolved_items:
            return None, []
        item = resolved_items[0]
        if isinstance(item, PictureItem) and declared_origin == "original":
            candidates_origin = ("picture_description", "chart_enrichment")
        elif not isinstance(item, PictureItem) and declared_origin != "original":
            candidates_origin = ("original",)
        else:
            return None, []
        for alt in candidates_origin:
            try:
                matches = unique(sources.occurrences(quote, locator, alt, page=page))
            except ValueError:
                continue
            for match in matches:
                anchors[match["evidence_id"]] = match
            return alt, [match["evidence_id"] for match in matches]
        return None, []

    for data, page in zip(
        native["extracted"], extraction_pages(native, sources.doc), strict=True
    ):
        for raw in data["observations"]:
            locator = {k: v for k, v in raw["locator"].items() if v is not None}
            dedup_key = (
                page,
                raw["origin"],
                json.dumps(locator, sort_keys=True),
                raw["quote"],
                raw["statement"],
            )
            if dedup_key in seen_obs:
                continue
            seen_obs.add(dedup_key)
            number = f"O{len(observations) + 1}"
            declared_origin = raw["origin"]
            evidence, err = bind(raw["quote"], locator, declared_origin, number, page)
            resolved_origin = declared_origin
            origin_reconciled = None
            symbolic_reconciled = False
            if (
                not evidence
                and err == "Unbekannte Docling-Referenz"
                and declared_origin == "original"
                and str(locator.get("self_ref") or "").strip().lower()
                in ("table", "#/table", "tables/0")
                and len(sources.doc.tables) == 1
            ):
                target_ref = sources.doc.tables[0].self_ref
                rec_locator = dict(locator, self_ref=target_ref)
                rec_evidence, rec_err = bind(
                    raw["quote"], rec_locator, declared_origin, number, page
                )
                if rec_evidence:
                    evidence, err = rec_evidence, None
                    locator = rec_locator
                    symbolic_reconciled = True
                    issues[:] = [
                        i
                        for i in issues
                        if not (
                            i.get("observation") == number
                            and i.get("status") == "UNRESOLVED"
                            and i.get("quote") == raw["quote"]
                        )
                    ]
                    issues.append(
                        dict(
                            status="REF_RECONCILED",
                            observation=number,
                            quote=raw["quote"],
                            declared_ref=raw["locator"].get("self_ref"),
                            resolved_ref=target_ref,
                            reason="Symbolische Tabellenreferenz auf einzige native Tabelle aufgelöst",
                        )
                    )
            if not evidence and err == "Wörtlicher Beleg an der angegebenen Quelle fehlt":
                if (
                    resolved_origin == "original"
                    and locator.get("self_ref")
                    and "|" in raw["quote"]
                ):
                    try:
                        pipe_matches = unique(
                            (m,)
                            for item in sources.items(None, page=page)
                            if isinstance(item, TableItem)
                            for m in sources.table_row_candidates(
                                item, dict(quote=raw["quote"])
                            )
                        )
                        for m in pipe_matches:
                            anchors[m["evidence_id"]] = m
                        evidence = [m["evidence_id"] for m in pipe_matches]
                        if evidence:
                            issues[:] = [
                                i
                                for i in issues
                                if not (
                                    i.get("observation") == number
                                    and i.get("status") == "UNRESOLVED"
                                    and i.get("quote") == raw["quote"]
                                )
                            ]
                            issues.append(
                                dict(
                                    status="REF_RECONCILED",
                                    observation=number,
                                    quote=raw["quote"],
                                    declared_ref=locator.get("self_ref"),
                                    resolved_ref=pipe_matches[0]["ref"],
                                    reason="Tabellenzeile über Pipe-Format von Textreferenz auf native Tabelle aufgelöst",
                                )
                            )
                    except ValueError:
                        pass
            if not evidence and err == "Wörtlicher Beleg an der angegebenen Quelle fehlt":
                alt_origin, alt_evidence = try_origin_reconcile(
                    raw["quote"], locator, declared_origin, page
                )
                if alt_origin:
                    evidence = alt_evidence
                    resolved_origin = alt_origin
                    origin_reconciled = {
                        "declared": declared_origin,
                        "resolved": alt_origin,
                    }
                    # Replace the primary UNRESOLVED issue with an explicit reconciliation notice.
                    issues[:] = [
                        i
                        for i in issues
                        if not (
                            i.get("observation") == number
                            and i.get("status") == "UNRESOLVED"
                            and i.get("quote") == raw["quote"]
                        )
                    ]
                    issues.append(
                        dict(
                            status="ORIGIN_RECONCILED",
                            observation=number,
                            quote=raw["quote"],
                            declared_origin=declared_origin,
                            resolved_origin=alt_origin,
                            ref=locator.get("self_ref"),
                            reason=f"Origin von {declared_origin} auf {alt_origin} über native Referenz korrigiert",
                        )
                    )
            if (
                not evidence
                and err == "Wörtlicher Beleg an der angegebenen Quelle fehlt"
                and resolved_origin == "original"
                and "row" in locator
                and "column" in locator
                and len((raw["quote"] or "").strip()) >= 12
            ):
                row_only_loc = {k: v for k, v in locator.items() if k != "column"}
                try:
                    row_cell_matches = unique(
                        sources.occurrences(
                            raw["quote"],
                            row_only_loc,
                            "original",
                            page=page,
                            modality="cell",
                        )
                    )
                except ValueError:
                    row_cell_matches = []
                if row_cell_matches:
                    for m in row_cell_matches:
                        anchors[m["evidence_id"]] = m
                    evidence = [m["evidence_id"] for m in row_cell_matches]
                    err = None
                    first_m = row_cell_matches[0]
                    old_loc = dict(locator)
                    locator = {
                        "self_ref": first_m["ref"],
                        "row": first_m["row"],
                        "column": first_m["column"],
                    }
                    issues[:] = [
                        i
                        for i in issues
                        if not (
                            i.get("observation") == number
                            and i.get("status") == "UNRESOLVED"
                            and i.get("quote") == raw["quote"]
                        )
                    ]
                    issues.append(
                        dict(
                            status="REF_RECONCILED",
                            observation=number,
                            quote=raw["quote"],
                            declared_ref=old_loc.get("self_ref"),
                            declared_locator=old_loc,
                            resolved_ref=first_m["ref"],
                            reason="Spaltenversatz innerhalb der angegebenen Tabellenzeile auf eindeutige Zelle korrigiert",
                        )
                    )
            if (
                not evidence
                and err
                in (
                    "Wörtlicher Beleg an der angegebenen Quelle fehlt",
                    "Unbekannte Docling-Referenz",
                )
                and locator
                and len((raw["quote"] or "").strip()) >= 6
            ):
                try:
                    uniq_matches = unique(
                        sources.occurrences(raw["quote"], {}, resolved_origin, page=page)
                    )
                except ValueError:
                    uniq_matches = []
                if uniq_matches:
                    for m in uniq_matches:
                        anchors[m["evidence_id"]] = m
                    evidence = [m["evidence_id"] for m in uniq_matches]
                    err = None
                    first_m = uniq_matches[0]
                    old_loc = dict(locator)
                    locator = {"self_ref": first_m["ref"]}
                    if "row" in first_m:
                        locator["row"] = first_m["row"]
                    if first_m.get("modality") == "cell" and "column" in first_m:
                        locator["column"] = first_m["column"]
                    issues[:] = [
                        i
                        for i in issues
                        if not (
                            i.get("observation") == number
                            and i.get("status") == "UNRESOLVED"
                            and i.get("quote") == raw["quote"]
                        )
                    ]
                    issues.append(
                        dict(
                            status="REF_RECONCILED",
                            observation=number,
                            quote=raw["quote"],
                            declared_ref=old_loc.get("self_ref"),
                            declared_locator=old_loc,
                            resolved_ref=first_m["ref"],
                            reason="Eindeutiges wörtliches Zitat auf einzige passende Dokumentstelle korrigiert",
                        )
                    )
            if (
                not evidence
                and err
                in (
                    "Wörtlicher Beleg an der angegebenen Quelle fehlt",
                    "Unbekannte Docling-Referenz",
                )
                and len((raw["quote"] or "").strip()) >= 4
            ):
                m_decl = re.fullmatch(
                    r"#/(texts|tables|pictures)/(\d+)",
                    str(locator.get("self_ref") or ""),
                )
                if m_decl:
                    coll, decl_idx = m_decl[1], int(m_decl[2])
                    near = []
                    for cand_tuple in sources.occurrences(
                        raw["quote"], {}, resolved_origin, page=page
                    ):
                        if len(cand_tuple) != 1:
                            continue
                        cand = cand_tuple[0]
                        m_cand = re.fullmatch(rf"#/{coll}/(\d+)", str(cand.get("ref") or ""))
                        if m_cand:
                            dist = abs(int(m_cand[1]) - decl_idx)
                            if 1 <= dist <= 2:
                                near.append((dist, cand))
                    if near:
                        min_d = min(d for d, _ in near)
                        closest = [c for d, c in near if d == min_d]
                        if len(closest) == 1:
                            chosen_m = closest[0]
                            anchors[chosen_m["evidence_id"]] = chosen_m
                            evidence = [chosen_m["evidence_id"]]
                            err = None
                            old_loc = dict(locator)
                            locator = {"self_ref": chosen_m["ref"]}
                            issues[:] = [
                                i
                                for i in issues
                                if not (
                                    i.get("observation") == number
                                    and i.get("status") == "UNRESOLVED"
                                    and i.get("quote") == raw["quote"]
                                )
                            ]
                            issues.append(
                                dict(
                                    status="REF_RECONCILED",
                                    observation=number,
                                    quote=raw["quote"],
                                    declared_ref=old_loc.get("self_ref"),
                                    declared_locator=old_loc,
                                    resolved_ref=chosen_m["ref"],
                                    reason="Nachbar-Indexversatz (±2) auf nächstliegende passende Docling-Referenz korrigiert",
                                )
                            )
            context = None
            if any(v is not None for v in raw["context"].values()):
                # The citation localizes the observation. Attribution remains a
                # proposal even when the cited text is found.
                context = dict(raw["context"], source_ids=evidence)
            context_ref = raw.get("context_reference")
            if isinstance(context_ref, dict) and any(
                v is not None for v in context_ref.values()
            ):
                context_ref = dict(context_ref)
                target_ref = context_ref.get("target_self_ref")
                if target_ref:
                    try:
                        RefItem(cref=target_ref).resolve(sources.doc)
                        context_ref["target_valid"] = True
                    except (KeyError, IndexError, AttributeError, ValueError):
                        context_ref["target_valid"] = False
            measurements = []
            primary = anchors[evidence[0]] if len(evidence) == 1 else None
            obs_span = (
                (primary["start"], primary["end"])
                if primary and primary["modality"] == "text"
                else None
            )
            prebound_measurements = {}
            if obs_span and resolved_origin == "original":
                by_val = {}
                for m_idx, val in enumerate(raw["measurements"]):
                    vloc = {k: v for k, v in val["locator"].items() if v is not None}
                    target_sref = vloc.get("self_ref") or primary["ref"]
                    if (
                        "row" not in vloc
                        and "column" not in vloc
                        and target_sref == primary["ref"]
                        and val.get("raw_value")
                    ):
                        by_val.setdefault(val["raw_value"], []).append(m_idx)
                for raw_val, idxs in by_val.items():
                    in_span_views = [
                        m[0]
                        for m in sources.occurrences(
                            raw_val,
                            {"self_ref": primary["ref"]},
                            "original",
                            page=page,
                            within_span=obs_span,
                            word_boundary=True,
                        )
                        if len(m) == 1
                    ]
                    if len(in_span_views) == len(idxs) and len(idxs) >= 1:
                        for k_i, m_idx in enumerate(idxs):
                            prebound_measurements[m_idx] = [in_span_views[k_i]]
                    elif len(idxs) == 1 and len(in_span_views) > 1:
                        prebound_measurements[idxs[0]] = in_span_views
            for m_idx, value in enumerate(raw["measurements"]):
                raw_val_loc = {
                    k: v for k, v in value["locator"].items() if v is not None
                }
                if (
                    str(raw_val_loc.get("self_ref") or "").strip().lower()
                    in ("table", "#/table", "tables/0")
                    and len(sources.doc.tables) == 1
                ):
                    target_ref = sources.doc.tables[0].self_ref
                    if not symbolic_reconciled:
                        symbolic_reconciled = True
                        issues.append(
                            dict(
                                status="REF_RECONCILED",
                                observation=number,
                                quote=value["raw_value"],
                                declared_ref=raw_val_loc.get("self_ref"),
                                resolved_ref=target_ref,
                                reason="Symbolische Tabellenreferenz auf einzige native Tabelle aufgelöst",
                            )
                        )
                    raw_val_loc["self_ref"] = target_ref
                value_locator = dict(raw_val_loc) if raw_val_loc else dict(locator)
                if primary and not value_locator.get("self_ref"):
                    value_locator["self_ref"] = primary["ref"]
                if (
                    primary
                    and primary["modality"] in ("cell", "table_row")
                    and not raw_val_loc
                ):
                    value_locator.setdefault("row", primary["row"])
                    if primary["modality"] == "cell":
                        value_locator.setdefault("column", primary["column"])
                matched = []
                if m_idx in prebound_measurements:
                    for v in prebound_measurements[m_idx]:
                        anchors[v["evidence_id"]] = v
                        matched.append(v["evidence_id"])
                elif (
                    obs_span
                    and resolved_origin == "original"
                    and "row" not in value_locator
                    and "column" not in value_locator
                    and value_locator.get("self_ref") == primary["ref"]
                ):
                    matched, _ = bind(
                        value["raw_value"],
                        value_locator,
                        resolved_origin,
                        number,
                        page,
                        issue_status="MEASUREMENT_UNRESOLVED",
                        within_span=obs_span,
                        word_boundary=True,
                    )
                if (
                    not matched
                    and len(evidence) > 1
                    and resolved_origin == "original"
                    and not raw_val_loc
                    and "row" not in value_locator
                    and "column" not in value_locator
                ):
                    span_matches = []
                    for eid in evidence:
                        anc = anchors.get(eid)
                        if not anc or anc.get("modality") != "text":
                            continue
                        try:
                            found = unique(
                                sources.occurrences(
                                    value["raw_value"],
                                    {"self_ref": anc["ref"]},
                                    resolved_origin,
                                    page=page,
                                    within_span=(anc["start"], anc["end"]),
                                    word_boundary=True,
                                )
                            )
                            span_matches.extend(found)
                        except ValueError:
                            continue
                    if len(span_matches) == 1:
                        m = span_matches[0]
                        anchors[m["evidence_id"]] = m
                        matched = [m["evidence_id"]]
                if not matched and (
                    not obs_span
                    or resolved_origin != "original"
                    or "row" in value_locator
                    or "column" in value_locator
                ):
                    matched, merr = bind(
                        value["raw_value"],
                        value_locator,
                        resolved_origin,
                        number,
                        page,
                        issue_status="MEASUREMENT_UNRESOLVED",
                    )
                    if (
                        not matched
                        and not raw_val_loc
                        and resolved_origin == "original"
                        and primary
                        and primary["modality"] in ("table_row", "cell")
                    ):
                        # Disambiguate row-level or header-scoped sibling-cell measurement using governing column header scope.
                        table_item = next(sources.items(primary["ref"]), None)
                        if isinstance(table_item, TableItem):
                            headers = _table_headers(table_item, sources.cell_text) or {}
                            col_headers = headers.get("columns", {})
                            scope_text = str(value.get("scope") or "").strip().lower()
                            candidate_cols = None
                            if scope_text:
                                matched_cols = [
                                    int(c)
                                    for c, h in col_headers.items()
                                    if h.lower() == scope_text
                                    or re.search(rf"(?<!\w){re.escape(scope_text)}(?!\w)", h.lower())
                                ]
                                if len(matched_cols) == 1:
                                    candidate_cols = matched_cols[0]
                            r_start = primary["row"]
                            r_end = primary.get("row_end", r_start + 1)
                            row_cells = [
                                c
                                for c in table_item.data.table_cells
                                if c.start_row_offset_idx < r_end
                                and c.end_row_offset_idx > r_start
                                and (
                                    candidate_cols is None
                                    or c.start_col_offset_idx
                                    <= candidate_cols
                                    < c.end_col_offset_idx
                                )
                                and (
                                    sources.cell_text(c) == value["raw_value"]
                                    or (
                                        value["raw_value"]
                                        and re.search(
                                            rf"(?<!\w){re.escape(value['raw_value'])}(?!\w)",
                                            sources.cell_text(c),
                                        )
                                        if re.match(r"^\w", value["raw_value"])
                                        and re.search(r"\w$", value["raw_value"])
                                        else value["raw_value"] in sources.cell_text(c)
                                    )
                                )
                            ]
                            if len(row_cells) > 1 and scope_text and candidate_cols is None:
                                scoped_cells = [
                                    c
                                    for c in row_cells
                                    if scope_text in sources.cell_text(c).lower()
                                ]
                                if len(scoped_cells) == 1:
                                    row_cells = scoped_cells
                                else:
                                    s_toks = set(re.findall(r"[a-z0-9äöüß]{2,}", scope_text))
                                    if s_toks:
                                        scored = []
                                        for c in row_cells:
                                            combined = (
                                                col_headers.get(str(c.start_col_offset_idx), "")
                                                + " "
                                                + sources.cell_text(c)
                                            ).lower()
                                            c_toks = set(re.findall(r"[a-z0-9äöüß]{2,}", combined))
                                            scored.append((len(s_toks & c_toks), c))
                                        best = max(sc for sc, _ in scored)
                                        winners = [c for sc, c in scored if sc == best and best > 0]
                                        if len(winners) == 1:
                                            row_cells = winners
                            if len(row_cells) == 1:
                                cell = row_cells[0]
                                anchor = sources.view(
                                    table_item,
                                    "cell",
                                    sources.cell_text(cell),
                                    row=cell.start_row_offset_idx,
                                    row_end=cell.end_row_offset_idx,
                                    column=cell.start_col_offset_idx,
                                    column_end=cell.end_col_offset_idx,
                                )
                                if cell.bbox is not None:
                                    anchor["cell_bbox"] = cell.bbox.model_dump(mode="json")
                                anchors[anchor["evidence_id"]] = anchor
                                matched = [anchor["evidence_id"]]
                                issues[:] = [
                                    i
                                    for i in issues
                                    if not (
                                        i.get("observation") == number
                                        and i.get("status") == "MEASUREMENT_UNRESOLVED"
                                        and i.get("quote") == value["raw_value"]
                                    )
                                ]
                    if (
                        not matched
                        and resolved_origin == "original"
                        and "row" in value_locator
                        and "column" in value_locator
                    ):
                        sub_matched, _ = bind(
                            value["raw_value"],
                            value_locator,
                            resolved_origin,
                            number,
                            page,
                            issue_status="MEASUREMENT_UNRESOLVED",
                            measurement_substring=True,
                        )
                        if sub_matched:
                            matched = sub_matched
                            issues[:] = [
                                i
                                for i in issues
                                if not (
                                    i.get("observation") == number
                                    and i.get("status") == "MEASUREMENT_UNRESOLVED"
                                    and i.get("quote") == value["raw_value"]
                                )
                            ]
                elif not matched:
                    matched, _ = bind(
                        value["raw_value"],
                        value_locator,
                        resolved_origin,
                        number,
                        page,
                        issue_status="MEASUREMENT_UNRESOLVED",
                    )
                measurements.append(dict(value, source_ids=matched))
            candidate_anchors = []
            ambiguous_total = 0
            if not evidence and raw.get("quote"):
                seen_cand_ids = set()
                try:
                    for cand_tuple in sources.occurrences(
                        raw["quote"], {}, resolved_origin, page=page
                    ):
                        if cand_tuple:
                            c_view = cand_tuple[0]
                            if c_view["evidence_id"] not in seen_cand_ids:
                                seen_cand_ids.add(c_view["evidence_id"])
                                ambiguous_total += 1
                                if len(candidate_anchors) < 6:
                                    candidate_anchors.append(c_view)
                except ValueError:
                    candidate_anchors = []
                    ambiguous_total = 0
            obs_record = dict(
                raw,
                id=number,
                origin=resolved_origin,
                source_ids=evidence,
                context=context,
                measurements=measurements,
            )
            if ambiguous_total >= 2:
                obs_record["candidate_anchors"] = candidate_anchors
                obs_record["ambiguous_count"] = ambiguous_total
            if origin_reconciled:
                obs_record["origin_reconciled"] = origin_reconciled
            if context_ref is not None:
                obs_record["context_reference"] = context_ref
            observations.append(obs_record)
    return observations, anchors, issues
