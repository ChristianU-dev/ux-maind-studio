"""Source-linked UX relations, finding hypotheses and append-only decisions.

The existing native Graph/LLM client synthesizes a consciously selected corpus.
Native GraphConverter supplies all graph topology; no retrieval or pair enumeration.
"""

import json
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from .evidence import READABLE_SCHEMAS, SCHEMA_VERSION, Sources
from .templates import ObservationRef


def reference(value):
    return ObservationRef.model_validate(value).model_dump()


def run_sources(w, row, result):
    version = result["document_version"]
    stored = w.version_row(row, version)
    configuration = json.loads(stored.get("diagnostics") or "{}").get("configuration")
    return Sources(
        w.document(stored),
        row["id"],
        version,
        configuration=configuration,
        source_sha256=result.get("source_sha256"),
    )


def entry(w, ref, result=None, sources=None):
    ref = reference(ref)
    if result is None:
        with w.db() as db:
            run = db.execute(
                "SELECT result FROM runs WHERE id=? AND document=?",
                (ref["run"], ref["document"]),
            ).fetchone()
        if run is None:
            raise ValueError("Lauf gehört nicht zur Quelle")
        result = json.loads(run["result"])
    raw = next(
        (o for o in result.get("observations", []) if o["id"] == ref["observation"]),
        None,
    )
    if result.get("schema_version") not in READABLE_SCHEMAS or raw is None:
        raise ValueError("Beobachtung fehlt")
    row = w.file(ref["document"])
    with w.db() as db:
        decisions = [
            dict(x, payload=json.loads(x["payload"]))
            for x in map(
                dict,
                db.execute(
                    "SELECT * FROM ux_decisions WHERE target_type='observation' AND target=? ORDER BY id",
                    (json.dumps(ref, sort_keys=True),),
                ),
            )
        ]
    effective = dict(raw)
    primary, contexts = None, []
    for decision in decisions:
        payload = decision["payload"]
        effective.update(payload.get("interpretation", {}))
        primary = payload.get("primary", primary)
        contexts = payload.get("context", contexts)
    diagnostics = []
    try:
        sources = sources or run_sources(w, row, result)

        def checked(value):
            try:
                return sources.select(value)
            except (KeyError, ValueError, FileNotFoundError) as error:
                diagnostics.append(type(error).__name__)
                return None

        def bound(aliases):
            anchors = []
            for alias in aliases:
                try:
                    value = result["sources"][alias]
                except KeyError:
                    diagnostics.append("KeyError")
                    continue
                if anchor := checked(value):
                    anchors.append(anchor)
            return anchors

        matches = bound(raw["source_ids"])
        raw_matches = list(matches)
        eff_measurements = effective.get("measurements")
        if not isinstance(eff_measurements, list):
            eff_measurements = raw["measurements"]
        measurements = [
            dict(m, sources=bound(m.get("source_ids") or []))
            for m in eff_measurements
        ]
        context = bound(raw["context"]["source_ids"]) if raw["context"] else []
        if primary:
            primary = checked(primary)
            if primary:
                matches = [primary]
        contexts = [dict(c, evidence=anchor) for c in contexts if (anchor := checked(c["evidence"]))]
    except (KeyError, ValueError, FileNotFoundError) as error:
        diagnostics.append(type(error).__name__)
        matches, raw_matches, context, contexts, primary = [], [], [], [], None
        eff_m = effective.get("measurements")
        measurements = [
            dict(m, sources=[])
            for m in (eff_m if isinstance(eff_m, list) else raw.get("measurements", []))
        ]
    return dict(
        ref=ref,
        name=row["name"],
        raw=raw,
        effective=effective,
        source_check=dict(
            status="SOURCE_RESOLVED" if matches else "UNRESOLVED", matches=matches,
            raw_matches=raw_matches, semantic_validation="NOT_PERFORMED",
            primary_applied=bool(primary),
        ),
        source_issues=list(
            dict.fromkeys(
                issue["reason"]
                for issue in result.get("issues", [])
                if issue.get("status") == "UNRESOLVED"
                and issue.get("observation") == raw["id"]
                and issue.get("reason")
            )
        ),
        picture_sources=sources.picture_sources(matches) if matches else [],
        candidate_anchors=raw.get("candidate_anchors", []) if not matches else [],
        selected_source=primary,
        context_sources=context,
        measurements=measurements,
        diagnostics=diagnostics,
        context_decisions=contexts,
        decisions=decisions,
        source_sha256=result.get("source_sha256"),
        document_version=result.get("document_version"),
    )


