"""Transparent, user-configurable base prompts, custom addenda & stage contracts."""

from __future__ import annotations

from .conversion_config import DEFAULT_VISION_PROMPT
from .templates import (
    FindingHypotheses,
    FindingProposal,
    Observation,
    RelationProposal,
    RelationshipProposals,
    UXEvidenceDocument,
)

MAX_STAGE_PROMPT_CHARS = 8000

STAGE_KEYS = ("vision", "A", "B", "C")


def stage_prompt_catalog() -> dict[str, dict]:
    """Return default prompts, input/output contracts, and schema rules per stage."""
    return {
        "vision": {
            "stage": "vision",
            "title_de": "Stufe 02 · Vision & Folienkontext",
            "title_en": "Stage 02 · Vision & Slide Context",
            "default_prompt": DEFAULT_VISION_PROMPT,
            "input_de": "Eingebettete Bilder, Screenshots, Diagramme sowie gerenderte 72-DPI-Ganzfolien (PPTX) aus dem DoclingDocument.",
            "input_en": "Embedded images, screenshots, charts, and rendered 72-DPI full slides (PPTX) from the DoclingDocument.",
            "output_de": "Versionierte Bildbeschreibung (PictureItem.meta.description) in einer neuen SHA-256-Anreicherungsfassung ohne Überschreiben der Basis.",
            "output_en": "Versioned image description (PictureItem.meta.description) stored in a new SHA-256 enrichment version without overwriting the base.",
            "schema_summary_de": (
                "Wird direkt an Docling PictureDescriptionApiOptions / PictureDescriptionVlmOptions übergeben. "
                "Transkribiert sichtbare UI-Labels, Diagrammachsen, Werte, Pfeilverbindungen (Quelle -> Ziel), "
                "Streichungen und Haftnotizen ohne Spekulation über unsichtbare Nutzerabsichten."
            ),
            "schema_summary_en": (
                "Passed directly to Docling PictureDescriptionApiOptions / PictureDescriptionVlmOptions. "
                "Transcribes visible UI labels, chart axes, values, connector flows (source -> target), "
                "crossings-out, and sticky notes without inferring unseen intent."
            ),
        },
        "A": {
            "stage": "A",
            "title_de": "Stufe 03 · Evidenz-Extraktion (A)",
            "title_en": "Stage 03 · Evidence Extraction (A)",
            "default_prompt": (UXEvidenceDocument.__doc__ or "").strip(),
            "item_docstring": (Observation.__doc__ or "").strip(),
            "input_de": "Einzelnes konvertiertes/angereichertes DoclingDocument (serialisiert als doclang-geo inkl. Koordinaten, Tabellen-Captions, Streichungen und Zeitspuren).",
            "input_en": "Single converted/enriched DoclingDocument (serialized as doclang-geo with coordinates, table captions, strikethroughs, and timestamps).",
            "output_de": "Atomare Beobachtungen (Observation O1..On) mit wörtlichem Zitat, Locator (self_ref, row, col), Sprecherrolle und Messwerten — anschließend rückwärts per 7-Stufen-Re-Grounding verifiziert.",
            "output_en": "Atomic observations (Observation O1..On) with verbatim quote, locator (self_ref, row, col), speaker attribution, and measurements — deterministically verified via 7-step re-grounding.",
            "schema_summary_de": (
                "Pydantic-Vertrag UXEvidenceDocument -> Observation: Jedes Zitat (quote) muss wörtlich "
                "und zusammenhängend aus genau einem Docling-Element (ux_maind__source_ref) stammen; "
                "Messwerte trennen raw_value, numeric_value, measurement_kind und scale_direction; "
                "Streichungen/Negationen und Sprecherrollen bleiben explizit erhalten."
            ),
            "schema_summary_en": (
                "Pydantic contract UXEvidenceDocument -> Observation: Every quote must be a verbatim "
                "contiguous substring of one Docling element (ux_maind__source_ref); measurements separate "
                "raw_value, numeric_value, measurement_kind, and scale_direction; strikethroughs and speaker roles stay explicit."
            ),
        },
        "B": {
            "stage": "B",
            "title_de": "Stufe 04 · Dokumentübergreifende Beziehungen (B)",
            "title_en": "Stage 04 · Cross-Document Relations (B)",
            "default_prompt": (RelationshipProposals.__doc__ or "").strip(),
            "item_docstring": (RelationProposal.__doc__ or "").strip(),
            "input_de": "Alle verankerten A-Beobachtungen der ausgewählten Studiendokumente, unzitierter Dokument-/Tabellenkontext, Provenance-Manifest, Ausschluss-Zusammenfassung und Forscher-Entscheidungen.",
            "input_en": "All anchored Stage A observations across selected study documents, uncited document/table context, provenance manifest, exclusion summary, and researcher decisions.",
            "output_de": "Reifizierte Beziehungsknoten (RelationProposal) zwischen je zwei A-Beobachtungen (z. B. corroborates, contradicts, precedes, qualifies, recovered_by) oder leere Liste [] bei fehlender Evidenz.",
            "output_en": "Reified relation nodes (RelationProposal) linking pairs of Stage A observations (e.g., corroborates, contradicts, precedes, qualifies, recovered_by) or [] when unsupported.",
            "schema_summary_de": (
                "Pydantic-Vertrag RelationshipProposals -> RelationProposal: Verbindet zwei verifizierte "
                "A-Beobachtungen ({document, run, observation}) nur bei belegter fachlicher Beziehung. "
                "Ganzfolien-Doppelungen gelten als Überlappung, nicht als unabhängige Bestätigung."
            ),
            "schema_summary_en": (
                "Pydantic contract RelationshipProposals -> RelationProposal: Connects two verified "
                "Stage A observations ({document, run, observation}) only when grounded by evidence. "
                "Full-slide renders count as overlap, not independent corroboration."
            ),
        },
        "C": {
            "stage": "C",
            "title_de": "Stufe 05 · Usability-Befunde & Synthese (C)",
            "title_en": "Stage 05 · Usability Findings & Synthesis (C)",
            "default_prompt": (FindingHypotheses.__doc__ or "").strip(),
            "item_docstring": (FindingProposal.__doc__ or "").strip(),
            "input_de": "Verankerte A-Beobachtungen, bestätigte/offene B-Relationen, Forscher-Korrekturen sowie unzitierter Studienkontext.",
            "input_en": "Anchored Stage A observations, confirmed/open Stage B relations, researcher overrides, and uncited study context.",
            "output_de": "Prüfbare Usability-Befunde (FindingProposal) mit Stützen (supports), Gegenbelegen (opposes), Einschränkungen (qualifies), Valenz, UX-Heuristik (Nielsen/ISO), Reichweite (scope) und Verbesserungs-Hypothese.",
            "output_en": "Verifiable UX findings (FindingProposal) with supports, counterevidence (opposes), qualifications (qualifies), valence, UX heuristic (Nielsen/ISO), scope, and improvement hypothesis.",
            "schema_summary_de": (
                "Pydantic-Vertrag FindingHypotheses -> FindingProposal: Verdichtet verankerte A-Belege und "
                "B-Relationen zu abgegrenzten Befunden inkl. Gegenbeleg-Pflichtprüfung, Nicht-Doppelzählung "
                "abhängiger Ansichten und optionaler Nielsen-/ISO-9241-110-Einordnung."
            ),
            "schema_summary_en": (
                "Pydantic contract FindingHypotheses -> FindingProposal: Synthesizes anchored A observations and "
                "B relations into bounded findings with counterevidence checks, overlap deduplication, "
                "and optional Nielsen / ISO 9241-110 heuristic mapping."
            ),
        },
    }


