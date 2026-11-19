"""Safe receipts for the existing workspace job and document callbacks."""

from datetime import datetime, timezone
import re


def now():
    return datetime.now(timezone.utc).isoformat()


def symbol(value):
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[\w./:@-]+", value)
        else None
    )


_SECRET_PATTERNS = re.compile(
    r"(?i)(bearer\s+\S+|sk-[A-Za-z0-9_-]{8,}|AIza[0-9A-Za-z_-]{12,}|https?://[^/\s:@]+:[^/\s@]+@)"
)


def safe_detail(value):
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"[\r\n\t]+", " ", value).strip()
    if not cleaned:
        return None
    cleaned = _SECRET_PATTERNS.sub("[REDACTED]", cleaned)
    return cleaned[:220]


def event(value):
    if not isinstance(value, dict):
        return {}
    fields = (
        "document",
        "document_name",
        "completed_pages",
        "total_pages",
        "observations",
        "resolved",
        "issues",
        "basis_eligible",
        "validated",
        "graph_observations",
        "blockers",
        "run",
        "http_status",
        "pixels",
        "pictures",
        "described",
        "classified",
        "charts",
        "description_open",
        "native",
        "total",
        "completed",
        "failed",
        "successful",
        "skipped",
        "reused",
        "targets",
        "proposed",
        "unresolved",
        "null_decisions",
        "duration_s",
        "timeout_s",
        "read_timeout_s",
        "attempt",
        "max_attempts",
        "chunks",
        "items_count",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "reasoning_tokens",
        "cached_tokens",
    )
    out = {
        **{k: value[k] for k in fields if k in value},
        **{
            k: symbol(value[k])
            for k in (
                "kind",
                "phase",
                "status",
                "reason",
                "error",
                "workflow_step",
                "confidence_grade",
                "model",
                "contract",
                "serializer",
                "response_format",
            )
            if k in value
        },
    }
    detail = safe_detail(value.get("detail"))
    if detail:
        out["detail"] = detail
    return out


def workflow_event(stages, value, items):
    phase = value.get("workflow_step")
    if value.get("kind") == "workflow":
        return {**stages, value["phase"]: value}
    if phase not in stages:
        return stages
    current = stages[phase]
    counter = {}
    if phase in ("conversion", "vision", "A"):
        targets = current.get("targets")
        count = sum(
            phase in item["steps"] and (targets is None or number in targets)
            for number, item in items.items()
        )
        counter["completed"] = min(
            current["total"],
            max(
                current.get("completed", 0),
                count + (current.get("reused", 0) if phase == "conversion" else 0),
            ),
        )
    return {**stages, phase: {**current, **counter, "event": value}}


def outcome(items, report):
    states = {str(v.get("status", "")).lower() for v in items}
    if isinstance(report, dict) and isinstance(report.get("status"), str):
        states.add(report["status"].lower())
    bad = {"error", "failure", "failed"}
    partial = {"partial", "partial_success", "waiting"}
    if states and states <= bad:
        return "ERROR"
    if states & (bad | partial):
        return "PARTIAL"
    return "FINISHED"