def catalog(w, numbers, *, include_context=False, basis=None):
    from .a_status import dimensions

    numbers = list(dict.fromkeys(map(int, numbers)))
    if basis is None:
        basis = {}
    if not isinstance(basis, dict):
        raise ValueError("Ungültige Auswahl der Evidenzläufe")
    basis = {int(document): run for document, run in basis.items()}
    if set(basis) - set(numbers) or any(type(run) is not int for run in basis.values()):
        raise ValueError("Evidenzlauf außerhalb der Dokumentauswahl")
    entries, links, documents = [], [], []
    context = []
    for number in dict.fromkeys(map(int, numbers)):
        row = w.file(number)
        runs = [
            r
            for r in w.results(number)
            if r["result"].get("schema_version") in READABLE_SCHEMAS
        ]
        candidates = [r for r in runs if r["result"].get("observations")]
        chosen = next(
            (r for r in candidates if number not in basis or r["id"] == basis[number]),
            None,
        )
        if number in basis and chosen is None:
            raise ValueError(
                "Zum gewählten Dokument ist dieser Evidenzlauf nicht verfügbar"
            )
        receipt = dict(
            document=number,
            name=row["name"],
            archived=bool(row["archived"]),
            latest_run=runs[0]["id"] if runs else None,
            latest_status=runs[0]["result"]["status"] if runs else None,
            selected_run=chosen["id"] if chosen else None,
            selection="Ausdrücklich gewählter Lauf"
            if number in basis
            else "Letzter Lauf mit Beobachtungen",
            source_available=bool(row["native"]),
        )
        documents.append(receipt)
        if not chosen:
            receipt["coverage_status"] = "NEEDS_REVIEW"
            continue
        run, result = chosen["id"], chosen["result"]
        try:
            sources = run_sources(w, row, result)
        except (FileNotFoundError, ValueError):
            sources = None
        receipt["coverage_status"] = result["status"] if sources else "UNRESOLVED"
        receipt["document_version"] = result["document_version"]
        coverage = result.get("coverage", {})
        receipt["coverage"] = {
            key: coverage[key]
            for key in ("parsed", "fully_offered", "offered", "source_verified")
            if key in coverage
        }
        document_entries = [
            entry(
                w, dict(document=number, run=run, observation=o["id"]), result, sources
            )
            for o in result["observations"]
        ]
        entries.extend(document_entries)
        technical = dimensions(result)
        technical["effective_resolved"] = sum(bool(e["source_check"]["matches"]) for e in document_entries)
        technical["primary_corrections"] = sum(bool(e["selected_source"]) for e in document_entries)
        technical["measurement_open"] = sum(
            not m["sources"] for e in document_entries for m in e["measurements"]
        )
        human_rejected_refs = {
            tuple(e["ref"].values())
            for e in document_entries
            if next(
                (
                    d["action"]
                    for d in reversed(e["decisions"])
                    if d["origin"] in ("human", "human_carried_forward")
                ),
                None,
            )
            == "rejected"
        }
        unresolved_entries = [
            e
            for e in document_entries
            if (
                not e["source_check"]["matches"]
                and tuple(e["ref"].values()) not in human_rejected_refs
            )
            or e["diagnostics"]
        ]
        if not sources or unresolved_entries:
            technical["eligible"] = False
            if "a_source_open" not in technical["reasons"]:
                technical["reasons"].append("a_source_open")
        elif technical["reasons"] == ["a_source_open"]:
            technical["reasons"] = []
            technical["eligible"] = True
            technical["human_reconciled"] = True
        exclusion_reasons = []
        for e in document_entries:
            rk = tuple(e["ref"].values())
            if rk in human_rejected_refs:
                last_h = next(
                    (
                        d
                        for d in reversed(e["decisions"])
                        if d["origin"] in ("human", "human_carried_forward")
                    ),
                    {},
                )
                exclusion_reasons.append(
                    dict(
                        observation=e["ref"]["observation"],
                        ref=e["ref"],
                        status="HUMAN_REJECTED",
                        reason=last_h.get("reason") or "Vom Forscher ausgeschlossen",
                        statement=str(e["effective"].get("statement") or "")[:180],
                        quote=str(e["effective"].get("quote") or "")[:140],
                        candidates_count=0,
                    )
                )
            elif not e["source_check"]["matches"] or e["diagnostics"]:
                issue_txt = (
                    "; ".join(e.get("source_issues") or [])
                    or "; ".join(e.get("diagnostics") or [])
                    or "Zitat konnte im DoclingDocument nicht eindeutig verankert werden"
                )
                exclusion_reasons.append(
                    dict(
                        observation=e["ref"]["observation"],
                        ref=e["ref"],
                        status="UNRESOLVED",
                        reason=issue_txt,
                        statement=str(e["effective"].get("statement") or "")[:180],
                        quote=str(e["effective"].get("quote") or "")[:140],
                        candidates_count=len(e.get("candidate_anchors") or []),
                        ambiguous_count=e.get("raw", {}).get("ambiguous_count") or len(e.get("candidate_anchors") or []),
                    )
                )
        receipt["exclusion_reasons"] = exclusion_reasons
        receipt["technical"] = technical
        from .handoff import manifest
        receipt["handoff"] = manifest(document_entries, [receipt])
        if include_context and sources:
            ledger = (result.get("native_graph") or {}).get("provenance") or {}
            pictures = {
                item.self_ref: dict(
                    sources.picture_source(item),
                    **(
                        {"description": item.meta.description.text}
                        if item.meta
                        and item.meta.description
                        and item.meta.description.text
                        else {}
                    ),
                )
                for item in sources.doc.pictures
            }
            context.extend(
                dict(
                    document=number,
                    name=row["name"],
                    version=result["document_version"],
                    run=run,
                    chunk=chunk["chunk_id"],
                    self_refs=chunk["doc_item_refs"],
                    headings=chunk["headings"],
                    pages=chunk.get("page_numbers", []),
                    geometry=chunk.get("item_geometry", []),
                    picture_sources=[
                        pictures[ref]
                        for ref in chunk["doc_item_refs"]
                        if ref in pictures
                    ],
                    text=chunk["text"],
                )
                for chunk in ledger.get("chunks", {}).values()
            )
        if sources:
            for rel in result["relations"]:
                links.append(
                    dict(
                        **{
                            k: v
                            for k, v in rel.items()
                            if k not in ("source", "target")
                        },
                        source=dict(
                            document=number, run=run, observation=rel["source"]
                        ),
                        target=dict(
                            document=number, run=run, observation=rel["target"]
                        ),
                        sources=[
                            sources.select(result["sources"][a])
                            for a in rel["source_ids"]
                        ],
                    )
                )
    return dict(
        observations=entries,
        relations=links,
        documents=documents,
        **({"native_source_context": context} if include_context else {}),
    )


def historical(w, numbers):
    with w.db() as db:
        decisions = [
            dict(d, target=json.loads(d["target"]), payload=json.loads(d["payload"]))
            for d in map(
                dict,
                db.execute(
                    "SELECT * FROM ux_decisions WHERE target_type='information' AND json_extract(target,'$.document') IN (SELECT value FROM json_each(?)) ORDER BY id",
                    (json.dumps(list(numbers)),),
                ),
            )
        ]
    return dict(
        runs=[
            dict(document=n, **r)
            for n in numbers
            for r in w.results(n)
            if r["historical"]
        ],
        decisions=decisions,
        objects=[
            o
            for o in objects(w, numbers)
            if o["metadata"].get("schema_version") not in READABLE_SCHEMAS
        ],
    )


def objects(w, numbers):
    scope = set(map(int, numbers))
    with w.db() as db:
        rows = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM ux_objects AS o WHERE NOT EXISTS (SELECT 1 FROM json_each(o.metadata,'$.scope') AS s WHERE s.value NOT IN (SELECT value FROM json_each(?))) ORDER BY id",
                (json.dumps(list(scope)),),
            )
        ]
        for r in rows:
            r["proposal"] = json.loads(r["proposal"])
            r["metadata"] = json.loads(r["metadata"])
            r["decisions"] = [
                dict(d, payload=json.loads(d["payload"]))
                for d in map(
                    dict,
                    db.execute(
                        "SELECT * FROM ux_decisions WHERE target_type=? AND target=? ORDER BY id",
                        (r["kind"], str(r["id"])),
                    ),
                )
            ]
            r["effective"] = (
                dict(r["proposal"])
                if isinstance(r["proposal"], dict)
                else dict(raw_value=r["proposal"])
            )
            for d in r["decisions"]:
                r["effective"].update(d["payload"].get("interpretation", {}))
            r["review"] = "UNREVIEWED"
            if r["decisions"]:
                last = r["decisions"][-1]
                r["review"] = (
                    "HUMAN_"
                    if last["origin"] in ("human", "human_carried_forward")
                    else "AUTOMATED_"
                ) + last["action"].upper()
    filtered = [r for r in rows if set(r["metadata"].get("scope", [])) <= scope]
    from . import dual_review

    return dual_review.apply_dual_review_projection(w, filtered, scope=scope)


