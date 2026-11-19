"""Workspace-owned files, retention and local export destination."""

import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from .conversion_config import VISION_TIMEOUT_DEFAULT


def local_directory(path, *, create=False):
    path = Path(path).absolute()
    if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
        raise ValueError("Umgeleiteter lokaler Ordner")
    if create:
        path.mkdir(exist_ok=True)
    if not path.is_dir():
        raise ValueError("Lokaler Ordner ist nicht verfügbar")
    return path.resolve(strict=True)


def _decode_setting_string(raw_value: str) -> str:
    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, str):
            return parsed
    except (ValueError, TypeError):
        pass
    return raw_value


def default_workspace_path() -> Path:
    """Permanent default application workspace path (`%LOCALAPPDATA%\\UX-mAInd\\workspace` on Windows)."""
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share"))
    return (base / "UX-mAInd" / "workspace").resolve()


def probe_legacy_workspace(workspace) -> dict:
    """Read-only check for an existing sibling `workspace-r12` folder without modifying it."""
    ws_root = Path(workspace.root).resolve()
    legacy_dir = ws_root.parent / "workspace-r12"
    if (
        ws_root == legacy_dir
        or not legacy_dir.is_dir()
        or legacy_dir.is_symlink()
        or legacy_dir.is_junction()
    ):
        return {"found": False, "path": str(legacy_dir)}
    db_file = legacy_dir / "workspace.sqlite"
    if not db_file.is_file() or db_file.is_symlink():
        return {"found": False, "path": str(legacy_dir)}
    docs = runs = findings = profiles = 0
    try:
        conn = sqlite3.connect(f"file:{db_file.as_posix()}?mode=ro", uri=True, timeout=3.0)
        try:
            docs = int(conn.execute("SELECT count(*) FROM documents").fetchone()[0])
            runs = int(conn.execute("SELECT count(*) FROM runs").fetchone()[0])
            findings = int(
                conn.execute("SELECT count(*) FROM ux_objects WHERE kind='finding'").fetchone()[0]
            )
            profiles = int(conn.execute("SELECT count(*) FROM profiles").fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error:
        return {"found": False, "path": str(legacy_dir)}
    has_data = bool(docs or runs or findings or profiles)
    return {
        "found": has_data,
        "path": str(legacy_dir),
        "documents": docs,
        "runs": runs,
        "findings": findings,
        "profiles": profiles,
    }


def paths(workspace):
    with workspace.db() as db:
        row = db.execute(
            "SELECT value FROM workspace_settings WHERE name='output'"
        ).fetchone()
        current_docs = int(db.execute("SELECT count(*) FROM documents").fetchone()[0])
    default_ws = default_workspace_path()
    ws_root = Path(workspace.root).resolve()
    legacy = probe_legacy_workspace(workspace)
    legacy_root = (ws_root.parent / "workspace-r12").resolve()
    stored_out = _decode_setting_string(row["value"]) if row else None
    use_default_out = row is None
    if stored_out and ws_root != legacy_root:
        try:
            if Path(stored_out).resolve().is_relative_to(legacy_root):
                stored_out = None
                use_default_out = True
        except OSError:
            pass
    return dict(
        workspace=str(workspace.root),
        default_workspace=str(default_ws),
        is_default_workspace=ws_root == default_ws,
        current_documents=current_docs,
        output=stored_out if stored_out else str(workspace.root / "exports"),
        output_default=use_default_out,
        legacy_workspace=legacy,
    )


def output_directory(workspace, selected=None):
    settings = paths(workspace)
    path = local_directory(
        selected or settings["output"],
        create=selected is None and settings["output_default"],
    )
    if path == workspace.root or (
        path.is_relative_to(workspace.root)
        and not path.is_relative_to(workspace.root / "exports")
    ):
        raise ValueError("Ausgabeordner liegt im verwalteten Dokumentbestand")
    if selected is not None:
        workspace.set_setting("output", str(path))
    return path


def list_saved_exports(workspace, limit=50):
    """Return metadata of files saved in the configured local export directory."""
    try:
        dest = output_directory(workspace)
    except ValueError:
        return []
    entries = []
    for entry in dest.iterdir():
        if not entry.is_file() or entry.is_symlink():
            continue
        try:
            st = entry.stat()
        except OSError:
            continue
        raw_name = entry.name
        display_name = (
            raw_name[33:]
            if len(raw_name) > 33
            and raw_name[32] == "-"
            and all(c in "0123456789abcdef" for c in raw_name[:32])
            else raw_name
        )
        entries.append(
            dict(
                filename=raw_name,
                display_name=display_name,
                path=str(entry),
                suffix=entry.suffix.lower(),
                size_bytes=st.st_size,
                modified_at=datetime.fromtimestamp(
                    st.st_mtime, tz=timezone.utc
                ).isoformat(),
            )
        )
    entries.sort(key=lambda x: x["modified_at"], reverse=True)
    return entries[: max(1, int(limit))]


def preview(db, number):
    row = db.execute("SELECT * FROM documents WHERE id=?", (number,)).fetchone()
    if row is None:
        raise ValueError("Dokument nicht verfügbar")
    runs, evidence = db.execute(
        """SELECT count(*), coalesce(sum(json_array_length(result,'$.observations')),0)
             FROM runs WHERE document=?""",
        (number,),
    ).fetchone()
    notes = db.execute(
        "SELECT count(*) FROM notes JOIN runs ON runs.id=notes.run WHERE runs.document=?",
        (number,),
    ).fetchone()[0]
    objects = db.execute(
        """SELECT id,kind FROM ux_objects AS o
           WHERE EXISTS (SELECT 1 FROM json_each(o.metadata,'$.scope') WHERE value=?)
              OR EXISTS (SELECT 1 FROM json_tree(o.proposal) WHERE key='document' AND value=?)""",
        (number, number),
    ).fetchall()
    decisions = db.execute(
        """SELECT count(*) FROM ux_decisions
           WHERE json_valid(target) AND json_extract(target,'$.document')=?""",
        (number,),
    ).fetchone()[0]
    decisions += sum(
        db.execute(
            "SELECT count(*) FROM ux_decisions WHERE target_type=? AND target=?",
            (obj["kind"], str(obj["id"])),
        ).fetchone()[0]
        for obj in objects
    )
    return dict(
        id=number,
        name=row["name"],
        origin=row["origin"],
        archived=bool(row["archived"]),
        stored=bool(row["stored"]),
        native=bool(row["native"]),
        runs=runs,
        evidence=evidence,
        notes=notes,
        objects=len(objects),
        decisions=decisions,
        removable=not (runs or notes or objects or decisions),
    )


def managed_directory(workspace, row):
    if not row["stored"]:
        if row["native"]:
            raise ValueError("Docling-Artefakt ohne zugehörige Workspace-Kopie")
        return None
    original = workspace.artifact(row, "stored")
    folder = original.parent.parent
    if (
        original.parent.name != "original"
        or folder.parent != workspace.root
        or UUID(folder.name).hex != folder.name
        or folder.resolve() != folder
        or Path(row["origin"]).resolve().is_relative_to(folder)
    ):
        raise ValueError("Workspace-Kopie liegt auf einem unsicheren Pfad")
    if row["native"] and not workspace.artifact(row, "native").resolve().is_relative_to(
        folder
    ):
        raise ValueError("Docling-Artefakt liegt außerhalb der Workspace-Kopie")
    for parent, directories, files in os.walk(folder, followlinks=False):
        for name in [*directories, *files]:
            entry = Path(parent) / name
            if entry.is_symlink() or entry.is_junction():
                raise ValueError("Workspace-Kopie enthält eine Umleitung")
    return folder


def _cleanup_orphaned_display_cache(workspace, removed_sha256: str | None):
    """Remove cached LibreOffice display derivatives when no remaining document shares source_sha256."""
    if not removed_sha256:
        return
    display_root = workspace.root / "display"
    if not display_root.is_dir() or display_root.is_symlink():
        return
    from .evidence import file_digest

    with workspace.db() as db:
        remaining_rows = [dict(r) for r in db.execute("SELECT * FROM documents").fetchall()]
    for r in remaining_rows:
        if r.get("stored"):
            try:
                if file_digest(workspace.artifact(r, "stored")) == removed_sha256:
                    return
            except (OSError, ValueError):
                continue
    for entry in display_root.iterdir():
        if not entry.is_dir() or entry.is_symlink() or entry.name == "lo-profile":
            continue
        meta_file = entry / "display.json"
        if not meta_file.is_file():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if meta.get("source_sha256") == removed_sha256:
            shutil.rmtree(entry, ignore_errors=True)


def remove(workspace, numbers, action):
    if action not in ("archive", "restore", "remove"):
        raise ValueError("Unbekannte Aktion")
    from .evidence import file_digest

    results = []
    for number in dict.fromkeys(map(int, numbers)):
        moved = folder = None
        removed_sha256 = None
        try:
            with workspace.db() as db:
                db.execute("BEGIN IMMEDIATE")
                document = preview(db, number)
                if action == "remove":
                    if not document["removable"]:
                        results.append(
                            dict(
                                id=number,
                                status="BLOCKED",
                                reason="Forschungs- oder Laufhistorie vorhanden",
                            )
                        )
                        continue
                    row = db.execute(
                        "SELECT * FROM documents WHERE id=?", (number,)
                    ).fetchone()
                    row_dict = dict(row)
                    if row_dict.get("stored"):
                        try:
                            removed_sha256 = file_digest(
                                workspace.artifact(row_dict, "stored")
                            )
                        except (OSError, ValueError):
                            removed_sha256 = None
                    folder = managed_directory(workspace, row_dict)
                    if folder:
                        moved = workspace.root / (".removed-" + uuid4().hex)
                        folder.rename(moved)
                    db.execute(
                        """INSERT INTO workspace_settings(name,value) VALUES('document_id',?)
                           ON CONFLICT(name) DO UPDATE SET value=max(CAST(value AS INTEGER),excluded.value)""",
                        (number,),
                    )
                    db.execute("DELETE FROM documents WHERE id=?", (number,))
                else:
                    db.execute(
                        "UPDATE documents SET archived=? WHERE id=?",
                        (action == "archive", number),
                    )
        except (OSError, ValueError, sqlite3.Error) as exc:
            if moved and moved.is_dir():
                try:
                    moved.rename(folder)
                except OSError:
                    results.append(
                        dict(
                            id=number,
                            status="PARTIAL",
                            reason="Workspace-Kopie konnte nicht zurückgestellt werden",
                            residue=str(moved),
                        )
                    )
                    continue
            results.append(dict(id=number, status="ERROR", reason=type(exc).__name__))
            continue
        if moved:
            try:
                shutil.rmtree(moved)
            except OSError:
                results.append(
                    dict(
                        id=number,
                        status="PARTIAL",
                        reason="Dateibereinigung unvollständig",
                        residue=str(moved),
                    )
                )
                continue
        if action == "remove" and removed_sha256:
            _cleanup_orphaned_display_cache(workspace, removed_sha256)
        results.append(
            dict(
                id=number,
                status={
                    "remove": "REMOVED",
                    "archive": "ARCHIVED",
                    "restore": "RESTORED",
                }[action],
            )
        )
    return results


def save_export(workspace, name, content):
    destination = output_directory(workspace)
    safe_name = Path(name).name
    target = destination / (uuid4().hex + "-" + safe_name)
    with target.open("xb") as file:
        try:
            if isinstance(content, Path):
                with content.open("rb") as source:
                    shutil.copyfileobj(source, file)
            else:
                file.write(content)
        except BaseException:
            file.close()
            target.unlink()
            raise
    return str(target)


def workflow_settings(workspace, update=None):
    from .conversion_config import (
        CONVERSION_DEFAULTS,
        DEFAULT_VISION_PROMPT,
        normalize_conversion_settings,
    )
    from .prompts_config import (
        normalize_base_prompts,
        normalize_stage_prompts,
        stage_prompt_catalog,
    )

    defaults = dict(
        profiles=dict(A="", B="", C="", vision=""),
        vision=dict(
            enabled=True,
            mode="api",
            description=True,
            classification=False,
            chart=False,
            picture_area_threshold=0,
            scale=2.0,
            prompt="",
            default_prompt=DEFAULT_VISION_PROMPT,
            timeout=VISION_TIMEOUT_DEFAULT,
        ),
        conversion=dict(CONVERSION_DEFAULTS),
        stage_prompts=dict(vision="", A="", B="", C=""),
        base_prompts=dict(vision="", A="", B="", C=""),
        stage_prompt_catalog=stage_prompt_catalog(),
        output_language="auto",
    )
    stored = workspace.setting("workflow") or {}
    if not isinstance(stored, dict):
        stored = {}
    if update is None:
        current = stored
    else:
        if not isinstance(update, dict):
            raise ValueError("Ungültige Workflow-Einstellungen")
        current = dict(stored)
        for field in ("profiles", "vision", "conversion", "stage_prompts", "base_prompts"):
            if field in update:
                val = update[field]
                if not isinstance(val, dict):
                    raise ValueError("Ungültige Workflow-Einstellungen")
                if field == "profiles":
                    current[field] = dict(val)
                else:
                    merged_sec = dict(stored.get(field) or {})
                    merged_sec.update(val)
                    current[field] = merged_sec
        if "output_language" in update:
            current["output_language"] = update["output_language"]

    if not isinstance(current, dict) or any(
        not isinstance(current.get(field, {}), dict)
        for field in ("profiles", "vision", "conversion", "stage_prompts", "base_prompts")
    ):
        raise ValueError("Ungültige Workflow-Einstellungen")
    out_lang = current.get("output_language", "auto")
    if out_lang not in ("auto", "de", "en"):
        raise ValueError("Ungültige Ausgabesprache")
    defaults["output_language"] = out_lang
    defaults["conversion"] = normalize_conversion_settings(current.get("conversion"))
    names = {p["name"] for p in workspace.profiles()}
    for step in defaults["profiles"]:
        value = current.get("profiles", {}).get(step, "")
        if value in names:
            defaults["profiles"][step] = value
        elif value and update is not None and "profiles" in update:
            raise ValueError("Dieses Modellprofil ist nicht gespeichert")
    for key, fallback in defaults["vision"].items():
        if key == "default_prompt":
            continue
        value = current.get("vision", {}).get(key, fallback)
        if key == "timeout" and value is None:
            value = fallback
        if key == "prompt":
            if value is None:
                value = ""
            if not isinstance(value, str) or len(value) > 8000:
                raise ValueError("Ungültiger Vision-Prompt")
            defaults["vision"][key] = value.strip()
            continue
        if key == "scale":
            if value in (None, ""):
                value = fallback
            if type(value) not in (int, float) or not 0.5 <= float(value) <= 4.0:
                raise ValueError("Ungültige Vision-Bildskalierung")
            defaults["vision"][key] = round(float(value), 2)
            continue
        if isinstance(fallback, bool) and type(value) is not bool:
            raise ValueError("Ungültige Bildoption")
        if key == "mode" and value not in ("api", "inline"):
            raise ValueError("Ungültiger Bildmodus")
        if key == "picture_area_threshold" and (
            type(value) not in (int, float) or not 0 <= value <= 1
        ):
            raise ValueError("Ungültiger Bildschwellwert")
        if (
            key == "timeout"
            and value is not None
            and (type(value) not in (int, float) or not 0 < value < float("inf"))
        ):
            raise ValueError("Ungültige Vision-Zeitgrenze")
        defaults["vision"][key] = value

    defaults["base_prompts"] = normalize_base_prompts(current.get("base_prompts"))
    raw_stage_prompts = current.get("stage_prompts")
    has_explicit_vision_stage = (
        isinstance(raw_stage_prompts, dict) and "vision" in raw_stage_prompts
    )
    defaults["stage_prompts"] = normalize_stage_prompts(
        raw_stage_prompts,
        vision_prompt_fallback=""
        if has_explicit_vision_stage or defaults["base_prompts"]["vision"]
        else defaults["vision"]["prompt"],
    )
    if (
        isinstance(update, dict)
        and "vision" in update
        and "prompt" in (update.get("vision") or {})
        and "base_prompts" not in update
        and "stage_prompts" not in update
    ):
        defaults["base_prompts"] = normalize_base_prompts(
            {**defaults["base_prompts"], "vision": defaults["vision"]["prompt"]}
        )
    effective_custom_vis = (
        defaults["base_prompts"]["vision"] or defaults["stage_prompts"]["vision"]
    )
    defaults["vision"]["prompt"] = effective_custom_vis

    if update is not None:
        to_store = {
            k: v
            for k, v in defaults.items()
            if k not in ("stage_prompt_catalog",)
        }
        to_store["vision"] = {
            k: v for k, v in defaults["vision"].items() if k != "default_prompt"
        }
        workspace.set_setting("workflow", to_store)
    return defaults