def normalize_stage_prompts(raw: dict | None, *, vision_prompt_fallback: str = "") -> dict[str, str]:
    """Validate and normalize custom supplementary stage instructions (`stage_prompts`)."""
    src = raw if isinstance(raw, dict) else {}
    out: dict[str, str] = {}
    for key in STAGE_KEYS:
        val = src.get(key, "")
        if val is None:
            val = ""
        if not isinstance(val, str) or len(val) > MAX_STAGE_PROMPT_CHARS:
            raise ValueError(f"Ungültiger Stufen-Zusatzprompt für {key}")
        out[key] = val.strip()
    if not out["vision"] and vision_prompt_fallback:
        out["vision"] = vision_prompt_fallback.strip()
    return out


def normalize_base_prompts(raw: dict | None) -> dict[str, str]:
    """Validate and normalize user-edited base prompts (`base_prompts`).

    Empty string `""` means: use the factory `default_prompt` from `stage_prompt_catalog()`.
    If the submitted text equals the factory `default_prompt`, normalize to `""` so default updates stay clean.
    """
    src = raw if isinstance(raw, dict) else {}
    catalog = stage_prompt_catalog()
    out: dict[str, str] = {}
    for key in STAGE_KEYS:
        val = src.get(key, "")
        if val is None:
            val = ""
        if not isinstance(val, str) or len(val) > MAX_STAGE_PROMPT_CHARS:
            raise ValueError(f"Ungültiger Basis-Prompt für {key}")
        cleaned = val.strip()
        default_text = (catalog.get(key, {}).get("default_prompt") or "").strip()
        out[key] = "" if cleaned == default_text else cleaned
    return out