def create(w, kind, proposal, numbers, metadata=None, *, db=None):
    if kind not in ("relation", "finding", "comparison"):
        raise ValueError("Unbekannte Objektart")
    meta = dict(
        metadata or {},
        schema_version=SCHEMA_VERSION,
        scope=list(dict.fromkeys(map(int, numbers))),
    )
    if db is None:
        with w.db() as transaction:
            transaction.execute("BEGIN IMMEDIATE")
            return create(w, kind, proposal, numbers, meta, db=transaction)
    count = db.execute(
        "SELECT count(*) FROM documents WHERE id IN (SELECT value FROM json_each(?))",
        (json.dumps(meta["scope"]),),
    ).fetchone()[0]
    if count != len(meta["scope"]):
        raise ValueError("Forschungsobjekt verweist auf ein fehlendes Dokument")
    return db.execute(
        "INSERT INTO ux_objects(kind,at,proposal,metadata) VALUES(?,?,?,?)",
        (
            kind,
            datetime.now(timezone.utc).isoformat(),
            json.dumps(proposal, ensure_ascii=False),
            json.dumps(meta, ensure_ascii=False),
        ),
    ).lastrowid


class PictureSourceNode(BaseModel):
    model_config = ConfigDict(graph_id_fields=["document", "version", "ref"])
    document: int
    version: str
    ref: str
    name: str
    pages: list[int]
    picture_source: dict[str, Any]


class ObservationNode(ObservationRef):
    model_config = ConfigDict(
        is_entity=True, graph_id_fields=["document", "run", "observation"]
    )
    text: Any = None
    evidence: Any = None
    pictures: list[PictureSourceNode] = Field(
        default_factory=list, json_schema_extra={"edge_label": "HAS_PICTURE_SOURCE"}
    )


class RelationNode(BaseModel):
    model_config = ConfigDict(graph_id_fields=["record_id"])
    record_id: str
    kind: Any = None
    rationale: Any = None
    situation: Any = None
    inference_basis: Any = None
    uncertainty: Any = None
    review: str = "UNREVIEWED"
    source: ObservationNode = Field(
        json_schema_extra={"edge_label": "SOURCE", "graph_reference": True}
    )
    target: ObservationNode = Field(
        json_schema_extra={"edge_label": "TARGET", "graph_reference": True}
    )


class FindingNode(BaseModel):
    model_config = ConfigDict(graph_id_fields=["record_id"])
    record_id: int
    title: Any = None
    valence: Any = None
    rationale: Any = None
    uncertainty: Any = None
    review: str = "UNREVIEWED"
    finding_type: str | None = None
    usability_heuristic: str | None = None
    observed_effect: str | None = None
    scope: str | None = None
    improvement_hypothesis: str | None = None
    improvement_basis: str | None = None
    epistemic_flags: list[str] = Field(default_factory=list)
    independence: dict[str, Any] = Field(default_factory=dict)
    supports: list[ObservationNode] = Field(
        default_factory=list,
        json_schema_extra={"edge_label": "SUPPORTS", "graph_reference": True},
    )
    opposes: list[ObservationNode] = Field(
        default_factory=list,
        json_schema_extra={"edge_label": "COUNTEREVIDENCE", "graph_reference": True},
    )
    qualifies: list[ObservationNode] = Field(
        default_factory=list,
        json_schema_extra={"edge_label": "QUALIFIES", "graph_reference": True},
    )
    improvement_evidence: list[ObservationNode] = Field(
        default_factory=list,
        json_schema_extra={"edge_label": "SUGGESTED_BY", "graph_reference": True},
    )
    relations: list[RelationNode] = Field(
        default_factory=list,
        json_schema_extra={"edge_label": "USES_RELATION", "graph_reference": True},
    )


def retain_finding_roles(native, registry, findings, warnings):
    """Annotate the existing native edge with every stored role of that pair."""
    fields = FindingNode.model_fields
    for finding in findings:
        source = registry.get_node_id(finding)
        roles = {}
        for field in ("supports", "opposes", "qualifies", "improvement_evidence"):
            label = fields[field].json_schema_extra["edge_label"]
            for observation in getattr(finding, field):
                target = registry.get_node_id(observation)
                roles.setdefault(target, set()).add(label)
        for target, labels in roles.items():
            edge = native.get_edge_data(source, target)
            if edge is not None:
                edge["roles"] = sorted(labels)
            else:
                warnings.append(
                    dict(
                        kind="finding",
                        id=finding.record_id,
                        status="EDGE_ROLE_LOSS",
                        issue="Eine gespeicherte Belegverbindung fehlt im nativen Graph.",
                    )
                )


def basis_runs(metadata):
    return set(metadata.get("basis_runs", ())) or {
        r["run"] for r in metadata.get("observations", ())
    }


def _is_entry_human_rejected(entry_obj: dict) -> bool:
    for d in reversed(entry_obj.get("decisions") or []):
        if d.get("origin") in ("human", "human_carried_forward"):
            return d.get("action") == "rejected"
    return False


