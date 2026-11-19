"""Optional independent Dual-Review ('Zweitprüfung') engine for UX-mAInd Studio.

Supports both local workflows with the exact same 4-stage state machine:
  1. 'same_machine' ('Am selben Rechner'): sequential blinded review via local profile switch.
  2. 'two_machines' ('Auf zwei Rechnern'): offline file-based package exchange (.zip / .json)
     with full Originalbelege & Docling Dual-View on Machine 2 and zero LLM re-execution.

Guarantees:
  - Strict blinding prior to explicit comparison release (both submissions required):
    each reviewer sees ONLY the frozen baseline and their own judgments across UI,
    decision history, knowledge graph, A4-HTML, Markdown, and JSON exports.
  - Immutable preservation of submitted initial judgments ('Ersturteile') alongside
    optional post-release revisions ('Überarbeitungen') and explicit study adoption.
  - Atomic, SHA-256-verified, idempotent package import (re-reads create zero duplicates;
    foreign-session or corrupted files fail atomically without partial state changes).
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import shutil
from uuid import UUID, uuid4
import zipfile

from . import auth
from .evidence import READABLE_SCHEMAS, SCHEMA_VERSION, file_digest

PACKAGE_SCHEMA = "ux_maind.dual_review.v1"
EDITABLE_FINDING_FIELDS = (
    "title",
    "valence",
    "finding_type",
    "usability_heuristic",
    "rationale",
    "observed_effect",
    "scope",
    "uncertainty",
    "improvement_hypothesis",
)
OBS_REF_LIST_FIELDS = ("supports", "opposes", "qualifies", "improvement_evidence")
VALID_ACTIONS = ("confirmed", "corrected", "rejected", "open")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_sha256(obj) -> str:
    packed = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256(packed).hexdigest()


def _clean_interpretation(raw: dict | None) -> dict:
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k in EDITABLE_FINDING_FIELDS:
        if k in raw:
            val = raw[k]
            if val is None:
                out[k] = None
            else:
                txt = str(val).strip()
                if txt != "" or k in ("usability_heuristic", "improvement_hypothesis"):
                    out[k] = txt or None
    return out


def _canonicalize_obs_ref(ref: dict, doc_rev: dict[int, str], run_rev: dict[int, str]) -> dict:
    doc_id = int(ref["document"])
    run_id = int(ref["run"])
    return {
        "doc_key": doc_rev[doc_id],
        "run_key": run_rev[run_id],
        "observation": str(ref["observation"]),
    }


def _localize_obs_ref(cref: dict, doc_fwd: dict[str, int], run_fwd: dict[str, int]) -> dict:
    if "document" in cref and "run" in cref:
        return {
            "document": int(cref["document"]),
            "run": int(cref["run"]),
            "observation": str(cref["observation"]),
        }
    return {
        "document": int(doc_fwd[cref["doc_key"]]),
        "run": int(run_fwd[cref["run_key"]]),
        "observation": str(cref["observation"]),
    }


def _canonicalize_finding_dict(
    fdict: dict,
    doc_rev: dict[int, str],
    run_rev: dict[int, str],
    rel_rev: dict[int, str],
) -> dict:
    out = dict(fdict)
    for field in OBS_REF_LIST_FIELDS:
        if isinstance(out.get(field), list):
            out[field] = [
                _canonicalize_obs_ref(r, doc_rev, run_rev)
                for r in out[field]
                if isinstance(r, dict)
                and int(r.get("document", -1)) in doc_rev
                and int(r.get("run", -1)) in run_rev
            ]
    if isinstance(out.get("relations"), list):
        out["relations"] = [
            rel_rev[int(rid)]
            for rid in out["relations"]
            if str(rid).isdigit() and int(rid) in rel_rev
        ]
    return out


def _localize_finding_dict(fdict: dict, id_map: dict) -> dict:
    doc_fwd = id_map.get("documents") or {}
    run_fwd = id_map.get("runs") or {}
    rel_fwd = id_map.get("relations") or {}
    out = dict(fdict)
    for field in OBS_REF_LIST_FIELDS:
        if isinstance(out.get(field), list):
            out[field] = [
                _localize_obs_ref(r, doc_fwd, run_fwd)
                for r in out[field]
                if isinstance(r, dict)
            ]
    if isinstance(out.get("relations"), list):
        localized_rels = []
        for rkey in out["relations"]:
            if isinstance(rkey, str) and rkey in rel_fwd:
                localized_rels.append(int(rel_fwd[rkey]))
            elif isinstance(rkey, int):
                localized_rels.append(rkey)
        out["relations"] = localized_rels
    return out


def _parse_session_row(row) -> dict:
    d = dict(row)
    return {
        "session_id": d["session_id"],
        "mode": d["mode"],
        "role_on_this_machine": d["role_on_this_machine"],
        "created_at": d["created_at"],
        "scope": json.loads(d["scope_json"] or "[]"),
        "reviewer_a": json.loads(d["reviewer_a_json"] or "{}"),
        "reviewer_b": json.loads(d["reviewer_b_json"] or "{}"),
        "baseline_sha256": d["baseline_sha256"],
        "baseline": json.loads(d["baseline_json"] or "{}"),
        "id_map": json.loads(d["id_map_json"] or "{}"),
        "submitted_a_at": d["submitted_a_at"],
        "submitted_b_at": d["submitted_b_at"],
        "released_at": d["released_at"],
        "resolutions": json.loads(d["resolutions_json"] or "{}"),
        "imported_receipts": json.loads(d["imported_receipts_json"] or "[]"),
    }


def _load_session(w, session_id: str) -> dict:
    sid = str(session_id or "").strip()
    if not sid:
        raise ValueError("Prüfungs-ID (session_id) fehlt")
    with w.db() as db:
        row = db.execute(
            "SELECT * FROM ux_review_sessions WHERE session_id=?", (sid,)
        ).fetchone()
    if row is None:
        raise ValueError("Zweitprüfungs-Sitzung in diesem Arbeitsbereich nicht gefunden")
    return _parse_session_row(row)


def _session_decisions_by_finding(w, session: dict) -> dict[str, dict[str, list[dict]]]:
    """Load all `origin='dual_review'` decisions for `session` grouped by canonical finding key & slot."""
    sid = session["session_id"]
    finding_map: dict[str, int] = session["id_map"].get("findings") or {}
    local_to_canon = {int(v): k for k, v in finding_map.items()}
    grouped: dict[str, dict[str, list[dict]]] = {
        fkey: {"reviewer_a": [], "reviewer_b": []} for fkey in finding_map
    }
    if not local_to_canon:
        return grouped
    placeholders = ",".join("?" for _ in local_to_canon)
    targets = [str(fid) for fid in local_to_canon]
    with w.db() as db:
        rows = db.execute(
            f"""SELECT * FROM ux_decisions
                WHERE target_type='finding' AND origin='dual_review' AND target IN ({placeholders})
                ORDER BY id""",
            targets,
        ).fetchall()
    for r in rows:
        payload = json.loads(r["payload"] or "{}")
        if payload.get("session_id") != sid:
            continue
        slot = payload.get("slot")
        fkey = payload.get("canonical_finding_key") or local_to_canon.get(int(r["target"]))
        if fkey in grouped and slot in ("reviewer_a", "reviewer_b"):
            grouped[fkey][slot].append(
                {
                    "id": r["id"],
                    "at": r["at"],
                    "action": r["action"],
                    "reason": r["reason"] or "",
                    "phase": payload.get("phase") or "initial",
                    "decision_uid": payload.get("decision_uid") or f"local-{r['id']}",
                    "reviewer": payload.get("reviewer") or {},
                    "interpretation": payload.get("interpretation") or {},
                }
            )
    return grouped


def _slot_history(entries: list[dict], baseline_eff: dict) -> dict:
    initials = [e for e in entries if e.get("phase") == "initial"]
    revisions = [e for e in entries if e.get("phase") == "revision"]
    initial = initials[-1] if initials else None
    current_eff = dict(baseline_eff)
    if initial and initial.get("interpretation"):
        current_eff.update(initial["interpretation"])
    initial_summary = (
        {
            **initial,
            "effective_preview": dict(current_eff),
        }
        if initial
        else None
    )
    rev_summaries = []
    for rev in revisions:
        rev_eff = dict(current_eff)
        if rev.get("interpretation"):
            rev_eff.update(rev["interpretation"])
        current_eff = rev_eff
        rev_summaries.append({**rev, "effective_preview": dict(rev_eff)})
    latest = rev_summaries[-1] if rev_summaries else initial_summary
    return {
        "initial": initial_summary,
        "revisions": rev_summaries,
        "latest": latest,
    }


def _compare_slot_views(slot_a: dict, slot_b: dict, baseline_eff: dict) -> dict:
    init_a, init_b = slot_a.get("initial"), slot_b.get("initial")
    lat_a, lat_b = slot_a.get("latest"), slot_b.get("latest")

    def _diff_fields(ea: dict | None, eb: dict | None) -> list[str]:
        if not ea or not eb:
            return ["unvollständig"]
        diffs = []
        if ea["action"] != eb["action"]:
            diffs.append("action")
        pa = ea.get("effective_preview") or baseline_eff
        pb = eb.get("effective_preview") or baseline_eff
        for field in EDITABLE_FINDING_FIELDS:
            va = (pa.get(field) or "").strip() if isinstance(pa.get(field), str) else pa.get(field)
            vb = (pb.get(field) or "").strip() if isinstance(pb.get(field), str) else pb.get(field)
            if (va or None) != (vb or None):
                diffs.append(field)
        return diffs

    init_diffs = _diff_fields(init_a, init_b)
    lat_diffs = _diff_fields(lat_a, lat_b)
    return {
        "initial_agreed": bool(init_a and init_b and len(init_diffs) == 0),
        "latest_agreed": bool(lat_a and lat_b and len(lat_diffs) == 0),
        "initial_differing_fields": init_diffs,
        "differing_fields": lat_diffs,
    }


def _viewer_slot_for(session: dict, viewer_id: str) -> str | None:
    if viewer_id == session["reviewer_a"].get("id"):
        return "reviewer_a"
    if viewer_id == session["reviewer_b"].get("id"):
        return "reviewer_b"
    return None


def session_status_code(session: dict) -> str:
    if session.get("released_at"):
        finding_keys = list((session["id_map"].get("findings") or {}).keys())
        res = session.get("resolutions") or {}
        if finding_keys and all(
            res.get(k, {}).get("state") in ("ADOPTED", "OPEN_DISAGREEMENT")
            for k in finding_keys
        ):
            return "COMPLETED"
        return "RELEASED"
    if session.get("submitted_a_at") and session.get("submitted_b_at"):
        return "READY_TO_RELEASE"
    return "IN_PROGRESS"


def format_session_for_viewer(w, session: dict, viewer_id: str | None = None) -> dict:
    """Build viewer-safe session summary respecting strict blinding before `released_at`."""
    if viewer_id is None:
        viewer_id = auth.list_profiles(w)["active"]["id"]
    viewer_slot = _viewer_slot_for(session, viewer_id)
    by_finding = _session_decisions_by_finding(w, session)
    finding_map = session["id_map"].get("findings") or {}
    baseline_findings = (session["baseline"].get("findings") or {})
    released = bool(session.get("released_at"))

    total_findings = len(finding_map)
    own_decided_count = 0
    if viewer_slot in ("reviewer_a", "reviewer_b"):
        own_decided_count = sum(
            1
            for fkey in finding_map
            if any(e.get("phase") == "initial" for e in by_finding.get(fkey, {}).get(viewer_slot, []))
        )

    summary_findings = []
    for fkey, local_fid in finding_map.items():
        bf = baseline_findings.get(fkey) or {}
        loc_base = _localize_finding_dict(
            bf.get("baseline_effective") or bf.get("proposal") or {},
            session["id_map"],
        )
        sh_a = _slot_history(by_finding.get(fkey, {}).get("reviewer_a", []), loc_base)
        sh_b = _slot_history(by_finding.get(fkey, {}).get("reviewer_b", []), loc_base)
        if not released:
            own_hist = (
                sh_a
                if viewer_slot == "reviewer_a"
                else sh_b
                if viewer_slot == "reviewer_b"
                else {"initial": None, "revisions": [], "latest": None}
            )
            summary_findings.append(
                {
                    "canonical_key": fkey,
                    "finding_id": int(local_fid),
                    "baseline_title": loc_base.get("title"),
                    "own_initial": own_hist["initial"],
                    "decided_by_viewer": own_hist["initial"] is not None,
                }
            )
        else:
            cmp_info = _compare_slot_views(sh_a, sh_b, loc_base)
            res = (session.get("resolutions") or {}).get(fkey)
            res_state = (
                res["state"]
                if isinstance(res, dict) and res.get("state")
                else ("OPEN_DISAGREEMENT" if not cmp_info["latest_agreed"] else "PENDING_ADOPTION")
            )
            summary_findings.append(
                {
                    "canonical_key": fkey,
                    "finding_id": int(local_fid),
                    "baseline_title": loc_base.get("title"),
                    "reviewer_a": sh_a,
                    "reviewer_b": sh_b,
                    "agreement": cmp_info,
                    "resolution_state": res_state,
                    "resolution": res,
                }
            )

    return {
        "session_id": session["session_id"],
        "mode": session["mode"],
        "role_on_this_machine": session["role_on_this_machine"],
        "created_at": session["created_at"],
        "status": session_status_code(session),
        "scope": session["scope"],
        "baseline_sha256": session["baseline_sha256"],
        "reviewer_a": session["reviewer_a"],
        "reviewer_b": session["reviewer_b"],
        "viewer_id": viewer_id,
        "viewer_slot": viewer_slot,
        "submitted_a_at": session["submitted_a_at"],
        "submitted_b_at": session["submitted_b_at"],
        "released_at": session["released_at"],
        "released": released,
        "total_findings": total_findings,
        "own_decided_count": own_decided_count,
        "findings": summary_findings,
    }


def list_sessions(w, scope_docs: list[int] | None = None, viewer_id: str | None = None) -> list[dict]:
    with w.db() as db:
        rows = db.execute(
            "SELECT * FROM ux_review_sessions ORDER BY created_at DESC, rowid DESC"
        ).fetchall()
    parsed = [_parse_session_row(r) for r in rows]
    if scope_docs is not None:
        want = set(map(int, scope_docs))
        parsed = [s for s in parsed if set(map(int, s["scope"])) <= want and bool(s["scope"])]
    return [format_session_for_viewer(w, s, viewer_id=viewer_id) for s in parsed]


def apply_dual_review_projection(w, object_rows: list[dict], *, scope: set[int]) -> list[dict]:
    """Enforce Dual-Review blinding & study adoption directly on `research.objects()` rows."""
    if not object_rows:
        return object_rows
    with w.db() as db:
        s_rows = db.execute(
            "SELECT * FROM ux_review_sessions ORDER BY created_at ASC, rowid ASC"
        ).fetchall()
    if not s_rows:
        return object_rows

    sessions = [
        s
        for s in (_parse_session_row(r) for r in s_rows)
        if set(map(int, s["scope"])) <= scope
    ]
    if not sessions:
        return object_rows

    # Map local finding_id -> latest governing session + canonical key
    governing: dict[int, tuple[dict, str]] = {}
    for s in sessions:
        for fkey, fid in (s["id_map"].get("findings") or {}).items():
            governing[int(fid)] = (s, fkey)

    if not governing:
        return object_rows

    viewer_id = auth.list_profiles(w)["active"]["id"]
    decisions_cache: dict[str, dict] = {}

    for r in object_rows:
        if r.get("kind") != "finding" or int(r["id"]) not in governing:
            continue
        session, fkey = governing[int(r["id"])]
        sid = session["session_id"]
        if sid not in decisions_cache:
            decisions_cache[sid] = _session_decisions_by_finding(w, session)
        by_slot = decisions_cache[sid].get(fkey) or {"reviewer_a": [], "reviewer_b": []}

        bf = (session["baseline"].get("findings") or {}).get(fkey) or {}
        loc_base = _localize_finding_dict(
            bf.get("baseline_effective") or bf.get("proposal") or r["proposal"],
            session["id_map"],
        )
        viewer_slot = _viewer_slot_for(session, viewer_id)
        released = bool(session.get("released_at"))

        pre_decisions = [
            d
            for d in r.get("decisions", [])
            if d.get("origin") not in ("dual_review", "dual_review_adopted")
            and d["at"] <= session["created_at"]
        ]

        if not released:
            # STRICT BLINDING: expose ONLY frozen baseline + active viewer's own dual_review decisions!
            own_raw = [
                d
                for d in r.get("decisions", [])
                if d.get("origin") == "dual_review"
                and (d.get("payload") or {}).get("session_id") == sid
                and viewer_slot is not None
                and (d.get("payload") or {}).get("slot") == viewer_slot
            ]
            r["decisions"] = [*pre_decisions, *own_raw]
            own_hist = (
                _slot_history(by_slot.get(viewer_slot, []), loc_base)
                if viewer_slot in ("reviewer_a", "reviewer_b")
                else {"initial": None, "revisions": [], "latest": None}
            )
            eff = dict(loc_base)
            if own_hist["latest"] and own_hist["latest"].get("interpretation"):
                eff.update(own_hist["latest"]["interpretation"])
            r["effective"] = eff
            r["review"] = (
                "HUMAN_" + own_hist["latest"]["action"].upper()
                if own_hist["latest"]
                else "UNREVIEWED"
            )
            own_submitted = (
                bool(session["submitted_a_at"])
                if viewer_slot == "reviewer_a"
                else bool(session["submitted_b_at"])
                if viewer_slot == "reviewer_b"
                else False
            )
            r["dual_review"] = {
                "session_id": sid,
                "mode": session["mode"],
                "role_on_this_machine": session["role_on_this_machine"],
                "status": session_status_code(session),
                "released": False,
                "viewer_slot": viewer_slot,
                "own_submitted": own_submitted,
                "own_initial": own_hist["initial"],
            }
        else:
            # RELEASED: side-by-side comparison + post-release revisions + explicit study adoption
            sh_a = _slot_history(by_slot.get("reviewer_a", []), loc_base)
            sh_b = _slot_history(by_slot.get("reviewer_b", []), loc_base)
            cmp_info = _compare_slot_views(sh_a, sh_b, loc_base)
            res = (session.get("resolutions") or {}).get(fkey)

            session_decs = [
                d
                for d in r.get("decisions", [])
                if d.get("origin") in ("dual_review", "dual_review_adopted")
                and (d.get("payload") or {}).get("session_id") == sid
            ]
            r["decisions"] = [*pre_decisions, *session_decs]

            if isinstance(res, dict) and res.get("state") == "ADOPTED":
                adopted_eff = _localize_finding_dict(
                    res.get("effective") or loc_base, session["id_map"]
                )
                r["effective"] = adopted_eff
                r["review"] = "HUMAN_" + str(res.get("action") or "confirmed").upper()
                res_state = "ADOPTED"
            else:
                r["effective"] = dict(loc_base)
                r["review"] = "UNREVIEWED"
                res_state = (
                    "OPEN_DISAGREEMENT"
                    if not cmp_info["latest_agreed"]
                    or (isinstance(res, dict) and res.get("state") == "OPEN_DISAGREEMENT")
                    else "PENDING_ADOPTION"
                )

            r["dual_review"] = {
                "session_id": sid,
                "mode": session["mode"],
                "role_on_this_machine": session["role_on_this_machine"],
                "status": session_status_code(session),
                "released": True,
                "released_at": session["released_at"],
                "viewer_slot": viewer_slot,
                "baseline_sha256": session["baseline_sha256"],
                "baseline_effective": loc_base,
                "reviewer_a_profile": session["reviewer_a"],
                "reviewer_b_profile": session["reviewer_b"],
                "submitted_a_at": session["submitted_a_at"],
                "submitted_b_at": session["submitted_b_at"],
                "reviewer_a": sh_a,
                "reviewer_b": sh_b,
                "agreement": cmp_info,
                "resolution_state": res_state,
                "resolution": res,
            }

    return object_rows


def guard_direct_finding_decision(w, finding_id: int) -> dict | None:
    """Detect if `finding_id` is governed by an active unreleased Dual-Review session."""
    with w.db() as db:
        rows = db.execute(
            "SELECT * FROM ux_review_sessions ORDER BY created_at DESC, rowid DESC"
        ).fetchall()
    for raw in rows:
        s = _parse_session_row(raw)
        for fkey, local_fid in (s["id_map"].get("findings") or {}).items():
            if int(local_fid) == int(finding_id) and not s.get("released_at"):
                return s
    return None


def create_session(w, body: dict) -> dict:
    """Step 1: Freeze baseline for selected Findings and initialize 1-machine or 2-machine Dual Review."""
    if not isinstance(body, dict):
        raise ValueError("Startparameter als JSON-Objekt angeben")
    mode = str(body.get("mode") or "").strip()
    if mode not in ("same_machine", "two_machines"):
        raise ValueError("Modus wählen: 'same_machine' (Am selben Rechner) oder 'two_machines' (Auf zwei Rechnern)")

    scope_docs = sorted({int(d) for d in (body.get("documents") or [])})
    if not scope_docs:
        raise ValueError("Mindestens ein Studiendokument im Umfang auswählen")

    raw_finding_ids = [int(fid) for fid in dict.fromkeys(body.get("finding_ids") or [])]
    if not raw_finding_ids:
        raise ValueError("Mindestens ein Finding für die Zweitprüfung auswählen")

    rev_a_in = body.get("reviewer_a") or {}
    rev_b_in = body.get("reviewer_b") or {}
    if not isinstance(rev_a_in, dict) or not isinstance(rev_b_in, dict):
        raise ValueError("Prüfer 1 und Prüfer 2 angeben")

    prof_a = auth.ensure_profile(
        w,
        display_name=str(rev_a_in.get("display_name") or "").strip(),
        short_code=str(rev_a_in.get("short_code") or "").strip(),
        role=str(rev_a_in.get("role") or "Erstprüfer").strip(),
        profile_id=str(rev_a_in.get("id") or "").strip(),
        activate=True,
    )
    prof_b = auth.ensure_profile(
        w,
        display_name=str(rev_b_in.get("display_name") or "").strip(),
        short_code=str(rev_b_in.get("short_code") or "").strip(),
        role=str(rev_b_in.get("role") or "Zweitprüfer").strip(),
        profile_id=str(rev_b_in.get("id") or "").strip(),
        activate=False,
    )
    if prof_a["id"] == prof_b["id"]:
        raise ValueError(
            "Prüfer 1 und Prüfer 2 müssen zwei verschiedene lokale Profile sein (eigener Name oder Kürzel)."
        )

    # Ensure no active unreleased session already locks these findings
    for fid in raw_finding_ids:
        existing_unreleased = guard_direct_finding_decision(w, fid)
        if existing_unreleased is not None:
            raise ValueError(
                f"Finding C #{fid} befindet sich bereits in einer laufenden unveröffentlichten Zweitprüfung."
            )

    raw_basis = body.get("basis") or {}
    basis_by_doc: dict[int, int] = {}
    for doc_id in scope_docs:
        chosen = raw_basis.get(str(doc_id)) or raw_basis.get(doc_id)
        runs = [
            r
            for r in w.results(doc_id, messages=False)
            if not r["historical"] and (r["result"].get("observations") or [])
        ]
        if chosen is not None and any(r["id"] == int(chosen) for r in runs):
            basis_by_doc[doc_id] = int(chosen)
        elif runs:
            basis_by_doc[doc_id] = int(runs[0]["id"])
        else:
            raise ValueError(f"Für Dokument #{doc_id} liegt kein zitierbarer Stufe-A-Lauf vor")

    doc_rev = {doc_id: f"D{idx}" for idx, doc_id in enumerate(scope_docs, start=1)}
    doc_fwd = {v: k for k, v in doc_rev.items()}
    run_rev = {basis_by_doc[doc_id]: f"R{idx}" for idx, doc_id in enumerate(scope_docs, start=1)}
    run_fwd = {v: k for k, v in run_rev.items()}

    # Snapshot documents & Stage A runs
    portable_docs = {}
    portable_runs = {}
    for doc_id in scope_docs:
        dkey = doc_rev[doc_id]
        rkey = run_rev[basis_by_doc[doc_id]]
        f_row = w.file(doc_id)
        stored_path = w.artifact(f_row, "stored")
        native_path = w.artifact(f_row, "native")
        all_runs = w.results(doc_id, messages=False)
        chosen_run = next(r for r in all_runs if r["id"] == basis_by_doc[doc_id])
        doc_ver = chosen_run["result"].get("document_version") or file_digest(native_path)
        portable_docs[dkey] = {
            "name": f_row["name"],
            "corpus_role": f_row.get("corpus_role") or "evidence",
            "status": f_row["status"],
            "diagnostics": json.loads(f_row.get("diagnostics") or "{}"),
            "source_sha256": file_digest(stored_path),
            "base_native_sha256": file_digest(native_path),
            "active_document_version": doc_ver,
        }
        portable_runs[rkey] = {
            "doc_key": dkey,
            "at": chosen_run["at"],
            "result": chosen_run["result"],
        }

    # Pre-session Stage A observation anchor healing decisions
    pre_obs_decisions = []
    with w.db() as db:
        obs_dec_rows = db.execute(
            "SELECT * FROM ux_decisions WHERE target_type='observation' ORDER BY id"
        ).fetchall()
    for od in obs_dec_rows:
        try:
            t_ref = json.loads(od["target"])
        except ValueError:
            continue
        d_id = int(t_ref.get("document", -1))
        r_id = int(t_ref.get("run", -1))
        if d_id in doc_rev and r_id in run_rev:
            pre_obs_decisions.append(
                {
                    "target": _canonicalize_obs_ref(t_ref, doc_rev, run_rev),
                    "at": od["at"],
                    "origin": od["origin"],
                    "action": od["action"],
                    "reason": od["reason"] or "",
                    "payload": json.loads(od["payload"] or "{}"),
                }
            )

    # Load Findings & linked Stage B/C comparison objects
    from . import research as research_mod

    all_objs = research_mod.objects(w, scope_docs)
    objs_by_id = {int(o["id"]): o for o in all_objs}

    selected_finding_objs = []
    for fid in raw_finding_ids:
        fobj = objs_by_id.get(fid)
        if not fobj or fobj.get("kind") != "finding":
            raise ValueError(f"Finding #{fid} im gewählten Studienumfang nicht gefunden")
        selected_finding_objs.append(fobj)

    result_runs_in = body.get("result_runs") or {}
    c_comp_id = result_runs_in.get("C") or (
        selected_finding_objs[0]["metadata"].get("comparison") if selected_finding_objs else None
    )
    b_comp_id = result_runs_in.get("B")
    c_comp_obj = objs_by_id.get(int(c_comp_id)) if c_comp_id is not None else None
    if b_comp_id is None and c_comp_obj:
        b_comp_id = c_comp_obj["metadata"].get("b_run")
    b_comp_obj = objs_by_id.get(int(b_comp_id)) if b_comp_id is not None else None

    rel_objs = [
        o
        for o in all_objs
        if o["kind"] == "relation"
        and (b_comp_id is None or o["metadata"].get("comparison") == int(b_comp_id))
    ]
    rel_rev = {int(o["id"]): f"REL{idx}" for idx, o in enumerate(rel_objs, start=1)}
    rel_fwd = {v: k for k, v in rel_rev.items()}

    portable_relations = {}
    for o in rel_objs:
        rk = rel_rev[int(o["id"])]
        prop = dict(o["proposal"])
        if isinstance(prop.get("source"), dict) and int(prop["source"].get("document", -1)) in doc_rev:
            prop["source"] = _canonicalize_obs_ref(prop["source"], doc_rev, run_rev)
        if isinstance(prop.get("target"), dict) and int(prop["target"].get("document", -1)) in doc_rev:
            prop["target"] = _canonicalize_obs_ref(prop["target"], doc_rev, run_rev)
        portable_relations[rk] = {
            "at": o["at"],
            "proposal": prop,
            "metadata": {
                k: v
                for k, v in o["metadata"].items()
                if k not in ("scope", "comparison", "observations", "basis_runs", "basis_by_doc")
            },
        }

    portable_findings = {}
    finding_fwd = {}
    for idx, fobj in enumerate(selected_finding_objs, start=1):
        fkey = f"F{idx}"
        finding_fwd[fkey] = int(fobj["id"])
        canon_prop = _canonicalize_finding_dict(fobj["proposal"], doc_rev, run_rev, rel_rev)
        canon_eff = _canonicalize_finding_dict(fobj["effective"], doc_rev, run_rev, rel_rev)
        portable_findings[fkey] = {
            "canonical_key": fkey,
            "at": fobj["at"],
            "proposal": canon_prop,
            "baseline_effective": canon_eff,
            "metadata": {
                k: v
                for k, v in fobj["metadata"].items()
                if k not in ("scope", "comparison", "observations", "basis_runs", "basis_by_doc")
            },
        }

    def _canon_comp_meta(comp_obj: dict | None, stage_label: str) -> dict | None:
        if not comp_obj:
            return None
        meta = comp_obj["metadata"]
        canon_obs = [
            _canonicalize_obs_ref(o, doc_rev, run_rev)
            for o in (meta.get("observations") or [])
            if isinstance(o, dict)
            and int(o.get("document", -1)) in doc_rev
            and int(o.get("run", -1)) in run_rev
        ]
        return {
            "at": comp_obj["at"],
            "stage": meta.get("stage") or stage_label,
            "status": meta.get("status") or "UNREVIEWED",
            "model": meta.get("model"),
            "provider": meta.get("provider"),
            "counts": meta.get("counts"),
            "observations": canon_obs,
        }

    portable_baseline = {
        "schema_version": SCHEMA_VERSION,
        "documents": portable_docs,
        "runs": portable_runs,
        "pre_observation_decisions": pre_obs_decisions,
        "b_comparison": _canon_comp_meta(b_comp_obj, "B"),
        "c_comparison": _canon_comp_meta(c_comp_obj, "C"),
        "relations": portable_relations,
        "findings": portable_findings,
    }
    baseline_sha256 = _canonical_sha256(portable_baseline)

    id_map = {
        "documents": doc_fwd,
        "runs": run_fwd,
        "relations": rel_fwd,
        "comparisons": {
            "B": int(b_comp_id) if b_comp_id is not None else None,
            "C": int(c_comp_id) if c_comp_id is not None else None,
        },
        "findings": finding_fwd,
    }

    session_id = uuid4().hex[:16]
    created_at = _now_iso()
    with w.db() as db:
        db.execute(
            """INSERT INTO ux_review_sessions(
                   session_id, mode, role_on_this_machine, created_at,
                   scope_json, reviewer_a_json, reviewer_b_json,
                   baseline_sha256, baseline_json, id_map_json,
                   resolutions_json, imported_receipts_json
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                session_id,
                mode,
                "origin",
                created_at,
                json.dumps(scope_docs),
                json.dumps(prof_a, ensure_ascii=False),
                json.dumps(prof_b, ensure_ascii=False),
                baseline_sha256,
                json.dumps(portable_baseline, ensure_ascii=False),
                json.dumps(id_map),
                "{}",
                "[]",
            ),
        )
    session = _load_session(w, session_id)
    return format_session_for_viewer(w, session, viewer_id=prof_a["id"])


