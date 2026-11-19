"""Decoupled CLI terminal monitor and persistent safe job history ledger."""

from __future__ import annotations

import sys

MAX_HISTORY_JOBS = 30
MAX_EVENTS_PER_HISTORY_JOB = 80


def format_event_line(at_iso: str, clean: dict) -> str | None:
    """Format one safe receipt event into a readable terminal line (or None for noisy empty sub-ticks)."""
    raw_kind = str(clean.get("kind") or "")
    if raw_kind in ("phase_started", "phase_completed", "document_started") and clean.get("completed_pages") is None:
        return None
    ts = (at_iso or "")[11:19] or "--:--:--"
    raw_stage = (
        clean.get("workflow_step")
        or clean.get("kind")
        or clean.get("phase")
        or "job"
    )
    stage_map = {
        "inventory": "IMPORT",
        "import_paths": "IMPORT",
        "conversion": "DOCLING",
        "document_completed": "DOCLING",
        "vision": "VISION",
        "enrich": "VISION",
        "A": "STUFE A",
        "B": "STUFE B",
        "C": "STUFE C",
        "workflow": "PIPELINE",
        "model_access": "MODELL",
    }
    stage = stage_map.get(str(raw_stage), str(raw_stage).upper()[:9])

    status_val = str(clean.get("status") or "")
    phase = clean.get("phase")
    http_code = clean.get("http_status")
    is_error = (
        status_val in ("ERROR", "failure", "error")
        or phase == "api_error"
        or bool(clean.get("error"))
        or (isinstance(http_code, int) and http_code >= 500)
    )
    is_warn = not is_error and (
        status_val in ("PARTIAL", "partial_success", "WARN", "WAITING_REVIEW", "NO_PROPOSALS")
        or phase in ("model_timeout", "stream_stalled", "model_retry", "structured_fallback")
        or (isinstance(http_code, int) and http_code >= 400)
        or bool(clean.get("unresolved"))
    )
    prefix = "✖ " if is_error else ("⚠ " if is_warn else "  ")

    parts: list[str] = []
    if clean.get("document_name"):
        parts.append(str(clean["document_name"]))
    elif clean.get("document"):
        parts.append(f"Dok #{clean['document']}")

    if phase and phase not in (raw_stage, "conversion", "enrich"):
        parts.append(str(phase))

    if status_val:
        parts.append(status_val)

    if clean.get("attempt") and clean.get("max_attempts") and clean["max_attempts"] > 1:
        parts.append(f"Versuch {clean['attempt']}/{clean['max_attempts']}")
    if clean.get("completed") is not None and clean.get("total"):
        parts.append(f"{clean['completed']}/{clean['total']} Schritte")
    if clean.get("completed_pages") is not None and clean.get("total_pages"):
        parts.append(f"Seite {clean['completed_pages']}/{clean['total_pages']}")
    if clean.get("duration_s") is not None:
        parts.append(f"{clean['duration_s']}s")
    elif clean.get("timeout_s") is not None and phase == "model_request":
        parts.append(f"Limit {clean['timeout_s']}s")
    if clean.get("confidence_grade"):
        parts.append(f"Güte={clean['confidence_grade']}")
    if clean.get("items_count") is not None:
        parts.append(f"{clean['items_count']} Blöcke")

    if clean.get("observations") is not None:
        res = clean.get("resolved")
        if res is not None:
            parts.append(f"Belege {res}/{clean['observations']} verankert")
        else:
            parts.append(f"{clean['observations']} Beobachtungen")

    if clean.get("proposed") is not None:
        parts.append(f"{clean['proposed']} Vorschläge")
    if clean.get("unresolved"):
        parts.append(f"{clean['unresolved']} offen")
    if clean.get("pictures") is not None and clean.get("described") is not None:
        parts.append(f"{clean['described']}/{clean['pictures']} Bilder beschrieben")
    if clean.get("total_tokens"):
        tok_txt = f"{clean['total_tokens']:,} Tokens"
        if clean.get("reasoning_tokens"):
            tok_txt += f" ({clean['reasoning_tokens']:,} Reasoning)"
        parts.append(tok_txt)
    if clean.get("model"):
        parts.append(f"Modell={clean['model']}")
    if clean.get("http_status"):
        parts.append(f"HTTP {clean['http_status']}")
    if clean.get("detail"):
        parts.append(str(clean["detail"]))
    elif clean.get("reason"):
        parts.append(f"Hinweis={clean['reason']}")
    if clean.get("error") and clean.get("error") != clean.get("reason"):
        parts.append(f"Fehler={clean['error']}")

    body = " · ".join(parts) if parts else "aktiv"
    return f"{prefix}[{ts}] [{stage:<9}] {body}"