def _finding_epistemics(p, by_ref, review, *, rejected_rel_ids=frozenset()):
    """Detect visual overlap, unanchored scales, negation, rejected supports & speaker diversity (`US-45`, `US-46`)."""
    flags = []
    support_refs = p.get("supports") or []
    all_role_entries = []
    support_entries = []
    for role_field in ("supports", "opposes", "qualifies", "improvement_evidence"):
        for raw_ref in p.get(role_field) or []:
            try:
                key = tuple(reference(raw_ref).values())
            except (ValueError, TypeError):
                continue
            if key in by_ref:
                ent = by_ref[key]
                all_role_entries.append(ent)
                if role_field == "supports":
                    support_entries.append(ent)

    rejected_support = any(_is_entry_human_rejected(e) for e in support_entries) or any(
        rid in rejected_rel_ids for rid in (p.get("relations") or [])
    )
    active_supports = [e for e in support_entries if not _is_entry_human_rejected(e)]

    doc_ids = {e["ref"]["document"] for e in active_supports}
    distinct_speakers = set()
    unique_evidence_ids = set()
    page_modalities = {}
    effective_units = set()
    for e in active_supports:
        ctx = (e.get("effective") or {}).get("context") or {}
        speaker_raw = str(ctx.get("actor_or_speaker") or "").strip()
        ep_role = ctx.get("epistemic_role")
        if speaker_raw and ep_role in (None, "participant_firsthand"):
            distinct_speakers.add(" ".join(speaker_raw.lower().split()))
        matches = e["source_check"].get("matches") or []
        pics = e.get("picture_sources") or []
        is_context_render = any(
            ps.get("picture_source", {}).get("kind") in ("slide_context", "page_context")
            for ps in pics
        )
        pages = sorted(
            {
                pr.get("page_no")
                for a in matches
                for pr in a.get("prov", ())
                if pr.get("page_no") is not None
            }
        )
        for a in matches:
            unique_evidence_ids.add(a["evidence_id"])
        doc_no = e["ref"]["document"]
        for pg in pages or [None]:
            page_modalities.setdefault((doc_no, pg), set()).add(
                "context_render" if is_context_render else "primary"
            )
        if not is_context_render:
            effective_units.add(
                (
                    doc_no,
                    tuple(sorted(a["evidence_id"] for a in matches)) or e["ref"]["observation"],
                )
            )
        else:
            effective_units.add((doc_no, "visual_render", tuple(pages)))

    for e in all_role_entries:
        for m in e.get("measurements") or []:
            if (
                m.get("numeric_value") is not None
                and (m.get("scale_direction") or "unknown") == "unknown"
                and m.get("measurement_kind") in (None, "rating_scale")
            ):
                if "unanchored_scale_direction" not in flags:
                    flags.append("unanchored_scale_direction")
        if e.get("effective", {}).get("negated_or_struck"):
            if "contains_negated_or_struck" not in flags:
                flags.append("contains_negated_or_struck")
        ctx_ref = e.get("effective", {}).get("context_reference")
        if isinstance(ctx_ref, dict) and (
            ctx_ref.get("target_self_ref") is None or ctx_ref.get("target_valid") is False
        ):
            if "unresolved_context_reference" not in flags:
                flags.append("unresolved_context_reference")

    if rejected_support:
        flags.append("contains_rejected_support")

    has_overlap = any(
        modes == {"primary", "context_render"} for modes in page_modalities.values()
    )
    if has_overlap:
        flags.append("dependent_visual_overlap")
        effective_units = {
            u
            for u in effective_units
            if not (
                len(u) == 3
                and u[1] == "visual_render"
                and any(
                    (u[0], pg) in page_modalities
                    and page_modalities[(u[0], pg)] == {"primary", "context_render"}
                    for pg in (u[2] or [None])
                )
            )
        }
    if review == "UNREVIEWED":
        flags.append("technical_source_only")

    return flags, dict(
        independent_documents=len(doc_ids),
        distinct_speakers=len(distinct_speakers),
        raw_supports=len(support_refs),
        effective_independent_supports=len(effective_units) if active_supports else 0,
        unique_anchors=len(unique_evidence_ids),
        dependent_visual_overlap=has_overlap,
        contains_rejected_support=rejected_support,
    )