def save_judgment(w, body: dict) -> dict:
    """Step 2 & Step 3: Save a reviewer's initial judgment (pre-release) or revision (post-release)."""
    if not isinstance(body, dict):
        raise ValueError("Bewertung als JSON-Objekt angeben")
    session = _load_session(w, body.get("session_id"))
    action = str(body.get("action") or "").strip()
    if action not in VALID_ACTIONS:
        raise ValueError("Ungültige Bewertungsaktion (erlaubt: confirmed, corrected, rejected, open)")
    reason = str(body.get("reason") or "").strip()
    raw_interp = _clean_interpretation(body.get("interpretation"))

    active_prof = auth.list_profiles(w)["active"]
    slot = _viewer_slot_for(session, active_prof["id"])
    if slot is None:
        raise ValueError(
            "Aktives Prüfer-Profil gehört nicht zu dieser Zweitprüfung. Bitte zu Prüfer 1 oder Prüfer 2 wechseln."
        )
    if session["mode"] == "two_machines":
        if session["role_on_this_machine"] == "origin" and slot != "reviewer_a":
            raise ValueError(
                "Im Modus ‚Auf zwei Rechnern‘ bewertet auf Rechner 1 ausschließlich Prüfer 1; "
                "die Bewertung von Prüfer 2 wird als Datei importiert."
            )
        if session["role_on_this_machine"] == "peer" and slot != "reviewer_b":
            raise ValueError(
                "Auf dem Zweitrechner (Empfänger des Prüfpakets) bewertet ausschließlich Prüfer 2."
            )

    finding_id = int(body.get("finding_id") or 0)
    finding_map: dict[str, int] = session["id_map"].get("findings") or {}
    fkey = next((k for k, v in finding_map.items() if int(v) == finding_id), None)
    if fkey is None:
        raise ValueError("Dieses Finding gehört nicht zum gewählten Prüfauftrag")

    released = bool(session.get("released_at"))
    if not released:
        already_submitted = (
            bool(session["submitted_a_at"])
            if slot == "reviewer_a"
            else bool(session["submitted_b_at"])
        )
        if already_submitted:
            raise ValueError(
                "Das Ersturteil wurde bereits verbindlich abgegeben und bleibt bis zur Freigabe des Vergleichs unveränderbar."
            )
        phase = "initial"
    else:
        phase = "revision"

    stamp = auth.active_reviewer_stamp(w)
    decision_uid = uuid4().hex
    at = _now_iso()
    payload = {
        "session_id": session["session_id"],
        "canonical_finding_key": fkey,
        "slot": slot,
        "phase": phase,
        "decision_uid": decision_uid,
        "reviewer": stamp,
    }
    if raw_interp:
        payload["interpretation"] = raw_interp

    with w.db() as db:
        db.execute(
            """INSERT INTO ux_decisions(target_type,target,at,origin,action,reason,payload)
               VALUES(?,?,?,?,?,?,?)""",
            (
                "finding",
                str(finding_id),
                at,
                "dual_review",
                action,
                reason,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
    updated = _load_session(w, session["session_id"])
    return format_session_for_viewer(w, updated, viewer_id=active_prof["id"])


def submit_slot(w, body: dict) -> dict:
    """Freeze the active reviewer's initial judgments ('Ersturteil verbindlich abgeben')."""
    if not isinstance(body, dict):
        raise ValueError("Abgabe-Anfrage als JSON-Objekt angeben")
    session = _load_session(w, body.get("session_id"))
    active_prof = auth.list_profiles(w)["active"]
    slot = _viewer_slot_for(session, active_prof["id"])
    if slot is None:
        raise ValueError("Bitte zuerst das Profil von Prüfer 1 oder Prüfer 2 aktivieren")
    if session["mode"] == "two_machines":
        if session["role_on_this_machine"] == "origin" and slot != "reviewer_a":
            raise ValueError("Auf Rechner 1 gibt Prüfer 1 ab; Prüfer 2 wird als Datei importiert.")
        if session["role_on_this_machine"] == "peer" and slot != "reviewer_b":
            raise ValueError("Auf Rechner 2 gibt Prüfer 2 ab.")

    col = "submitted_a_at" if slot == "reviewer_a" else "submitted_b_at"
    if session.get(col):
        return format_session_for_viewer(w, session, viewer_id=active_prof["id"])

    by_finding = _session_decisions_by_finding(w, session)
    finding_map = session["id_map"].get("findings") or {}
    missing = [
        int(fid)
        for fkey, fid in finding_map.items()
        if not any(e.get("phase") == "initial" for e in by_finding.get(fkey, {}).get(slot, []))
    ]
    if missing:
        joined = ", ".join(f"C #{m}" for m in missing)
        raise ValueError(
            f"Bitte vor der verbindlichen Abgabe alle ausgewählten Findings bewerten (noch offen: {joined})."
        )

    now_ts = _now_iso()
    with w.db() as db:
        db.execute(
            f"UPDATE ux_review_sessions SET {col}=? WHERE session_id=?",
            (now_ts, session["session_id"]),
        )
    updated = _load_session(w, session["session_id"])
    return format_session_for_viewer(w, updated, viewer_id=active_prof["id"])


def release_comparison(w, body: dict) -> dict:
    """Step 3: Explicitly unlock side-by-side comparison ONLY once BOTH initial submissions exist."""
    if not isinstance(body, dict):
        raise ValueError("Freigabe-Anfrage als JSON-Objekt angeben")
    session = _load_session(w, body.get("session_id"))
    if not session.get("submitted_a_at") or not session.get("submitted_b_at"):
        missing_who = []
        if not session.get("submitted_a_at"):
            missing_who.append(f"Prüfer 1 ({session['reviewer_a']['display_name']})")
        if not session.get("submitted_b_at"):
            missing_who.append(f"Prüfer 2 ({session['reviewer_b']['display_name']})")
        raise ValueError(
            "Vergleich kann erst freigegeben werden, nachdem beide Prüfer ihr Ersturteil abgegeben haben "
            f"(es fehlt: {', '.join(missing_who)})."
        )
    if not session.get("released_at"):
        with w.db() as db:
            db.execute(
                "UPDATE ux_review_sessions SET released_at=? WHERE session_id=?",
                (_now_iso(), session["session_id"]),
            )
    updated = _load_session(w, session["session_id"])
    return format_session_for_viewer(w, updated)


def adopt_resolution(w, body: dict) -> dict:
    """Step 4: Explicitly choose which version enters the canonical study state (or keep OPEN_DISAGREEMENT)."""
    if not isinstance(body, dict):
        raise ValueError("Übernahme-Anfrage als JSON-Objekt angeben")
    session = _load_session(w, body.get("session_id"))
    if not session.get("released_at"):
        raise ValueError("Ergebnisse können erst nach Freigabe des Vergleichs übernommen werden")

    finding_id = int(body.get("finding_id") or 0)
    finding_map: dict[str, int] = session["id_map"].get("findings") or {}
    fkey = next((k for k, v in finding_map.items() if int(v) == finding_id), None)
    if fkey is None:
        raise ValueError("Finding gehört nicht zu dieser Zweitprüfung")

    adopt_from = str(body.get("adopt_from") or "").strip()
    if adopt_from not in ("reviewer_a", "reviewer_b", "baseline", "consensus", "open_disagreement"):
        raise ValueError(
            "Gültige Quelle wählen: 'reviewer_a', 'reviewer_b', 'baseline', 'consensus' oder 'open_disagreement'"
        )

    bf = (session["baseline"].get("findings") or {}).get(fkey) or {}
    canon_base = dict(bf.get("baseline_effective") or bf.get("proposal") or {})
    loc_base = _localize_finding_dict(canon_base, session["id_map"])
    by_finding = _session_decisions_by_finding(w, session)
    sh_a = _slot_history(by_finding.get(fkey, {}).get("reviewer_a", []), loc_base)
    sh_b = _slot_history(by_finding.get(fkey, {}).get("reviewer_b", []), loc_base)

    stamp = auth.active_reviewer_stamp(w)
    note = str(body.get("reason") or "").strip()
    now_ts = _now_iso()
    resolutions = dict(session.get("resolutions") or {})

    if adopt_from == "open_disagreement":
        resolutions[fkey] = {
            "state": "OPEN_DISAGREEMENT",
            "adopted_from": "open_disagreement",
            "action": "open",
            "reason": note or "Abweichung bewusst offen gelassen",
            "decided_by": stamp,
            "at": now_ts,
        }
        with w.db() as db:
            db.execute(
                "UPDATE ux_review_sessions SET resolutions_json=? WHERE session_id=?",
                (json.dumps(resolutions, ensure_ascii=False), session["session_id"]),
            )
            db.execute(
                """INSERT INTO ux_decisions(target_type,target,at,origin,action,reason,payload)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    "finding",
                    str(finding_id),
                    now_ts,
                    "dual_review_adopted",
                    "open",
                    note or "Als offene Abweichung markiert",
                    json.dumps(
                        {
                            "session_id": session["session_id"],
                            "canonical_finding_key": fkey,
                            "adopted_from": "open_disagreement",
                            "reviewer": stamp,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
        return format_session_for_viewer(w, _load_session(w, session["session_id"]))

    if adopt_from == "reviewer_a":
        chosen = sh_a.get("latest")
        if not chosen:
            raise ValueError("Keine Bewertung von Prüfer 1 vorhanden")
        chosen_action = chosen["action"] if chosen["action"] != "open" else "confirmed"
        chosen_interp = _clean_interpretation(chosen.get("effective_preview"))
        default_note = f"Fassung von Prüfer 1 ({session['reviewer_a']['display_name']}) übernommen"
    elif adopt_from == "reviewer_b":
        chosen = sh_b.get("latest")
        if not chosen:
            raise ValueError("Keine Bewertung von Prüfer 2 vorhanden")
        chosen_action = chosen["action"] if chosen["action"] != "open" else "confirmed"
        chosen_interp = _clean_interpretation(chosen.get("effective_preview"))
        default_note = f"Fassung von Prüfer 2 ({session['reviewer_b']['display_name']}) übernommen"
    elif adopt_from == "baseline":
        chosen_action = str(body.get("action") or "confirmed").strip()
        if chosen_action not in ("confirmed", "rejected"):
            chosen_action = "confirmed"
        chosen_interp = _clean_interpretation(loc_base)
        default_note = "Gemeinsamen Ausgangsvorschlag übernommen"
    else:  # consensus
        chosen_action = str(body.get("action") or "corrected").strip()
        if chosen_action not in ("confirmed", "corrected", "rejected"):
            raise ValueError("Ungültige Aktion für Konsensfassung")
        base_for_cons = dict(loc_base)
        base_for_cons.update(_clean_interpretation(body.get("interpretation")))
        chosen_interp = _clean_interpretation(base_for_cons)
        default_note = "Gemeinsame Konsensfassung nach Vergleich übernommen"

    canon_adopted = dict(canon_base)
    canon_adopted.update(chosen_interp)
    final_reason = note or default_note

    resolutions[fkey] = {
        "state": "ADOPTED",
        "adopted_from": adopt_from,
        "action": chosen_action,
        "effective": canon_adopted,
        "reason": final_reason,
        "decided_by": stamp,
        "at": now_ts,
    }
    with w.db() as db:
        db.execute(
            "UPDATE ux_review_sessions SET resolutions_json=? WHERE session_id=?",
            (json.dumps(resolutions, ensure_ascii=False), session["session_id"]),
        )
        db.execute(
            """INSERT INTO ux_decisions(target_type,target,at,origin,action,reason,payload)
               VALUES(?,?,?,?,?,?,?)""",
            (
                "finding",
                str(finding_id),
                now_ts,
                "dual_review_adopted",
                chosen_action,
                final_reason,
                json.dumps(
                    {
                        "session_id": session["session_id"],
                        "canonical_finding_key": fkey,
                        "adopted_from": adopt_from,
                        "interpretation": chosen_interp,
                        "reviewer": stamp,
                    },
                    ensure_ascii=False,
                ),
            ),
        )
    return format_session_for_viewer(w, _load_session(w, session["session_id"]))


# ---------------------------------------------------------------------------
# Two-Machine Offline File Exchange (.zip Assignment + .json Submissions/Comparison)
# ---------------------------------------------------------------------------


def export_assignment_zip(w, session_id: str) -> tuple[str, bytes]:
    """Export self-contained Prüfpaket (.zip) for Machine 2 with ZERO leak of Reviewer 1's judgments."""
    session = _load_session(w, session_id)
    doc_fwd = session["id_map"].get("documents") or {}
    baseline_docs = session["baseline"].get("documents") or {}

    buf = io.BytesIO()
    file_entries = []

    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        display_root = w.root / "display"
        for dkey, local_doc_id in sorted(doc_fwd.items()):
            f_row = w.file(int(local_doc_id))
            bdoc = baseline_docs[dkey]
            orig_path = w.artifact(f_row, "stored")
            base_native_path = w.artifact(f_row, "native")

            def _add_file(src_path: Path, arcname: str):
                data = src_path.read_bytes()
                zf.writestr(arcname, data)
                file_entries.append(
                    {
                        "arcname": arcname,
                        "sha256": sha256(data).hexdigest(),
                        "size": len(data),
                    }
                )

            _add_file(orig_path, f"docs/{dkey}/original/{Path(f_row['name']).name}")
            _add_file(base_native_path, f"docs/{dkey}/native/document.json")

            # Include enrichment versions so active_document_version resolves identically on Machine 2
            enr_dir = base_native_path.parent / "enrichment"
            if enr_dir.is_dir():
                for ver_dir in sorted(enr_dir.iterdir()):
                    if not ver_dir.is_dir() or ver_dir.is_symlink():
                        continue
                    for item in sorted(ver_dir.iterdir()):
                        if item.is_file() and not item.is_symlink():
                            _add_file(
                                item,
                                f"docs/{dkey}/enrichment/{ver_dir.name}/{item.name}",
                            )

            # Include cached LibreOffice display derivative if available so Machine 2 needs no LibreOffice!
            if display_root.is_dir() and not display_root.is_symlink():
                want_sha = bdoc["source_sha256"]
                for d_entry in sorted(display_root.iterdir()):
                    if not d_entry.is_dir() or d_entry.is_symlink() or d_entry.name == "lo-profile":
                        continue
                    meta_p = d_entry / "display.json"
                    if not meta_p.is_file():
                        continue
                    try:
                        meta = json.loads(meta_p.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        continue
                    if meta.get("source_sha256") == want_sha:
                        for df in sorted(d_entry.iterdir()):
                            if df.is_file() and not df.is_symlink():
                                _add_file(df, f"display/{d_entry.name}/{df.name}")
                        break

        manifest = {
            "schema": PACKAGE_SCHEMA,
            "package_type": "dual_review_assignment",
            "session_id": session["session_id"],
            "mode": "two_machines",
            "created_at": session["created_at"],
            "reviewer_a": session["reviewer_a"],
            "reviewer_b": session["reviewer_b"],
            "baseline_sha256": session["baseline_sha256"],
            "baseline": session["baseline"],
            "files": file_entries,
        }
        manifest["package_sha256"] = _canonical_sha256(
            {k: v for k, v in manifest.items() if k != "package_sha256"}
        )
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    filename = f"ux-pruefpaket-{session['session_id']}.zip"
    return filename, buf.getvalue()


def export_submission_json(w, session_id: str, *, slot: str | None = None) -> tuple[str, bytes]:
    """Export frozen initial judgment ('Ersturteil') or post-release revision file (.json)."""
    session = _load_session(w, session_id)
    if slot is None:
        active_id = auth.list_profiles(w)["active"]["id"]
        slot = _viewer_slot_for(session, active_id) or (
            "reviewer_b" if session["role_on_this_machine"] == "peer" else "reviewer_a"
        )
    if slot not in ("reviewer_a", "reviewer_b"):
        raise ValueError("Ungültiger Prüfer-Slot")

    submitted_at = (
        session["submitted_a_at"] if slot == "reviewer_a" else session["submitted_b_at"]
    )
    if not submitted_at:
        raise ValueError(
            "Bitte zuerst die eigene Erstbewertung verbindlich abgeben, bevor die Rückgabedatei exportiert wird."
        )

    by_finding = _session_decisions_by_finding(w, session)
    released = bool(session.get("released_at"))
    decisions_out = {}
    has_revision = False
    for fkey in sorted((session["id_map"].get("findings") or {}).keys()):
        entries = by_finding.get(fkey, {}).get(slot, [])
        initials = [e for e in entries if e.get("phase") == "initial"]
        revisions = [e for e in entries if e.get("phase") == "revision"] if released else []
        if revisions:
            has_revision = True
        chosen_entries = ([initials[-1]] if initials else []) + revisions
        decisions_out[fkey] = [
            {
                "decision_uid": e["decision_uid"],
                "at": e["at"],
                "phase": e["phase"],
                "action": e["action"],
                "reason": e["reason"],
                "reviewer": e["reviewer"],
                "interpretation": e["interpretation"],
            }
            for e in chosen_entries
        ]

    phase_kind = "revision" if has_revision else "initial"
    body = {
        "schema": PACKAGE_SCHEMA,
        "package_type": "dual_review_submission",
        "session_id": session["session_id"],
        "baseline_sha256": session["baseline_sha256"],
        "slot": slot,
        "phase_bundle": phase_kind,
        "reviewer": session[slot],
        "submitted_at": submitted_at,
        "decisions": decisions_out,
    }
    body["submission_uid"] = _canonical_sha256(body)
    body["package_sha256"] = _canonical_sha256(body)
    prefix = "ux-ueberarbeitung" if has_revision else "ux-abgabe"
    filename = f"{prefix}-{session['session_id']}-{slot}.json"
    return filename, json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")


def export_comparison_json(w, session_id: str) -> tuple[str, bytes]:
    """Export released side-by-side comparison (.json) so Machine 2 can inspect & optionally revise."""
    session = _load_session(w, session_id)
    if not session.get("released_at"):
        raise ValueError("Der Vergleich muss zuerst freigegeben werden, bevor er exportiert werden kann.")

    by_finding = _session_decisions_by_finding(w, session)
    decisions_out = {}
    for fkey in sorted((session["id_map"].get("findings") or {}).keys()):
        decisions_out[fkey] = {}
        for slot in ("reviewer_a", "reviewer_b"):
            entries = by_finding.get(fkey, {}).get(slot, [])
            initials = [e for e in entries if e.get("phase") == "initial"]
            revisions = [e for e in entries if e.get("phase") == "revision"]
            chosen = ([initials[-1]] if initials else []) + revisions
            decisions_out[fkey][slot] = [
                {
                    "decision_uid": e["decision_uid"],
                    "at": e["at"],
                    "phase": e["phase"],
                    "action": e["action"],
                    "reason": e["reason"],
                    "reviewer": e["reviewer"],
                    "interpretation": e["interpretation"],
                }
                for e in chosen
            ]

    body = {
        "schema": PACKAGE_SCHEMA,
        "package_type": "dual_review_comparison",
        "session_id": session["session_id"],
        "baseline_sha256": session["baseline_sha256"],
        "submitted_a_at": session["submitted_a_at"],
        "submitted_b_at": session["submitted_b_at"],
        "released_at": session["released_at"],
        "resolutions": session.get("resolutions") or {},
        "decisions": decisions_out,
    }
    body["comparison_uid"] = _canonical_sha256(body)
    body["package_sha256"] = _canonical_sha256(body)
    filename = f"ux-vergleich-{session['session_id']}.json"
    return filename, json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")


def _rebind_anchor_view(view: dict, local_doc_id: int, doc_version: str) -> dict:
    """Recompute `evidence_id` and `picture_source.document` for Machine 2's local document ID."""
    if not isinstance(view, dict) or "ref" not in view or "modality" not in view:
        return view
    anchor_keys = ("ref", "modality", "start", "end", "row", "row_end", "column", "column_end")
    anchor = {k: view[k] for k in anchor_keys if k in view}
    identity = json.dumps([int(local_doc_id), str(doc_version), anchor], sort_keys=True)
    out = dict(view)
    out["evidence_id"] = sha256(identity.encode()).hexdigest()
    if isinstance(out.get("picture_source"), dict):
        ps = dict(out["picture_source"])
        ps["document"] = int(local_doc_id)
        out["picture_source"] = ps
    return out


def _rebind_run_result_for_local_doc(run_result: dict, local_doc_id: int) -> tuple[dict, dict[str, str]]:
    """Translate all `evidence_id` references inside a Stage-A run result to `local_doc_id`."""
    res = json.loads(json.dumps(run_result))
    doc_ver = str(res.get("document_version") or "")
    old_sources = res.get("sources") or {}
    new_sources = {}
    eid_map: dict[str, str] = {}
    for old_eid, sview in old_sources.items():
        rebound = _rebind_anchor_view(sview, local_doc_id, doc_ver)
        new_eid = rebound.get("evidence_id") or old_eid
        eid_map[old_eid] = new_eid
        new_sources[new_eid] = rebound
    res["sources"] = new_sources

    for obs in res.get("observations") or []:
        if isinstance(obs.get("source_ids"), list):
            obs["source_ids"] = [eid_map.get(s, s) for s in obs["source_ids"]]
        for m in obs.get("measurements") or []:
            if isinstance(m, dict) and isinstance(m.get("source_ids"), list):
                m["source_ids"] = [eid_map.get(s, s) for s in m["source_ids"]]
        if isinstance(obs.get("context"), dict) and isinstance(
            obs["context"].get("source_ids"), list
        ):
            obs["context"]["source_ids"] = [
                eid_map.get(s, s) for s in obs["context"]["source_ids"]
            ]
        if isinstance(obs.get("candidate_anchors"), list):
            obs["candidate_anchors"] = [
                _rebind_anchor_view(c, local_doc_id, doc_ver)
                for c in obs["candidate_anchors"]
            ]
    return res, eid_map


def _import_assignment_zip(w, raw_bytes: bytes) -> dict:
    try:
        zf_check = zipfile.ZipFile(io.BytesIO(raw_bytes), "r")
    except zipfile.BadZipFile as exc:
        raise ValueError("Beschädigtes Prüfpaket: Keine gültige ZIP-Datei") from exc

    with zf_check as zf:
        bad_member = zf.testzip()
        if bad_member is not None:
            raise ValueError(f"Beschädigtes Archiv-Element im Prüfpaket: {bad_member}")
        names = set(zf.namelist())
        if "manifest.json" not in names:
            raise ValueError("Ungültiges Prüfpaket: manifest.json fehlt")
        try:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError("Ungültiges Prüfpaket: manifest.json ist beschädigt") from exc

        if (
            not isinstance(manifest, dict)
            or manifest.get("schema") != PACKAGE_SCHEMA
            or manifest.get("package_type") != "dual_review_assignment"
        ):
            raise ValueError("Unbekanntes Paketformat (erwartet: UX-mAInd Prüfpaket v1)")

        expected_pkg_sha = _canonical_sha256(
            {k: v for k, v in manifest.items() if k != "package_sha256"}
        )
        if manifest.get("package_sha256") != expected_pkg_sha:
            raise ValueError("Prüfpaket-Integritätsprüfung fehlgeschlagen (Hash-Abweichung)")

        baseline = manifest.get("baseline")
        session_id = str(manifest.get("session_id") or "").strip()
        if not session_id or not isinstance(baseline, dict):
            raise ValueError("Unvollständiges Prüfpaket (session_id oder baseline fehlt)")

        computed_base_sha = _canonical_sha256(baseline)
        if computed_base_sha != manifest.get("baseline_sha256"):
            raise ValueError("Ausgangsstand-Hash (baseline_sha256) stimmt nicht mit Paketinhalt überein")

        # Verify every declared file inside ZIP BEFORE touching disk or SQLite
        extracted_blobs: dict[str, bytes] = {}
        for fentry in manifest.get("files") or []:
            arc = str(fentry.get("arcname") or "")
            if (
                not arc
                or ".." in Path(arc).parts
                or arc.startswith(("/", "\\"))
                or arc not in names
            ):
                raise ValueError(f"Fehlendes oder unsicheres Dateielement im Prüfpaket: {arc}")
            blob = zf.read(arc)
            if sha256(blob).hexdigest() != fentry.get("sha256") or len(blob) != int(fentry.get("size", -1)):
                raise ValueError(f"Prüfsumme für Paketdatei {arc} weicht ab (Paket beschädigt)")
            extracted_blobs[arc] = blob

    # Idempotency check: if session already exists in this workspace
    with w.db() as db:
        existing = db.execute(
            "SELECT * FROM ux_review_sessions WHERE session_id=?", (session_id,)
        ).fetchone()
    if existing is not None:
        parsed_ex = _parse_session_row(existing)
        if parsed_ex["baseline_sha256"] != computed_base_sha:
            raise ValueError(
                "Eine Sitzung mit dieser ID existiert bereits, besitzt aber einen abweichenden Ausgangsstand."
            )
        return {
            "status": "already_imported",
            "kind": "assignment",
            "duplicates_created": 0,
            "session": format_session_for_viewer(w, parsed_ex),
        }

    # Stage managed document folders atomically on filesystem
    staged_folders: list[Path] = []
    staged_display: list[Path] = []
    try:
        b_docs = baseline.get("documents") or {}
        b_runs = baseline.get("runs") or {}
        b_rels = baseline.get("relations") or {}
        b_findings = baseline.get("findings") or {}

        doc_folder_map: dict[str, tuple[Path, str, str]] = {}
        for dkey, dmeta in sorted(b_docs.items()):
            folder_uuid = uuid4().hex
            doc_dir = w.root / folder_uuid
            staged_folders.append(doc_dir)
            orig_name = Path(dmeta["name"]).name
            orig_rel = f"{folder_uuid}/original/{orig_name}"
            nat_rel = f"{folder_uuid}/native/document.json"

            (doc_dir / "original").mkdir(parents=True, exist_ok=True)
            (doc_dir / "native").mkdir(parents=True, exist_ok=True)
            (doc_dir / "original" / orig_name).write_bytes(
                extracted_blobs[f"docs/{dkey}/original/{orig_name}"]
            )
            (doc_dir / "native" / "document.json").write_bytes(
                extracted_blobs[f"docs/{dkey}/native/document.json"]
            )

            prefix_enr = f"docs/{dkey}/enrichment/"
            for arc, blob in extracted_blobs.items():
                if arc.startswith(prefix_enr):
                    sub_rel = arc[len(prefix_enr) :]
                    dest_p = doc_dir / "native" / "enrichment" / sub_rel
                    dest_p.parent.mkdir(parents=True, exist_ok=True)
                    dest_p.write_bytes(blob)

            doc_folder_map[dkey] = (doc_dir, orig_rel, nat_rel)

        # Copy optional cached LibreOffice display PDFs
        for arc, blob in extracted_blobs.items():
            if arc.startswith("display/"):
                sub_rel = arc[len("display/") :]
                dest_d = w.root / "display" / sub_rel
                if not dest_d.parent.exists():
                    dest_d.parent.mkdir(parents=True, exist_ok=True)
                    staged_display.append(dest_d.parent)
                if not dest_d.exists():
                    dest_d.write_bytes(blob)

        rev_a = manifest["reviewer_a"]
        rev_b = manifest["reviewer_b"]

        doc_fwd: dict[str, int] = {}
        run_fwd: dict[str, int] = {}
        rel_fwd: dict[str, int] = {}
        finding_fwd: dict[str, int] = {}
        scope_local: list[int] = []

        with w.db() as db:
            db.execute("BEGIN IMMEDIATE")
            for dkey, dmeta in sorted(b_docs.items()):
                _, orig_rel, nat_rel = doc_folder_map[dkey]
                new_doc_id = db.execute(
                    """INSERT INTO documents(name, origin, stored, native, status, error, diagnostics, archived, corpus_role)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        dmeta["name"],
                        f"Prüfpaket {session_id} ({dmeta['name']})",
                        orig_rel,
                        nat_rel,
                        dmeta.get("status") or "success",
                        None,
                        json.dumps(dmeta.get("diagnostics") or {}, ensure_ascii=False),
                        0,
                        dmeta.get("corpus_role") or "evidence",
                    ),
                ).lastrowid
                doc_fwd[dkey] = int(new_doc_id)
                scope_local.append(int(new_doc_id))

            doc_ver_by_local_id: dict[int, str] = {}
            for rkey, rmeta in sorted(b_runs.items()):
                local_doc_id = doc_fwd[rmeta["doc_key"]]
                rebound_res, _ = _rebind_run_result_for_local_doc(rmeta["result"], local_doc_id)
                doc_ver_by_local_id[local_doc_id] = str(rebound_res.get("document_version") or "")
                new_run_id = db.execute(
                    "INSERT INTO runs(document, at, result) VALUES(?,?,?)",
                    (
                        local_doc_id,
                        rmeta["at"],
                        json.dumps(rebound_res, ensure_ascii=False),
                    ),
                ).lastrowid
                run_fwd[rkey] = int(new_run_id)

            for odec in baseline.get("pre_observation_decisions") or []:
                loc_ref = _localize_obs_ref(odec["target"], doc_fwd, run_fwd)
                loc_doc_id = int(loc_ref["document"])
                dver = doc_ver_by_local_id.get(loc_doc_id, "")
                pay = json.loads(json.dumps(odec.get("payload") or {}))
                if isinstance(pay.get("primary"), dict):
                    pay["primary"] = _rebind_anchor_view(pay["primary"], loc_doc_id, dver)
                if isinstance(pay.get("context"), list):
                    for ctx_item in pay["context"]:
                        if isinstance(ctx_item, dict) and isinstance(ctx_item.get("evidence"), dict):
                            ctx_item["evidence"] = _rebind_anchor_view(
                                ctx_item["evidence"], loc_doc_id, dver
                            )
                db.execute(
                    """INSERT INTO ux_decisions(target_type,target,at,origin,action,reason,payload)
                       VALUES('observation',?,?,?,?,?,?)""",
                    (
                        json.dumps(loc_ref, sort_keys=True),
                        odec["at"],
                        odec["origin"],
                        odec["action"],
                        odec.get("reason") or "",
                        json.dumps(pay, ensure_ascii=False),
                    ),
                )

            basis_runs_local = sorted(run_fwd.values())
            basis_by_doc_local = {
                str(doc_fwd[dk]): run_fwd[rmeta["run_key"]]
                for dk, rmeta in (
                    (rm["doc_key"], {"run_key": rk}) for rk, rm in b_runs.items()
                )
            }

            b_comp_local = None
            if baseline.get("b_comparison") or b_rels:
                bc = baseline.get("b_comparison") or {}
                b_obs_local = [
                    _localize_obs_ref(o, doc_fwd, run_fwd)
                    for o in (bc.get("observations") or [])
                ]
                b_meta = {
                    "origin": "model",
                    "stage": "B",
                    "status": bc.get("status") or "UNREVIEWED",
                    "model": bc.get("model"),
                    "provider": bc.get("provider"),
                    "counts": bc.get("counts"),
                    "observations": b_obs_local,
                    "basis_runs": basis_runs_local,
                    "basis_by_doc": basis_by_doc_local,
                    "schema_version": SCHEMA_VERSION,
                    "scope": scope_local,
                }
                b_comp_local = db.execute(
                    "INSERT INTO ux_objects(kind,at,proposal,metadata) VALUES('comparison',?,?,?)",
                    (
                        bc.get("at") or manifest["created_at"],
                        "[]",
                        json.dumps(b_meta, ensure_ascii=False),
                    ),
                ).lastrowid
                for rk, rel_item in sorted(b_rels.items()):
                    r_prop = dict(rel_item["proposal"])
                    if isinstance(r_prop.get("source"), dict):
                        r_prop["source"] = _localize_obs_ref(r_prop["source"], doc_fwd, run_fwd)
                    if isinstance(r_prop.get("target"), dict):
                        r_prop["target"] = _localize_obs_ref(r_prop["target"], doc_fwd, run_fwd)
                    r_meta = {
                        **(rel_item.get("metadata") or {}),
                        "comparison": int(b_comp_local),
                        "schema_version": SCHEMA_VERSION,
                        "scope": scope_local,
                    }
                    new_rel_id = db.execute(
                        "INSERT INTO ux_objects(kind,at,proposal,metadata) VALUES('relation',?,?,?)",
                        (
                            rel_item["at"],
                            json.dumps(r_prop, ensure_ascii=False),
                            json.dumps(r_meta, ensure_ascii=False),
                        ),
                    ).lastrowid
                    rel_fwd[rk] = int(new_rel_id)

            cc = baseline.get("c_comparison") or {}
            c_obs_local = [
                _localize_obs_ref(o, doc_fwd, run_fwd)
                for o in (cc.get("observations") or [])
            ]
            c_meta = {
                "origin": "model",
                "stage": "C",
                "status": cc.get("status") or "UNREVIEWED",
                "model": cc.get("model"),
                "provider": cc.get("provider"),
                "counts": cc.get("counts"),
                "b_run": int(b_comp_local) if b_comp_local is not None else None,
                "observations": c_obs_local,
                "basis_runs": basis_runs_local,
                "basis_by_doc": basis_by_doc_local,
                "schema_version": SCHEMA_VERSION,
                "scope": scope_local,
            }
            c_comp_local = db.execute(
                "INSERT INTO ux_objects(kind,at,proposal,metadata) VALUES('comparison',?,?,?)",
                (
                    cc.get("at") or manifest["created_at"],
                    "[]",
                    json.dumps(c_meta, ensure_ascii=False),
                ),
            ).lastrowid

            temp_id_map = {
                "documents": doc_fwd,
                "runs": run_fwd,
                "relations": rel_fwd,
                "comparisons": {
                    "B": int(b_comp_local) if b_comp_local is not None else None,
                    "C": int(c_comp_local),
                },
                "findings": {},
            }
            for fkey, fitem in sorted(b_findings.items()):
                loc_prop = _localize_finding_dict(fitem["proposal"], temp_id_map)
                f_meta = {
                    **(fitem.get("metadata") or {}),
                    "comparison": int(c_comp_local),
                    "b_run": int(b_comp_local) if b_comp_local is not None else None,
                    "schema_version": SCHEMA_VERSION,
                    "scope": scope_local,
                }
                new_fid = db.execute(
                    "INSERT INTO ux_objects(kind,at,proposal,metadata) VALUES('finding',?,?,?)",
                    (
                        fitem["at"],
                        json.dumps(loc_prop, ensure_ascii=False),
                        json.dumps(f_meta, ensure_ascii=False),
                    ),
                ).lastrowid
                finding_fwd[fkey] = int(new_fid)
            temp_id_map["findings"] = finding_fwd

            db.execute(
                """INSERT INTO ux_review_sessions(
                       session_id, mode, role_on_this_machine, created_at,
                       scope_json, reviewer_a_json, reviewer_b_json,
                       baseline_sha256, baseline_json, id_map_json,
                       resolutions_json, imported_receipts_json
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    session_id,
                    "two_machines",
                    "peer",
                    manifest["created_at"],
                    json.dumps(scope_local),
                    json.dumps(rev_a, ensure_ascii=False),
                    json.dumps(rev_b, ensure_ascii=False),
                    computed_base_sha,
                    json.dumps(baseline, ensure_ascii=False),
                    json.dumps(temp_id_map),
                    "{}",
                    json.dumps([manifest["package_sha256"]]),
                ),
            )

        # Register both reviewer profiles locally and activate Reviewer 2 on Machine 2
        auth.ensure_profile(
            w,
            display_name=rev_a["display_name"],
            short_code=rev_a.get("short_code") or "",
            role=rev_a.get("role") or "Erstprüfer",
            profile_id=rev_a["id"],
            activate=False,
        )
        auth.ensure_profile(
            w,
            display_name=rev_b["display_name"],
            short_code=rev_b.get("short_code") or "",
            role=rev_b.get("role") or "Zweitprüfer",
            profile_id=rev_b["id"],
            activate=True,
        )
        imported_session = _load_session(w, session_id)
        return {
            "status": "imported",
            "kind": "assignment",
            "duplicates_created": 0,
            "imported_documents": scope_local,
            "session": format_session_for_viewer(w, imported_session, viewer_id=rev_b["id"]),
        }
    except Exception:
        for d in staged_folders:
            shutil.rmtree(d, ignore_errors=True)
        for d in staged_display:
            shutil.rmtree(d, ignore_errors=True)
        raise


def _import_submission_or_comparison_json(w, raw_bytes: bytes) -> dict:
    try:
        doc = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Beschädigte JSON-Datei: Datei konnte nicht gelesen werden") from exc
    if not isinstance(doc, dict) or doc.get("schema") != PACKAGE_SCHEMA:
        raise ValueError("Ungültiges Dateiformat (kein UX-mAInd Zweitprüfungs-Dokument)")

    pkg_type = doc.get("package_type")
    if pkg_type not in ("dual_review_submission", "dual_review_comparison"):
        raise ValueError(f"Unbekannter Pakettyp: {pkg_type}")

    expected_sha = _canonical_sha256({k: v for k, v in doc.items() if k != "package_sha256"})
    if doc.get("package_sha256") != expected_sha:
        raise ValueError("Integritätsprüfung fehlgeschlagen: Datei wurde verändert oder ist unvollständig")

    session_id = str(doc.get("session_id") or "").strip()
    try:
        session = _load_session(w, session_id)
    except ValueError as exc:
        raise ValueError(
            f"Abgabe gehört zu einem anderen Prüfauftrag (session_id={session_id!r} hier unbekannt)."
        ) from exc

    if doc.get("baseline_sha256") != session["baseline_sha256"]:
        raise ValueError(
            "Abgabe passt nicht zum eingefrorenen Ausgangsstand (baseline_sha256 weicht ab)."
        )

    finding_map: dict[str, int] = session["id_map"].get("findings") or {}
    existing_by_f = _session_decisions_by_finding(w, session)
    seen_uids = {
        e["decision_uid"]
        for slots in existing_by_f.values()
        for entries in slots.values()
        for e in entries
    }
    receipts = list(session.get("imported_receipts") or [])

    if pkg_type == "dual_review_submission":
        sub_uid = str(doc.get("submission_uid") or "")
        slot = str(doc.get("slot") or "")
        if slot not in ("reviewer_a", "reviewer_b"):
            raise ValueError("Ungültiger Prüfer-Slot in Abgabedatei")
        decisions_in = doc.get("decisions")
        if not isinstance(decisions_in, dict) or set(decisions_in.keys()) != set(finding_map.keys()):
            raise ValueError("Abgabedatei enthält nicht genau die Findings dieses Prüfauftrags")

        # Validate all entries in memory BEFORE opening transaction
        to_insert: list[tuple] = []
        for fkey, entries in sorted(decisions_in.items()):
            if not isinstance(entries, list) or not entries:
                raise ValueError(f"Fehlende Entscheidung für Finding {fkey} in Abgabedatei")
            local_fid = int(finding_map[fkey])
            for e in entries:
                if not isinstance(e, dict) or e.get("action") not in VALID_ACTIONS:
                    raise ValueError(f"Ungültige Entscheidung in Finding {fkey}")
                phase = e.get("phase") or "initial"
                if phase not in ("initial", "revision"):
                    raise ValueError(f"Ungültige Entscheidungsphase {phase!r}")
                if phase == "revision" and not session.get("released_at"):
                    raise ValueError(
                        "Überarbeitungen (Revisions) können erst nach Freigabe des Vergleichs importiert werden"
                    )
                duid = str(e.get("decision_uid") or "")
                if not duid:
                    raise ValueError("decision_uid fehlt in Abgabedatei")
                if duid in seen_uids:
                    continue
                payload = {
                    "session_id": session_id,
                    "canonical_finding_key": fkey,
                    "slot": slot,
                    "phase": phase,
                    "decision_uid": duid,
                    "reviewer": e.get("reviewer") or session[slot],
                }
                interp = _clean_interpretation(e.get("interpretation"))
                if interp:
                    payload["interpretation"] = interp
                to_insert.append(
                    (
                        str(local_fid),
                        str(e.get("at") or _now_iso()),
                        e["action"],
                        str(e.get("reason") or ""),
                        json.dumps(payload, ensure_ascii=False),
                    )
                )

        if sub_uid in receipts and not to_insert:
            return {
                "status": "already_imported",
                "kind": "submission",
                "duplicates_created": 0,
                "session": format_session_for_viewer(w, session),
            }

        col = "submitted_a_at" if slot == "reviewer_a" else "submitted_b_at"
        submitted_ts = str(doc.get("submitted_at") or _now_iso())
        if sub_uid and sub_uid not in receipts:
            receipts.append(sub_uid)

        with w.db() as db:
            db.execute("BEGIN IMMEDIATE")
            for target_str, at_ts, act, rsn, pay_json in to_insert:
                db.execute(
                    """INSERT INTO ux_decisions(target_type,target,at,origin,action,reason,payload)
                       VALUES('finding',?,?,'dual_review',?,?,?)""",
                    (target_str, at_ts, act, rsn, pay_json),
                )
            db.execute(
                f"""UPDATE ux_review_sessions
                    SET {col}=COALESCE({col}, ?), imported_receipts_json=?
                    WHERE session_id=?""",
                (submitted_ts, json.dumps(receipts), session_id),
            )

        updated = _load_session(w, session_id)
        return {
            "status": "imported" if to_insert else "already_imported",
            "kind": "submission",
            "inserted_decisions": len(to_insert),
            "duplicates_created": 0,
            "session": format_session_for_viewer(w, updated),
        }

    # pkg_type == "dual_review_comparison"
    cmp_uid = str(doc.get("comparison_uid") or "")
    released_at = str(doc.get("released_at") or "").strip()
    sub_a = str(doc.get("submitted_a_at") or "").strip()
    sub_b = str(doc.get("submitted_b_at") or "").strip()
    if not released_at or not sub_a or not sub_b:
        raise ValueError("Ungültige Vergleichsdatei: Freigabe- oder Abgabezeitstempel fehlen")

    decisions_in = doc.get("decisions")
    if not isinstance(decisions_in, dict) or set(decisions_in.keys()) != set(finding_map.keys()):
        raise ValueError("Vergleichsdatei passt nicht zu den Findings dieses Prüfauftrags")

    to_insert = []
    for fkey, slot_dict in sorted(decisions_in.items()):
        if not isinstance(slot_dict, dict):
            raise ValueError("Beschädigte Slot-Daten in Vergleichsdatei")
        local_fid = int(finding_map[fkey])
        for slot in ("reviewer_a", "reviewer_b"):
            for e in slot_dict.get(slot) or []:
                if not isinstance(e, dict) or e.get("action") not in VALID_ACTIONS:
                    raise ValueError(f"Ungültige Entscheidung in Vergleichsdatei ({fkey}/{slot})")
                duid = str(e.get("decision_uid") or "")
                if not duid:
                    raise ValueError("decision_uid fehlt in Vergleichsdatei")
                if duid in seen_uids:
                    continue
                payload = {
                    "session_id": session_id,
                    "canonical_finding_key": fkey,
                    "slot": slot,
                    "phase": e.get("phase") or "initial",
                    "decision_uid": duid,
                    "reviewer": e.get("reviewer") or session[slot],
                }
                interp = _clean_interpretation(e.get("interpretation"))
                if interp:
                    payload["interpretation"] = interp
                to_insert.append(
                    (
                        str(local_fid),
                        str(e.get("at") or _now_iso()),
                        e["action"],
                        str(e.get("reason") or ""),
                        json.dumps(payload, ensure_ascii=False),
                    )
                )

    resolutions_in = doc.get("resolutions") if isinstance(doc.get("resolutions"), dict) else {}
    if cmp_uid in receipts and not to_insert and resolutions_in == (session.get("resolutions") or {}):
        return {
            "status": "already_imported",
            "kind": "comparison",
            "duplicates_created": 0,
            "session": format_session_for_viewer(w, session),
        }

    if cmp_uid and cmp_uid not in receipts:
        receipts.append(cmp_uid)

    with w.db() as db:
        db.execute("BEGIN IMMEDIATE")
        for target_str, at_ts, act, rsn, pay_json in to_insert:
            db.execute(
                """INSERT INTO ux_decisions(target_type,target,at,origin,action,reason,payload)
                   VALUES('finding',?,?,'dual_review',?,?,?)""",
                (target_str, at_ts, act, rsn, pay_json),
            )
        db.execute(
            """UPDATE ux_review_sessions
               SET submitted_a_at=COALESCE(submitted_a_at, ?),
                   submitted_b_at=COALESCE(submitted_b_at, ?),
                   released_at=COALESCE(released_at, ?),
                   resolutions_json=?,
                   imported_receipts_json=?
               WHERE session_id=?""",
            (
                sub_a,
                sub_b,
                released_at,
                json.dumps(resolutions_in, ensure_ascii=False),
                json.dumps(receipts),
                session_id,
            ),
        )

    updated = _load_session(w, session_id)
    return {
        "status": "imported" if (to_insert or not session.get("released_at")) else "already_imported",
        "kind": "comparison",
        "inserted_decisions": len(to_insert),
        "duplicates_created": 0,
        "session": format_session_for_viewer(w, updated),
    }


def import_package(w, raw_bytes: bytes, filename: str = "") -> dict:
    """Auto-detect and atomically import a Dual-Review `.zip` assignment or `.json` return/comparison."""
    if not raw_bytes:
        raise ValueError("Leere Importdatei")
    fname = (filename or "").lower()
    if raw_bytes[:4] == b"PK\x03\x04" or fname.endswith(".zip"):
        return _import_assignment_zip(w, raw_bytes)
    return _import_submission_or_comparison_json(w, raw_bytes)
