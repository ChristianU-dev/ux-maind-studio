"""Modular run token/cost telemetry, multi-model evaluation matrix, and printable study handout."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json

from . import models, research


def _extract_usage(requests_list):
    prompt = 0
    completion = 0
    total = 0
    reasoning_tokens = 0
    cached_tokens = 0
    calls = 0
    reasoning_calls = 0
    truncated_calls = 0
    for req in requests_list or []:
        if not isinstance(req, dict):
            continue
        calls += 1
        if req.get("reasoning_present"):
            reasoning_calls += 1
        if req.get("finish_reason") in ("length", "max_tokens"):
            truncated_calls += 1
        usage = req.get("usage")
        details = req.get("usage_details") or {}
        if isinstance(usage, dict):
            p = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
            c = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
            t = int(usage.get("total_tokens") or (p + c))
            prompt += p
            completion += c
            total += t
            r_tok = details.get("reasoning_tokens")
            if r_tok is None:
                r_tok = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
            if r_tok is None:
                r_tok = usage.get("reasoning_tokens")
            if isinstance(r_tok, int) and r_tok > 0:
                reasoning_tokens += r_tok
            c_tok = details.get("cached_tokens")
            if c_tok is None:
                c_tok = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
            if c_tok is None:
                c_tok = usage.get("cache_read_input_tokens")
            if isinstance(c_tok, int) and c_tok > 0:
                cached_tokens += c_tok
    return dict(
        calls=calls,
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total or (prompt + completion),
        reasoning_tokens=reasoning_tokens,
        cached_tokens=cached_tokens,
        reasoning_calls=reasoning_calls,
        truncated_calls=truncated_calls,
    )


def _estimate_cost(provider, model_id, prompt_tokens, completion_tokens, cached_tokens=0):
    """Compute strictly genuine API costs from verified LiteLLM tariffs (`US-56`: zero fictional rates!)."""
    provider = str(provider or "").strip()
    model_id = str(model_id or "").strip()
    zero_billed = provider in ("nhr_fau", "ollama", "local")
    meta = models.catalog_meta(provider, model_id)
    in_rate = meta.get("input_cost_per_1m")
    out_rate = meta.get("output_cost_per_1m")
    cache_rate = meta.get("cache_read_cost_per_1m")
    verified = bool(meta.get("pricing_verified"))

    # Check if an exact OpenRouter/OpenAI commercial tariff exists for reference comparison
    ref_meta = meta if verified else models.catalog_meta("openrouter", model_id)
    ref_in = ref_meta.get("input_cost_per_1m") if ref_meta.get("pricing_verified") else None
    ref_out = ref_meta.get("output_cost_per_1m") if ref_meta.get("pricing_verified") else None
    ref_cache = ref_meta.get("cache_read_cost_per_1m") if ref_meta.get("pricing_verified") else None

    uncached_prompt = max(0, int(prompt_tokens) - int(cached_tokens or 0))
    cached_part = max(0, int(cached_tokens or 0))

    if isinstance(ref_in, (int, float)) and isinstance(ref_out, (int, float)):
        eff_cache_rate = ref_cache if isinstance(ref_cache, (int, float)) else ref_in
        cloud_ref_usd = round(
            (uncached_prompt * ref_in + cached_part * eff_cache_rate + completion_tokens * ref_out)
            / 1_000_000,
            6,
        )
    else:
        cloud_ref_usd = None

    if zero_billed:
        billed_usd = 0.0
        pricing_origin = "cluster_or_local_free"
    elif verified and isinstance(in_rate, (int, float)) and isinstance(out_rate, (int, float)):
        eff_cache_rate = cache_rate if isinstance(cache_rate, (int, float)) else in_rate
        billed_usd = round(
            (uncached_prompt * in_rate + cached_part * eff_cache_rate + completion_tokens * out_rate)
            / 1_000_000,
            6,
        )
        pricing_origin = "litellm_verified_tariff"
    else:
        billed_usd = None
        pricing_origin = "unlisted_model_tariff"

    return dict(
        billed_usd=billed_usd,
        cloud_reference_usd=cloud_ref_usd,
        input_cost_per_1m=0.0 if zero_billed else in_rate,
        output_cost_per_1m=0.0 if zero_billed else out_rate,
        cache_read_cost_per_1m=0.0 if zero_billed else cache_rate,
        pricing_verified=True if zero_billed else verified,
        pricing_origin=pricing_origin,
    )


def _vision_receipt_usage(receipt: dict | None):
    """Inspect a native Docling vision enrichment receipt without inventing exact token counts."""
    if not isinstance(receipt, dict):
        return None
    cfg = receipt.get("configuration") or {}
    pics = receipt.get("pictures") or []
    described = [p for p in pics if p.get("description_status") == "ENRICHED"]
    charts = [p for p in pics if p.get("chart")]
    if not described and not charts:
        return None
    mode = cfg.get("mode") or "api"
    provider = cfg.get("provider") or ("local" if mode == "inline" else "")
    model_id = cfg.get("model") or ""
    calls = len(described) + len(charts)
    # Docling PictureDescriptionApiOptions uses direct HTTP without returning OpenAI usage dicts;
    # estimate conservative image+text tokens transparently marked as token_origin="vision_estimate".
    est_prompt = calls * 1150 if mode == "api" else 0
    est_completion = sum(
        max(24, round(len(str(p.get("description") or "")) / 3.8)) for p in described
    ) + (len(charts) * 180 if mode == "api" else 0)
    cost = _estimate_cost(provider, model_id, est_prompt, est_completion)
    return dict(
        kind="vision",
        run_id=receipt.get("version", "")[:8] or "vision",
        at=receipt.get("at") or "",
        provider=provider,
        model=model_id,
        status=receipt.get("status") or "",
        duration_s=receipt.get("duration_s"),
        items_count=len(described) + len(charts),
        resolved_count=len(described) + len(charts),
        pictures_total=len(pics),
        described_count=len(described),
        charts_count=len(charts),
        calls=calls,
        prompt_tokens=est_prompt,
        completion_tokens=est_completion,
        total_tokens=est_prompt + est_completion,
        reasoning_calls=0,
        truncated_calls=0,
        token_origin="vision_estimate" if mode == "api" else "local_vlm",
        tokens_per_item=round((est_prompt + est_completion) / max(1, calls), 1)
        if mode == "api"
        else None,
        **cost,
    )


def _build_model_comparison(all_run_rows: list[dict]) -> list[dict]:
    """Aggregate empirical performance metrics per (stage, provider, model) for pipeline evaluation."""
    buckets: dict[tuple[str, str, str], dict] = {}
    for row in all_run_rows:
        stage = str(row.get("kind") or "")
        provider = str(row.get("provider") or "")
        model_id = str(row.get("model") or "")
        if not model_id:
            continue
        key = (stage, provider, model_id)
        b = buckets.setdefault(
            key,
            dict(
                stage=stage,
                provider=provider,
                model=model_id,
                runs=0,
                calls=0,
                items_total=0,
                resolved_total=0,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                reasoning_tokens=0,
                cached_tokens=0,
                truncated_runs=0,
                error_runs=0,
                billed_usd=0.0,
                billed_known=False,
                cloud_reference_usd=0.0,
                cloud_ref_known=False,
                token_origin=row.get("token_origin") or "exact_api_usage",
            ),
        )
        b["runs"] += 1
        b["calls"] += int(row.get("calls") or 0)
        b["items_total"] += int(row.get("items_count") or 0)
        b["resolved_total"] += int(row.get("resolved_count") or 0)
        b["prompt_tokens"] += int(row.get("prompt_tokens") or 0)
        b["completion_tokens"] += int(row.get("completion_tokens") or 0)
        b["total_tokens"] += int(row.get("total_tokens") or 0)
        b["reasoning_tokens"] += int(row.get("reasoning_tokens") or 0)
        b["cached_tokens"] += int(row.get("cached_tokens") or 0)
        if (row.get("truncated_calls") or 0) > 0:
            b["truncated_runs"] += 1
        if str(row.get("status") or "").upper() == "ERROR":
            b["error_runs"] += 1
        if row.get("billed_usd") is not None:
            b["billed_known"] = True
            b["billed_usd"] = round(b["billed_usd"] + float(row["billed_usd"]), 6)
        if row.get("cloud_reference_usd") is not None:
            b["cloud_ref_known"] = True
            b["cloud_reference_usd"] = round(
                b["cloud_reference_usd"] + float(row["cloud_reference_usd"]), 6
            )

    stage_rank = {"vision": 0, "A": 1, "B": 2, "C": 3}
    result = []
    for b in buckets.values():
        items = b["items_total"]
        b["anchor_rate_pct"] = (
            round((b["resolved_total"] / items) * 100.0, 1) if items > 0 else None
        )
        b["tokens_per_item"] = (
            round(b["total_tokens"] / items, 1)
            if items > 0 and b["total_tokens"] > 0
            else None
        )
        if not b["billed_known"]:
            b["billed_usd"] = None
        if not b["cloud_ref_known"]:
            b["cloud_reference_usd"] = None
        result.append(b)
    result.sort(key=lambda x: (stage_rank.get(x["stage"], 9), x["model"].lower()))
    return result


def study_telemetry(workspace, numbers, *, basis=None, result_runs=None):
    """Aggregate token usage, API costs, Vision receipts, Docling timings, and multi-model comparison."""
    doc_ids = [int(n) for n in dict.fromkeys(numbers or [])]
    g = (
        research.graph(
            workspace, doc_ids, history=False, basis=basis, result_runs=result_runs
        )
        if doc_ids
        else {"documents": [], "objects": [], "observations": [], "analysis": {}}
    )

    selected_a_by_doc = {
        d["document"]: d.get("selected_run") for d in g.get("documents", [])
    }

    stage_totals = {
        k: dict(
            stage=k,
            runs=0,
            calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            billed_usd=0.0,
            cloud_reference_usd=0.0,
            items_yielded=0,
            token_origin="vision_estimate" if k == "vision" else "exact_api_usage",
        )
        for k in ("vision", "A", "B", "C")
    }

    document_rows = []
    all_run_rows = []

    with workspace.db() as db:
        for doc_id in doc_ids:
            try:
                file_row = workspace.file(doc_id)
            except FileNotFoundError:
                continue
            diag = json.loads(file_row.get("diagnostics") or "{}")
            timings = diag.get("timings") or {}
            conv_sec = 0.0
            for tval in timings.values():
                if isinstance(tval, dict) and isinstance(tval.get("total"), (int, float)):
                    conv_sec = max(conv_sec, float(tval["total"]))
            conf = diag.get("confidence") or {}

            runs = db.execute(
                "SELECT id, at, result FROM runs WHERE document=? ORDER BY id DESC",
                (doc_id,),
            ).fetchall()

            active_run_id = selected_a_by_doc.get(doc_id)
            active_metrics = None
            active_doc_version = None

            for r in runs:
                res = json.loads(r["result"])
                ng = res.get("native_graph") or {}
                usage = _extract_usage(ng.get("requests"))
                obs = res.get("observations") or []
                resolved = sum(bool(o.get("source_ids")) for o in obs)
                cost = _estimate_cost(
                    res.get("provider"),
                    res.get("model"),
                    usage["prompt_tokens"],
                    usage["completion_tokens"],
                    usage.get("cached_tokens", 0),
                )
                is_active = r["id"] == active_run_id
                if is_active:
                    active_doc_version = res.get("document_version")
                inp = res.get("input") or {}
                row_entry = dict(
                    kind="A",
                    run_id=r["id"],
                    at=r["at"],
                    active=is_active,
                    document=doc_id,
                    scope_label=file_row["name"],
                    provider=res.get("provider") or "",
                    model=res.get("model") or "",
                    status=res.get("status") or "",
                    contract=inp.get("contract"),
                    serializer=inp.get("serializer"),
                    items_count=len(obs),
                    resolved_count=resolved,
                    token_origin="exact_api_usage",
                    tokens_per_item=round(usage["total_tokens"] / len(obs), 1)
                    if obs and usage["total_tokens"]
                    else None,
                    **usage,
                    **cost,
                )
                all_run_rows.append(row_entry)
                if is_active:
                    active_metrics = row_entry
                    st = stage_totals["A"]
                    st["runs"] += 1
                    st["calls"] += usage["calls"]
                    st["prompt_tokens"] += usage["prompt_tokens"]
                    st["completion_tokens"] += usage["completion_tokens"]
                    st["total_tokens"] += usage["total_tokens"]
                    st["billed_usd"] = round(st["billed_usd"] + (cost["billed_usd"] or 0.0), 6)
                    st["cloud_reference_usd"] = round(
                        st["cloud_reference_usd"] + (cost["cloud_reference_usd"] or 0.0), 6
                    )
                    st["items_yielded"] += len(obs)

            # Inspect versioned Vision enrichment receipts for this document
            active_vision = None
            if file_row.get("native"):
                try:
                    versions = workspace.versions(file_row)
                except (OSError, ValueError):
                    versions = []
                target_ver = active_doc_version or workspace.preferred_version(file_row, versions)
                for v_rec in reversed(versions):
                    if v_rec.get("kind") == "conversion":
                        continue
                    v_usage = _vision_receipt_usage(v_rec)
                    if not v_usage:
                        continue
                    is_v_active = bool(target_ver and v_rec.get("version") == target_ver) and active_vision is None
                    v_row = dict(
                        v_usage,
                        active=is_v_active,
                        document=doc_id,
                        scope_label=file_row["name"],
                    )
                    all_run_rows.append(v_row)
                    if is_v_active:
                        active_vision = v_row
                        vst = stage_totals["vision"]
                        vst["runs"] += 1
                        vst["calls"] += v_row["calls"]
                        vst["prompt_tokens"] += v_row["prompt_tokens"]
                        vst["completion_tokens"] += v_row["completion_tokens"]
                        vst["total_tokens"] += v_row["total_tokens"]
                        vst["billed_usd"] = round(
                            vst["billed_usd"] + (v_row["billed_usd"] or 0.0), 6
                        )
                        vst["cloud_reference_usd"] = round(
                            vst["cloud_reference_usd"] + (v_row["cloud_reference_usd"] or 0.0), 6
                        )
                        vst["items_yielded"] += v_row["items_count"]

            document_rows.append(
                dict(
                    document=doc_id,
                    name=file_row["name"],
                    status=file_row["status"],
                    conversion_seconds=round(conv_sec, 3) if conv_sec else None,
                    confidence=conf or None,
                    active_vision=active_vision,
                    active_a_run=active_metrics,
                    total_a_runs=len(runs),
                )
            )

        scope_set = set(doc_ids)
        comp_rows = db.execute(
            "SELECT id, at, proposal, metadata FROM ux_objects WHERE kind='comparison' ORDER BY id DESC"
        ).fetchall()
        active_b = (g.get("analysis", {}).get("selected_runs") or {}).get("B")
        active_c = (g.get("analysis", {}).get("selected_runs") or {}).get("C")
        if active_b is None and isinstance(result_runs, dict):
            active_b = result_runs.get("B")
        if active_c is None and isinstance(result_runs, dict):
            active_c = result_runs.get("C")

        stages_meta = g.get("analysis", {}).get("stages") or {}
        if active_b is None and stages_meta.get("B"):
            active_b = stages_meta["B"][0]["id"]
        if active_c is None and stages_meta.get("C"):
            active_c = stages_meta["C"][0]["id"]

        for cr in comp_rows:
            meta = json.loads(cr["metadata"] or "{}")
            r_scope = set(meta.get("scope") or [])
            if scope_set and r_scope != scope_set:
                continue
            stage = meta.get("stage")
            if stage not in ("B", "C"):
                continue
            ng = meta.get("native_graph") or {}
            usage = _extract_usage(ng.get("requests"))
            counts = meta.get("counts") or {}
            yielded = int(counts.get("proposed") or 0)
            unresolved_cnt = int(counts.get("unresolved") or 0)
            resolved_cnt = max(0, yielded - unresolved_cnt)
            cost = _estimate_cost(
                meta.get("provider"),
                meta.get("model"),
                usage["prompt_tokens"],
                usage["completion_tokens"],
                usage.get("cached_tokens", 0),
            )
            is_active = cr["id"] in (active_b, active_c)
            entry = dict(
                kind=stage,
                run_id=cr["id"],
                at=cr["at"],
                active=is_active,
                document=None,
                scope_label=f"{len(r_scope)} Dok. (Synthese {stage})",
                provider=meta.get("provider") or "",
                model=meta.get("model") or "",
                status=meta.get("status") or "",
                items_count=yielded,
                resolved_count=resolved_cnt,
                token_origin="exact_api_usage",
                tokens_per_item=round(usage["total_tokens"] / yielded, 1)
                if yielded and usage["total_tokens"]
                else None,
                **usage,
                **cost,
            )
            all_run_rows.append(entry)
            if is_active:
                st = stage_totals[stage]
                st["runs"] += 1
                st["calls"] += usage["calls"]
                st["prompt_tokens"] += usage["prompt_tokens"]
                st["completion_tokens"] += usage["completion_tokens"]
                st["total_tokens"] += usage["total_tokens"]
                st["billed_usd"] = round(st["billed_usd"] + (cost["billed_usd"] or 0.0), 6)
                st["cloud_reference_usd"] = round(
                    st["cloud_reference_usd"] + (cost["cloud_reference_usd"] or 0.0), 6
                )
                st["items_yielded"] += yielded

    text_stages = [stage_totals["A"], stage_totals["B"], stage_totals["C"]]
    active_prompt = sum(s["prompt_tokens"] for s in text_stages)
    active_completion = sum(s["completion_tokens"] for s in text_stages)
    active_total = sum(s["total_tokens"] for s in text_stages)
    vision_est_tokens = stage_totals["vision"]["total_tokens"]
    active_billed = round(sum(s["billed_usd"] for s in stage_totals.values()), 6)
    active_cloud_ref = round(
        sum(s["cloud_reference_usd"] for s in stage_totals.values()), 6
    )
    obs_count = stage_totals["A"]["items_yielded"]
    find_count = stage_totals["C"]["items_yielded"]

    all_run_rows.sort(
        key=lambda x: (str(x.get("at") or ""), str(x.get("run_id") or "")),
        reverse=True,
    )

    stages_list = (
        [stage_totals["vision"], *text_stages]
        if stage_totals["vision"]["runs"] > 0
        else text_stages
    )

    active_reasoning = sum(
        int(r.get("reasoning_tokens") or 0) for r in all_run_rows if r.get("active")
    )
    active_cached = sum(
        int(r.get("cached_tokens") or 0) for r in all_run_rows if r.get("active")
    )
    any_cloud_ref = any(
        r.get("cloud_reference_usd") is not None for r in all_run_rows if r.get("active")
    )

    return dict(
        scope=doc_ids,
        pricing_policy=dict(
            formula="(uncached_prompt_tokens * input_rate + cached_tokens * cache_rate + completion_tokens * output_rate) / 1_000_000",
            fau_and_local="0.00 EUR / USD real billed cost (academic gateway / local inference)",
            unlisted_models="Null (no fictional or guessed fallback prices)",
        ),
        summary=dict(
            documents=len(document_rows),
            prompt_tokens=active_prompt,
            completion_tokens=active_completion,
            total_tokens=active_total,
            reasoning_tokens=active_reasoning,
            cached_tokens=active_cached,
            vision_estimated_tokens=vision_est_tokens,
            combined_tokens_with_vision=active_total + vision_est_tokens,
            api_calls=sum(s["calls"] for s in stage_totals.values()),
            billed_usd=active_billed,
            cloud_reference_usd=active_cloud_ref if any_cloud_ref else None,
            pictures_described=stage_totals["vision"]["items_yielded"],
            observations=obs_count,
            relations=stage_totals["B"]["items_yielded"],
            findings=find_count,
            tokens_per_observation=round(active_total / obs_count, 1)
            if obs_count and active_total
            else None,
            tokens_per_finding=round(active_total / find_count, 1)
            if find_count and active_total
            else None,
        ),
        stages=stages_list,
        model_comparison=_build_model_comparison(all_run_rows),
        documents=document_rows,
        runs=all_run_rows,
    )


study_metrics = study_telemetry


def html_handout(
    workspace, numbers, *, basis=None, result_runs=None, lang="de", include_toolbar=True
):
    """Generate a clean, standalone, A4 print-ready HTML study handout with verified anchors & review audit."""
    g = research.graph(
        workspace, numbers, history=False, basis=basis, result_runs=result_runs
    )
    tel = study_telemetry(workspace, numbers, basis=basis, result_runs=result_runs)
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
    docs = g.get("documents", [])
    ts = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")

    valence_map = {
        "problem": ("Usability Problem" if en else "Nutzungsproblem", "#9f1239", "#ffe4e6"),
        "negative": ("Negative / Friction" if en else "Negativ / Hürde", "#9f1239", "#ffe4e6"),
        "strength": ("Strength / Positive" if en else "Stärke / Positiv", "#065f46", "#d1fae5"),
        "positive": ("Positive" if en else "Positiv", "#065f46", "#d1fae5"),
        "mixed": ("Ambivalent / Mixed" if en else "Ambivalent / Gemischt", "#92400e", "#fef3c7"),
    }
    review_map = {
        "HUMAN_CONFIRMED": ("Human Confirmed" if en else "Menschlich bestätigt", "#065f46"),
        "HUMAN_CORRECTED": ("Human Corrected" if en else "Menschlich korrigiert", "#0f766e"),
        "HUMAN_OPEN": ("Flagged for Review" if en else "Offen zur Prüfung", "#b45309"),
        "HUMAN_REJECTED": ("Rejected" if en else "Verworfen", "#9f1239"),
        "UNREVIEWED": ("Unreviewed Proposal" if en else "Ungeprüfter Vorschlag", "#52525b"),
    }

    def anchor_badge(obs):
        matches = (obs.get("source_check") or {}).get("matches") or []
        if obs.get("selected_source"):
            matches = [obs["selected_source"]]
        if not matches:
            return escape(obs.get("name") or "")
        a = matches[0]
        parts = [obs.get("name") or f"Doc #{obs['ref']['document']}", a.get("ref") or ""]
        if a.get("prov") and len(a["prov"]) == 1:
            parts.append(f"p.{a['prov'][0]['page_no']}" if en else f"S.{a['prov'][0]['page_no']}")
        if isinstance(a.get("row"), int):
            parts.append(f"R{a['row'] + 1}/C{(a.get('column') or 0) + 1}")
        if a.get("track"):
            tr = a["track"][0]
            if tr.get("voice"):
                parts.append(str(tr["voice"]))
            if tr.get("start_time") is not None:
                parts.append(f"{tr['start_time']:.1f}s")
        return escape(" · ".join(p for p in parts if p))

    cards_html = []
    for idx, f in enumerate(findings, 1):
        p = f.get("effective") or {}
        fnode = finding_nodes.get(f["id"], {})
        indep = fnode.get("independence") or {}
        ep_flags = [
            fl
            for fl in (fnode.get("epistemic_flags") or [])
            if fl != "technical_source_only"
        ]
        val_raw = str(p.get("valence") or "neutral").lower()
        val_lbl, val_fg, val_bg = valence_map.get(
            val_raw, ("Neutral / Context" if en else "Neutral / Kontext", "#3f3f46", "#f4f4f5")
        )
        rev_lbl, rev_fg = review_map.get(
            f.get("review", "UNREVIEWED"), (f.get("review") or "UNREVIEWED", "#52525b")
        )
        human_decs = [
            d
            for d in f.get("decisions") or []
            if d.get("origin") in ("human", "dual_review", "dual_review_adopted")
        ]

        quotes_html = []
        for role_key, role_tag in (
            ("supports", "Support" if en else "Stützender Beleg"),
            ("opposes", "Counter" if en else "Gegenbeleg"),
            ("qualifies", "Qualifier" if en else "Einschränkung"),
            ("improvement_evidence", "Participant Idea" if en else "Teilnehmer-Vorschlag"),
        ):
            for ref in p.get(role_key) or []:
                obs = obs_by_key.get(
                    (ref.get("document"), ref.get("run"), ref.get("observation"))
                )
                if not obs:
                    continue
                q_txt = " ".join(str(obs["effective"].get("quote") or "").split())
                stmt_txt = obs["effective"].get("statement") or ""
                speaker = (obs["effective"].get("context") or {}).get("actor_or_speaker")
                spk_tag = f" · <span>{escape(str(speaker))}</span>" if speaker else ""
                stmt_block = f'<div class="stmt">{escape(stmt_txt)}</div>' if stmt_txt else ""
                quotes_html.append(
                    f'<div class="quote-row">'
                    f'<div class="quote-meta"><span class="role-pill">{escape(role_tag)}</span> '
                    f'<strong>{anchor_badge(obs)}</strong>{spk_tag}</div>'
                    f"{stmt_block}"
                    f'<blockquote>„{escape(q_txt)}“</blockquote>'
                    f"</div>"
                )

        notes_html = ""
        dr = f.get("dual_review") or {}
        if dr.get("released"):
            res_state = dr.get("resolution_state")
            if res_state == "OPEN_DISAGREEMENT":
                dis_lbl = (
                    "Dual Review — Open Disagreement"
                    if en
                    else "Zweitprüfung — Offene Abweichung"
                )
                dis_msg = (
                    "Reviewer 1 and Reviewer 2 recorded differing judgments; divergence remains explicitly open."
                    if en
                    else "Prüfer 1 und Prüfer 2 haben abweichend geurteilt; die Abweichung bleibt sichtbar offen."
                )
                notes_html += (
                    f'<div class="review-note" style="background:#fffbeb;border-left-color:#d97706;color:#92400e">'
                    f"<strong>⚠ {dis_lbl}:</strong> {escape(dis_msg)}</div>"
                )
            elif res_state == "ADOPTED":
                ad_lbl = (
                    "Dual Review — Adopted Study State"
                    if en
                    else "Zweitprüfung — Übernommener Studienstand"
                )
                ad_src = escape(str((dr.get("resolution") or {}).get("adopted_from") or "-"))
                ad_rsn = escape(str((dr.get("resolution") or {}).get("reason") or ""))
                notes_html += (
                    f'<div class="review-note" style="background:#ecfdf5;border-left-color:#059669;color:#065f46">'
                    f"<strong>✓ {ad_lbl} ({ad_src}):</strong> {ad_rsn}</div>"
                )
            elif res_state == "PENDING_ADOPTION":
                pa_lbl = (
                    "Dual Review — Comparison Released (Adoption Pending)"
                    if en
                    else "Zweitprüfung — Vergleich freigegeben (Übernahme noch offen)"
                )
                notes_html += (
                    f'<div class="review-note">'
                    f"<strong>{pa_lbl}</strong></div>"
                )
        if human_decs:
            latest = human_decs[-1]
            fallback_note = "Reviewed without extra note" if en else "Geprüft ohne Zusatznotiz"
            note_lbl = "Researcher Review" if en else "Forscher-Prüfentscheidung"
            rev_who = ((latest.get("payload") or {}).get("reviewer") or {}).get("name")
            who_suffix = f" · {escape(str(rev_who))}" if rev_who else ""
            notes_html += (
                f'<div class="review-note"><strong>'
                f'{note_lbl} ({escape(latest.get("action", ""))}{who_suffix}):</strong> '
                f'{escape(latest.get("reason") or fallback_note)}</div>'
            )

        title_txt = p.get("title") or ("Finding #" + str(f["id"]))
        ftype_badge = (
            f'<span class="pill-outline">{escape(str(p["finding_type"]))}</span>'
            if p.get("finding_type")
            else ""
        )
        heur_badge = (
            f'<span class="pill-outline" style="color:#0f766e;border-color:#0f766e55">{escape(str(p["usability_heuristic"]))}</span>'
            if p.get("usability_heuristic")
            else ""
        )
        rationale_html = (
            f'<p class="rationale">{escape(p.get("rationale") or "")}</p>'
            if p.get("rationale")
            else ""
        )
        detail_rows = []
        if p.get("usability_heuristic"):
            detail_rows.append(
                f'<div><strong>{"Usability Heuristic / Standard" if en else "Usability-Heuristik / Norm"}:</strong> {escape(str(p["usability_heuristic"]))}</div>'
            )
        if p.get("observed_effect"):
            detail_rows.append(
                f'<div><strong>{"Observed Effect" if en else "Beobachtete Wirkung"}:</strong> {escape(str(p["observed_effect"]))}</div>'
            )
        if p.get("scope"):
            detail_rows.append(
                f'<div><strong>{"Scope" if en else "Geltungsbereich"}:</strong> {escape(str(p["scope"]))}</div>'
            )
        if p.get("uncertainty"):
            detail_rows.append(
                f'<div><strong>{"Uncertainty & Limits" if en else "Unsicherheit & Grenzen"}:</strong> {escape(str(p["uncertainty"]))}</div>'
            )
        if p.get("improvement_hypothesis"):
            imp_basis = p.get("improvement_basis") or ("analyst_inference" if en else " ungeprüft")
            detail_rows.append(
                f'<div class="imp-box"><strong>{"Improvement Hypothesis" if en else "Verbesserungshypothese"} ({escape(str(imp_basis))}):</strong> {escape(str(p["improvement_hypothesis"]))}</div>'
            )
        used_rels = [rel_by_id[rid] for rid in (p.get("relations") or []) if rid in rel_by_id]
        if used_rels:
            rel_txt = ", ".join(
                f"B #{r['id']} ({(r.get('effective') or {}).get('kind') or '-'})"
                for r in used_rels
            )
            detail_rows.append(
                f'<div><strong>{"Linked Relations" if en else "Verknüpfte B-Beziehungen"}:</strong> {escape(rel_txt)}</div>'
            )
        if ep_flags:
            detail_rows.append(
                f'<div><strong>{"Epistemic Flags" if en else "Epistemische Prüfhinweise"}:</strong> <code>{escape(", ".join(ep_flags))}</code></div>'
            )
        details_block = (
            f'<div class="detail-stack">{"".join(detail_rows)}</div>' if detail_rows else ""
        )

        indep_sup = indep.get("effective_independent_supports", len(p.get("supports") or []))
        indep_docs = indep.get("independent_documents", 1)
        indep_spk = indep.get("distinct_speakers", 0)
        indep_phrase = "independent anchors across" if en else "unabhängige Belege aus"
        docs_word = "documents" if en else "Dokument(en)"
        spk_html = (
            f' · <span><strong>{"Named Speakers" if en else "Genannte Sprecher"}:</strong> {indep_spk}</span>'
            if indep_spk
            else ""
        )

        cards_html.append(
            f'<article class="finding-card">'
            f'<div class="finding-head">'
            f'<div><span class="finding-num">#{idx} · C-{f["id"]}</span>'
            f"<h3>{escape(title_txt)}</h3></div>"
            f'<div class="badges">'
            f"{ftype_badge}{heur_badge}"
            f'<span class="pill" style="color:{val_fg};background:{val_bg}">{escape(val_lbl)}</span>'
            f'<span class="pill-outline" style="color:{rev_fg};border-color:{rev_fg}45">{escape(rev_lbl)}</span>'
            f"</div></div>"
            f"{rationale_html}"
            f'<div class="meta-strip">'
            f"<span><strong>Triangulation:</strong> {indep_sup} {indep_phrase} {indep_docs} {docs_word}</span>{spk_html}"
            f"</div>"
            f"{details_block}"
            f"{notes_html}"
            f'<div class="quotes-list">{"".join(quotes_html)}</div>'
            f"</article>"
        )

    rejected_html = ""
    if rejected_findings:
        rej_items = []
        for rf in rejected_findings:
            rp = rf.get("effective") or {}
            decs = [
                d
                for d in rf.get("decisions") or []
                if d.get("origin") in ("human", "dual_review", "dual_review_adopted")
            ]
            r_note = (
                decs[-1].get("reason")
                if decs and decs[-1].get("reason")
                else ("Rejected in researcher review" if en else "Im Forscher-Review verworfen")
            )
            rej_items.append(
                f"<tr><td>C-{rf['id']}</td><td>{escape(str(rp.get('title') or ''))}</td><td>{escape(str(r_note))}</td></tr>"
            )
        rejected_html = (
            f'<h2>{"Rejected Proposals (Audit Trail)" if en else "Verworfene Modellvorschläge (Prüfnachweis)"}</h2>'
            f'<table><thead><tr><th>ID</th><th>{"Proposal" if en else "Vorschlag"}</th>'
            f'<th>{"Researcher Rationale" if en else "Begründung"}</th></tr></thead>'
            f'<tbody>{"".join(rej_items)}</tbody></table>'
        )

    docs_rows = "".join(
        f"<tr><td>#{d['document']}</td><td><strong>{escape(d['name'])}</strong></td>"
        f"<td>A #{d.get('selected_run') or '—'}</td>"
        f"<td><code>{escape((d.get('document_version') or '—')[:12])}</code></td>"
        f"<td>{escape(str(d.get('coverage_status') or '—'))}</td></tr>"
        for d in docs
    )

    toolbar = (
        '<div class="no-print toolbar">'
        f'<span><strong>UX-mAInd · {"Study Handout" if en else "Studien-Handout"}</strong> — '
        f'{"Optimized for A4 / PDF Print" if en else "Optimiert für A4-Übergabe & PDF-Druck"}</span>'
        '<span class="print-hint">🖨 '
        + (
            "Press Ctrl+P (⌘+P) → Save as PDF"
            if en
            else "Strg + P (⌘ + P) → Als PDF speichern / drucken"
        )
        + "</span></div>"
        if include_toolbar
        else ""
    )

    t_sum = tel["summary"]
    if (t_sum.get("billed_usd") or 0) > 0:
        cost_txt = f"${t_sum['billed_usd']:.4f}"
    elif t_sum.get("cloud_reference_usd") is not None:
        cost_txt = f"$0.00 (Ref: ~${t_sum['cloud_reference_usd']:.4f})"
    else:
        cost_txt = "$0.00 (Lokal / FAU)"

    empty_msg = (
        "No active findings synthesized yet."
        if en
        else "Noch keine aktiven Findings im gewählten Laufstand vorhanden."
    )
    findings_section_html = (
        "".join(cards_html) if cards_html else f"<p><em>{empty_msg}</em></p>"
    )

    return f"""<!doctype html>