def graph(w, numbers, *, history=False, basis=None, result_runs=None):
    from docling_graph.core.converters.graph_converter import GraphConverter
    from docling_graph.core.exporters.json_exporter import graph_to_dict

    numbers = list(dict.fromkeys(map(int, numbers)))
    data = catalog(w, numbers, basis=basis)
    entries = list(data["observations"])
    current_runs = {d["selected_run"] for d in data["documents"] if d["selected_run"]}
    by_ref = {tuple(e["ref"].values()): e for e in entries}
    nodes = {}
    scope = set(map(int, numbers))
    warnings = []

    def info(ref):
        r = reference(ref)
        key = tuple(r.values())
        if r["document"] not in scope:
            raise ValueError("Endpunkt außerhalb der Auswahl")
        if result_runs is not None and r["run"] not in current_runs:
            raise ValueError("Endpunkt gehört zu einem anderen A-Stand")
        if key not in nodes:
            e = by_ref.get(key)
            if e is None:
                e = entry(w, r)
                by_ref[key] = e
            if not e["source_check"]["matches"]:
                raise ValueError("Quellenbindung nicht auflösbar")
            nodes[key] = ObservationNode(
                **r,
                text=e["effective"].get("statement"),
                evidence=dict(check=e["source_check"], selected=e["selected_source"]),
                pictures=[
                    PictureSourceNode(
                        document=r["document"],
                        version=e["document_version"],
                        ref=anchor["ref"],
                        name=e["name"],
                        pages=sorted({p["page_no"] for p in anchor["prov"]}),
                        picture_source=anchor["picture_source"],
                    )
                    for anchor in e["picture_sources"]
                ],
            )
        return nodes[key]

    for e in entries:
        if e["source_check"]["matches"]:
            info(e["ref"])
    extracted = []
    for i, link in enumerate(data["relations"]):
        try:
            extracted.append(
                RelationNode(
                    record_id=f"extraction:{i}",
                    kind=link["kind"],
                    rationale=link["rationale"],
                    situation=link.get("situation"),
                    inference_basis=link.get("inference_basis"),
                    uncertainty=link.get("uncertainty"),
                    source=info(link["source"]),
                    target=info(link["target"]),
                )
            )
        except ValueError as error:
            warnings.append(
                dict(kind="extraction_relation", status="UNRESOLVED", issue=str(error))
            )
    relations = {}
    findings = []
    all_saved = [
        o
        for o in objects(w, numbers)
        if o["metadata"].get("schema_version") in READABLE_SCHEMAS
    ]

    def group(obj):
        meta = obj["metadata"]
        return tuple(sorted(meta["scope"])), meta.get("stage", "legacy")

    latest = {}
    for obj in all_saved:
        if (
            obj["kind"] == "comparison"
            and obj["metadata"].get("origin") == "model"
            and obj["metadata"].get("status")
            in ("UNREVIEWED", "PARTIAL", "NO_PROPOSALS")
        ):
            latest[group(obj)] = obj["id"]
    saved = [
        obj
        for obj in all_saved
        if history
        or obj["decisions"]
        or obj["metadata"].get("origin") != "model"
        or not latest.get(group(obj))
        or (
            obj["id"]
            if obj["kind"] == "comparison"
            else obj["metadata"].get("comparison")
        )
        == latest.get(group(obj))
    ]
    if result_runs is not None:
        if not isinstance(result_runs, dict) or any(
            stage not in ("B", "C") or run_id is not None and type(run_id) is not int
            for stage, run_id in result_runs.items()
        ):
            raise ValueError("Ungültige Auswahl der Ergebnisläufe")
        requested = {r for r in result_runs.values() if r is not None}
        compatible = {
            o["id"]: o["metadata"]
            for o in all_saved
            if o["kind"] == "comparison"
            and set(o["metadata"].get("scope", ())) == scope
            and basis_runs(o["metadata"]) == current_runs
        }
        for stage, run_id in result_runs.items():
            if run_id is not None and (
                run_id not in compatible
                or (compatible[run_id].get("stage") or "legacy")
                not in (stage, "legacy")
            ):
                raise ValueError("Gewählter Ergebnislauf passt nicht zur A-Basis.")
        c_run = result_runs.get("C")
        if c_run:
            b_run = (
                compatible[c_run].get("b_run")
                if compatible[c_run].get("stage") == "C"
                else c_run
            )
            if b_run != result_runs.get("B"):
                raise ValueError("Dieser C-Lauf gehört zu einem anderen B-Stand.")
        saved = [
            o
            for o in all_saved
            if (
                o["id"]
                if o["kind"] == "comparison"
                else o["metadata"].get("comparison")
            )
            in requested
            or (
                o["kind"] in ("finding", "relation")
                and not result_runs.get("C" if o["kind"] == "finding" else "B")
                and o["metadata"].get("origin") != "model"
                and not o["metadata"].get("comparison")
                and set(o["metadata"].get("scope", ())) == scope
            )
        ]
    # Explicit links from retained findings keep the referenced relation accessible.
    linked = {
        n
        for obj in saved
        if obj["kind"] == "finding"
        for n in (obj["effective"].get("relations") or [])
        if type(n) is int
    }
    saved += [
        obj
        for obj in all_saved
        if result_runs is None
        and obj["kind"] == "relation"
        and obj["id"] in linked
        and obj not in saved
    ]
    for r in saved:
        if r["kind"] != "relation":
            continue
        p = r["effective"]
        try:
            if r["metadata"].get("origin") == "model":
                offered = r["metadata"].get("observations", [])
                for key, label in (
                    ("source", "Ausgangsbeleg"),
                    ("target", "Zielbeleg"),
                ):
                    if p.get(key) not in offered:
                        raise ValueError(
                            label + " war nicht im übermittelten A-Stand enthalten"
                        )
            if (
                r["metadata"].get("reference_status") == "UNRESOLVED"
                and not r["decisions"]
            ):
                raise ValueError("Beziehung mit diesen Referenzen nicht validiert")
            left, right = info(p.get("source")), info(p.get("target"))
            if (
                left is not right
                and "kind" in p
                and p["kind"] is None
                and p.get("rationale")
            ):
                warnings.append(
                    dict(
                        kind="relation",
                        id=r["id"],
                        status="NO_RELATION",
                        issue=p["rationale"],
                    )
                )
                continue
            if left is right or not p.get("kind"):
                raise ValueError("Keine belegte fachliche Verbindung vorgeschlagen")
            relations[r["id"]] = RelationNode(
                record_id=str(r["id"]),
                kind=p.get("kind"),
                rationale=p.get("rationale"),
                situation=p.get("situation"),
                inference_basis=p.get("inference_basis"),
                uncertainty=p.get("uncertainty"),
                review=r["review"],
                source=left,
                target=right,
            )
        except (ValueError, KeyError, TypeError) as exc:
            warnings.append(
                dict(kind="relation", id=r["id"], status="UNRESOLVED", issue=str(exc))
            )
    for r in saved:
        if r["kind"] != "finding":
            continue
        p = r["effective"]
        try:
            if (
                r["metadata"].get("reference_status") == "UNRESOLVED"
                and not r["decisions"]
            ):
                raise ValueError("Referenzen außerhalb des übermittelten Stands")
            if any(x not in relations for x in (p.get("relations") or [])):
                raise ValueError("Finding referenziert keine zugeordnete Relation")
            if r["metadata"].get("origin") == "model":
                offered = r["metadata"].get("observations", [])
                if any(
                    x not in offered
                    for x in [
                        *(p.get("supports") or []),
                        *(p.get("opposes") or []),
                        *(p.get("qualifies") or []),
                        *(p.get("improvement_evidence") or []),
                    ]
                ):
                    raise ValueError(
                        "Finding-Beleg war nicht im Modellvergleich enthalten"
                    )
            supports_nodes = [info(x) for x in (p.get("supports") or [])]
            opposes_nodes = [info(x) for x in (p.get("opposes") or [])]
            qualifies_nodes = [info(x) for x in (p.get("qualifies") or [])]
            improvement_nodes = [info(x) for x in (p.get("improvement_evidence") or [])]
            rejected_rel_ids = {
                rid for rid, rnode in relations.items() if rnode.review == "HUMAN_REJECTED"
            }
            ep_flags, independence = _finding_epistemics(
                p, by_ref, r["review"], rejected_rel_ids=rejected_rel_ids
            )
            findings.append(
                FindingNode(
                    record_id=r["id"],
                    title=p.get("title"),
                    valence=p.get("valence"),
                    rationale=p.get("rationale"),
                    uncertainty=p.get("uncertainty"),
                    review=r["review"],
                    finding_type=p.get("finding_type"),
                    usability_heuristic=p.get("usability_heuristic"),
                    observed_effect=p.get("observed_effect"),
                    scope=p.get("scope"),
                    improvement_hypothesis=p.get("improvement_hypothesis"),
                    improvement_basis=p.get("improvement_basis"),
                    epistemic_flags=ep_flags,
                    independence=independence,
                    supports=supports_nodes,
                    opposes=opposes_nodes,
                    qualifies=qualifies_nodes,
                    improvement_evidence=improvement_nodes,
                    relations=[
                        relations[x]
                        for x in (p.get("relations") or [])
                        if x in relations
                    ],
                )
            )
        except (ValueError, KeyError, TypeError) as exc:
            warnings.append(
                dict(kind="finding", id=r["id"], status="UNRESOLVED", issue=str(exc))
            )
    all_nodes = [*nodes.values(), *extracted, *relations.values(), *findings]
    native = None
    if all_nodes:
        converter = GraphConverter(auto_cleanup=False, alias_llm_fn=None)
        native, _ = converter.pydantic_list_to_graph(all_nodes)
        retain_finding_roles(native, converter.registry, findings, warnings)
    comparison = next(
        (
            o
            for o in reversed(all_saved)
            if o["kind"] == "comparison"
            and set(o["metadata"].get("scope", ())) == scope
            and (
                result_runs is None
                or o["id"] == (result_runs.get("C") or result_runs.get("B"))
            )
        ),
        None,
    )
    compared_runs = (
        (
            set(comparison["metadata"].get("basis_runs", ()))
            or {r["run"] for r in comparison["metadata"].get("observations", ())}
        )
        if comparison
        else set()
    )
    status = (
        "NOT_RUN"
        if comparison is None
        else "STALE"
        if compared_runs and not current_runs.issubset(compared_runs)
        else comparison["metadata"].get("status", "UNREVIEWED")
    )
    relation_nodes = [*extracted, *relations.values()]
    stats = dict(
        internal=sum(r.source.document == r.target.document for r in relation_nodes),
        cross_document=sum(
            r.source.document != r.target.document for r in relation_nodes
        ),
        proposed=len(data["relations"]) + sum(o["kind"] == "relation" for o in saved),
        null_decisions=sum(i.get("status") == "NO_RELATION" for i in warnings),
        unresolved=sum(
            i.get("status") == "UNRESOLVED"
            and i["kind"] in ("relation", "extraction_relation")
            for i in warnings
        ),
        representation_limits=sum(
            i.get("status") == "EDGE_ROLE_LOSS" for i in warnings
        ),
    )
    from . import dual_review

    return dict(
        graph=graph_to_dict(native) if native is not None else dict(nodes=[], edges=[]),
        **data,
        objects=saved,
        prior_attempt_objects=len(all_saved) - len(saved),
        issues=warnings,
        dual_review_sessions=dual_review.list_sessions(w, scope_docs=list(scope)),
        analysis=dict(
            status=status,
            stages=analysis_stages(all_saved, scope, current_runs),
            relationships=stats,
            comparison=comparison["id"] if comparison else None,
            basis_runs=sorted(compared_runs),
            observations=len(nodes),
            relations=len(extracted) + len(relations),
            findings=len(findings),
        ),
        **({"history": historical(w, numbers)} if history else {}),
    )


