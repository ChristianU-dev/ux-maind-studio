"""Technical eligibility of a stored A run, including pre-R20 receipts."""

reason_text = {
    "response_truncated": "Die Modellantwort wurde abgeschnitten. A erneut ausführen oder einen vollständigen A-Lauf wählen.",
    "a_validation_open": "Es fehlt eine vollständige validierte A-Antwort. A erneut ausführen oder einen anderen A-Lauf wählen.",
    "a_schema_salvaged": "Mindestens ein Teil-Objekt musste bei der Schema-Validierung automatisch bereinigt werden (Salvage). Extrahierte Beobachtungen vor der Übergabe prüfen.",
    "a_source_open": "Mindestens eine notwendige Quelle oder Messstelle ist offen. Fundstellen prüfen oder einen geeigneten A-Lauf wählen.",
    "a_measurement_open": "Mindestens eine sekundäre Messstelle konnte nicht eindeutig gebunden werden.",
    "a_extraction_open": "Die Extraktion meldet offene technische Ergebnisse. A prüfen oder einen anderen Lauf wählen.",
    "a_ledger_open": "Erkannte Inhalte fehlen im nativen Quellenprotokoll. A prüfen oder einen anderen Lauf wählen.",
    "a_input_partial": "Die verwendete Dokumentverarbeitung war teilweise offen. Die Version prüfen oder einen anderen A-Lauf wählen.",
}


def dimensions(result):
    native = result.get("native_graph") or {}
    observations = result.get("observations") or []
    issues = result.get("issues") or []
    graph_nodes = (native.get("graph") or {}).get("nodes", [])
    projected = sum(n.get("__class__") == "Observation" for n in graph_nodes)
    projection_issues = [i for i in issues if i.get("stage") == "graph_conversion"]
    finishes = {r.get("finish_reason") for r in native.get("requests", [])}
    truncated = (native.get("last_response") or {}).get("truncated") or bool(
        finishes & {"length", "max_tokens"}
    )
    salvaged = bool(native.get("salvaged")) or (
        not native.get("error")
        and any(
            e.get("event_type") == "validation_error_raw_data"
            for e in (native.get("trace") or [])
        )
    ) or any(i.get("status") == "SCHEMA_SALVAGED" for i in issues)
    coverage = result.get("coverage") or {}
    resolved = sum(bool(o.get("source_ids")) for o in observations)
    open_sources = resolved < len(observations) or any(
        i.get("status") == "UNRESOLVED" for i in issues
    )
    measurement_open = sum(
        i.get("status") == "MEASUREMENT_UNRESOLVED" for i in issues
    )
    reasons = []
    if truncated:
        reasons.append("response_truncated")
    if not observations or result.get("error") or native.get("error"):
        reasons.append("a_validation_open")
    if salvaged:
        reasons.append("a_schema_salvaged")
    if open_sources:
        reasons.append("a_source_open")
    if any(
        i not in projection_issues
        and i.get("status")
        not in (
            "UNRESOLVED",
            "MEASUREMENT_UNRESOLVED",
            "ORIGIN_RECONCILED",
            "REF_RECONCILED",
            "SCHEMA_SALVAGED",
        )
        for i in issues
    ):
        reasons.append("a_extraction_open")
    inp = result.get("input") or {}
    is_one_to_one = inp.get("processing") == "one-to-one"
    if coverage.get("missing_ledger_items") or (
        coverage.get("undocumented_ledger_items") and not is_one_to_one
    ):
        reasons.append("a_ledger_open")
    if (result.get("status") == "PARTIAL" and not issues) or result.get(
        "partial_input"
    ):
        reasons.append("a_input_partial")
    # Older rows with no evidence of a completed native extraction cannot use
    # a projection-only exception.
    if result.get("status") != "UNREVIEWED" and not native.get("extracted"):
        reasons.append("a_validation_open")
    return dict(
        eligible=not reasons,
        reasons=list(dict.fromkeys(reasons)),
        response="truncated"
        if truncated
        else "complete"
        if finishes and finishes <= {"stop", "end_turn"}
        else "unknown",
        validated=len(observations),
        resolved=resolved,
        measurement_open=measurement_open,
        salvaged=salvaged,
        graph_observations=projected if native.get("graph") is not None else None,
        graph_difference=bool(projection_issues)
        or bool(native.get("graph") and projected < len(observations)),
        semantically_reviewed=coverage.get("semantically_reviewed"),
    )