<html lang="{'en' if en else 'de'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>UX-mAInd · {'Study Handout' if en else 'Usability-Studien-Handout'}</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 0;
    font: 13.5px/1.55 "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #18181b; background: #f4f4f5;
  }}
  .toolbar {{
    position: sticky; top: 0; z-index: 10;
    display: flex; justify-content: space-between; align-items: center;
    padding: 10px 24px; background: #18181b; color: #fafafa; font-size: 13px;
  }}
  .toolbar .print-hint {{
    background: #0f766e; color: #fff; border-radius: 6px;
    padding: 6px 12px; font-size: 12px; font-weight: 600;
  }}
  .sheet {{
    max-width: 900px; margin: 24px auto; background: #ffffff;
    padding: 40px 48px; border-radius: 10px;
    box-shadow: 0 4px 24px rgba(24,24,27,.07);
  }}
  header.doc-head {{ border-bottom: 2px solid #18181b; padding-bottom: 16px; margin-bottom: 22px; }}
  .eyebrow {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: #0f766e; }}
  h1 {{ margin: 4px 0 6px; font-size: 24px; letter-spacing: -0.02em; }}
  .sub {{ color: #52525b; font-size: 13px; margin: 0; }}
  .kpi-grid {{
    display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 26px;
  }}
  .kpi {{
    border: 1px solid #e4e4e7; border-radius: 8px; padding: 10px 12px; background: #fafafa;
  }}
  .kpi .lbl {{ font-size: 11px; color: #71717a; text-transform: uppercase; letter-spacing: .04em; }}
  .kpi .val {{ font-size: 18px; font-weight: 700; margin-top: 2px; font-variant-numeric: tabular-nums; }}
  h2 {{ font-size: 14px; text-transform: uppercase; letter-spacing: .05em; color: #3f3f46; margin: 26px 0 12px; border-bottom: 1px solid #e4e4e7; padding-bottom: 6px; }}
  .finding-card {{
    border: 1px solid #d4d4d8; border-radius: 8px; padding: 16px 18px; margin-bottom: 16px;
    page-break-inside: avoid; break-inside: avoid;
  }}
  .finding-head {{ display: flex; flex-direction: column; align-items: flex-start; gap: 6px; margin-bottom: 6px; }}
  .finding-num {{ font-size: 11px; font-weight: 700; color: #71717a; text-transform: uppercase; }}
  .finding-head h3 {{ margin: 2px 0 2px; font-size: 16.5px; line-height: 1.35; color: #18181b; }}
  .badges {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  .pill, .pill-outline {{ font-size: 11px; font-weight: 600; padding: 3px 9px; border-radius: 999px; }}
  .pill-outline {{ border: 1px solid #d4d4d8; background: #fff; color: #3f3f46; }}
  .rationale {{ margin: 6px 0 10px; color: #27272a; }}
  .meta-strip {{ display: flex; flex-wrap: wrap; gap: 16px; font-size: 12px; color: #52525b; margin-bottom: 8px; }}
  .detail-stack {{ display: flex; flex-direction: column; gap: 5px; font-size: 12.5px; color: #3f3f46; margin-bottom: 10px; padding: 8px 10px; background: #fafafa; border: 1px solid #e4e4e7; border-radius: 6px; }}
  .imp-box {{ padding-top: 4px; border-top: 1px dashed #d4d4d8; color: #0f766e; }}
  .review-note {{
    background: #f0fdfa; border-left: 3px solid #0f766e; padding: 7px 10px;
    font-size: 12.5px; color: #115e59; margin-bottom: 10px; border-radius: 0 4px 4px 0;
  }}
  .quotes-list {{ display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }}
  .quote-row {{ background: #fafafa; border: 1px solid #e4e4e7; border-radius: 6px; padding: 8px 11px; }}
  .quote-meta {{ font-size: 11.5px; color: #52525b; margin-bottom: 3px; }}
  .role-pill {{ background: #e4e4e7; color: #18181b; font-weight: 600; padding: 1px 6px; border-radius: 4px; font-size: 10.5px; margin-right: 4px; }}
  .stmt {{ font-size: 12.5px; font-weight: 600; color: #18181b; margin-bottom: 2px; }}
  blockquote {{ margin: 0; color: #3f3f46; font-style: italic; font-size: 12.5px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 14px; }}
  th, td {{ text-align: left; padding: 7px 9px; border-bottom: 1px solid #e4e4e7; }}
  th {{ background: #fafafa; color: #52525b; font-weight: 600; }}
  code {{ font-family: Consolas, monospace; font-size: 11px; background: #f4f4f5; padding: 1px 4px; border-radius: 3px; }}
  footer {{ margin-top: 28px; padding-top: 12px; border-top: 1px solid #e4e4e7; font-size: 11px; color: #71717a; display: flex; justify-content: space-between; }}
  @media print {{
    body {{ background: #fff; font-size: 11.5px; }}
    .no-print {{ display: none !important; }}
    .sheet {{ max-width: none; margin: 0; padding: 0; box-shadow: none; border-radius: 0; }}
    @page {{ size: A4; margin: 14mm; }}
  }}
</style>
</head>
<body>
{toolbar}
<main class="sheet">
  <header class="doc-head">
    <div class="eyebrow">UX-mAInd · {'Source-Grounded Study Handout' if en else 'Quellengebundenes Studien-Handout'}</div>
    <h1>{'Usability Synthesis & Evidence Overview' if en else 'Usability-Befunde & Belegübersicht'}</h1>
    <p class="sub">{'Generated' if en else 'Stand'}: {escape(ts)} · {'Every finding remains anchored to verbatim original sources (technical anchor ≠ semantic truth without researcher review).' if en else 'Jeder Befund bleibt an wörtliche Originalstellen gebunden (technische Verankerung ersetzt keine fachliche Forscherprüfung).'}</p>
  </header>

  <section class="kpi-grid">
    <div class="kpi"><div class="lbl">{'Documents' if en else 'Dokumente'}</div><div class="val">{len(docs)}</div></div>
    <div class="kpi"><div class="lbl">{'Observations (A)' if en else 'Beobachtungen (A)'}</div><div class="val">{g['analysis']['observations']}</div></div>
    <div class="kpi"><div class="lbl">{'Relations (B)' if en else 'Relationen (B)'}</div><div class="val">{g['analysis']['relations']}</div></div>
    <div class="kpi"><div class="lbl">{'Active Findings (C)' if en else 'Aktive Befunde (C)'}</div><div class="val">{len(findings)}</div></div>
    <div class="kpi"><div class="lbl">{'Tokens / Cost' if en else 'Tokens / Kosten'}</div><div class="val" style="font-size:13.5px">{t_sum['total_tokens']:,} · {escape(cost_txt)}</div></div>
  </section>

  <h2>1. {'Synthesized UX Findings' if en else 'Verdichtete Usability-Befunde (Stufe C)'}</h2>
  {findings_section_html}
  {rejected_html}

  <h2>2. {'Study Corpus & Cryptographic Versions' if en else 'Untersuchte Studiendokumente & Versions-Provenienz'}</h2>
  <table>
    <thead><tr><th>ID</th><th>{'Document' if en else 'Dokument'}</th><th>{'Stage A Run' if en else 'A-Basis'}</th><th>Docling SHA-256</th><th>Status</th></tr></thead>
    <tbody>{docs_rows}</tbody>
  </table>

  <footer>
    <span>UX-mAInd · Open-Source Research Studio (Docling + Docling Graph)</span>
    <span>{len(findings)} {'Active Findings' if en else 'Aktive Befunde'} · {g['analysis']['observations']} {'Observations' if en else 'Beobachtungen'}</span>
  </footer>
</main>
</body>
</html>"""