def decide(w, body):
    """Record an append-only human researcher decision on an observation, relation, or finding."""
    if not isinstance(body, dict):
        raise ValueError("Entscheidung als JSON-Objekt angeben")
    target_type = body.get("target_type")
    if target_type not in ("observation", "relation", "finding"):
        raise ValueError("Unbekannter Entscheidungstyp")
    action = body.get("action")
    if action not in ("confirmed", "rejected", "corrected", "open"):
        raise ValueError("Unbekannte Entscheidungsaktion")
    reason = str(body.get("reason") or "").strip()
    payload = dict(body.get("payload") or {})
    if "reviewer" not in payload:
        from . import auth

        payload["reviewer"] = auth.active_reviewer_stamp(w)
    if target_type == "observation":
        ref = reference(body.get("target"))
        current = entry(w, ref)
        target_key = json.dumps(ref, sort_keys=True)
        sources = run_sources(w, w.file(ref["document"]), dict(document_version=current["document_version"], source_sha256=current["source_sha256"]))
        if "primary" in payload and payload["primary"] is not None:
            payload["primary"] = sources.select(payload["primary"])
        if "context" in payload and payload["context"] is not None:
            payload["context"] = [
                dict(c, evidence=sources.select(c["evidence"]))
                for c in payload["context"]
                if isinstance(c, dict) and c.get("evidence")
            ]
        from hashlib import sha256

        active_matches = (
            [payload["primary"]]
            if payload.get("primary")
            else (current.get("source_check", {}).get("matches") or [])
        )
        stmt_norm = " ".join(str((current.get("effective") or {}).get("statement") or "").split())
        payload["_fingerprint"] = dict(
            document_version=current.get("document_version"),
            evidence_ids=sorted({a["evidence_id"] for a in active_matches if a.get("evidence_id")}),
            statement_sha256=sha256(stmt_norm.encode("utf-8")).hexdigest() if stmt_norm else "",
        )
    else:
        raw_id = body.get("target")
        try:
            obj_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Gültige Objekt-ID angeben") from exc
        with w.db() as db:
            row = db.execute(
                "SELECT id, kind FROM ux_objects WHERE id=? AND kind=?",
                (obj_id, target_type),
            ).fetchone()
        if row is None:
            raise ValueError("Forschungsobjekt nicht gefunden")
        if target_type == "finding":
            from . import dual_review

            unreleased = dual_review.guard_direct_finding_decision(w, obj_id)
            if unreleased is not None:
                return dual_review.save_judgment(
                    w,
                    {
                        "session_id": unreleased["session_id"],
                        "finding_id": obj_id,
                        "action": action,
                        "reason": reason,
                        "interpretation": payload.get("interpretation"),
                    },
                )
        target_key = str(obj_id)

    at = datetime.now(timezone.utc).isoformat()
    with w.db() as db:
        decision_id = db.execute(
            """INSERT INTO ux_decisions(target_type,target,at,origin,action,reason,payload)
               VALUES(?,?,?,?,?,?,?)""",
            (
                target_type,
                target_key,
                at,
                "human",
                action,
                reason,
                json.dumps(payload, ensure_ascii=False),
            ),
        ).lastrowid
    return dict(
        id=decision_id,
        target_type=target_type,
        target=body.get("target") if target_type == "observation" else target_key,
        at=at,
        origin="human",
        action=action,
        reason=reason,
        payload=payload,
    )


def carry_forward_decisions(w, document_id: int, target_run_id: int) -> dict:
    """Carry forward verified human observation decisions across A re-runs on the same document version (`US-47`)."""
    from hashlib import sha256

    doc_id = int(document_id)
    run_id = int(target_run_id)
    runs = w.results(doc_id, messages=False)
    target_run = next((r for r in runs if r["id"] == run_id), None)
    if target_run is None:
        raise ValueError("Ziel-A-Lauf nicht gefunden")
    target_ver = target_run["result"].get("document_version")

    with w.db() as db:
        prior_rows = [
            dict(r, payload=json.loads(r["payload"]))
            for r in map(
                dict,
                db.execute(
                    "SELECT * FROM ux_decisions WHERE target_type='observation' AND origin IN ('human','human_carried_forward') ORDER BY id"
                ),
            )
        ]

    latest_by_obs_target = {}
    for row in prior_rows:
        try:
            t_ref = json.loads(row["target"])
        except ValueError:
            continue
        if t_ref.get("document") != doc_id or t_ref.get("run") == run_id:
            continue
        latest_by_obs_target[row["target"]] = row

    by_fingerprint = {}
    for row in latest_by_obs_target.values():
        fp = (row.get("payload") or {}).get("_fingerprint") or {}
        eids = tuple(fp.get("evidence_ids") or ())
        st_hash = fp.get("statement_sha256") or ""
        if fp.get("document_version") == target_ver and eids and st_hash:
            by_fingerprint[(eids, st_hash)] = row

    existing_targets = {
        r["target"]
        for r in prior_rows
        if json.loads(r["target"]).get("document") == doc_id
        and json.loads(r["target"]).get("run") == run_id
    }

    carried = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    for obs in target_run["result"].get("observations") or []:
        ref = dict(document=doc_id, run=run_id, observation=obs["id"])
        target_key = json.dumps(ref, sort_keys=True)
        if target_key in existing_targets:
            continue
        eids = tuple(sorted(obs.get("source_ids") or ()))
        stmt_norm = " ".join(str(obs.get("statement") or "").split())
        st_hash = sha256(stmt_norm.encode("utf-8")).hexdigest() if stmt_norm else ""
        matched_dec = by_fingerprint.get((eids, st_hash))
        if matched_dec is not None:
            with w.db() as db:
                db.execute(
                    """INSERT INTO ux_decisions(target_type,target,at,origin,action,reason,payload)
                       VALUES(?,?,?,?,?,?,?)""",
                    (
                        "observation",
                        target_key,
                        now_iso,
                        "human_carried_forward",
                        matched_dec["action"],
                        matched_dec["reason"],
                        json.dumps(matched_dec["payload"], ensure_ascii=False),
                    ),
                )
            carried += 1
    return dict(document=doc_id, run=run_id, carried_forward=carried)


