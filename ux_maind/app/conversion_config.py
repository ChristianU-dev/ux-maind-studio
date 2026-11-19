"""Standalone, non-hardcoded native Docling conversion options & validation."""

from __future__ import annotations

import re

VISION_TIMEOUT_DEFAULT = 120

DEFAULT_VISION_PROMPT = (
    "Describe what is visibly depicted, transcribing relevant interface labels, "
    "chart axes, units, colors, status badges and values if legible. Distinguish uncertainty. "
    "For arrows or connectors, explicitly state source -> target flow and any label on the connector. "
    "For any whole slide/page or annotated figure, report visible crossings-out, strikethroughs, occluded regions, "
    "sticky notes/callouts and the exact items or areas they touch. "
    "Distinguish actual text formatting or drawn annotations from underlying UI elements, and report visual grouping. "
    "Do not infer behavior, user intent or events beyond the visible pixels."
)

CONVERSION_DEFAULTS = {
    "do_ocr": True,
    "force_full_page_ocr": False,
    "replace_broken_text_layer": False,
    "ocr_lang": [],
    "ocr_scale": 3.0,
    "force_backend_text": False,
    "do_table_structure": True,
    "table_mode": "accurate",
    "do_cell_matching": True,
    "extract_form_fields": False,
    "images_scale": 1.0,
    "heading_hierarchy": False,
    "do_code_enrichment": False,
    "do_formula_enrichment": False,
    "document_timeout": None,
    "accelerator_device": "auto",
    "num_threads": 4,
}


def _parse_lang_list(val) -> list[str]:
    if val is None or val == "":
        return []
    items = (
        [str(x).strip() for x in val]
        if isinstance(val, (list, tuple))
        else [s.strip() for s in str(val).split(",")]
    )
    out = []
    for code in items:
        if not code:
            continue
        if not re.fullmatch(r"[A-Za-z]{2,8}(?:[-_][A-Za-z0-9]{2,8})?", code):
            raise ValueError(f"Ungültiger OCR-Sprachcode: {code}")
        out.append(code)
    return list(dict.fromkeys(out))


def normalize_conversion_settings(raw: dict | None) -> dict:
    """Validate and normalize user-configurable native Docling conversion options."""
    src = raw if isinstance(raw, dict) else {}
    out = dict(CONVERSION_DEFAULTS)

    bool_keys = (
        "do_ocr",
        "force_full_page_ocr",
        "replace_broken_text_layer",
        "force_backend_text",
        "do_table_structure",
        "do_cell_matching",
        "extract_form_fields",
        "heading_hierarchy",
        "do_code_enrichment",
        "do_formula_enrichment",
    )
    for k in bool_keys:
        if k in src and src[k] is not None:
            if type(src[k]) is not bool:
                raise ValueError(f"Boolesche Docling-Option erwartet: {k}")
            out[k] = src[k]

    if "ocr_lang" in src:
        out["ocr_lang"] = _parse_lang_list(src["ocr_lang"])

    if src.get("ocr_scale") not in (None, ""):
        scale = float(src["ocr_scale"])
        if not 0.5 <= scale <= 6.0:
            raise ValueError("OCR-Skalierung muss zwischen 0.5 und 6.0 liegen")
        out["ocr_scale"] = round(scale, 2)

    if src.get("images_scale") not in (None, ""):
        img_scale = float(src["images_scale"])
        if not 0.5 <= img_scale <= 4.0:
            raise ValueError("Bildauflösung (images_scale) muss zwischen 0.5 und 4.0 liegen")
        out["images_scale"] = round(img_scale, 2)

    if "table_mode" in src and src["table_mode"] not in (None, ""):
        if src["table_mode"] not in ("accurate", "fast"):
            raise ValueError("Tabellenmodus muss 'accurate' oder 'fast' sein")
        out["table_mode"] = src["table_mode"]

    if src.get("document_timeout") in (None, ""):
        out["document_timeout"] = None
    else:
        t_val = float(src["document_timeout"])
        if not 1.0 <= t_val <= 7200.0:
            raise ValueError("Dokument-Timeout muss zwischen 1 und 7200 Sekunden liegen")
        out["document_timeout"] = round(t_val, 1)

    if "accelerator_device" in src and src["accelerator_device"] not in (None, ""):
        if src["accelerator_device"] not in ("auto", "cpu", "cuda", "mps"):
            raise ValueError("Ungültiges Beschleuniger-Gerät")
        out["accelerator_device"] = src["accelerator_device"]

    if src.get("num_threads") not in (None, ""):
        threads = int(src["num_threads"])
        if not 1 <= threads <= 64:
            raise ValueError("Thread-Anzahl muss zwischen 1 und 64 liegen")
        out["num_threads"] = threads

    return out


def build_pdf_pipeline_parameters(conversion: dict | None, base_update: dict) -> dict:
    """Build native PdfPipelineOptions update dict without hardcoding values."""
    from docling.datamodel.pipeline_options import (
        AcceleratorOptions,
        HeadingHierarchyOptions,
        OcrAutoOptions,
        TableFormerMode,
        TableStructureOptions,
    )

    cfg = normalize_conversion_settings(conversion)
    table_mode = (
        TableFormerMode.FAST if cfg["table_mode"] == "fast" else TableFormerMode.ACCURATE
    )
    params = dict(
        base_update,
        generate_picture_images=True,
        generate_page_images=True,
        images_scale=cfg["images_scale"],
        do_ocr=cfg["do_ocr"],
        force_backend_text=cfg["force_backend_text"],
        ocr_options=OcrAutoOptions(
            lang=cfg["ocr_lang"],
            scale=cfg["ocr_scale"],
            replace_broken_text_layer=cfg["replace_broken_text_layer"],
            force_full_page_ocr=cfg["force_full_page_ocr"],
        ),
        do_table_structure=cfg["do_table_structure"],
        table_structure_options=TableStructureOptions(
            do_cell_matching=cfg["do_cell_matching"],
            mode=table_mode,
        ),
        extract_form_fields=cfg["extract_form_fields"],
        heading_hierarchy_options=HeadingHierarchyOptions(
            enabled=cfg["heading_hierarchy"]
        ),
        do_code_enrichment=cfg["do_code_enrichment"],
        do_formula_enrichment=cfg["do_formula_enrichment"],
        document_timeout=cfg["document_timeout"],
        accelerator_options=AcceleratorOptions(
            num_threads=cfg["num_threads"],
            device=cfg["accelerator_device"],
        ),
    )
    return params
