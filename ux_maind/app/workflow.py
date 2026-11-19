"""One workspace job through the existing native steps."""

from functools import partial
from hashlib import sha256
import json

from . import interpretation, library, models, research
from .evidence import file_digest

STEPS = ("conversion", "vision", "A", "B", "C")


def configuration(workspace, numbers):
    saved = library.workflow_settings(workspace)
    profiles = {p["name"]: p["options"] for p in workspace.profiles()}
    text = profiles.get(saved["profiles"]["A"])
    if not text:
        raise ValueError(
            "Unter Einstellungen → Aktive Zuordnungen ein Textmodell für A wählen."
        )
    documents = [workspace.file(i) for i in dict.fromkeys(map(int, numbers))]
    if not documents or any(row["archived"] for row in documents):
        raise ValueError("Aktive Dokumente für die Analyse auswählen.")
    stages = {
        step: models.profile_options(profiles.get(saved["profiles"][step], text))
        for step in ("A", "B", "C")
    }
    vision = dict(saved["vision"], profile=profiles.get(saved["profiles"]["vision"]))
    if not vision["profile"] and models.vision_capability(stages["A"]) is True:
        vision["profile"] = stages["A"]
    return documents, stages, vision


def fingerprint(documents, stages, vision):
    return sha256(
        json.dumps(
            ([row["id"] for row in documents], stages, vision), sort_keys=True
        ).encode()
    ).hexdigest()


def model_label(profile):
    return f"{profile['model']} · {profile['base_url'] or profile['provider']}"


def preview(documents, stages, vision, *, versions=None, reuse_basis=None):
    profile = models.vision_options(vision["profile"]) if vision["profile"] else None
    return dict(
        configuration=fingerprint(documents, stages, vision),
        documents=[row["name"] for row in documents],
        versions=versions or {},
        reuse_basis=reuse_basis,
        models={key: model_label(profile) for key, profile in stages.items()},
        vision_enabled=vision["enabled"],
        vision_model=model_label(profile) if profile else None,
        vision_timeout=vision["timeout"],
        vision_pixels=vision["enabled"]
        and vision["mode"] == "api"
        and bool(vision["profile"])
        and (vision["description"] or vision["chart"]),
    )


def retry_vision(vision, review):
    return dict(vision, **(review or {}).get("vision_tasks", {}))


def step(progress, phase, status, **details):
    progress(dict(kind="workflow", phase=phase, status=status, **details))


def to_stage(progress, phase, event):
    progress(dict(event, workflow_step=phase))


def record_a(progress, basis, outcomes, event):
    if event.get("run"):
        number = event["document"]
        outcomes[number] = event["status"]
        if event.get(
            "basis_eligible", event.get("resolved") and event["status"] == "UNREVIEWED"
        ):
            basis[number] = event["run"]
        else:
            basis.pop(number, None)
    to_stage(progress, "A", event)


def record_vision(progress, versions, outcomes, event):
    if event.get("status"):
        outcomes[event["document"]] = event
    if event.get("version") and event["status"] in ("success", "partial_success"):
        versions[str(event["document"])] = event["version"]
    to_stage(progress, "vision", event)


def usable(row):
    return row["native"] and row["status"] in ("success", "partial_success")


def selected_version(workspace, row):
    if not row["native"]:
        return None
    return workspace.preferred_version(row) or file_digest(
        workspace.artifact(row, "native")
    )


def conversion_status(row):
    diagnostics = json.loads(row.get("diagnostics") or "{}")
    return diagnostics.get("last_conversion", {}).get("status", row["status"])