def emit_startup_banner(
    *,
    port: int,
    workspace_root,
    output_dir: str,
    detected_envs: list[str],
    workflow_cfg: dict,
    verbose: bool = False,
    stream=None,
) -> None:
    out = stream or sys.stderr
    profs = (workflow_cfg or {}).get("profiles") or {}
    conv = (workflow_cfg or {}).get("conversion") or {}
    envs_txt = ", ".join(detected_envs) if detected_envs else "keine erkannt (Lokal/Ollama bereit)"
    roles_txt = " | ".join(
        f"{k}: {profs.get(k) or ('=A' if k in ('B', 'C') else '—')}"
        for k in ("A", "B", "C", "vision")
    )
    conv_txt = (
        f"OCR={'an' if conv.get('do_ocr', True) else 'aus'}"
        f"{' (Vollseite)' if conv.get('force_full_page_ocr') else ''}, "
        f"TableFormer={conv.get('table_mode', 'accurate')}, "
        f"Scale={conv.get('images_scale', 1.0)}x"
    )
    sep = "=" * 78
    print(
        f"\n{sep}\n"
        f"  UX-mAInd Studio · Quellengebundene Usability-Synthese\n"
        f"  URL             : http://127.0.0.1:{port}\n"
        f"  Arbeitsbereich  : {workspace_root}\n"
        f"  Ausgabeordner   : {output_dir}\n"
        f"  API-Umgebung    : {envs_txt}\n"
        f"  Aktive Rollen   : {roles_txt}\n"
        f"  Docling-Engine  : {conv_txt}\n"
        f"  Terminal-Modus  : {'Ausführlich (+ HTTP-Requests)' if verbose else 'Live-Verlaufsprotokoll (--verbose für HTTP)'}\n"
        f"{sep}",
        file=out,
        flush=True,
    )


def emit_job_start(action: str, doc_names: list[str], started_iso: str, stream=None) -> None:
    out = stream or sys.stderr
    ts = (started_iso or "")[11:19] or "--:--:--"
    scope_str = (
        f"{len(doc_names)} Dokument(e): {', '.join(doc_names[:5])}"
        + (f" (+{len(doc_names) - 5} weitere)" if len(doc_names) > 5 else "")
        if doc_names
        else "Arbeitsbereichs-Auftrag"
    )
    print(
        f"\n▶ [{ts}] AUFTRAG GESTARTET: {action} · {scope_str}",
        file=out,
        flush=True,
    )


def emit_job_end(final_job: dict, stream=None) -> None:
    out = stream or sys.stderr
    ts = (final_job.get("ended") or "")[11:19] or "--:--:--"
    state = final_job.get("state") or "FINISHED"
    action = final_job.get("action") or "job"
    docs = final_job.get("documents") or []
    marker = "✔" if state == "FINISHED" else "⚠" if state in ("PARTIAL", "WAITING_REVIEW") else "✖"
    print(
        f"{marker} [{ts}] AUFTRAG BEENDET: {action} -> {state} "
        f"({len(docs)} Dok., {len(final_job.get('events') or [])} Ereignisse)\n",
        file=out,
        flush=True,
    )


def append_job_history(workspace, final_job: dict) -> list[dict]:
    """Persist a bounded, secret-free ledger of completed workspace jobs."""
    existing = workspace.setting("job_history")
    history = list(existing) if isinstance(existing, list) else []
    entry = {
        "action": final_job.get("action"),
        "state": final_job.get("state"),
        "started": final_job.get("started"),
        "ended": final_job.get("ended"),
        "documents": [
            {
                "document": d.get("document"),
                "document_name": d.get("document_name"),
                "status": d.get("status"),
                "observations": d.get("observations"),
                "resolved": d.get("resolved"),
                "detail": d.get("detail") or d.get("reason"),
                "http_status": d.get("http_status"),
            }
            for d in (final_job.get("documents") or [])
        ],
        "events": list(final_job.get("events") or [])[-MAX_EVENTS_PER_HISTORY_JOB:],
    }
    history.append(entry)
    bounded = history[-MAX_HISTORY_JOBS:]
    workspace.set_setting("job_history", bounded)
    workspace.set_setting("job_history_cleared", False)
    return bounded