def resolve_vision_prompt(
    *,
    vision_cfg: dict | None = None,
    stage_prompts: dict | None = None,
    base_prompts: dict | None = None,
    output_language: str = "auto",
) -> str:
    """Resolve effective Vision prompt from base override + custom addendum + output language."""
    vcfg = vision_cfg if isinstance(vision_cfg, dict) else {}
    sp = stage_prompts if isinstance(stage_prompts, dict) else {}
    bp = base_prompts if isinstance(base_prompts, dict) else {}

    base_override = str(bp.get("vision") or "").strip()
    legacy_direct = str(vcfg.get("prompt") or "").strip()
    custom_addendum = str(sp.get("vision") or "").strip()

    # If legacy callers passed vision.prompt directly (and it differs from custom_addendum when base_override is empty),
    # treat legacy vision.prompt as override only when neither base_prompts nor stage_prompts split was used.
    if base_override:
        prompt = base_override
    elif legacy_direct and not custom_addendum:
        prompt = legacy_direct
    else:
        prompt = DEFAULT_VISION_PROMPT

    if custom_addendum and custom_addendum != prompt:
        prompt = f"{prompt}\n\nAdditional researcher instructions: {custom_addendum}"

    if not base_override and not legacy_direct:
        if output_language == "de":
            prompt = (
                f"{prompt} Write descriptive sentences in German while transcribing "
                "visible UI labels, numbers, and text verbatim in their original language."
            )
        elif output_language == "en":
            prompt = (
                f"{prompt} Write descriptive sentences in English while transcribing "
                "visible UI labels, numbers, and text verbatim in their original language."
            )
    return prompt


def apply_stage_prompt(
    template_cls,
    custom_prompt: str | None = None,
    *,
    base_override: str | None = None,
    output_language: str = "auto",
):
    """Return a Pydantic template subclass carrying base prompt overrides, addenda, and language."""
    default_doc = (template_cls.__doc__ or "").strip()
    base_doc = str(base_override or "").strip() or default_doc
    extra = str(custom_prompt or "").strip()
    lang_note = ""
    if output_language == "de":
        lang_note = "Write synthesized analytical text fields in German while keeping verbatim quotes in their original source language."
    elif output_language == "en":
        lang_note = "Write synthesized analytical text fields in English while keeping verbatim quotes in their original source language."

    parts = [base_doc]
    if extra:
        parts.append(f"Additional researcher instructions:\n{extra}")
    if lang_note:
        parts.append(lang_note)
    combined = "\n\n".join(p for p in parts if p)
    if combined == default_doc:
        return template_cls
    return type(template_cls.__name__, (template_cls,), {"__doc__": combined})


def build_synthesis_directive(
    stage: str,
    *,
    focus: str = "",
    output_language: str = "auto",
    base_override: str = "",
    custom_prompt: str = "",
) -> str:
    """Build clean System-Message synthesis directive for Stage B and Stage C (`US-34` / `D-03`)."""
    role = (
        "You are performing source-grounded UX cross-observation relationship analysis (Stage B)."
        if stage == "B"
        else "You are performing source-grounded UX finding synthesis (Stage C)."
    )
    rules = [
        role,
        "Operate strictly on the supplied pre-extracted Stage A observations ({document, run, observation}) and provenance manifest.",
        "Never fabricate observation IDs, relation IDs, severity numbers, or unstated causal certainty.",
        "Abstain and output an empty list [] whenever no genuine evidence-backed relation or counterevidence exists (overriding generic completeness heuristics).",
    ]
    if base_override.strip():
        rules.append(f"Stage base directive: {base_override.strip()}")
    if custom_prompt.strip():
        rules.append(f"Researcher stage instructions: {custom_prompt.strip()}")
    if focus.strip():
        rules.append(f"Specific research focus for this run: {focus.strip()}")
    if output_language == "de":
        rules.append(
            "Output language: Write all analytical fields (title, rationale, situation, observed_effect, scope, uncertainty, improvement_hypothesis) in German."
        )
    elif output_language == "en":
        rules.append(
            "Output language: Write all analytical fields (title, rationale, situation, observed_effect, scope, uncertainty, improvement_hypothesis) in English."
        )
    return "\n".join(rules)
