"""Docling conversion options and native picture diagnostics."""

from importlib.metadata import version
from contextlib import contextmanager
import logging
import os
import re
from urllib.parse import urlsplit

from . import models
from .conversion_config import DEFAULT_VISION_PROMPT, VISION_TIMEOUT_DEFAULT

PICTURE_PROMPT = DEFAULT_VISION_PROMPT


class VisionDiagnostics(logging.Handler):
    def __init__(self):
        super().__init__()
        self.events = []

    def emit(self, record):
        message = record.getMessage()
        http = re.search(r"\bstatus=([1-5][0-9]{2})\b", message)
        self.events.append(
            {"http_status": int(http[1]), "reason": "api_response"}
            if http
            else {
                "reason": "read_timeout"
                if "read timed out" in message.lower()
                else "native_api_error"
            }
        )


@contextmanager
def vision_diagnostics():
    logger = logging.getLogger("docling.utils.api_image_request")
    previous = logger.level, logger.propagate
    handler = VisionDiagnostics()
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    try:
        yield handler.events
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous[0])
        logger.propagate = previous[1]


def import_plan(vision):
    """Use verified capability for automatic descriptions and retain open states."""
    if not vision.get("enabled", True):
        return "disabled"
    problem = manual_plan({**vision, "send": True})
    if problem:
        return problem
    needs_model = vision.get("description", True) or vision.get("chart", False)
    if not needs_model or vision.get("mode") == "inline":
        return "planned"
    profile = models.profile_options(vision["profile"])
    capability = models.vision_capability(profile)
    if capability is None and profile["provider"] == "nhr_fau":
        try:
            capability = models.vision_capability(
                profile, directory=models.fau_entries(vision["profile"])
            )
        except ValueError:
            pass
    if capability is not True:
        return "vision_unknown" if capability is None else "vision_unsupported"
    return "planned" if vision.get("send") is True else "authorization_pending"


def api_picture_options(vision, profile, threshold):
    from docling.datamodel.pipeline_options import PictureDescriptionApiOptions

    if vision.get("send") is not True:
        raise ValueError("Pixelübermittlung bewusst bestätigen")
    clean = models.vision_options(profile)
    base = clean["base_url"]
    address = urlsplit(base)
    if not base or (
        address.scheme != "https"
        and address.hostname not in ("localhost", "127.0.0.1", "::1")
    ):
        raise ValueError(
            "HTTPS-Endpunkt oder lokalen OpenAI-kompatiblen Endpunkt angeben"
        )
    if clean["provider"] == "ollama" and not address.path.rstrip("/").endswith("/v1"):
        base += "/v1"
    key = models.runtime_key(clean, profile.get("key"))
    generation = {
        k: v
        for k, v in clean["generation"].items()
        if k in ("temperature", "top_p", "max_tokens", "seed")
    }
    if "max_output_tokens" in clean:
        generation.setdefault("max_tokens", clean["max_output_tokens"])
    params = dict(model=clean["model"], **generation)
    timeout = float(vision.get("timeout") or VISION_TIMEOUT_DEFAULT)
    if not 0 < timeout < float("inf"):
        raise ValueError("Positive Vision-Zeitgrenze angeben")
    active_prompt = str(vision.get("prompt") or "").strip() or PICTURE_PROMPT
    vis_scale = float(vision.get("scale") or 2.0)
    endpoint = base + "/chat/completions"
    options = PictureDescriptionApiOptions(
        url=endpoint,
        headers={"Authorization": "Bearer " + key} if key else {},
        params=params,
        picture_area_threshold=threshold,
        scale=vis_scale,
        prompt=active_prompt,
        timeout=timeout,
    )
    receipt = dict(
        provider=clean["provider"],
        endpoint=endpoint,
        model=clean["model"],
        generation=generation,
        scale=vis_scale,
        custom_prompt=bool(str(vision.get("prompt") or "").strip()),
        timeout=timeout,
    )
    return options, receipt


