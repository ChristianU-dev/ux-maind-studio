"""Separate source-bound B/C analyses through the shared native pipeline."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from . import models, research
from .templates import FindingHypotheses, RelationshipProposals

STAGES = {
    "B": (RelationshipProposals, "relations", "relation"),
    "C": (FindingHypotheses, "findings", "finding"),
}


def refkey(ref):
    return tuple(research.reference(ref).values())


def relation_valid(proposal, available):
    try:
        source, target = (refkey(proposal[k]) for k in ("source", "target"))
    except (KeyError, TypeError, ValueError):
        return False
    return (
        source in available
        and target in available
        and source != target
        and bool(proposal.get("rationale"))
    )


def finding_valid(proposal, available, relations):
    """Check every explicit source reference without constraining optional UX meaning."""
    try:
        evidence = [
            *proposal["supports"],
            *proposal.get("opposes", []),
            *proposal.get("qualifies", []),
            *proposal.get("improvement_evidence", []),
        ]
        return (
            bool(proposal["supports"])
            and all(refkey(ref) in available for ref in evidence)
            and set(proposal.get("relations", [])).issubset(relations)
        )
    except (KeyError, TypeError, ValueError):
        return False


def selected_relations(
    workspace, numbers, b_run, available, basis_runs, *, allow_partial=False
):
    saved = research.objects(workspace, numbers)
    selected = next(
        (r for r in saved if r["id"] == b_run and r["kind"] == "comparison"), None
    )
    allowed_statuses = (
        ("UNREVIEWED", "NO_PROPOSALS", "PARTIAL")
        if allow_partial
        else ("UNREVIEWED", "NO_PROPOSALS")
    )
    ng = (selected["metadata"].get("native_graph") or {}) if selected else {}
    b_truncated = bool(
        (ng.get("last_response") or {}).get("truncated")
        or any(
            r.get("finish_reason") in ("length", "max_tokens")
            for r in ng.get("requests", [])
        )
    )
    if (
        not selected
        or selected["metadata"].get("stage") not in (None, "B")
        or selected["metadata"].get("status") not in allowed_statuses
        or (selected["metadata"].get("status") == "PARTIAL" and b_truncated)
        or sorted(selected["metadata"]["scope"]) != sorted(set(map(int, numbers)))
        or research.basis_runs(selected["metadata"]) != basis_runs
    ):
        raise ValueError(
            "Der B-Lauf muss vollständig sein und zur gewählten A-Basis passen."
        )
    offered, excluded = [], []
    for relation in saved:
        if (
            relation["kind"] != "relation"
            or relation["metadata"].get("comparison") != b_run
        ):
            continue
        proposal = relation["effective"]
        if (
            proposal.get("kind")
            and relation_valid(proposal, available)
            and relation["review"] != "HUMAN_REJECTED"
        ):
            offered.append(
                dict(
                    proposal,
                    id=relation["id"],
                    review=relation["review"],
                    decisions=relation.get("decisions") or [],
                )
            )
        else:
            human_reasons = [
                d["reason"]
                for d in (relation.get("decisions") or [])
                if d.get("origin") == "human" and d.get("reason")
            ]
            excluded.append(dict(
                id=relation["id"], review=relation["review"], proposal=proposal,
                reason="HUMAN_REJECTED" if relation["review"] == "HUMAN_REJECTED"
                else "NO_RELATION" if not proposal.get("kind") else "UNRESOLVED_REFERENCE",
                **(
                    {"researcher_reason": human_reasons[-1]}
                    if human_reasons
                    else {}
                ),
            ))
    return offered, excluded


def plan(workspace, numbers, *, basis=None, b_run=None, stage="B", allow_partial=False):
    from .handoff import manifest
    if stage not in STAGES or (stage == "B" and b_run is not None):
        raise ValueError("Ungültige Analysestufe oder B-Basis")
    catalog = research.catalog(workspace, numbers, include_context=True, basis=basis)
    records, excluded = [], []
    picture_count = 0
    for entry in catalog["observations"]:
        ref, matches = entry["ref"], entry["source_check"]["matches"]
        rejected = (
            next(
                (
                    d["action"]
                    for d in reversed(entry["decisions"])
                    if d["origin"] == "human"
                ),
                None,
            )
            == "rejected"
        )
        if not matches or rejected:
            human_notes = [
                d["reason"]
                for d in entry["decisions"]
                if d.get("origin") == "human" and d.get("reason")
            ]
            excluded.append(
                dict(
                    ref=ref,
                    statement=entry["effective"].get("statement"),
                    reason="HUMAN_REJECTED" if rejected else "UNRESOLVED_SOURCE",
                    **(
                        {"researcher_reason": human_notes[-1]}
                        if human_notes
                        else {}
                    ),
                )
            )
            continue
        picture_count += bool(entry["picture_sources"])
        records.append(
            dict(
                ref=ref,
                quote=entry["effective"].get("quote"),
                statement=entry["effective"].get("statement"),
                kind=entry["effective"].get("kind"),
                origin=entry["effective"].get("origin"),
                negated_or_struck=bool(entry["effective"].get("negated_or_struck", False)),
                context=entry["effective"].get("context"),
                context_reference=entry["effective"].get("context_reference"),
                uncertainty=entry["effective"].get("uncertainty"),
                sources=matches,
                picture_sources=[
                    dict(a["picture_source"], modality=a["modality"], prov=a["prov"])
                    for a in entry["picture_sources"]
                ],
                measurements=entry["measurements"],
                selected_source=entry["selected_source"],
                context_decisions=entry["context_decisions"],
                review=entry["decisions"],
                document_version=entry["document_version"],
                source_sha256=entry.get("source_sha256"),
            )
        )
    b_run = int(b_run) if b_run is not None else None
    selected = {d["selected_run"] for d in catalog["documents"] if d["selected_run"]}
    relationships, excluded_relations = (
        selected_relations(
            workspace,
            numbers,
            b_run,
            {refkey(r["ref"]) for r in records},
            selected,
            allow_partial=allow_partial,
        )
        if b_run is not None
        else ([], [])
    )
    return dict(
        stage=stage,
        documents=catalog["documents"],
        offered=records,
        excluded=excluded,
        total=len(catalog["observations"]),
        grounded=sum(
            bool(e["source_check"]["matches"]) for e in catalog["observations"]
        ),
        pictures=picture_count,
        context=catalog["native_source_context"],
        a_relations=catalog.get("relations", []),
        relations=relationships,
        excluded_relations=[r["id"] for r in excluded_relations],
        excluded_relation_manifest=excluded_relations,
        b_run=b_run,
        manifest=manifest(catalog["observations"], catalog["documents"]),
    )


def require_basis(inputs, *, allow_partial=False):
    from .a_status import reason_text

    hard_blocks = {"response_truncated", "a_validation_open"}
    for document in inputs["documents"]:
        if document.get("archived"):
            raise ValueError(
                f"{document['name']}: Dokument für einen neuen Auftrag wiederherstellen."
            )
        technical = document.get("technical")
        if not technical:
            raise ValueError(
                f"{document['name']}: Einen gespeicherten A-Lauf wählen oder A ausführen."
            )
        reasons = list(dict.fromkeys(technical["reasons"]))
        blocking = [r for r in reasons if r in hard_blocks] if allow_partial else reasons
        if blocking or (not allow_partial and not technical["eligible"]):
            message = " ".join(reason_text.get(code, code) for code in (blocking or reasons))
            raise ValueError(
                f"{document['name']} · A #{document['selected_run']}: {message}"
            )
    if not inputs["offered"]:
        raise ValueError(
            "Die A-Basis enthält keine verwendbaren quellengebundenen Beobachtungen."
        )


def _compact_anchor(anchor, *, include_quote=True):
    if not isinstance(anchor, dict):
        return anchor
    pages = sorted(
        {
            p["page_no"]
            for p in anchor.get("prov", ())
            if isinstance(p, dict) and p.get("page_no") is not None
        }
    )
    keys = (
        "evidence_id",
        "ref",
        "modality",
        "quote" if include_quote else None,
        "row",
        "row_end",
        "column",
        "column_end",
        "column_header",
        "row_header",
        "worksheet",
        "picture_source",
        "track",
        "strikethrough_spans",
        "label_origin",
        "chart_cell",
    )
    compact = {
        k: anchor[k]
        for k in keys
        if k and anchor.get(k) not in (None, [])
    }
    if isinstance(anchor.get("formatting"), dict):
        active_fmt = {
            fk: fv
            for fk, fv in anchor["formatting"].items()
            if fv is True
        }
        if active_fmt:
            compact["formatting"] = active_fmt
    if isinstance(anchor.get("outline"), list) and anchor["outline"]:
        trail = [o.get("text") for o in anchor["outline"] if isinstance(o, dict) and o.get("text")]
        if trail:
            compact["outline"] = trail
    if anchor.get("layer") not in (None, "body"):
        compact["layer"] = anchor["layer"]
    if pages:
        compact["pages"] = pages
    return compact


def _compact_measurement(m):
    out = {
        k: m[k]
        for k in (
            "numeric_value",
            "raw_value",
            "unit",
            "scope",
            "measurement_kind",
            "uncertainty",
        )
        if m.get(k) is not None
    }
    if "numeric_value" not in out and m.get("value") is not None:
        out["numeric_value"] = m["value"]
    if m.get("scale_direction") not in (None, "unknown"):
        out["scale_direction"] = m["scale_direction"]
    if m.get("negated"):
        out["negated"] = True
    sources = m.get("sources") or []
    if sources:
        if any(a.get("picture_source") or a.get("layer") == "derived" for a in sources):
            out["sources"] = [_compact_anchor(a, include_quote=False) for a in sources]
        else:
            out["source_refs"] = [
                f"{a['ref']}[{a['row']},{a['column']}]"
                if "row" in a and "column" in a and a.get("ref")
                else a.get("ref") or a.get("evidence_id")
                for a in sources
            ]
    return out


def _compact_human_decisions(decisions):
    human = [d for d in (decisions or []) if d.get("origin") == "human"]
    if not human:
        return None
    latest = human[-1]
    notes = [d["reason"] for d in human if d.get("reason")]
    info = {"origin": "human_researcher_decision", "latest_action": latest.get("action")}
    if notes:
        info["researcher_notes"] = notes
    return info


def _compact_observation(record):
    compact = {
        "ref": record["ref"],
        "quote": record.get("quote"),
        "statement": record.get("statement"),
        "kind": record.get("kind"),
        "origin": record.get("origin"),
        "sources": [_compact_anchor(a, include_quote=False) for a in record.get("sources", [])],
    }
    if record.get("negated_or_struck"):
        compact["negated_or_struck"] = True
    for key in ("context", "context_reference", "uncertainty"):
        if record.get(key):
            compact[key] = record[key]
    if record.get("picture_sources"):
        compact["picture_sources"] = [
            {k: v for k, v in p.items() if k != "prov"}
            | (
                {
                    "pages": sorted(
                        {
                            x["page_no"]
                            for x in p.get("prov", ())
                            if isinstance(x, dict) and x.get("page_no") is not None
                        }
                    )
                }
                if p.get("prov")
                else {}
            )
            for p in record.get("picture_sources", [])
        ]
    if record.get("measurements"):
        compact["measurements"] = [_compact_measurement(m) for m in record["measurements"]]
    if record.get("selected_source"):
        compact["selected_source"] = _compact_anchor(record["selected_source"], include_quote=False)
    if record.get("context_decisions"):
        compact["context_decisions"] = record["context_decisions"]
    human_rev = _compact_human_decisions(
        record.get("review") if isinstance(record.get("review"), list) else record.get("decisions")
    )
    if human_rev:
        compact["human_review"] = human_rev
    return compact


def _compact_relation(rel):
    out = {
        k: rel[k]
        for k in (
            "id",
            "review",
            "source",
            "target",
            "kind",
            "rationale",
            "uncertainty",
            "situation",
            "inference_basis",
        )
        if rel.get(k) is not None
    }
    human_rev = _compact_human_decisions(rel.get("decisions"))
    if human_rev:
        out["human_review"] = human_rev
    return out


def _compact_context(chunk, quoted_by_doc_ref=None):
    out = {
        k: chunk[k]
        for k in (
            "document",
            "name",
            "chunk",
            "self_refs",
            "headings",
            "pages",
            "picture_sources",
        )
        if chunk.get(k) not in (None, [])
    }
    text = chunk.get("text")
    if text:
        refs = chunk.get("self_refs") or []
        if (
            quoted_by_doc_ref is not None
            and refs
            and not chunk.get("picture_sources")
            and all((chunk.get("document"), ref) in quoted_by_doc_ref for ref in refs)
        ):
            covered_chars = sum(
                len(quoted_by_doc_ref[(chunk.get("document"), ref)]) for ref in refs
            )
            norm_len = max(1, len(" ".join(text.split())))
            if all(str(r).startswith("#/tables/") for r in refs):
                data_lines = [
                    ln.strip()
                    for ln in text.splitlines()
                    if ln.strip() and not set(ln.strip()) <= {"|", "-", ":", " "}
                ]
                if len(data_lines) >= 3:
                    combined_q = " ".join(
                        quoted_by_doc_ref[(chunk.get("document"), ref)] for ref in refs
                    ).lower()
                    body_rows = data_lines[1:]
                    covered_rows = sum(
                        any(
                            cell.strip() and len(cell.strip()) >= 2 and cell.strip().lower() in combined_q
                            for cell in row_ln.split("|")
                        )
                        for row_ln in body_rows
                    )
                    if body_rows and covered_rows >= 0.85 * len(body_rows):
                        out["text_omitted"] = "table_covered_in_observations"
                        return out
                elif covered_chars >= 0.50 * norm_len:
                    out["text_omitted"] = "table_covered_in_observations"
                    return out
            elif covered_chars >= 0.92 * norm_len:
                out["text_omitted"] = "covered_in_observations"
                return out
        out["text"] = text
    return out


def _build_synthesis_document(inputs, stage):
    """Build pure-data synthetic DoclingDocument for Stage B/C (`US-34` / `D-03`)."""
    from docling_core.types.doc import DocItemLabel, DoclingDocument

    rows, relations = inputs["offered"], inputs["relations"]
    document = DoclingDocument(name=f"UX evidence for stage {stage}")
    excluded_summary = []
    for item in inputs["excluded"]:
        ex_obs = dict(
            type="observation",
            ref=item["ref"],
            reason=item["reason"],
        )
        if item.get("statement"):
            ex_obs["statement"] = str(item["statement"])[:240]
        if item.get("researcher_reason"):
            ex_obs["researcher_reason"] = item["researcher_reason"]
        excluded_summary.append(ex_obs)
    for item in inputs.get("excluded_relation_manifest", []):
        prop = item.get("proposal") or {}
        ex_rel = dict(
            type="relation",
            id=item["id"],
            reason=item["reason"],
            review=item["review"],
        )
        for rk in ("source", "target", "kind"):
            if prop.get(rk) is not None:
                ex_rel[rk] = prop[rk]
        if prop.get("rationale"):
            ex_rel["rationale"] = str(prop["rationale"])[:240]
        if item.get("researcher_reason"):
            ex_rel["researcher_reason"] = item["researcher_reason"]
        excluded_summary.append(ex_rel)
    quoted_by_doc_ref = {}
    for r in rows:
        doc_id = (r.get("ref") or {}).get("document")
        q = " ".join(str(r.get("quote") or "").split())
        if not doc_id or not q:
            continue
        for a in r.get("sources", []):
            sref = a.get("ref")
            if sref:
                key = (doc_id, sref)
                prev = quoted_by_doc_ref.get(key, "")
                if q not in prev:
                    quoted_by_doc_ref[key] = (prev + " " + q).strip()
    manifest_by_doc = {
        (d.get("document") or d.get("id")): {
            "document": d.get("document") or d.get("id"),
            "name": d.get("name"),
        }
        for d in inputs.get("documents", [])
        if (d.get("document") or d.get("id")) is not None
    }
    for r in rows:
        ref_obj = r.get("ref") or {}
        doc_id = ref_obj.get("document")
        if doc_id is not None:
            entry = manifest_by_doc.setdefault(doc_id, {"document": doc_id})
            if ref_obj.get("run") and not entry.get("run"):
                entry["run"] = ref_obj["run"]
            if ref_obj.get("observation"):
                entry.setdefault("valid_observation_ids", []).append(ref_obj["observation"])
            if r.get("document_version") and not entry.get("document_version"):
                entry["document_version"] = r["document_version"]
            if r.get("source_sha256") and not entry.get("source_sha256"):
                entry["source_sha256"] = r["source_sha256"]
    doc_manifest = list(manifest_by_doc.values())
    sections = [
        ("Document provenance manifest", doc_manifest),
        ("Source-bound observations", [_compact_observation(r) for r in rows]),
        (
            "Intra-document relations from Stage A",
            inputs.get("a_relations") or [],
        ),
        (
            "Selected relations and their review status",
            [_compact_relation(rel) for rel in relations],
        ),
        (
            "Native document context in source order. Cite supplied observations as evidence.",
            [_compact_context(c, quoted_by_doc_ref) for c in inputs["context"]],
        ),
    ]
    if excluded_summary:
        sections.append(
            (
                "Excluded items summary (omitted from active basis; do not confuse with absence)",
                excluded_summary,
            )
        )
    for title, entries in sections:
        if not entries:
            continue
        heading = document.add_heading(title, level=1)
        for entry in entries:
            document.add_text(
                DocItemLabel.TEXT,
                json.dumps(entry, ensure_ascii=False),
                parent=heading,
            )
    return document


def run(
    workspace,
    numbers,
    options,
    focus="",
    progress=lambda event: None,
    *,
    basis=None,
    b_run=None,
    stage="B",
    allow_partial=False,
    output_language=None,
):
    from . import library, native_graph
    from .prompts_config import apply_stage_prompt, build_synthesis_directive

    template, field, object_kind = STAGES[stage]
    inputs = plan(
        workspace, numbers, basis=basis, b_run=b_run, stage=stage, allow_partial=allow_partial
    )
    require_basis(inputs, allow_partial=allow_partial)
    rows, relations = inputs["offered"], inputs["relations"]
    available = {refkey(r["ref"]) for r in rows}
    by_relation = {r["id"] for r in relations}
    native, clean, settings = None, {}, None
    diagnostic = dict(stage="input", reason="basis_no_grounded")
    proposals = []
    status = "ERROR"
    if rows:
        phase = "model_access"
        try:
            progress(dict(phase=phase, kind=stage))
            clean = models.profile_options(options)
            client = models.connect(options)
            settings = models.describe(clean, client=client)
            phase = "native_extraction"
            wf_cfg = library.workflow_settings(workspace)
            stage_base_prompt = str(
                options.get("base_prompt")
                if "base_prompt" in options
                else (wf_cfg.get("base_prompts") or {}).get(stage, "")
            ).strip()
            stage_custom_prompt = str(
                options.get("stage_prompt")
                if "stage_prompt" in options
                else (wf_cfg.get("stage_prompts") or {}).get(stage, "")
            ).strip()
            out_lang = (
                output_language
                or options.get("output_language")
                or wf_cfg.get("output_language", "auto")
            )
            active_template = apply_stage_prompt(
                template,
                stage_custom_prompt,
                base_override=stage_base_prompt,
                output_language=out_lang,
            )
            directive = build_synthesis_directive(
                stage,
                focus=focus,
                output_language=out_lang,
                base_override=stage_base_prompt,
                custom_prompt=stage_custom_prompt,
            )
            document = _build_synthesis_document(inputs, stage)
            stage_contract = options.get("extraction_contract")
            if stage_contract not in ("direct", "dense"):
                stage_contract = "direct"
            stage_options = dict(
                clean,
                processing_mode="many-to-one",
                extraction_contract=stage_contract,
                gleaning_enabled=bool(options.get("stage_gleaning", False)),
                structured_sparse_check=False,
            )
            scope_label = f"Korpus ({len(numbers)} Dok.)"
            def _stage_progress(ev):
                if isinstance(ev, dict):
                    payload = dict(ev)
                    payload.setdefault("kind", stage)
                    payload.setdefault("document_name", scope_label)
                    payload.setdefault("model", clean.get("model"))
                    progress(payload)
                else:
                    progress(
                        dict(
                            phase=ev,
                            kind=stage,
                            document_name=scope_label,
                            model=clean.get("model"),
                        )
                    )
            with TemporaryDirectory(dir=workspace.root) as directory:
                path = Path(directory) / "evidence.json"
                document.save_as_json(path)
                native = native_graph.run(
                    path,
                    active_template,
                    client,
                    stage_options,
                    progress=_stage_progress,
                    system_appendix=directive,
                )
            diagnostic = native_graph.outcome(native)
            proposals = [
                (
                    proposal,
                    relation_valid(proposal, available)
                    if stage == "B"
                    else finding_valid(proposal, available, by_relation),
                )
                for result in native["extracted"]
                for proposal in result.get(field, [])
            ]
            if not native["error"] and native["extracted"]:
                status = (
                    "PARTIAL"
                    if native["last_response"].get("truncated")
                    or native.get("salvaged")
                    or any(
                        r.get("finish_reason") in ("length", "max_tokens")
                        for r in native.get("requests", [])
                    )
                    or any(not valid for _, valid in proposals)
                    else ("UNREVIEWED" if proposals else "NO_PROPOSALS")
                )
        except Exception as error:
            diagnostic = dict(stage=phase, reason=type(error).__name__)
    counts = dict(
        proposed=len(proposals),
        unresolved=sum(not valid for _, valid in proposals),
        null_decisions=sum(
            stage == "B" and valid and p["kind"] is None for p, valid in proposals
        ),
    )
    metadata = dict(
        origin="model",
        stage=stage,
        status=status,
        basis_mode="partial_confirmed" if allow_partial else "eligible",
        provider=clean.get("provider"),
        model=clean.get("model"),
        observations=[r["ref"] for r in rows],
        basis_runs=[
            d["selected_run"]
            for d in inputs["documents"]
            if d["selected_run"] is not None
        ],
        basis_by_doc={
            str(d["document"]): d["selected_run"]
            for d in inputs["documents"]
            if d.get("document") is not None and d.get("selected_run") is not None
        },
        relation_ids=sorted(by_relation),
        b_run=inputs["b_run"],
        counts=counts,
        native_projection=native_graph.projection_status(native, stage),
    )
    with workspace.db() as db:
        db.execute("BEGIN IMMEDIATE")
        receipt = research.create(
            workspace,
            "comparison",
            native["extracted"] if native else [],
            numbers,
            dict(
                metadata,
                options=clean,
                model_settings=settings,
                native_graph=native,
                diagnostic=diagnostic,
                inputs=inputs,
                focus=focus,
            ),
            db=db,
        )
        saved = [
            dict(
                id=research.create(
                    workspace,
                    object_kind,
                    proposal,
                    numbers,
                    dict(
                        metadata,
                        comparison=receipt,
                        reference_status="RESOLVED" if valid else "UNRESOLVED",
                    ),
                    db=db,
                ),
                kind=object_kind,
            )
            for proposal, valid in proposals
        ]
    reqs = (native or {}).get("requests", [])
    p_tok = sum(int((r.get("usage") or {}).get("prompt_tokens") or 0) for r in reqs)
    c_tok = sum(int((r.get("usage") or {}).get("completion_tokens") or 0) for r in reqs)
    t_tok = sum(int((r.get("usage") or {}).get("total_tokens") or 0) for r in reqs) or (p_tok + c_tok)
    r_tok = sum(int((r.get("usage_details") or {}).get("reasoning_tokens") or 0) for r in reqs)
    ca_tok = sum(int((r.get("usage_details") or {}).get("cached_tokens") or 0) for r in reqs)
    dur_s = round(sum(float(r.get("duration_s") or 0) for r in reqs), 2) or None
    for document in inputs["documents"]:
        progress(
            dict(
                kind=stage,
                phase=diagnostic.get("stage", "native_extraction"),
                document=document["document"],
                document_name=document["name"],
                status=status,
                run=receipt,
                model=clean.get("model"),
                duration_s=dur_s,
                proposed=counts["proposed"],
                unresolved=counts["unresolved"],
                prompt_tokens=p_tok or None,
                completion_tokens=c_tok or None,
                total_tokens=t_tok or None,
                reasoning_tokens=r_tok or None,
                cached_tokens=ca_tok or None,
                reason=diagnostic.get("reason"),
                http_status=diagnostic.get("http_status"),
                detail=diagnostic.get("detail"),
            )
        )
    return dict(
        comparison=receipt, saved=saved, status=status, stage=stage, counts=counts
    )
