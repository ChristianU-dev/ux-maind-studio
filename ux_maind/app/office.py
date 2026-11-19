"""The shared LibreOffice display derivative and its native Docling slide evidence."""

from hashlib import sha256
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import subprocess
from threading import Lock

_RENDER = Lock()


def office_renderer():
    configured = os.environ.get("UX_MAIND_SOFFICE", "")
    renderer = (
        (configured if configured and Path(configured).is_file() else None)
        or shutil.which("soffice")
        or next(
            (
                str(p)
                for p in [
                    Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
                    / "LibreOffice/program/soffice.exe",
                    Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
                ]
                if p.is_file()
            ),
            None,
        )
    )
    # Windows' console launcher waits and supplies conversion diagnostics reliably.
    console = Path(renderer).with_suffix(".com") if renderer else None
    return (
        str(console) if os.name == "nt" and console and console.is_file() else renderer
    )


def office_pdf(source, destination):
    """Render an Office document via headless LibreOffice into display_root/<sha256>."""
    renderer = office_renderer()
    if not renderer:
        raise ValueError("LibreOffice nicht installiert")
    from .evidence import file_digest

    if hasattr(source, "artifact"):
        workspace_root = source.root
        original = source.artifact(destination, "stored")
        display_root = workspace_root / "display"
    else:
        original = Path(source).resolve()
        display_root = Path(destination).resolve()
        workspace_root = display_root.parent
    stat = Path(renderer).stat()
    identity = dict(
        source_sha256=file_digest(original),
        renderer=renderer,
        renderer_size=stat.st_size,
        renderer_mtime_ns=stat.st_mtime_ns,
        options="headless-pdf-v1",
    )
    version_file = Path(renderer).parent / "version.ini"
    if version_file.is_file():
        identity["renderer_build"] = version_file.read_text(encoding="utf8")
    key = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    directory = display_root / key
    for folder in (display_root, directory):
        if folder.is_symlink() or not folder.resolve().is_relative_to(workspace_root):
            raise ValueError("Unsicherer Anzeigepfad")
        folder.mkdir(exist_ok=True)
    target = directory / (original.stem + ".pdf")
    profile = display_root / "lo-profile"
    with _RENDER:
        if (
            target.is_symlink()
            or profile.is_symlink()
            or not profile.resolve().is_relative_to(workspace_root)
        ):
            raise ValueError("Unsicherer Pfad für LibreOffice")
        if not target.is_file():
            process = subprocess.run(
                [
                    renderer,
                    "-env:UserInstallation=" + profile.as_uri(),
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(directory),
                    str(original),
                ],
                capture_output=True,
                timeout=120,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if process.returncode or not target.is_file():
                raise ValueError("Lokale Anzeige-Konvertierung fehlgeschlagen")
        with target.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ValueError("LibreOffice lieferte kein gültiges Anzeige-PDF")
        identity["display_sha256"] = file_digest(target)
        (directory / "display.json").write_text(
            json.dumps(identity, indent=2), encoding="utf8"
        )
    return target, identity


def attach_slide_views(target, identity, doc):
    """Keep rendered slide context as a native page and a native Vision source."""
    from math import isclose
    import pypdfium2
    from docling_core.types.doc import (
        BoundingBox,
        ImageRef,
        PictureMeta,
        ProvenanceItem,
    )

    with pypdfium2.PdfDocument(target) as pdf:
        if set(doc.pages) != set(range(1, len(pdf) + 1)):
            return {"status": "page_count_mismatch"}
        page_images = {}
        for number, page in doc.pages.items():
            with closing(pdf[number - 1]) as rendered:
                if not all(
                    isclose(points * 12700, emu, rel_tol=0.001)
                    for points, emu in zip(
                        rendered.get_size(), (page.size.width, page.size.height)
                    )
                ):
                    return {"status": "page_size_mismatch"}
                with closing(rendered.render()) as bitmap:
                    page_images[number] = ImageRef.from_pil(bitmap.to_pil(), dpi=72)
    render = {
        "renderer": "LibreOffice",
        **{key: identity[key] for key in ("source_sha256", "display_sha256")},
    }
    groups = {group.name: group for group in doc.groups}
    for number, page in doc.pages.items():
        page.image = page_images[number]
        picture = doc.add_picture(
            parent=groups.get(f"slide-{number - 1}"),
            prov=ProvenanceItem(
                page_no=number,
                bbox=BoundingBox(l=0, t=0, r=page.size.width, b=page.size.height),
                charspan=(0, 0),
            ),
        )
        picture.meta = PictureMeta()
        picture.meta.set_custom_field("ux_maind", "slide_context", True)
        picture.meta.set_custom_field("ux_maind", "render_source", render)
    return {
        "status": "success",
        "pages": len(page_images),
        **render,
    }


def explicit_run_format(run):
    from pptx.oxml.ns import qn

    properties = run._r.find(qn("a:rPr"))
    strike = properties is not None and properties.get("strike") in (
        "sngStrike",
        "dblStrike",
    )
    return (
        run.font.bold is True,
        run.font.italic is True,
        bool(run.font.underline),
        strike,
    )


def slide_run_formats(original):
    from collections import defaultdict
    from pptx import Presentation

    candidates = defaultdict(list)
    for number, slide in enumerate(Presentation(original).slides, start=1):
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            bbox = (
                shape.left,
                shape.top,
                shape.left + shape.width,
                shape.top + shape.height,
            )
            for paragraph in shape.text_frame.paragraphs:
                non_empty = [run for run in paragraph.runs if run.text.strip()]
                formats = {explicit_run_format(run) for run in non_empty}
                struck = [
                    run.text.strip()
                    for run in non_empty
                    if explicit_run_format(run)[3]
                ]
                candidates[number, bbox, paragraph.text.strip()].append((formats, struck))
    return candidates


def pptx_formatting(original, doc):
    """Copy explicit uniform and partial strikethrough run formatting onto native paragraphs."""
    from docling_core.types.doc import BaseMeta
    from docling_core.types.doc.common.formatting import Formatting

    candidates = slide_run_formats(original)
    count = 0
    for item in doc.texts:
        if len(item.prov) != 1:
            continue
        prov = item.prov[0]
        box = prov.bbox.to_top_left_origin(doc.pages[prov.page_no].size.height)
        matched = candidates[
            prov.page_no, (box.l, box.t, box.r, box.b), item.text.strip()
        ]
        if len(matched) != 1:
            continue
        formats, struck = matched[0]
        if len(formats) == 1 and item.formatting is None:
            bold, italic, underline, strike = next(iter(formats))
            if bold or italic or underline or strike:
                item.formatting = Formatting(
                    bold=bold, italic=italic, underline=underline, strikethrough=strike
                )
                count += 1
        elif struck:
            item.meta = item.meta or BaseMeta()
            item.meta.set_custom_field("ux_maind", "strikethrough_spans", struck)
            count += 1
    return count


def _docx_run_strike(run, qn):
    if run.font.strike is True or run.font.double_strike is True:
        return True
    rpr = run._r.find(qn("w:rPr"))
    if rpr is None:
        return False
    for tag in ("w:strike", "w:dStrike"):
        el = rpr.find(qn(tag))
        if el is not None and el.get(qn("w:val")) not in ("0", "false", "False"):
            return True
    return False


def docx_formatting(original, doc):
    """Preserve uniform and inline DOCX strikethrough formatting on native items."""
    from collections import defaultdict
    from docx import Document
    from docx.oxml.ns import qn
    from docling_core.types.doc import BaseMeta, FloatingMeta
    from docling_core.types.doc.common.formatting import Formatting

    word_doc = Document(original)
    paragraphs = defaultdict(list)

    def collect(para):
        text = para.text.strip()
        if not text:
            return
        non_empty = [r for r in para.runs if r.text.strip()]
        if not non_empty:
            return
        formats = {
            (
                r.font.bold is True,
                r.font.italic is True,
                bool(r.font.underline),
                _docx_run_strike(r, qn),
            )
            for r in non_empty
        }
        struck = [r.text.strip() for r in non_empty if _docx_run_strike(r, qn)]
        paragraphs[text].append((formats, struck))

    for p in word_doc.paragraphs:
        collect(p)

    table_strikes = []
    for t_idx, tbl in enumerate(word_doc.tables):
        t_entries = []
        for r_idx, row in enumerate(tbl.rows):
            for c_idx, cell in enumerate(row.cells):
                struck = []
                for p in cell.paragraphs:
                    for r in p.runs:
                        if r.text.strip() and _docx_run_strike(r, qn):
                            struck.append(r.text.strip())
                if struck:
                    t_entries.append(dict(row=r_idx, column=c_idx, struck=struck))
        table_strikes.append((t_idx, t_entries))

    count = 0
    doc_text_counts = defaultdict(int)
    for item in doc.texts:
        doc_text_counts[item.text.strip()] += 1
    doc_text_seen = defaultdict(int)
    for item in doc.texts:
        key = item.text.strip()
        matched = paragraphs.get(key, [])
        if not matched:
            continue
        idx_seen = doc_text_seen[key]
        doc_text_seen[key] += 1
        if len(matched) == 1:
            formats, struck = matched[0]
        elif len(matched) == doc_text_counts[key] and idx_seen < len(matched):
            formats, struck = matched[idx_seen]
        elif len({(frozenset(f), tuple(s)) for f, s in matched}) == 1:
            formats, struck = matched[0]
        else:
            continue
        if len(formats) == 1 and item.formatting is None:
            bold, italic, underline, strike = next(iter(formats))
            if strike or bold or italic or underline:
                item.formatting = Formatting(
                    bold=bold, italic=italic, underline=underline, strikethrough=strike
                )
                count += 1
        elif struck:
            item.meta = item.meta or BaseMeta()
            item.meta.set_custom_field("ux_maind", "strikethrough_spans", struck)
            count += 1
    for t_idx, entries in table_strikes:
        if entries and t_idx < len(doc.tables):
            tbl_item = doc.tables[t_idx]
            tbl_item.meta = tbl_item.meta or FloatingMeta()
            tbl_item.meta.set_custom_field("ux_maind", "table_strikethrough", entries)
            count += len(entries)
    return count


def attach_pdf_page_views(doc, source_sha256):
    """Attach full-page PictureItems for PDF pages containing pictures so visual context is enriched once per page."""
    from docling_core.types.doc import (
        BoundingBox,
        CoordOrigin,
        PictureMeta,
        ProvenanceItem,
    )

    pages_with_pictures = {
        p.page_no
        for pic in doc.pictures
        if not (
            pic.meta
            and (
                getattr(pic.meta, "ux_maind__slide_context", False)
                or getattr(pic.meta, "ux_maind__page_context", False)
            )
        )
        for p in pic.prov
    }
    existing_context_pages = {
        p.page_no
        for pic in doc.pictures
        if pic.meta
        and (
            getattr(pic.meta, "ux_maind__slide_context", False)
            or getattr(pic.meta, "ux_maind__page_context", False)
        )
        for p in pic.prov
    }
    added = 0
    for number in sorted(pages_with_pictures - existing_context_pages):
        page = doc.pages.get(number)
        if not page or not page.image or not str(page.image.uri).startswith("data:image/"):
            continue
        picture = doc.add_picture(
            prov=ProvenanceItem(
                page_no=number,
                bbox=BoundingBox(
                    l=0,
                    t=0,
                    r=page.size.width,
                    b=page.size.height,
                    coord_origin=CoordOrigin.TOPLEFT,
                ),
                charspan=(0, 0),
            )
        )
        picture.meta = PictureMeta()
        picture.meta.set_custom_field("ux_maind", "page_context", True)
        picture.meta.set_custom_field(
            "ux_maind",
            "render_source",
            {"renderer": "pypdfium2", "source_sha256": source_sha256},
        )
        added += 1
    return {"status": "success" if added else "none_needed", "pages": added}