def reconstruct_historical_ledger(workspace) -> list[dict]:
    """Synthesize chronological Conversion, Vision, Stage A, Stage B, and Stage C jobs from SQLite (`US-58`)."""
    import json

    synthetic_jobs: list[dict] = []
    with workspace.db() as db:
        docs = [dict(r) for r in db.execute("SELECT * FROM documents ORDER BY id").fetchall()]
        doc_names = {d["id"]: d["name"] for d in docs}

        # 1. Conversion & Vision enrichment records per document
        conv_events = []
        conv_docs = []
        for d in docs:
            if not d.get("native"):
                continue
            diag = json.loads(d.get("diagnostics") or "{}")
            conf = (diag.get("confidence") or {}).get("mean_grade")
            conv_docs.append(
                {
                    "document": d["id"],
                    "document_name": d["name"],
                    "status": d.get("status") or "READY",
                }
            )
            conv_events.append(
                {
                    "at": "",
                    "kind": "conversion",
                    "phase": "conversion",
                    "document": d["id"],
                    "document_name": d["name"],
                    "status": d.get("status") or "READY",
                    "confidence_grade": conf,
                }
            )
            try:
                versions = workspace.versions(d)
            except Exception:
                versions = []
            for v in versions:
                if v.get("kind") == "conversion":
                    continue
                pics = v.get("pictures") or []
                desc_cnt = sum(1 for p in pics if p.get("description_status") == "ENRICHED")
                if desc_cnt or v.get("status"):
                    v_at = v.get("at") or ""
                    synthetic_jobs.append(
                        {
                            "action": "enrich",
                            "state": "FINISHED" if desc_cnt else "PARTIAL",
                            "started": v_at,
                            "ended": v_at,
                            "reconstructed": True,
                            "documents": [
                                {
                                    "document": d["id"],
                                    "document_name": d["name"],
                                    "status": v.get("status") or "ENRICHED",
                                }
                            ],
                            "events": [
                                {
                                    "at": v_at,
                                    "kind": "vision",
                                    "phase": "enrich",
                                    "document": d["id"],
                                    "document_name": d["name"],
                                    "status": v.get("status") or "ENRICHED",
                                    "pictures": len(pics),
                                    "described": desc_cnt,
                                    "duration_s": v.get("duration_s"),
                                    "model": (v.get("configuration") or {}).get("model"),
                                }
                            ],
                        }
                    )
        if conv_events:
            synthetic_jobs.append(
                {
                    "action": "convert",
                    "state": "FINISHED",
                    "started": "",
                    "ended": "",
                    "reconstructed": True,
                    "documents": conv_docs,
                    "events": conv_events[-MAX_EVENTS_PER_HISTORY_JOB:],
                }
            )

        # 2. Stage A runs from `runs` table
        a_rows = db.execute("SELECT id, document, at, result FROM runs ORDER BY id").fetchall()
        for r in a_rows:
            res = json.loads(r["result"] or "{}")
            obs = res.get("observations") or []
            resolved = sum(bool(o.get("source_ids")) for o in obs)
            reqs = (res.get("native_graph") or {}).get("requests") or []
            t_tok = sum(
                int((req.get("usage") or {}).get("total_tokens") or 0) for req in reqs
            ) or sum(
                int((req.get("usage") or {}).get("prompt_tokens") or 0)
                + int((req.get("usage") or {}).get("completion_tokens") or 0)
                for req in reqs
            )
            d_id = r["document"]
            d_name = doc_names.get(d_id, f"Dok #{d_id}")
            st = res.get("status") or "UNREVIEWED"
            diag = res.get("diagnostic") or {}
            r_tok = sum(int((req.get("usage_details") or {}).get("reasoning_tokens") or 0) for req in reqs)
            dur_s = round(sum(float(req.get("duration_s") or 0) for req in reqs), 2) or None
            synthetic_jobs.append(
                {
                    "action": f"extract (A #{r['id']})",
                    "state": "ERROR" if st == "ERROR" else ("PARTIAL" if st == "PARTIAL" else "FINISHED"),
                    "started": r["at"],
                    "ended": r["at"],
                    "reconstructed": True,
                    "documents": [
                        {
                            "document": d_id,
                            "document_name": d_name,
                            "status": st,
                            "observations": len(obs),
                            "resolved": resolved,
                            "detail": diag.get("detail") or diag.get("reason"),
                            "http_status": diag.get("http_status"),
                        }
                    ],
                    "events": [
                        {
                            "at": r["at"],
                            "kind": "A",
                            "phase": diag.get("stage") or "source_resolution",
                            "document": d_id,
                            "document_name": d_name,
                            "status": st,
                            "run": r["id"],
                            "model": res.get("model"),
                            "observations": len(obs),
                            "resolved": resolved,
                            "duration_s": dur_s,
                            "total_tokens": t_tok or None,
                            "reasoning_tokens": r_tok or None,
                            "reason": diag.get("reason") if st in ("ERROR", "PARTIAL") else None,
                            "error": res.get("error"),
                            "http_status": diag.get("http_status"),
                            "detail": diag.get("detail"),
                        }
                    ],
                }
            )

        # 3. Stage B & Stage C synthesis runs from `ux_objects`
        comp_rows = db.execute(
            "SELECT id, at, metadata FROM ux_objects WHERE kind='comparison' ORDER BY id"
        ).fetchall()
        for cr in comp_rows:
            meta = json.loads(cr["metadata"] or "{}")
            stg = meta.get("stage") or "B"
            counts = meta.get("counts") or {}
            reqs = (meta.get("native_graph") or {}).get("requests") or []
            t_tok = sum(
                int((req.get("usage") or {}).get("total_tokens") or 0) for req in reqs
            ) or sum(
                int((req.get("usage") or {}).get("prompt_tokens") or 0)
                + int((req.get("usage") or {}).get("completion_tokens") or 0)
                for req in reqs
            )
            r_tok = sum(int((req.get("usage_details") or {}).get("reasoning_tokens") or 0) for req in reqs)
            dur_s = round(sum(float(req.get("duration_s") or 0) for req in reqs), 2) or None
            diag = meta.get("diagnostic") or {}
            scope_ids = meta.get("scope") or []
            st = meta.get("status") or "UNREVIEWED"
            synthetic_jobs.append(
                {
                    "action": f"analysis_{stg} ({stg} #{cr['id']})",
                    "state": "ERROR" if st == "ERROR" else ("PARTIAL" if st == "PARTIAL" else "FINISHED"),
                    "started": cr["at"],
                    "ended": cr["at"],
                    "reconstructed": True,
                    "documents": [
                        {
                            "document": did,
                            "document_name": doc_names.get(did, f"Dok #{did}"),
                            "status": st,
                            "detail": diag.get("detail") or diag.get("reason"),
                            "http_status": diag.get("http_status"),
                        }
                        for did in scope_ids
                    ],
                    "events": [
                        {
                            "at": cr["at"],
                            "kind": stg,
                            "phase": diag.get("stage") or "synthesis",
                            "status": st,
                            "run": cr["id"],
                            "model": meta.get("model"),
                            "proposed": counts.get("proposed"),
                            "unresolved": counts.get("unresolved"),
                            "duration_s": dur_s,
                            "total_tokens": t_tok or None,
                            "reasoning_tokens": r_tok or None,
                            "reason": diag.get("reason") if st in ("ERROR", "PARTIAL") else None,
                            "http_status": diag.get("http_status"),
                            "detail": diag.get("detail"),
                        }
                    ],
                }
            )

    synthetic_jobs.sort(key=lambda j: str(j.get("ended") or j.get("started") or ""))
    return synthetic_jobs[-MAX_HISTORY_JOBS:]


def read_job_history(workspace) -> list[dict]:
    """Return newest-first job history, automatically reconstructing historical SQLite runs if needed."""
    stored = workspace.setting("job_history")
    if isinstance(stored, list) and stored:
        return list(reversed(stored))
    if workspace.setting("job_history_cleared") is True:
        return []
    reconstructed = reconstruct_historical_ledger(workspace)
    return list(reversed(reconstructed))