def analysis_run(workspace, run_id):
    with workspace.db() as db:
        receipt = db.execute(
            "SELECT id,at,proposal,metadata FROM ux_objects WHERE kind='comparison' AND id=?",
            (run_id,),
        ).fetchone()
    if receipt is None:
        raise ValueError("Analyselauf nicht verfügbar")
    return dict(
        id=receipt["id"],
        at=receipt["at"],
        proposal=json.loads(receipt["proposal"]),
        metadata=json.loads(receipt["metadata"]),
    )


def analysis_stages(saved, scope, current_runs):
    from .native_graph import projection_status
    stages = {stage: [] for stage in ("B", "C", "legacy")}
    for item in reversed(saved):
        metadata = item["metadata"]
        if item["kind"] != "comparison" or set(metadata.get("scope", ())) != scope:
            continue
        base = basis_runs(metadata)
        raw_by_doc = metadata.get("basis_by_doc")
        if isinstance(raw_by_doc, dict) and raw_by_doc:
            basis_map = {int(k): int(v) for k, v in raw_by_doc.items()}
        else:
            basis_map = {
                int(r["document"]): int(r["run"])
                for r in metadata.get("observations", ())
                if isinstance(r, dict)
                and r.get("document") is not None
                and r.get("run") is not None
            }
        state = metadata.get("status", "UNREVIEWED")
        stages.setdefault(metadata.get("stage") or "legacy", []).append(
            dict(
                id=item["id"],
                at=item["at"],
                model=metadata.get("model"),
                provider=metadata.get("provider"),
                status="STALE" if base != current_runs and state != "ERROR" else state,
                result_status=state,
                basis_runs=sorted(base),
                basis=basis_map,
                b_run=metadata.get("b_run"),
                counts=metadata.get("counts"),
                native_projection=projection_status(metadata.get("native_graph"), metadata.get("stage")),
            )
        )
    return stages


