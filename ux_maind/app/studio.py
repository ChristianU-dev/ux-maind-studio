"""Loopback HTTP boundary; native document views, explicit jobs and non-secret profiles."""

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from html import escape
import mimetypes
import json
import os
from pathlib import Path
import secrets
import hashlib
from urllib.parse import urlencode
import webbrowser
from starlette.applications import Starlette
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from .workspace import Workspace
from .office import office_pdf, office_renderer as office_renderer
from . import (
    interpretation,
    library,
    models,
    receipts,
    research,
    telemetry,
    terminal_ui,
    workflow,
)

WEB = Path(__file__).parent / "web"
FRAME_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; sandbox"


def pick_paths(folder):
    import tkinter as tk
    from tkinter import filedialog

    window = tk.Tk()
    window.withdraw()
    window.attributes("-topmost", True)
    try:
        paths = (
            [filedialog.askdirectory(parent=window, mustexist=True)]
            if folder
            else list(filedialog.askopenfilenames(parent=window))
        )
        return [p for p in paths if p]
    finally:
        window.destroy()


def run_export(workspace, number, graph=None):
    runs = workspace.results(number)
    if graph is None:
        return runs
    run = next((r for r in runs if str(r["id"]) == str(graph)), None)
    if run is None:
        raise ValueError("Lauf gehört nicht zum gewählten Dokument")
    return (run["result"].get("native_graph") or run["result"]).get("graph")


def _format_progress_label(clean: dict) -> str:
    stage = clean.get("workflow_step") or clean.get("kind") or clean.get("phase") or ""
    doc_name = clean.get("document_name")
    status = clean.get("status")
    http_code = f"HTTP {clean['http_status']}" if clean.get("http_status") else None
    detail = clean.get("detail") or clean.get("reason")
    parts = [str(p) for p in (stage, doc_name, status, http_code, detail) if p]
    return " · ".join(parts) if parts else "Aktiv"


def _forbid_reference_documents(workspace, numbers, *, allow_reference=False):
    if allow_reference:
        return
    ref_names = []
    for n in dict.fromkeys(map(int, numbers or ())):
        try:
            row = workspace.file(n)
        except FileNotFoundError:
            continue
        if row.get("corpus_role") == "reference":
            ref_names.append(row["name"])
    if ref_names:
        joined = ", ".join(ref_names)
        raise ValueError(
            f"Referenz-/Codebook-Dokumente ({joined}) sind vor induktiver KI-Synthese geschützt "
            "(Kontaminationsschutz). Bitte im Studienkorpus aus der Auswahl abwählen oder Rolle auf ‚Primärquelle‘ setzen."
        )


def save_export(workspace, body):
    kind = body["kind"]
    if kind == "report":
        report_md = research.markdown_report(
            workspace,
            body["documents"],
            basis=body.get("basis"),
            result_runs=body.get("result_runs"),
            lang=body.get("lang", "de"),
        )
        return library.save_export(
            workspace, "ux-study-report.md", report_md.encode("utf-8")
        )
    if kind == "handout":
        handout_doc = telemetry.html_handout(
            workspace,
            body["documents"],
            basis=body.get("basis"),
            result_runs=body.get("result_runs"),
            lang=body.get("lang", "de"),
            include_toolbar=True,
        )
        return library.save_export(
            workspace, "ux-study-handout.html", handout_doc.encode("utf-8")
        )
    if kind == "research":
        name = "ux-research.json"
        value = research.graph(
            workspace,
            body["documents"],
            history=True,
            basis=body.get("basis"),
            result_runs=body.get("result_runs"),
        )
    else:
        row = workspace.file(body["document"])
        if kind == "original":
            return library.save_export(
                workspace, row["name"], workspace.artifact(row, "stored")
            )
        if kind == "native":
            row = workspace.version_row(row, body.get("version") or None)
            return library.save_export(
                workspace, "document.json", workspace.artifact(row, "native")
            )
        if kind == "markdown":
            row = workspace.version_row(row, body.get("version") or None)
            stem = Path(row["name"]).stem or f"document-{row['id']}"
            md_text = workspace.export_markdown(row)
            return library.save_export(
                workspace, f"{stem}.docling.md", md_text.encode("utf-8")
            )
        if kind not in ("runs", "graph"):
            raise ValueError("Unbekanntes Exportformat")
        name = "docling-graph.json" if kind == "graph" else "ux-results.json"
        value = run_export(
            workspace, row["id"], body["run"] if kind == "graph" else None
        )
        if kind == "graph" and value is None:
            raise ValueError("Dieser Lauf enthält keinen nativen Graph")
    return library.save_export(
        workspace, name, json.dumps(value, ensure_ascii=False, indent=2).encode()
    )


