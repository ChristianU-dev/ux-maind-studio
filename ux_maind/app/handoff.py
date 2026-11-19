"""Read-only accounting of every A input, including blocked and excluded evidence."""


def manifest(entries, documents):
    docs = {d["document"]: d for d in documents}
    rows = []
    for entry in entries:
        last_human = next((d["action"] for d in reversed(entry["decisions"])
                           if d["origin"] == "human"), None)
        resolved = bool(entry["source_check"]["matches"])
        rejected = last_human == "rejected"
        document = docs[entry["ref"]["document"]]
        technical = document.get("technical") or {}
        reasons = []
        if rejected:
            reasons.append("HUMAN_REJECTED")
        if not resolved:
            reasons.append("UNRESOLVED_SOURCE")
        if any(not m["sources"] for m in entry["measurements"]):
            reasons.append("UNRESOLVED_MEASUREMENT")
        if entry["diagnostics"]:
            reasons.append("ANCHOR_DIAGNOSTIC")
        if entry["source_issues"]:
            reasons.append("RECORDED_SOURCE_ISSUE")
        offered = resolved and not rejected
        rows.append(dict(
            ref=entry["ref"], document_version=entry["document_version"],
            source_resolved=resolved, citation_ready=offered and not reasons,
            offered=offered, reasons=reasons,
            raw_source_issues=entry["source_issues"],
            primary_applied=bool(entry["selected_source"]),
            context_only=not resolved and bool(entry["context_sources"] or entry["context_decisions"]),
            blocked=not technical.get("eligible", False) or bool(document.get("archived")),
            blocking_reasons=technical.get("reasons", []),
            source_ids=[a["evidence_id"] for a in entry["source_check"]["matches"]],
        ))
    return dict(
        semantic_validation="NOT_PERFORMED",
        total=len(rows), source_resolved=sum(r["source_resolved"] for r in rows),
        citation_ready=sum(r["citation_ready"] for r in rows),
        offered=sum(r["offered"] for r in rows),
        excluded=sum(not r["offered"] for r in rows),
        blocked=sum(r["blocked"] for r in rows), rows=rows,
    )