def converter(vision=None, conversion=None):
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        AcceleratorOptions,
        ConvertPipelineOptions,
        PdfPipelineOptions,
        PictureDescriptionVlmOptions,
    )
    from docling.datamodel.settings import settings
    from docling.document_converter import DocumentConverter
    from .conversion_config import (
        build_pdf_pipeline_parameters,
        normalize_conversion_settings,
    )

    conv_cfg = normalize_conversion_settings(conversion)
    settings.debug.profile_pipeline_timings = True
    native = DocumentConverter()
    receipt = {
        "docling": version("docling"),
        "docling_core": version("docling-core"),
        "conversion_options": conv_cfg,
    }
    update = {}
    if vision:
        mode = vision.get("mode")
        description = vision.get("description", True)
        classify = vision.get("classification", False)
        chart = vision.get("chart", False)
        threshold = float(vision.get("picture_area_threshold", 0.0))
        if not 0 <= threshold <= 1 or any(
            type(v) is not bool for v in (description, classify, chart)
        ):
            raise ValueError("Ungültige Bildoptionen")
        update.update(
            do_picture_description=description,
            do_picture_classification=classify or chart,
            do_chart_extraction=chart,
        )
        receipt.update(
            mode=mode,
            description=description,
            classification=classify or chart,
            chart=chart,
            picture_area_threshold=threshold,
        )
        if classify or chart:
            from docling.datamodel import stage_model_specs

            classifier = (
                stage_model_specs.IMAGE_CLASSIFICATION_DOCUMENT_FIGURE.model_spec
            )
            receipt["classification_model"] = dict(
                repo=classifier.repo_id, revision=classifier.revision
            )
            if chart:
                chart_model = (
                    stage_model_specs.CHART_EXTRACTION_GRANITE_VISION_V4.model_spec
                )
                receipt["chart_model"] = dict(
                    repo=chart_model.default_repo_id, revision=chart_model.revision
                )
        profile = vision.get("profile") or {}
        if mode == "api" and (description or chart):
            picture, api_receipt = api_picture_options(vision, profile, threshold)
            receipt.update(api_receipt)
            update.update(
                enable_remote_services=True, picture_description_options=picture
            )
            for name in ("docling.utils.api_image_request", "urllib3"):
                logging.getLogger(name).setLevel(logging.CRITICAL)
            if chart:
                from docling.datamodel.chart_extraction_options import (
                    ChartExtractionVlmEngineOptions,
                )
                from docling.datamodel.vlm_engine_options import (
                    ApiVlmEngineOptions,
                    VlmEngineType,
                )

                update["chart_extraction_options"] = (
                    ChartExtractionVlmEngineOptions.from_preset(
                        "granite_vision_v4",
                        engine_options=ApiVlmEngineOptions(
                            engine_type=VlmEngineType.API_OPENAI,
                            url=picture.url,
                            headers=picture.headers,
                            params=picture.params,
                            timeout=picture.timeout,
                        ),
                        use_natural_language_prompts=True,
                    )
                )
                receipt["chart_model"] = dict(
                    provider=api_receipt["provider"], model=api_receipt["model"]
                )
        elif description:
            model = str(profile.get("model", "")).strip()
            if mode != "inline" or not model:
                raise ValueError("Vision-Verarbeitung und lokales Modell angeben")
            active_prompt = str(vision.get("prompt") or "").strip() or PICTURE_PROMPT
            update["picture_description_options"] = PictureDescriptionVlmOptions(
                repo_id=model,
                picture_area_threshold=threshold,
                scale=float(vision.get("scale") or 2.0),
                prompt=active_prompt,
            )
            receipt["model"] = model
    accel = AcceleratorOptions(
        num_threads=conv_cfg["num_threads"],
        device=conv_cfg["accelerator_device"],
    )
    for fmt, option in native.format_to_options.items():
        if not isinstance(option.pipeline_options, ConvertPipelineOptions):
            continue
        if isinstance(option.pipeline_options, PdfPipelineOptions):
            parameters = build_pdf_pipeline_parameters(conv_cfg, update)
        else:
            parameters = dict(
                update,
                document_timeout=conv_cfg["document_timeout"],
                accelerator_options=accel,
            )
        option.pipeline_options = option.pipeline_options.model_copy(update=parameters)
        if fmt == InputFormat.PDF and os.name == "nt":
            from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

            option.backend = PyPdfiumDocumentBackend
    return native, receipt


def pictures(doc, receipt, *, configuration=None):
    from .evidence import picture_source

    details = []
    for picture in doc.pictures:
        try:
            # Stored documents may contain user-controlled image links. Resolve only
            # embedded images and crops of embedded pages in a read-only view.
            page = doc.pages.get(picture.prov[0].page_no) if picture.prov else None
            image = picture.image or (page.image if page else None)
            pixels = bool(
                image
                and str(image.uri).startswith("data:image/")
                and picture.get_image(doc) is not None
            )
            error = None
        except Exception as exc:
            pixels, error = False, type(exc).__name__
        meta = picture.meta
        desc = getattr(meta, "description", None)
        classification = getattr(meta, "classification", None)
        image_type = (
            classification.get_main_prediction().class_name
            if classification and classification.predictions
            else None
        )
        chart = getattr(meta, "tabular_chart", None)
        fraction = None
        if picture.prov:
            prov = picture.prov[0]
            page = doc.pages.get(prov.page_no)
            if page and page.size.width and page.size.height:
                fraction = prov.bbox.area() / (page.size.width * page.size.height)
        description_status = (
            "ENRICHED"
            if desc and desc.text
            else "NO_PIXELS"
            if not pixels
            else "BELOW_THRESHOLD"
            if fraction is not None
            and fraction < receipt.get("picture_area_threshold", 0)
            else "NO_DESCRIPTION"
            if receipt.get("description")
            else "NOT_REQUESTED"
        )
        classification_status = (
            "ENRICHED"
            if image_type
            else "NOT_REQUESTED"
            if not receipt.get("classification")
            else "NO_CLASSIFICATION"
            if pixels
            else "NO_PIXELS"
        )
        chart_status = "ENRICHED" if chart else "NOT_REQUESTED"
        if receipt.get("chart") and not chart:
            from docling.models.stages.chart_extraction.granite_vision import (
                SUPPORTED_CHART_TYPES,
            )

            chart_status = (
                "NO_PIXELS"
                if not pixels
                else "NO_CLASSIFICATION"
                if not image_type
                else "NO_CHART_DATA"
                if image_type in SUPPORTED_CHART_TYPES
                else "UNSUPPORTED_CLASS"
            )
        details.append(
            dict(
                ref=picture.self_ref,
                page=picture.prov[0].page_no if picture.prov else None,
                category=picture_source(picture, configuration)["kind"],
                status=description_status
                if receipt.get("description") or desc or not pixels
                else "ENRICHED"
                if image_type or chart
                else classification_status,
                pixel_available=pixels,
                area_fraction=fraction,
                description=desc.text if desc else None,
                description_status=description_status,
                error=error,
                classification=bool(image_type),
                image_type=image_type,
                classification_status=classification_status,
                chart=bool(chart),
                chart_status=chart_status,
            )
        )
    return details