def application(root, *, terminal_log=False):
    import sys

    workspace = Workspace(root)
    pool = ThreadPoolExecutor(max_workers=1)
    activity = workspace.setting("latest_job") or dict(
        busy=False, message="Bereit", report=None
    )
    if isinstance(activity.get("message"), dict):
        activity["last_event"] = activity["message"]
        activity["message"] = _format_progress_label(activity["last_event"])
    parked_workflow = workspace.setting("parked_workflow")
    if activity.get("state") == "WAITING_REVIEW":
        parked_workflow = activity
        workspace.set_setting("parked_workflow", parked_workflow)
    token = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        yield
        pool.shutdown(wait=False)

    async def job(function, *args, documents=(), previous=None, **kwargs):
        nonlocal activity
        if activity["busy"]:
            raise ValueError("Ein Auftrag läuft bereits")
        items = {}
        for number in dict.fromkeys(map(int, documents)):
            try:
                row = workspace.file(number)
            except FileNotFoundError:
                continue
            items[number] = {
                "document": number,
                "document_name": row["name"],
                "steps": {},
            }
        checked = previous and kwargs["resume"].get("checked")
        if checked:
            items.update((row["document"], row) for row in previous["documents"])
            review = kwargs["resume"]
            for number in review["pending"]:
                item = items[number]
                items[number] = dict(
                    item,
                    steps={
                        key: value
                        for key, value in item["steps"].items()
                        if key != review["phase"]
                    },
                )
        events = list(previous.get("events") or [])[-100:] if checked else []
        action_name = (
            "workflow"
            if function is workflow.run
            else f"analysis_{kwargs['stage']}"
            if function is interpretation.run
            else function.__name__
        )
        started_iso = previous["started"] if previous else receipts.now()
        activity = dict(
            busy=True,
            message="Gestartet",
            report=None,
            state="RUNNING",
            action=action_name,
            started=started_iso,
            documents=list(items.values()),
            events=events,
        )
        if terminal_log:
            terminal_ui.emit_job_start(
                action_name,
                [row["document_name"] for row in items.values()],
                started_iso,
                stream=sys.stderr,
            )

        if function is workflow.run:
            activity["workflow"] = (
                previous["workflow"].copy()
                if checked
                else {step: {"status": "planned"} for step in workflow.STEPS}
            )

        def progress(event):
            nonlocal events
            clean = receipts.event(event)
            if not clean:
                return
            now_ts = receipts.now()
            events = (events + [dict(at=now_ts, **clean)])[-150:]
            if terminal_log:
                line = terminal_ui.format_event_line(now_ts, clean)
                if line:
                    print(line, file=sys.stderr, flush=True)
            if clean.get("document") and clean.get("document_name"):
                number = clean["document"]
                item = items.get(number) or {
                    "document": number,
                    "document_name": clean["document_name"],
                    "steps": {},
                }
                step = (
                    clean.get("kind")
                    if clean.get("kind")
                    in ("inventory", "conversion", "vision", "A", "B", "C")
                    else None
                )
                steps = dict(item["steps"])
                if (
                    step
                    and clean.get("status")
                    and not (function is workflow.run and step in ("B", "C"))
                ):
                    steps[step] = clean
                items[number] = dict(
                    item,
                    **{
                        k: v
                        for k, v in clean.items()
                        if k not in ("document", "document_name")
                    },
                    steps=steps,
                )
            if "workflow" in activity:
                activity["workflow"] = receipts.workflow_event(
                    activity["workflow"], clean, items
                )
            activity.update(
                message=_format_progress_label(clean),
                last_event=clean,
                documents=list(items.values()),
                events=events,
            )

        def run():
            nonlocal parked_workflow
            try:
                report = function(*args, progress=progress, **kwargs)
                state = receipts.outcome(
                    [
                        step
                        for item in items.values()
                        for step in item["steps"].values()
                    ],
                    report,
                )
                if function is workflow.run and report.get("status") == "ERROR":
                    state = "ERROR"
                if (
                    function is workflow.run
                    and report.get("status") == "WAITING_REVIEW"
                ):
                    state = "WAITING_REVIEW"
            except Exception as exc:
                state = "ERROR"
                report = dict(error=type(exc).__name__)
            last_ev = activity.get("last_event")
            end_detail = (
                last_ev.get("detail") or last_ev.get("reason")
                if state == "ERROR" and isinstance(last_ev, dict)
                else None
            )
            final = dict(
                activity,
                message=f"Auftrag beendet · {end_detail}" if end_detail else "Auftrag beendet",
                state=state,
                report=report,
                busy=False,
                ended=receipts.now(),
                last_document=last_ev if isinstance(last_ev, dict) else None,
            )
            try:
                if function is workflow.run:
                    parked_workflow = final if state == "WAITING_REVIEW" else None
                    workspace.set_setting("parked_workflow", parked_workflow)
                workspace.set_setting("latest_job", final)
                terminal_ui.append_job_history(workspace, final)
            finally:
                activity.update(final)
                if terminal_log:
                    terminal_ui.emit_job_end(final, stream=sys.stderr)

        asyncio.get_running_loop().run_in_executor(pool, run)

    async def endpoint(request):
        nonlocal activity, parked_workflow
        try:
            action = request.path_params["action"]
            q = request.query_params
            if request.method == "POST":
                if request.headers.get("x-workspace-token") != token:
                    return JSONResponse(
                        dict(error="Die Sitzung hat sich geändert. Seite neu laden."),
                        status_code=403,
                    )
                body = await request.json()
                if action == "import":
                    await job(
                        workspace.import_paths,
                        body["paths"],
                        vision=body.get("vision"),
                        convert=body.get("convert", True) is not False,
                    )
                elif action == "convert":
                    await job(
                        workspace.convert_selected,
                        body["documents"],
                        documents=body["documents"],
                        vision=body.get("vision"),
                    )
                elif action in ("workflow-preview", "workflow-start"):
                    resume = body.get("resume")
                    previous = parked_workflow if resume else None
                    if resume and (not previous or resume != previous.get("ended")):
                        raise ValueError(
                            "Der angezeigte Prüfstand ist nicht mehr aktuell."
                        )
                    review = dict(previous["report"]["review"]) if previous else None
                    if review and review.get("phase") == "A":
                        review["a_attempts"] = {
                            str(d["document"]): d["steps"]["A"]["run"]
                            for d in previous["documents"]
                            if d.get("steps", {}).get("A", {}).get("run")
                        }
                    numbers = (
                        [row["document"] for row in previous["documents"]]
                        if previous
                        else body["documents"]
                    )
                    _forbid_reference_documents(
                        workspace, numbers, allow_reference=body.get("allow_reference") is True
                    )
                    documents, stages, vision = workflow.configuration(
                        workspace, numbers
                    )
                    vision = workflow.retry_vision(vision, review)
                    basis = body.get("reuse_basis") if not review else None
                    reuse = (
                        workflow.validate_reuse(workspace, numbers, basis)
                        if basis
                        else None
                    )
                    if action == "workflow-preview":
                        versions = (
                            review.get("versions", {})
                            if review
                            else {
                                str(row["id"]): workflow.selected_version(
                                    workspace, row
                                )
                                for row in documents
                            }
                        )
                        return JSONResponse(
                            workflow.preview(
                                documents,
                                stages,
                                vision,
                                versions=versions,
                                reuse_basis=basis,
                            )
                        )
                    if body.get("send") is not True or body.get(
                        "configuration"
                    ) != workflow.fingerprint(documents, stages, vision):
                        raise ValueError(
                            "Modelle und Übermittlung für den aktuellen Auftrag bestätigen."
                        )
                    await job(
                        workflow.run,
                        workspace,
                        documents,
                        stages,
                        dict(vision, send=body.get("send_pixels") is True),
                        refresh=body.get("refresh") is True,
                        resume=review,
                        reuse=reuse,
                        allow_partial=body.get("allow_partial") is True,
                        previous=previous,
                        documents=[row["id"] for row in documents],
                    )
                elif action == "workflow-end":
                    if (
                        activity["busy"]
                        or not parked_workflow
                        or body.get("resume") != parked_workflow.get("ended")
                    ):
                        raise ValueError(
                            "Der angezeigte Prüfstand ist nicht mehr aktuell."
                        )
                    ended_workflow = dict(
                        parked_workflow,
                        state="PARTIAL",
                        message="Bei der Prüfung beendet",
                        report=dict(status="PARTIAL", reason="review_ended"),
                    )
                    if activity.get("ended") == parked_workflow.get("ended"):
                        activity = ended_workflow
                        workspace.set_setting("latest_job", activity)
                    parked_workflow = None
                    workspace.set_setting("parked_workflow", None)
                elif action == "remove-preview":
                    with workspace.db() as db:
                        return JSONResponse(
                            [library.preview(db, int(n)) for n in body["documents"]]
                        )
                elif action == "remove":
                    if activity["busy"] or activity.get("state") == "WAITING_REVIEW":
                        return JSONResponse(
                            dict(error="Ein Auftrag läuft bereits"), status_code=409
                        )
                    if body.get("confirmed") is not True:
                        raise ValueError(
                            "Aktion für die ausgewählten Dokumente bestätigen"
                        )
                    return JSONResponse(
                        library.remove(workspace, body["documents"], body["action"])
                    )
                elif action == "output-pick":
                    paths = pick_paths(True)
                    if paths:
                        library.output_directory(workspace, paths[0])
                    return JSONResponse(library.paths(workspace))
                elif action == "save-export":
                    return JSONResponse(
                        dict(path=await asyncio.to_thread(save_export, workspace, body))
                    )
                elif action == "enrich":
                    await job(
                        workspace.enrich,
                        body["documents"],
                        body["vision"],
                        documents=body["documents"],
                    )
                elif action == "corpus-role":
                    return JSONResponse(
                        workspace.set_corpus_role(
                            body.get("documents", []),
                            str(body.get("corpus_role", "evidence")),
                        )
                    )
                elif action == "researcher-save":
                    from . import auth

                    return JSONResponse(auth.save_profile(workspace, body))
                elif action == "researcher-select":
                    from . import auth

                    return JSONResponse(
                        auth.select_profile(workspace, str(body.get("id", "")))
                    )
                elif action == "researcher-delete":
                    from . import auth

                    return JSONResponse(
                        auth.delete_profile(workspace, str(body.get("id", "")))
                    )
                elif action == "oidc-authorize":
                    from . import auth

                    return JSONResponse(
                        await asyncio.to_thread(
                            auth.build_oidc_authorize_url,
                            workspace,
                            str(body.get("redirect_uri", "")),
                        )
                    )
                elif action == "extract":
                    if body.get("send") is not True:
                        raise ValueError("Übermittlung bewusst bestätigen")
                    _forbid_reference_documents(
                        workspace,
                        body["documents"],
                        allow_reference=body.get("allow_reference") is True,
                    )
                    await job(
                        workspace.extract,
                        body["documents"],
                        body["options"],
                        versions=body.get("versions"),
                        documents=body["documents"],
                    )
                elif action in ("ux-relations", "ux-findings"):
                    if body.get("send") is not True:
                        raise ValueError("Übermittlung bewusst bestätigen")
                    stage = "B" if action == "ux-relations" else "C"
                    basis = body.get("basis")
                    allow_partial = body.get("allow_partial") is True
                    numbers = body["documents"]
                    _forbid_reference_documents(
                        workspace,
                        numbers,
                        allow_reference=body.get("allow_reference") is True,
                    )
                    if not isinstance(basis, dict) or set(map(int, basis)) != set(
                        map(int, numbers)
                    ):
                        raise ValueError(
                            "Für jedes ausgewählte Dokument einen A-Lauf bestätigen."
                        )
                    planned = await asyncio.to_thread(
                        interpretation.plan,
                        workspace,
                        numbers,
                        basis=basis,
                        b_run=body.get("b_run"),
                        stage=stage,
                        allow_partial=allow_partial,
                    )
                    interpretation.require_basis(planned, allow_partial=allow_partial)
                    await job(
                        interpretation.run,
                        workspace,
                        body["documents"],
                        body["options"],
                        body.get("focus", ""),
                        basis=body.get("basis"),
                        b_run=body.get("b_run"),
                        stage=stage,
                        allow_partial=allow_partial,
                        documents=body["documents"],
                    )
                elif action == "ux-decision":
                    return JSONResponse(
                        await asyncio.to_thread(research.decide, workspace, body)
                    )
                elif action == "profile-save":
                    await asyncio.to_thread(
                        workspace.save_profile, body["name"], body["options"]
                    )
                elif action == "profile-delete":
                    workspace.delete_profile(body["name"])
                elif action == "workflow-settings":
                    return JSONResponse(library.workflow_settings(workspace, body))
                elif action == "model-check":
                    try:
                        return JSONResponse(
                            await asyncio.to_thread(models.check_access, body)
                        )
                    except Exception as exc:
                        status = getattr(exc, "status_code", None)
                        return JSONResponse(
                            dict(
                                status="error",
                                error=type(exc).__name__,
                                http_status=status if isinstance(status, int) else None,
                            )
                        )
                elif action == "model-preview":
                    return JSONResponse(
                        await asyncio.to_thread(
                            models.describe,
                            body,
                            discover_vision=body.get("vision_check") is True,
                            discover_limits=body.get("discover_limits") is True,
                        )
                    )
                elif action == "model-list":
                    return JSONResponse(
                        await asyncio.to_thread(models.offered_models, body)
                    )
                elif action == "model-catalog":
                    verified_vis = workspace.setting("verified_vision_models")
                    return JSONResponse(
                        await asyncio.to_thread(
                            models.discover_catalog,
                            body,
                            verified_vision=verified_vis if isinstance(verified_vis, dict) else None,
                        )
                    )
                elif action == "vision-probe":
                    probe_res = await asyncio.to_thread(models.probe_vision_access, body)
                    if body.get("provider") and body.get("model") and probe_res.get("status") == "responded":
                        v_map = workspace.setting("verified_vision_models")
                        v_map = dict(v_map) if isinstance(v_map, dict) else {}
                        v_map[f"{body['provider']}:{body['model']}"] = bool(probe_res.get("supports_vision"))
                        workspace.set_setting("verified_vision_models", v_map)
                    return JSONResponse(probe_res)
                elif action == "carry-forward-decisions":
                    return JSONResponse(
                        await asyncio.to_thread(
                            research.carry_forward_decisions,
                            workspace,
                            int(body["document"]),
                            int(body["run"]),
                        )
                    )
                elif action == "job-history-clear":
                    workspace.set_setting("job_history", [])
                    workspace.set_setting("job_history_cleared", True)
                    return JSONResponse(dict(history=[]))
                elif action == "pick":
                    if body.get("workspace") is True and activity["busy"]:
                        raise ValueError(
                            "Arbeitsbereichswechsel erst nach Auftragsende vorbereiten"
                        )
                    return JSONResponse(
                        dict(paths=pick_paths(body.get("folder") is True))
                    )
                else:
                    return Response(status_code=404)
                return JSONResponse(dict(ok=True))
            if action == "files":
                return JSONResponse(
                    workspace.files(
                        int(q.get("offset", 0)),
                        q.get("search", ""),
                        archived=q.get("archived") == "1",
                        sort=q.get("sort", ""),
                    )
                )
            if action == "paths":
                return JSONResponse(library.paths(workspace))
            if action == "researchers":
                from . import auth

                return JSONResponse(auth.list_profiles(workspace))
            if action == "exports-list":
                return JSONResponse(
                    dict(
                        output=library.paths(workspace)["output"],
                        items=library.list_saved_exports(workspace),
                    )
                )
            if action == "export-file":
                dest = library.output_directory(workspace)
                safe_name = Path(q["name"]).name
                target = (dest / safe_name).resolve()
                if (
                    not target.is_relative_to(dest)
                    or not target.is_file()
                    or target.is_symlink()
                ):
                    raise FileNotFoundError("Exportdatei nicht gefunden")
                media = {
                    ".html": "text/html; charset=utf-8",
                    ".md": "text/markdown; charset=utf-8",
                    ".json": "application/json",
                }.get(target.suffix.lower(), "application/octet-stream")
                headers = {"X-Content-Type-Options": "nosniff"}
                if target.suffix.lower() == ".html":
                    headers["Content-Security-Policy"] = (
                        "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'"
                    )
                if q.get("download") == "1" or target.suffix.lower() not in (".html",):
                    headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'
                return FileResponse(target, media_type=media, headers=headers)
            if action == "workspace-bundle":
                doc_ids = [int(n) for n in dict.fromkeys(json.loads(q.get("documents", "[]")))]
                has_lo = bool(office_renderer())
                use_compact = q.get("compact", "1") != "0"
                bundles = []
                for doc_id in doc_ids:
                    f = workspace.file(doc_id)
                    bundles.append(
                        dict(
                            file=f,
                            summary=dict(workspace.summary(f), office_renderer=has_lo),
                            runs=workspace.results(doc_id, messages=False, compact=use_compact),
                        )
                    )
                return JSONResponse(bundles)
            if action == "manual":
                app_dir = Path(__file__).resolve().parent
                repo_docs = app_dir.parent.parent / "docs"
                gen_docs = app_dir / "web" / "generated" / "docs"
                manual_p = (
                    repo_docs / "USER_MANUAL.md"
                    if (repo_docs / "USER_MANUAL.md").is_file()
                    else gen_docs / "USER_MANUAL.md"
                )
                limits_p = (
                    repo_docs / "SYSTEM_LIMITS.md"
                    if (repo_docs / "SYSTEM_LIMITS.md").is_file()
                    else gen_docs / "SYSTEM_LIMITS.md"
                )
                return JSONResponse(
                    dict(
                        user_manual=manual_p.read_text(encoding="utf-8") if manual_p.is_file() else "",
                        system_limits=limits_p.read_text(encoding="utf-8") if limits_p.is_file() else "",
                    )
                )
            if action == "file":
                return JSONResponse(workspace.file(q["id"]))
            if action == "status":
                return JSONResponse(
                    dict(
                        activity,
                        parked_workflow=parked_workflow
                        if not activity.get("workflow")
                        else None,
                    ),
                    headers={"Cache-Control": "no-store"},
                )
            if action == "job-history":
                return JSONResponse(
                    dict(
                        history=terminal_ui.read_job_history(workspace),
                        active=activity if activity.get("busy") else None,
                    ),
                    headers={"Cache-Control": "no-store"},
                )
            if action == "workflow-settings":
                return JSONResponse(library.workflow_settings(workspace))
            if action == "results":
                return JSONResponse(
                    workspace.results(
                        int(q["id"]),
                        messages=False,
                        compact=q.get("compact") == "1",
                    )
                )
            if action == "model-input":
                return JSONResponse(workspace.model_input(int(q["id"]), int(q["run"])))
            if action == "profiles":
                return JSONResponse(
                    dict(
                        profiles=workspace.profiles(),
                        presets=models.PRESETS,
                        env_status=models.env_status(),
                        detected_env_vars=models.detected_env_vars(),
                    )
                )
            if action.startswith("ux-"):
                numbers = json.loads(q.get("documents", "[]"))
                if action == "ux-telemetry":
                    return JSONResponse(
                        telemetry.study_telemetry(
                            workspace,
                            numbers,
                            basis=json.loads(q.get("basis", "null")),
                            result_runs=json.loads(q.get("result_runs", "null")),
                        )
                    )
                if action == "ux-handout":
                    handout_html = telemetry.html_handout(
                        workspace,
                        numbers,
                        basis=json.loads(q.get("basis", "null")),
                        result_runs=json.loads(q.get("result_runs", "null")),
                        lang=q.get("lang", "de"),
                        include_toolbar=True,
                    )
                    return HTMLResponse(
                        handout_html,
                        headers={
                            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'",
                            "X-Content-Type-Options": "nosniff",
                        },
                    )
                if action == "ux-report":
                    report_md = research.markdown_report(
                        workspace,
                        numbers,
                        basis=json.loads(q.get("basis", "null")),
                        result_runs=json.loads(q.get("result_runs", "null")),
                        lang=q.get("lang", "de"),
                    )
                    return Response(
                        report_md,
                        media_type="text/markdown; charset=utf-8",
                        headers={
                            "Content-Disposition": 'attachment; filename="ux-study-report.md"',
                            "X-Content-Type-Options": "nosniff",
                        },
                    )
                if action == "ux-inputs":
                    return JSONResponse(
                        interpretation.plan(
                            workspace,
                            numbers,
                            basis=json.loads(q.get("basis", "null")),
                            b_run=q.get("b_run"),
                            stage=q.get("stage", "B"),
                        )
                    )
                if action in ("ux-run", "ux-run-export"):
                    receipt = research.analysis_run(workspace, int(q["id"]))
                    return JSONResponse(
                        receipt,
                        headers={
                            "Content-Disposition": 'attachment; filename="ux-analysis-run.json"'
                        }
                        if action == "ux-run-export"
                        else None,
                    )
                if action == "ux-observation":
                    ref = research.reference(json.loads(q["ref"]))
                    if ref["document"] not in numbers:
                        raise ValueError("Beobachtung außerhalb der Dokumentauswahl")
                    return JSONResponse(research.entry(workspace, ref))
                if action == "ux-history":
                    return JSONResponse(research.historical(workspace, numbers))
                if action in ("ux-graph", "ux-export"):
                    value = research.graph(
                        workspace,
                        numbers,
                        history=action == "ux-export" or q.get("history") == "1",
                        basis=json.loads(q.get("basis", "null")),
                        result_runs=json.loads(q.get("result_runs", "null")),
                    )
                    return JSONResponse(
                        value,
                        headers={
                            "Content-Disposition": 'attachment; filename="ux-research.json"'
                        }
                        if action == "ux-export"
                        else None,
                    )
            row = workspace.file(q["id"])
            if action in ("summary", "elements", "cells"):
                row = workspace.version_row(row, q.get("version") or None)
            if action == "summary":
                return JSONResponse(
                    dict(
                        workspace.summary(row), office_renderer=bool(office_renderer())
                    )
                )
            if action == "elements":
                return JSONResponse(
                    workspace.elements(
                        row, int(q.get("offset", 0)), q.get("search", "")
                    )
                )
            if action == "cells":
                return JSONResponse(
                    workspace.cells(
                        row,
                        q["ref"],
                        int(q.get("start", 0)),
                        int(q.get("column", 0)),
                        q.get("search", ""),
                        int(q.get("offset", 0)),
                    )
                )
            return Response(status_code=404)
        except (ValueError, KeyError, TypeError, FileNotFoundError, IndexError) as exc:
            return JSONResponse(dict(error=str(exc)), status_code=400)

    async def view(request):
        try:
            row = workspace.file(request.path_params["number"])
            kind = request.path_params["kind"]
            q = request.query_params
            if kind in ("native", "markdown", "web", "resource", "view", "cells"):
                row = workspace.version_row(row, q.get("version") or None)
            if kind == "markdown":
                stem = Path(row["name"]).stem or f"document-{row['id']}"
                md_text = workspace.export_markdown(row)
                return Response(
                    md_text,
                    media_type="text/markdown; charset=utf-8",
                    headers={
                        "Content-Disposition": f'attachment; filename="{stem}.docling.md"',
                        "X-Content-Type-Options": "nosniff",
                    },
                )
            if kind == "export":
                graph = q.get("graph")
                value = run_export(workspace, row["id"], graph)
                if not graph and q.get("run"):
                    value = [r for r in value if str(r["id"]) == q["run"]]
                    if not value:
                        raise ValueError("Lauf gehört nicht zum gewählten Dokument")
                return Response(
                    json.dumps(value, ensure_ascii=False, indent=2),
                    media_type="application/json",
                    headers={
                        "Content-Disposition": 'attachment; filename="'
                        + ("docling-graph.json" if graph else "ux-results.json")
                        + '"',
                        "X-Content-Type-Options": "nosniff",
                    },
                )
            if kind in ("original", "native"):
                return FileResponse(
                    workspace.artifact(
                        row, "stored" if kind == "original" else "native"
                    ),
                    filename=row["name"] if kind == "original" else "document.json",
                    media_type="application/octet-stream",
                    headers={"X-Content-Type-Options": "nosniff"},
                )
            if kind == "web":
                return Response(
                    workspace.web_document(row), media_type="application/json"
                )
            if kind == "resource":
                content, mime = workspace.resource(row, q["kind"], int(q["index"]))
                return Response(
                    content,
                    media_type=mime,
                    headers={
                        "Content-Security-Policy": FRAME_CSP,
                        "X-Content-Type-Options": "nosniff",
                        "Cache-Control": "private, max-age=3600",
                    },
                )
            is_dark = q.get("theme") == "dark"
            theme_bg = "#14181f" if is_dark else "#f8fafc"
            theme_card = "#1b2028" if is_dark else "#ffffff"
            theme_fg = "#e6edf3" if is_dark else "#1e293b"
            theme_muted = "#8b949e" if is_dark else "#64748b"
            theme_border = "#2d3540" if is_dark else "#e2e8f0"
            if kind == "original-view":
                path = workspace.artifact(row, "stored")
                mime = mimetypes.guess_type(row["name"])[0] or ""
                if mime == "application/pdf":
                    theme_suffix = "&theme=dark" if is_dark else ""
                    return Response(
                        status_code=307,
                        headers={
                            "Location": f"/assets/pdf.html?document={row['id']}&kind=pdf{theme_suffix}"
                        },
                    )
                elif mime in (
                    "image/png",
                    "image/jpeg",
                    "image/webp",
                    "image/gif",
                    "image/bmp",
                ):
                    import base64

                    text = (
                        '<style>body{margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh}</style>'
                        '<img alt="Originalpixel" style="max-width:96%;max-height:94vh;object-fit:contain;border-radius:6px" src="data:'
                        + mime
                        + ";base64,"
                        + base64.b64encode(path.read_bytes()).decode()
                        + '">'
                    )
                elif mime == "text/plain" or path.suffix.lower() in (".vtt", ".md"):
                    return HTMLResponse(
                        f'<meta charset="utf-8"><style>'
                        f"body{{margin:0;padding:20px 24px;background:{theme_bg};color:{theme_fg};font:13.5px/1.65 -apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif}}"
                        f"pre{{margin:0;padding:18px 20px;background:{theme_card};border:1px solid {theme_border};border-radius:8px;"
                        f"font:13px/1.65 'JetBrains Mono',Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}}"
                        "::highlight(ux-source){background:#fde047;color:#0f172a}"
                        "::highlight(ux-preview){background:#93c5fd;color:#0f172a}"
                        '</style><pre id="original-text">'
                        + escape(path.read_text(encoding="utf-8", errors="replace"))
                        + "</pre>",
                        headers={
                            "Content-Security-Policy": FRAME_CSP + " allow-same-origin"
                        },
                    )
                elif row.get("native") and path.suffix.lower() in (".csv", ".xlsx", ".xls", ".ods"):
                    # Render structured native table grid directly when viewing tabular original files
                    doc_tbl = workspace.document(row)
                    tbl_html = "".join(t.export_to_html(doc_tbl) for t in doc_tbl.tables[:5])
                    text = (
                        f'<div class="orig-card"><div class="orig-pill">Tabellarische Originaldatei · {escape(row["name"])}</div>'
                        + (tbl_html or "<p>Keine Tabellenzellen erkannt.</p>")
                        + "</div>"
                    )
                else:
                    text = (
                        f'<div class="orig-card">'
                        f'<div class="orig-pill">Office-/Containerdatei · {escape(row["name"])}</div>'
                        "<p>Kein eingebauter binärer Browser-Renderer für dieses Dateiformat ohne lokales LibreOffice. "
                        "Die vollständige Docling-Struktur steht rechts bereit; die unveränderte Originaldatei kann oben jederzeit heruntergeladen werden.</p>"
                        "</div>"
                    )
            elif kind == "pdf":
                original = workspace.artifact(row, "stored")
                with original.open("rb") as source:
                    if source.read(5) != b"%PDF-":
                        raise ValueError("Kein Original-PDF")
                return FileResponse(
                    original,
                    media_type="application/pdf",
                    headers={"X-Content-Type-Options": "nosniff"},
                )
            elif kind == "office-pdf":
                target, identity = await asyncio.to_thread(
                    office_pdf,
                    workspace.artifact(row, "stored"),
                    workspace.root / "display",
                )
                return FileResponse(
                    target,
                    media_type="application/pdf",
                    headers={
                        "X-Display-Derivative": "LibreOffice",
                        "X-Source-SHA256": identity["source_sha256"],
                        "X-Display-SHA256": identity["display_sha256"],
                        "X-Content-Type-Options": "nosniff",
                    },
                )
            else:
                from docling_core.types.doc import (
                    ContentLayer,
                    DoclingDocument,
                    DocItemLabel,
                    ImageRefMode,
                    RefItem,
                )
                from docling_core.transforms.serializer.html import (
                    HTMLDocSerializer,
                    HTMLParams,
                )

                doc = workspace.document(row)
                if kind == "cells":
                    data = workspace.cells(
                        row,
                        q["ref"],
                        int(q.get("start", 0)),
                        int(q.get("column", 0)),
                        q.get("search", ""),
                        int(q.get("offset", 0)),
                    )
                    text = (
                        "<h1>Native Zellen "
                        + escape(data["ref"])
                        + "</h1><p>"
                        + str(data["rows"])
                        + " × "
                        + str(data["columns"])
                        + "; 0-basierte Koordinaten, kein Vollraster.</p><table><tr><th>Zeile / Spalte</th><th>Spanne / Kopf</th><th>Text</th></tr>"
                    )
                    text += (
                        "".join(
                            "<tr><td>"
                            + str(c["start_row_offset_idx"])
                            + " / "
                            + str(c["start_col_offset_idx"])
                            + "</td><td>"
                            + str(c["row_span"])
                            + " × "
                            + str(c["col_span"])
                            + (
                                " · Kopf"
                                if c["column_header"] or c["row_header"]
                                else ""
                            )
                            + "</td><td>"
                            + escape(c["text"])
                            + "</td></tr>"
                            for c in data["cells"]
                        )
                        + "</table>"
                    )
                elif kind == "view":
                    from .document_view import TableView

                    version_query = (
                        {"version": q["version"]} if q.get("version") else {}
                    )
                    table_view = TableView(version=q.get("version"))
                    params = HTMLParams(
                        layers=set(ContentLayer),
                        labels=set(DocItemLabel),
                        image_mode=ImageRefMode.EMBEDDED,
                        traverse_pictures=True,
                        enable_chart_tables=q.get("presentation") != "picture",
                        formula_to_mathml=False,
                        include_hyperlinks=False,
                    )
                    if q.get("ref"):
                        item = RefItem(cref=q["ref"]).resolve(doc)
                        if q.get("presentation") == "chart":
                            chart = getattr(item.meta, "tabular_chart", None)
                            if chart is None:
                                raise ValueError(
                                    "Keine native Diagrammtabelle verfügbar"
                                )
                            # Docling's HTML picture serializer uses the same table export.
                            display = DoclingDocument(
                                name="Abgeleitete Diagrammtabelle"
                            )
                            table = display.add_table(data=chart.chart_data)
                            text = (
                                "<h1>Abgeleitete Diagrammtabelle</h1>"
                                + table.export_to_html(display)
                            )
                        else:
                            text = (
                                HTMLDocSerializer(
                                    doc=doc, params=params, table_serializer=table_view
                                )
                                .serialize(item=item)
                                .text
                            )
                    else:
                        offset = max(0, int(q.get("offset", 0)))
                        text = (
                            HTMLDocSerializer(
                                doc=doc,
                                table_serializer=table_view,
                                params=params.model_copy(
                                    update=dict(start_idx=offset, stop_idx=offset + 100)
                                ),
                            )
                            .serialize()
                            .text
                        )
                        previous = escape(
                            urlencode(dict(version_query, offset=max(0, offset - 100)))
                        )
                        following = escape(
                            urlencode(dict(version_query, offset=offset + 100))
                        )
                        text += f'<p><a href="?{previous}">Vorige Elemente</a> · <a href="?{following}">Weitere Elemente</a></p>'
                else:
                    return Response(status_code=404)
            return HTMLResponse(
                f'<meta charset="utf-8"><style>'
                f"body{{font:13.5px/1.6 -apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif;margin:0;padding:20px 24px;background:{theme_bg};color:{theme_fg}}}"
                f"h1,h2,h3{{color:{theme_fg};letter-spacing:-0.01em;margin:1.1em 0 0.45em}}h1{{font-size:18px;margin-top:0}}h2{{font-size:15px}}h3{{font-size:13.5px}}"
                f"p,li{{color:{theme_fg};margin:0.45em 0}}"
                f"a{{color:#0f766e;text-decoration:none;font-weight:500}}"
                f".orig-card{{background:{theme_card};border:1px solid {theme_border};border-radius:10px;padding:18px 20px}}"
                f".orig-pill{{display:inline-block;font-size:11px;font-weight:600;color:{theme_muted};background:{theme_bg};border:1px solid {theme_border};border-radius:999px;padding:3px 10px;margin-bottom:12px}}"
                f"img{{max-width:100%;max-height:76vh;width:auto;height:auto;object-fit:contain;border-radius:6px;border:1px solid {theme_border}}}"
                f"table{{width:100%;border-collapse:collapse;background:{theme_card};border:1px solid {theme_border};border-radius:8px;overflow:hidden;font-size:12.5px;margin:10px 0}}"
                f"th{{background:{theme_bg};color:{theme_muted};font-weight:600;text-align:left;padding:8px 10px;border-bottom:1px solid {theme_border}}}"
                f"td{{border-top:1px solid {theme_border};padding:7px 10px;vertical-align:top}}"
                "pre{overflow-wrap:anywhere}</style>" + text,
                headers={"Content-Security-Policy": FRAME_CSP + " allow-same-origin"},
            )
        except Exception as exc:
            return HTMLResponse(
                "<p>Darstellung nicht verfügbar: "
                + escape(
                    str(exc) if isinstance(exc, ValueError) else type(exc).__name__
                )
                + "</p>",
                status_code=400,
                headers={"Content-Security-Policy": FRAME_CSP},
            )

    async def index(request):
        if not (WEB / "generated/components.js").is_file():
            return HTMLResponse(
                "<h1>Lokale Webkomponenten fehlen</h1><p>Im Projekt einmal npm ci --prefix frontend und npm run build --prefix frontend ausführen; danach Seite neu laden. Keine Node-Serverlaufzeit nötig.</p>",
                status_code=503,
            )
        return HTMLResponse(
            (WEB / "index.html")
            .read_text(encoding="utf-8")
            .replace("WORKSPACE_TOKEN", token),
            headers={
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self'; connect-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
            },
        )

    app = Starlette(
        routes=[
            Route("/", index),
            Route("/api/{action}", endpoint, methods=["GET", "POST"]),
            Route("/document/{number:int}/{kind}", view),
            Mount("/assets", StaticFiles(directory=WEB)),
        ],
        lifespan=lifespan,
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )
    app.state.workspace = workspace
    return app