def convert(workspace, documents, refresh, progress, retained):
    pending = [row["id"] for row in documents if refresh or not usable(row)]
    reused = retained + len(documents) - len(pending)
    total = retained + len(documents)
    step(
        progress,
        "conversion",
        "running",
        total=total,
        completed=reused,
        reused=reused,
        targets=pending,
    )
    changed = (
        workspace.convert_selected(
            pending,
            progress=partial(to_stage, progress, "conversion"),
        )
        if pending
        else []
    )
    outcomes = {row["id"]: row["status"] for row in changed}
    failed = [
        row["id"]
        for row in documents
        if outcomes.get(row["id"], conversion_status(row)) != "success"
    ]
    step(
        progress,
        "conversion",
        "PARTIAL" if failed else "success" if pending else "skipped",
        total=total,
        completed=total,
        failed=len(failed),
    )
    return failed


def enrich(workspace, ready, versions, vision, outcomes, progress, retry=False):
    total = len(ready) + len(outcomes)
    step(
        progress,
        "vision",
        "running",
        total=total,
        completed=len(outcomes),
        reused=len(outcomes),
    )
    if vision["enabled"]:
        bases = {
            str(n): versions[str(n)]
            if retry
            else workspace.latest_conversion(workspace.file(n))
            for n in ready
        }
        workspace.enrich(
            ready,
            vision,
            progress=partial(record_vision, progress, versions, outcomes),
            versions=bases,
            automatic=True,
            retry=retry,
        )
    pending = sorted(
        n for n, e in outcomes.items() if e["status"] not in ("success", "skipped")
    )
    skipped = sum(e["status"] == "skipped" for e in outcomes.values())
    successful = sum(e["status"] == "success" for e in outcomes.values())
    step(
        progress,
        "vision",
        "PARTIAL" if pending else "success" if successful else "skipped",
        total=total,
        completed=total,
        failed=len(pending),
        successful=successful,
        skipped=skipped if vision["enabled"] else total,
        **{
            key: sum(e.get(key, 0) for e in outcomes.values())
            for key in (
                "pictures",
                "described",
                "classified",
                "charts",
                "description_open",
            )
        },
    )
    return pending


def extract(workspace, ready, profile, versions, basis, outcomes, progress):
    total = len(ready) + len(outcomes)
    step(
        progress,
        "A",
        "running",
        total=total,
        completed=len(outcomes),
        reused=len(outcomes),
    )
    if ready:
        workspace.extract(
            ready,
            profile,
            versions=versions,
            progress=partial(record_a, progress, basis, outcomes),
        )
    pending = sorted(n for n in outcomes if n not in basis)
    pending = sorted(set(pending).union(set(ready) - outcomes.keys()))
    step(
        progress,
        "A",
        "PARTIAL" if pending else "success",
        total=total,
        completed=total,
        failed=len(pending),
    )
    return pending


def analyze(
    workspace,
    stage,
    profile,
    basis,
    progress,
    b_run=None,
    *,
    allow_partial=False,
    output_language=None,
):
    step(progress, stage, "running", total=1, completed=0)
    extra = {}
    if allow_partial:
        extra["allow_partial"] = True
    if output_language:
        extra["output_language"] = output_language
    result = interpretation.run(
        workspace,
        list(basis),
        profile,
        basis=basis,
        b_run=b_run,
        stage=stage,
        progress=partial(to_stage, progress, stage),
        **extra,
    )
    step(
        progress,
        stage,
        result["status"],
        total=1,
        completed=1,
        run=result["comparison"],
        **result["counts"],
    )
    return result


def waiting(phase, pending, state):
    return dict(
        status="WAITING_REVIEW",
        review=dict(state, phase=phase, pending=pending, checked=True),
    )


def prior_outcomes(values, retry):
    return {int(n): value for n, value in values.items() if int(n) not in retry}


def validate_reuse(workspace, numbers, basis):
    if not isinstance(basis, dict) or set(map(int, basis)) != set(numbers):
        raise ValueError(
            "Für die Wiederverwendung ist je Dokument ein A-Lauf erforderlich."
        )
    inputs = interpretation.plan(workspace, numbers, basis=basis)
    interpretation.require_basis(inputs)
    return {
        "basis": {int(n): run for n, run in basis.items()},
        "versions": {
            str(d["document"]): d["document_version"] for d in inputs["documents"]
        },
    }