def markdown_report(w, numbers, *, basis=None, result_runs=None, lang="de"):
    """Generate a structured, source-grounded Markdown research report including human review decisions."""
    g = graph(w, numbers, history=False, basis=basis, result_runs=result_runs)
    en = str(lang or "de").lower().startswith("en")
    obs_by_key = {
        (e["ref"]["document"], e["ref"]["run"], e["ref"]["observation"]): e
        for e in g.get("observations", [])
    }
    graph_nodes = g.get("graph", {}).get("nodes", [])
    finding_nodes = {
        n["record_id"]: n for n in graph_nodes if n.get("__class__") == "FindingNode"
    }
    all_findings = [o for o in g.get("objects", []) if o.get("kind") == "finding"]
    findings = [f for f in all_findings if f.get("review") != "HUMAN_REJECTED"]
    rejected_findings = [f for f in all_findings if f.get("review") == "HUMAN_REJECTED"]
    relations = [o for o in g.get("objects", []) if o.get("kind") == "relation"]
    rel_by_id = {r["id"]: r for r in relations}

    lines = [
        "# UX-mAInd · Source-Grounded Usability Study Report"
        if en
        else "# UX-mAInd · Quellengebundener Usability-Studienbericht",
        "",
        f"- **{'Generated at' if en else 'Erstellt am'}:** `{datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}`",
        f"- **{'Selected documents' if en else 'Ausgewählte Dokumente'}:** `{len(g.get('documents', []))}`",
        f"- **{'Grounded observations (A)' if en else 'Verankerte Beobachtungen (A)'}:** `{g['analysis']['observations']}`",
        f"- **{'Cross-observation relations (B)' if en else 'Beziehungen (B)'}:** `{g['analysis']['relations']}`",
        f"- **{'Active findings (C)' if en else 'Aktive Findings (C)'}:** `{len(findings)}`"
        + (
            f" (`{len(rejected_findings)}` {'rejected in review' if en else 'menschlich verworfen'})"
            if rejected_findings
            else ""
        ),
        "",
        "## 1. " + ("Study Corpus & Provenance" if en else "Studienbestand & Provenienz"),
        "",
    ]
    for d in g.get("documents", []):
        lines.append(
            f"- **#{d['document']} `{d['name']}`** — A-Run `#{d.get('selected_run') or '-'}` · "
            f"Version `{(d.get('document_version') or '-')[:12]}` · Status `{d.get('coverage_status')}`"
        )
    lines.append("")
    lines.append("## 2. " + ("Synthesized Findings & Researcher Review" if en else "Findings & Menschlicher Prüfstand"))
    lines.append("")
    if not findings:
        lines.append("_" + ("No active findings in current run state." if en else "Keine aktiven Findings im aktuellen Laufstand vorhanden.") + "_")
        lines.append("")
    for idx, f in enumerate(findings, 1):
        p = f.get("effective", {})
        fnode = finding_nodes.get(f["id"], {})
        rev = f.get("review", "UNREVIEWED")
        flags = fnode.get("epistemic_flags", [])
        indep = fnode.get("independence", {})
        lines.append(f"### 2.{idx} {p.get('title') or f'Finding #{f['id']}'}")
        lines.append(
            f"- **ID:** `#{f['id']}` · **Review:** `{rev}` · **{'Valence' if en else 'Valenz'}:** `{p.get('valence') or '-'}` · "
            f"**{'Type' if en else 'Typ'}:** `{p.get('finding_type') or '-'}`"
            + (
                f" · **{'UX Heuristic' if en else 'UX-Heuristik'}:** `{p['usability_heuristic']}`"
                if p.get("usability_heuristic")
                else ""
            )
        )
        if indep:
            sp_part = (
                f" · `{indep['distinct_speakers']}` {'named speakers' if en else 'genannte Sprecher'}"
                if indep.get("distinct_speakers")
                else ""
            )
            lines.append(
                f"- **{'Independent Evidence' if en else 'Unabhängige Stützen'}:** "
                f"`{indep.get('effective_independent_supports', 0)}` {'independent anchors across' if en else 'unabhängige Anker über'} "
                f"`{indep.get('independent_documents', 0)}` {'documents' if en else 'Dokumente'} (`{indep.get('raw_supports', 0)}` raw){sp_part}"
            )
        if flags:
            lines.append(f"- **{'Epistemic Notices' if en else 'Epistemische Hinweise'}:** `{', '.join(flags)}`")
        if p.get("scope"):
            lines.append(f"- **{'Scope' if en else 'Geltungsbereich'}:** {p['scope']}")
        used_rels = [rel_by_id[rid] for rid in (p.get("relations") or []) if rid in rel_by_id]
        if used_rels:
            rel_tags = ", ".join(
                f"`B #{r['id']} ({(r.get('effective') or {}).get('kind') or '-'})`"
                for r in used_rels
            )
            lines.append(f"- **{'Linked Stage-B Relations' if en else 'Verknüpfte B-Beziehungen'}:** {rel_tags}")
        lines.append("")
        if p.get("rationale"):
            lines.append(p["rationale"])
            lines.append("")
        if p.get("observed_effect"):
            lines.append(f"**{'Observed Effect' if en else 'Beobachtete Wirkung'}:** {p['observed_effect']}")
            lines.append("")
        if p.get("uncertainty"):
            lines.append(f"**{'Remaining Uncertainty' if en else 'Verbleibende Unsicherheit'}:** {p['uncertainty']}")
            lines.append("")
        if p.get("improvement_hypothesis"):
            lines.append(
                f"**{'Improvement Hypothesis (Unverified)' if en else 'Verbesserungshypothese (ungeprüft)'} "
                f"(`{p.get('improvement_basis') or 'unspecified'}`):** {p['improvement_hypothesis']}"
            )
            lines.append("")
        dr = f.get("dual_review") or {}
        if dr.get("released"):
            res_state = dr.get("resolution_state")
            if res_state == "OPEN_DISAGREEMENT":
                lines.append(
                    f"- **{'Dual Review' if en else 'Zweitprüfung'}:** "
                    f"⚠️ **{'OPEN DISAGREEMENT (unresolved divergence between Reviewer 1 and Reviewer 2)' if en else 'OFFENE ABWEICHUNG (abweichende Urteile zwischen Prüfer 1 und Prüfer 2 noch offen)'}**"
                )
            elif res_state == "ADOPTED":
                adopted_src = (dr.get("resolution") or {}).get("adopted_from") or "-"
                lines.append(
                    f"- **{'Dual Review' if en else 'Zweitprüfung'}:** "
                    f"`ADOPTED ({adopted_src})` — {(dr.get('resolution') or {}).get('reason') or ''}"
                )
            elif res_state == "PENDING_ADOPTION":
                lines.append(
                    f"- **{'Dual Review' if en else 'Zweitprüfung'}:** "
                    f"`PENDING_ADOPTION` — {'Comparison released; explicit adoption into study state pending' if en else 'Vergleich freigegeben; Übernahme in den Studienstand noch offen'}"
                )
            lines.append("")
        human_decs = [
            d
            for d in f.get("decisions", [])
            if d.get("origin") in ("human", "dual_review", "dual_review_adopted")
        ]
        if human_decs:
            lines.append("#### " + ("Researcher Decisions & Notes" if en else "Forscherentscheidungen & Notizen"))
            for d in human_decs:
                rev_name = ((d.get("payload") or {}).get("reviewer") or {}).get("name")
                who_part = f" ({rev_name})" if rev_name else ""
                note_part = f" — _{d['reason']}_" if d.get("reason") else ""
                lines.append(f"- `{d.get('at', '')[:19]}` · **`{d.get('action')}`**{who_part}{note_part}")
            lines.append("")
        lines.append("#### " + ("Anchored Source Quotes" if en else "Verankerte Originalbelege"))
        for role_key, role_label in (
            ("supports", "Support" if en else "Stützend"),
            ("opposes", "Counterevidence" if en else "Gegenbeleg"),
            ("qualifies", "Qualifying" if en else "Einschränkend"),
            ("improvement_evidence", "Participant Idea" if en else "Teilnehmer-Vorschlag"),
        ):
            for ref in p.get(role_key) or []:
                rk = (ref.get("document"), ref.get("run"), ref.get("observation"))
                obs = obs_by_key.get(rk)
                if obs:
                    q = " ".join(str(obs["effective"].get("quote") or "").split())
                    speaker = (obs["effective"].get("context") or {}).get("actor_or_speaker") or "-"
                    obs_decs = [d for d in obs.get("decisions", []) if d.get("origin") == "human"]
                    obs_note = ""
                    if obs_decs:
                        last_d = obs_decs[-1]
                        obs_note = f" _(Review `{last_d.get('action')}`" + (
                            f": {last_d['reason']})" if last_d.get("reason") else ")"
                        )
                    lines.append(
                        f"- **[{role_label}] `{obs['name']}` (`A #{ref['run']} · {ref['observation']}`, Speaker: `{speaker}`):** "
                        f"„{q}“{obs_note}"
                    )
        lines.append("")

    if rejected_findings:
        lines.append("### " + ("Rejected Finding Proposals (Audit Trail)" if en else "Verworfene Finding-Vorschläge (Prüfnachweis)"))
        lines.append("")
        for rf in rejected_findings:
            rp = rf.get("effective", {})
            decs = [
                d
                for d in rf.get("decisions", [])
                if d.get("origin") in ("human", "dual_review", "dual_review_adopted")
            ]
            reason_txt = decs[-1].get("reason") if decs and decs[-1].get("reason") else ("Rejected by researcher" if en else "Menschlich verworfen")
            lines.append(f"- **#{rf['id']} {rp.get('title') or ''}** (`HUMAN_REJECTED`) — _{reason_txt}_")
        lines.append("")

    if relations:
        lines.append("## 3. " + ("Cross-Observation Relations (Stage B)" if en else "Beziehungen zwischen Beobachtungen (Stufe B)"))
        lines.append("")
        for r in relations:
            rp = r.get("effective", {})
            if not rp.get("kind"):
                continue
            s_refs = rp.get("source") or []
            t_refs = rp.get("target") or []
            if isinstance(s_refs, dict):
                s_refs = [s_refs]
            if isinstance(t_refs, dict):
                t_refs = [t_refs]
            s_lbl = ", ".join(f"`D{x.get('document')}/{x.get('observation')}`" for x in s_refs if isinstance(x, dict)) or "`-`"
            t_lbl = ", ".join(f"`D{x.get('document')}/{x.get('observation')}`" for x in t_refs if isinstance(x, dict)) or "`-`"
            decs = [d for d in r.get("decisions", []) if d.get("origin") == "human" and d.get("reason")]
            note_txt = f" · Note: _{decs[-1]['reason']}_" if decs else ""
            lines.append(
                f"- **Relation `#{r['id']}` (`{rp.get('kind')}`, `{r.get('review')}`):** "
                f"{s_lbl} → {t_lbl} — "
                f"{rp.get('rationale') or ''}{note_txt}"
            )
        lines.append("")
    return "\n".join(lines)