def runtime_info():
    import sys
    from importlib.metadata import version

    manifest = WEB / "generated" / "build.json"
    module = Path(__file__).resolve()
    return dict(
        python=sys.executable,
        python_version=sys.version.split()[0],
        studio=str(module),
        studio_sha256=hashlib.sha256(module.read_bytes()).hexdigest(),
        assets=str(WEB),
        build_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest()
        if manifest.is_file()
        else None,
        packages={
            name: version(name)
            for name in (
                "ux-maind",
                "docling",
                "docling-core",
                "docling-graph",
                "litellm",
                "starlette",
                "uvicorn",
            )
        },
    )


def main():
    import sys

    parser = argparse.ArgumentParser(description="UX-mAInd Dokumentarbeitsbereich")
    parser.add_argument("--port", type=int, default=8465)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share"))
        / "UX-mAInd"
        / "workspace-r12",
    )
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--runtime-info", action="store_true")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Zusätzlich alle HTTP-Anfragen (Access-Log) live im Terminal ausgeben",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Live-Auftragsprotokoll im Terminal stummschalten",
    )
    args = parser.parse_args()
    if args.runtime_info:
        print(json.dumps(runtime_info(), ensure_ascii=False, indent=2))
        return
    import uvicorn

    app = application(args.workspace, terminal_log=not args.quiet)
    if not args.quiet:
        ws = app.state.workspace
        terminal_ui.emit_startup_banner(
            port=args.port,
            workspace_root=ws.root,
            output_dir=library.paths(ws).get("output") or "(noch nicht gewählt)",
            detected_envs=models.detected_env_vars(),
            workflow_cfg=library.workflow_settings(ws),
            verbose=args.verbose,
            stream=sys.stderr,
        )
    if not args.no_browser:
        webbrowser.open(f"http://127.0.0.1:{args.port}")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=args.port,
        access_log=args.verbose,
        log_level="info" if args.verbose else "warning",
    )