def missing_output(pictures, requested):
    return any(
        requested.get("description")
        and p["description_status"] in ("NO_PIXELS", "NO_DESCRIPTION")
        or requested.get("classification")
        and p["classification_status"] in ("NO_PIXELS", "NO_CLASSIFICATION")
        or requested.get("chart")
        and p["chart_status"] == "NO_CHART_DATA"
        for p in pictures
    )


def picture_counts(pictures):
    return dict(
        pictures=len(pictures),
        pixels=sum(p["pixel_available"] for p in pictures),
        described=sum(p["description_status"] == "ENRICHED" for p in pictures),
        classified=sum(p["classification"] for p in pictures),
        charts=sum(p["chart"] for p in pictures),
        description_open=sum(
            p["description_status"] in ("NO_DESCRIPTION", "NO_PIXELS") for p in pictures
        ),
    )


def applied_metadata(doc):
    """Ignore the native empty description placeholder on API failure."""
    fields = []
    for picture in doc.pictures:
        meta = picture.meta
        description = getattr(meta, "description", None)
        fields.append(
            (
                description if description and description.text else None,
                getattr(meta, "classification", None),
                getattr(meta, "tabular_chart", None),
            )
        )
    return fields


def retry_input(doc, path):
    """Let Docling retry empty placeholders while retaining completed descriptions."""
    from io import BytesIO
    from docling.datamodel.base_models import DocumentStream

    if not any(
        p.meta and p.meta.description and not p.meta.description.text
        for p in doc.pictures
    ):
        return path
    copy = doc.model_copy(deep=True)
    for picture in copy.pictures:
        if (
            picture.meta
            and picture.meta.description
            and not picture.meta.description.text
        ):
            picture.meta.description = None
    return DocumentStream(
        name=path.name,
        stream=BytesIO(
            copy.model_dump_json(by_alias=True, exclude_computed_fields=True).encode()
        ),
    )


def manual_plan(vision):
    """Block incomplete or unconsented requests before creating a remote pipeline."""
    if not vision.get("description", True) and not vision.get("chart", False):
        return None if vision.get("classification", False) else "no_vision_tasks"
    if vision.get("mode") == "inline" and not vision.get("description", True):
        return None
    profile = vision.get("profile") or {}
    if not profile:
        return "profile_missing"
    if not str(profile.get("model", "")).strip():
        return "model_missing"
    if vision.get("mode") == "api":
        if vision.get("send") is not True:
            return "authorization_pending"
        try:
            clean = models.vision_options(profile)
        except ValueError:
            return "invalid_profile"
        host = urlsplit(clean["base_url"]).hostname
        if not host:
            return "vision_endpoint_missing"
        if host not in ("127.0.0.1", "localhost", "::1") and not models.runtime_key(
            clean, profile.get("key")
        ):
            return "vision_access_missing"
        if models.vision_capability(clean) is False:
            return "vision_unsupported"
    return None


def picture_outcome(pictures, status):
    if status not in ("success", "partial_success"):
        return "vision_failed"
    if pictures and not any(p["pixel_available"] for p in pictures):
        return "no_pixels"
    if any(p["description_status"] == "NO_DESCRIPTION" for p in pictures):
        return "no_description"
    if status == "partial_success":
        return "vision_partial"
    return "enriched"


def error_receipt(error):
    # Public ErrorItem text may contain the provider body, preserve only its native HTTP prefix.
    match = re.match(r"^HTTP ([1-5][0-9]{2})(?=[: ]|$)", error.error_message)
    return dict(
        component=error.component_type.value,
        module=error.module_name,
        category=error.category.value,
        page=error.page_no,
        http_status=int(match[1]) if match else None,
    )