def run(
    workspace,
    documents,
    stages,
    vision,
    refresh=False,
    *,
    resume=None,
    reuse=None,
    allow_partial=False,
    output_language=None,
    progress=lambda event: None,
):
    state = dict(resume) if resume and resume.get("checked") else {}
    if reuse:
        state.update(reuse, phase="B")
        for skipped in ("conversion", "vision", "A"):
            step(progress, skipped, "skipped", reused=len(reuse["basis"]))
    phase = state.get("phase")
    pending = state.get("pending", [])
    ready = [row["id"] for row in documents]
    if phase in (None, "conversion") or state.get("conversion_open"):
        targets = state.get("conversion_open") or pending or ready
        rows = [row for row in documents if row["id"] in targets]
        failed = convert(
            workspace,
            rows,
            refresh or bool(phase),
            progress,
            len(ready) - len(rows),
        )
        if failed:
            return waiting("conversion", failed, dict(conversion_open=failed))
        state = dict(
            versions={
                str(n): selected_version(workspace, workspace.file(n)) for n in ready
            }
        )
        phase = None
    versions = state["versions"] = state["versions"].copy()
    for n in ready:
        if versions.get(str(n)) is None:
            # Historical checkpoints used null for the unversioned base.
            versions[str(n)] = file_digest(
                workspace.artifact(workspace.file(n), "native")
            )
    if phase in (None, "vision"):
        vision = retry_vision(vision, state)
        state["vision_tasks"] = {
            key: vision[key]
            for key in ("enabled", "description", "classification", "chart")
            if key in vision
        }
        targets = pending if phase else ready
        images = prior_outcomes(state.get("images", {}), targets)
        vision_open = enrich(
            workspace, targets, versions, vision, images, progress, phase == "vision"
        )
        state["images"] = images
        if vision_open:
            return waiting("vision", vision_open, state)
    basis = {int(n): run_id for n, run_id in state.get("basis", {}).items()}
    if phase not in ("B", "C"):
        targets = pending if phase == "A" else ready
        outcomes = prior_outcomes(state.get("observations", {}), targets)
        if phase == "A":
            for n in list(targets):
                checkpoint_run = (state.get("a_attempts") or {}).get(str(n))
                if checkpoint_run is None or not any(
                    attempt["id"] == checkpoint_run
                    and attempt["result"].get("observations")
                    for attempt in workspace.results(n, messages=False)
                ):
                    continue
                document = research.catalog(workspace, [n], basis={n: checkpoint_run})[
                    "documents"
                ][0]
                if (
                    document["technical"]["eligible"]
                    and document["document_version"] == versions[str(n)]
                ):
                    basis[n] = checkpoint_run
                    outcomes[n] = document["coverage_status"]
            targets = [n for n in targets if n not in basis]
        a_open = extract(
            workspace, targets, stages["A"], versions, basis, outcomes, progress
        )
        state.update(basis=basis, observations=outcomes)
        if a_open:
            return waiting("A", a_open, state)
    if phase != "C":
        outcome = analyze(
            workspace,
            "B",
            stages["B"],
            basis,
            progress,
            allow_partial=allow_partial,
            output_language=output_language,
        )
        state["b"] = {k: outcome[k] for k in ("status", "comparison")}
        if outcome["status"] not in ("UNREVIEWED", "NO_PROPOSALS"):
            return waiting("B", list(basis), state)
    b_run = state["b"]["comparison"]
    c = analyze(
        workspace,
        "C",
        stages["C"],
        basis,
        progress,
        b_run=b_run,
        allow_partial=allow_partial,
        output_language=output_language,
    )
    if c["status"] not in ("UNREVIEWED", "NO_PROPOSALS"):
        return waiting("C", list(basis), state)
    return dict(
        status=c["status"],
        documents=list(basis),
        basis=basis,
        b_run=b_run,
        c_run=c["comparison"],
        findings=c["counts"]["proposed"],
        unresolved=c["counts"]["unresolved"],
    )
