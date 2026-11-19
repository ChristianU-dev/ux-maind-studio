"""Local document workspace; native conversion/extraction, explicit source checks and notes."""

from hashlib import sha256
import json
import os
import re
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from uuid import uuid4


from . import enrichment, models
from .evidence import (
    READABLE_SCHEMAS,
    SCHEMA_VERSION,
    Sources,
    file_digest,
    ledger_coverage,
    model_source,
    observation_view,
)
from .templates import UXEvidenceDocument


def _native_confidence(report):
    if report is None:
        return None
    import math

    raw = report.model_dump(mode="json") if hasattr(report, "model_dump") else {}
    clean = {}
    for key in (
        "mean_grade",
        "low_grade",
        "mean_score",
        "low_score",
        "parse_score",
        "layout_score",
        "table_score",
        "ocr_score",
    ):
        val = raw.get(key)
        if isinstance(val, float):
            if math.isfinite(val):
                clean[key] = round(val, 4)
        elif isinstance(val, str) and val and val != "unspecified":
            clean[key] = val
    return clean or None


@lru_cache(maxsize=8)
def load_document(path, stamp):
    from docling_core.types.doc import DoclingDocument

    return DoclingDocument.load_from_json(path)


class Workspace:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, name TEXT, origin TEXT,
                    stored TEXT, native TEXT, status TEXT, error TEXT);
                CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, document INTEGER, at TEXT, result TEXT);
                CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, run INTEGER, item INTEGER, at TEXT, text TEXT);
                CREATE TABLE IF NOT EXISTS workspace_settings(name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS profiles(name TEXT PRIMARY KEY, options TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS ux_objects(id INTEGER PRIMARY KEY, kind TEXT, at TEXT, proposal TEXT, metadata TEXT);
                CREATE TABLE IF NOT EXISTS ux_decisions(id INTEGER PRIMARY KEY, target_type TEXT, target TEXT, at TEXT, origin TEXT, action TEXT, reason TEXT, payload TEXT);
                CREATE INDEX IF NOT EXISTS ux_decision_target ON ux_decisions(target_type,target,id);
                CREATE TABLE IF NOT EXISTS ux_review_sessions(
                    session_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    role_on_this_machine TEXT NOT NULL DEFAULT 'origin',
                    created_at TEXT NOT NULL,
                    scope_json TEXT NOT NULL,
                    reviewer_a_json TEXT NOT NULL,
                    reviewer_b_json TEXT NOT NULL,
                    baseline_sha256 TEXT NOT NULL,
                    baseline_json TEXT NOT NULL,
                    id_map_json TEXT NOT NULL,
                    submitted_a_at TEXT,
                    submitted_b_at TEXT,
                    released_at TEXT,
                    resolutions_json TEXT NOT NULL DEFAULT '{}',
                    imported_receipts_json TEXT NOT NULL DEFAULT '[]'
                );
            """)
            columns = {r["name"] for r in db.execute("PRAGMA table_info(documents)")}
            if "diagnostics" not in columns:
                db.execute(
                    "ALTER TABLE documents ADD COLUMN diagnostics TEXT DEFAULT '{}'"
                )
            if "archived" not in columns:
                db.execute(
                    "ALTER TABLE documents ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
                )
            if "corpus_role" not in columns:
                db.execute(
                    "ALTER TABLE documents ADD COLUMN corpus_role TEXT NOT NULL DEFAULT 'evidence'"
                )

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.root / "workspace.sqlite", timeout=30.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        try:
            with db:
                yield db
        finally:
            db.close()

    def setting(self, name):
        with self.db() as db:
            row = db.execute(
                "SELECT value FROM workspace_settings WHERE name=?", (name,)
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["value"])
        except ValueError:
            return row["value"]

    def set_setting(self, name, value):
        with self.db() as db:
            db.execute(
                "INSERT INTO workspace_settings(name,value) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                (name, json.dumps(value, ensure_ascii=False)),
            )

    def files(self, offset=0, search="", archived=False, sort=""):
        order = {
            "newest": "id DESC",
            "oldest": "id ASC",
            "name": "name COLLATE NOCASE, id",
            "status": "status, id",
        }.get(sort, "id")
        like = "%" + search + "%"
        with self.db() as db:
            total = db.execute(
                "SELECT count(*) FROM documents WHERE archived=? AND (name LIKE ? OR origin LIKE ?)",
                (archived, like, like),
            ).fetchone()[0]
            rows = db.execute(
                f"""SELECT documents.*, COALESCE(
                    (SELECT json_extract(result,'$.status') FROM runs
                     WHERE document=documents.id AND json_extract(result,'$.status') != 'ERROR'
                     ORDER BY id DESC LIMIT 1),
                    (SELECT json_extract(result,'$.status') FROM runs
                     WHERE document=documents.id ORDER BY id DESC LIMIT 1)
                ) AS extraction FROM documents WHERE archived=? AND (name LIKE ? OR origin LIKE ?)
                ORDER BY {order} LIMIT 100 OFFSET ?""",
                (archived, like, like, max(0, offset)),
            ).fetchall()
        return {"total": total, "items": [dict(r) for r in rows]}

    def file(self, number):
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM documents WHERE id=?", (int(number),)
            ).fetchone()
        if row is None:
            raise FileNotFoundError("Dokument fehlt")
        return dict(row)

    def set_corpus_role(self, numbers, role: str):
        if role not in ("evidence", "reference"):
            raise ValueError("Ungültige Korpus-Rolle (erlaubt: 'evidence' oder 'reference')")
        ids = [int(n) for n in dict.fromkeys(numbers or ())]
        if not ids:
            return {"updated": 0, "corpus_role": role}
        placeholders = ",".join("?" for _ in ids)
        with self.db() as db:
            cur = db.execute(
                f"UPDATE documents SET corpus_role=? WHERE id IN ({placeholders})",
                (role, *ids),
            )
        return {"updated": cur.rowcount, "corpus_role": role, "documents": ids}

    def artifact(self, row, field):
        if not row.get(field):
            raise FileNotFoundError("Kein verfügbares Artefakt")
        path = self.root / row[field]
        if (
            any(
                p.is_symlink() or p.is_junction()
                for p in (path, *path.parents)
                if p.is_relative_to(self.root)
            )
            or not path.resolve().is_relative_to(self.root)
            or not path.is_file()
        ):
            raise ValueError("Unsicherer Artefaktpfad")
        return path

    def document(self, row):
        path = self.artifact(row, "native")
        return load_document(str(path), path.stat().st_mtime_ns)

    def versions(self, row):
        path = self.artifact(row, "native")
        directory = path.parent / "enrichment"
        return sorted(
            (
                json.loads(meta.read_text(encoding="utf-8"))
                for meta in directory.glob("*/receipt*.json")
            ),
            key=lambda receipt: receipt["at"],
        )

    def preferred_version(self, row, versions=None):
        return next(
            (
                r["version"]
                for r in reversed(self.versions(row) if versions is None else versions)
                if r["status"] in ("success", "partial_success")
                and r["version"] != r["base_version"]
                and (
                    r.get("kind") == "conversion"
                    or any(
                        p.get("description")
                        or p.get("classification")
                        or p.get("chart")
                        for p in r["pictures"]
                    )
                )
            ),
            None,
        )

    def latest_conversion(self, row):
        return next(
            (
                v["version"]
                for v in reversed(self.versions(row))
                if v.get("kind") == "conversion"
                and v["status"] in ("success", "partial_success")
            ),
            None,
        )

    def version_row(self, row, version):
        if version is None:
            return row
        if (
            not isinstance(version, str)
            or len(version) != 64
            or any(c not in "0123456789abcdef" for c in version)
        ):
            raise ValueError("Ungültige Docling-Version")
        base = self.artifact(row, "native")
        if file_digest(base) == version:
            return row
        path = base.parent / "enrichment" / version / "document.json"
        versioned = dict(
            row, native=str(path.relative_to(self.root)), native_version=version
        )
        if file_digest(self.artifact(versioned, "native")) != version:
            raise ValueError("Docling-Version weicht vom gespeicherten Hash ab")
        ancestry, conversions = {}, {}
        for receipt in reversed(self.versions(row)):
            digest, parent = receipt["version"], receipt.get("base_version")
            if receipt.get("kind") == "conversion":
                conversions.setdefault(digest, receipt["diagnostics"])
            elif digest != parent:
                ancestry.setdefault(digest, parent)
        seen = set()
        while version and version not in seen:
            seen.add(version)
            if version in conversions:
                versioned["diagnostics"] = json.dumps(conversions[version])
                break
            version = ancestry.get(version)
        return versioned

    def save_version(self, base, receipt, content=None):
        folder = base.parent / "enrichment" / receipt["version"]
        if not folder.resolve().is_relative_to(base.parent) or any(
            p.is_junction() or p.is_symlink() for p in (folder, folder.parent)
        ):
            raise ValueError("Unsicherer Versionsordner")
        folder.mkdir(parents=True, exist_ok=True)
        files = {f"receipt-{uuid4().hex}.json": json.dumps(receipt).encode()}
        if content is not None:
            files = {"document.json": content, **files}
        for name, value in files.items():
            dest = folder / name
            if not dest.exists():
                temp = folder / (uuid4().hex + ".tmp")
                temp.write_bytes(value)
                temp.replace(dest)

    def enrich(
        self,
        numbers,
        vision,
        progress=lambda text: None,
        versions=None,
        *,
        automatic=False,
        retry=False,
    ):
        from docling_core.types.doc import ContentLayer

        counts = {}
        converter = None
        config = {}
        plan = enrichment.import_plan(vision) if automatic else None
        blocked = None if plan == "planned" else plan or enrichment.manual_plan(vision)
        for number in numbers:
            row = self.file(number)

            def emit(status=None, **fields):
                progress(
                    dict(
                        kind="vision",
                        phase="enrich",
                        document=number,
                        document_name=row["name"],
                        status=status,
                        **fields,
                    )
                )

            emit()
            try:
                from time import perf_counter

                t0_vis = perf_counter()
                destination = self.artifact(row, "native")
                requested_ver = (versions or {}).get(str(number))
                if requested_ver is None and row["native"]:
                    requested_ver = self.preferred_version(row) or self.latest_conversion(row)
                active = self.version_row(row, requested_ver)
                base = self.artifact(active, "native")
                original = self.document(active)
                conversion = json.loads(active.get("diagnostics") or "{}").get(
                    "configuration"
                )
                pictures = enrichment.pictures(original, {}, configuration=conversion)
                unavailable = (
                    "no_pictures"
                    if not pictures
                    else (
                        "no_pixels"
                        if not any(p["pixel_available"] for p in pictures)
                        else None
                    )
                )
                if unavailable or blocked:
                    reason = unavailable or blocked
                    state = (
                        "skipped"
                        if reason in ("no_pictures", "no_vision_tasks")
                        else "error"
                        if blocked and not unavailable
                        else "partial_success"
                    )
                    emit(
                        state,
                        reason=reason,
                        pictures=len(pictures),
                        pixels=sum(p["pixel_available"] for p in pictures),
                    )
                    self.record_enrichment_failure(
                        number, {"status": state, "reason": reason}
                    )
                    counts[state] = counts.get(state, 0) + 1
                    continue
                if converter is None:
                    from . import library
                    from .prompts_config import resolve_vision_prompt

                    wf_cfg = library.workflow_settings(self)
                    conv_cfg = wf_cfg.get("conversion")
                    effective_v_prompt = resolve_vision_prompt(
                        vision_cfg=vision,
                        stage_prompts=wf_cfg.get("stage_prompts"),
                        base_prompts=wf_cfg.get("base_prompts"),
                        output_language=wf_cfg.get("output_language", "auto"),
                    )
                    converter, config = enrichment.converter(
                        dict(vision, prompt=effective_v_prompt), conversion=conv_cfg
                    )
                source = enrichment.retry_input(original, base) if retry else base
                with enrichment.vision_diagnostics() as api_diagnostics:
                    result = converter.convert(source, raises_on_error=False)
                derived = result.document

                def structure(doc):
                    for item, _ in doc.iterate_items(
                        included_content_layers=set(ContentLayer),
                        traverse_pictures=True,
                    ):
                        yield item.model_dump(
                            mode="json",
                            exclude={"meta", "annotations"},
                            exclude_computed_fields=True,
                        )

                same_refs = list(structure(original)) == list(structure(derived))
                same_refs = same_refs and original.pages == derived.pages
                if not same_refs:
                    raise ValueError(
                        "Referenzen in der abgeleiteten Docling-Version weichen ab"
                    )
                for src_item, dst_item in zip(
                    (
                        item
                        for item, _ in original.iterate_items(
                            included_content_layers=set(ContentLayer),
                            traverse_pictures=True,
                        )
                    ),
                    (
                        item
                        for item, _ in derived.iterate_items(
                            included_content_layers=set(ContentLayer),
                            traverse_pictures=True,
                        )
                    ),
                    strict=True,
                ):
                    custom = src_item.meta.get_custom_part() if src_item.meta else {}
                    for k, v in custom.items():
                        if k.startswith("ux_maind__"):
                            field_name = k[len("ux_maind__") :]
                            dst_item.meta = dst_item.meta or type(src_item.meta)()
                            if not getattr(dst_item.meta, k, None):
                                dst_item.meta.set_custom_field("ux_maind", field_name, v)
                packed = derived.model_dump_json(
                    by_alias=True, exclude_computed_fields=True
                ).encode()

                pictures = enrichment.pictures(
                    derived, config, configuration=conversion
                )
                base_hash = file_digest(base)
                digest = (
                    sha256(packed).hexdigest()
                    if enrichment.applied_metadata(original)
                    != enrichment.applied_metadata(derived)
                    else base_hash
                )
                status = result.status.value
                if status == "success" and enrichment.missing_output(pictures, config):
                    status = "partial_success"
                reason = enrichment.picture_outcome(pictures, status)
                receipt = dict(
                    reason=reason,
                    at=datetime.now(timezone.utc).isoformat(),
                    version=digest,
                    base_version=base_hash,
                    same_refs=same_refs,
                    status=status,
                    duration_s=round(perf_counter() - t0_vis, 2),
                    configuration=config,
                    pictures=pictures,
                    errors=[enrichment.error_receipt(e) for e in result.errors],
                    api_diagnostics=api_diagnostics,
                )
                self.save_version(
                    destination, receipt, packed if digest != base_hash else None
                )
            except Exception as error:
                status = "error"
                failure = dict(
                    document=number,
                    at=datetime.now(timezone.utc).isoformat(),
                    error=type(error).__name__,
                    configuration=config,
                )
                reason = "vision_failed" if row["native"] else "native_document_missing"
                failure["reason"] = reason
                counts.setdefault("errors", []).append(failure)
                self.record_enrichment_failure(number, failure)
                emit(status, reason=reason, error=type(error).__name__)
            else:
                emit(
                    status,
                    reason=reason,
                    version=digest,
                    **enrichment.picture_counts(pictures),
                )
            counts[status] = counts.get(status, 0) + 1
        return counts

    def record_enrichment_failure(self, number, failure):
        failure = {"at": datetime.now(timezone.utc).isoformat(), **failure}
        with self.db() as db:
            db.execute(
                """UPDATE documents SET diagnostics=json_insert(
                       CASE WHEN json_type(diagnostics,'$.enrichment_errors')='array'
                            THEN diagnostics
                            ELSE json_set(coalesce(diagnostics,'{}'),'$.enrichment_errors',json('[]'))
                       END, '$.enrichment_errors[#]', json(?)
                   ) WHERE id=?""",
                (json.dumps(failure, ensure_ascii=False), number),
            )

    def profiles(self):
        with self.db() as db:
            return [
                dict(name=r["name"], options=json.loads(r["options"]))
                for r in db.execute("SELECT * FROM profiles ORDER BY name")
            ]

    def save_profile(self, name, options):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Profilname erforderlich")
        clean = models.profile_options(options)
        with self.db() as db:
            db.execute(
                "INSERT INTO profiles(name,options) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET options=excluded.options",
                (name.strip(), json.dumps(clean)),
            )

    def delete_profile(self, name):
        with self.db() as db:
            db.execute("DELETE FROM profiles WHERE name=?", (name,))

    def summary(self, row):
        if not row["native"]:
            return dict(
                pages=[],
                counts={},
                tables=[],
                diagnostics=json.loads(row.get("diagnostics") or "{}"),
            )
        doc = self.document(row)
        base = self.file(row["id"]) if row.get("native_version") else row
        versions = self.versions(base)
        version = row.get("native_version") or file_digest(self.artifact(row, "native"))
        vision_receipt = next(
            (
                v
                for v in reversed(versions)
                if v["version"] == version and v.get("kind") != "conversion"
            ),
            None,
        )
        diagnostics = json.loads(row.get("diagnostics") or "{}")
        pictures = enrichment.pictures(
            doc,
            (vision_receipt or {}).get("configuration")
            or diagnostics.get("enrichment", {}),
            configuration=diagnostics.get("configuration"),
        )
        return dict(
            pages=[
                dict(page_no=p.page_no, image=bool(p.image), size=p.size.model_dump())
                for p in doc.pages.values()
            ],
            counts=dict(
                texts=len(doc.texts), pictures=len(doc.pictures), tables=len(doc.tables)
            ),
            tables=[
                dict(ref=t.self_ref, rows=t.data.num_rows, columns=t.data.num_cols)
                for t in doc.tables
            ],
            diagnostics=diagnostics,
            pictures=pictures,
            picture_counts=enrichment.picture_counts(pictures),
            vision_receipt=vision_receipt
            and {
                k: vision_receipt.get(k)
                for k in ("status", "reason", "api_diagnostics", "configuration")
            },
            versions=versions,
            version=version,
            base_version=file_digest(self.artifact(base, "native")),
            preferred_version=self.preferred_version(base, versions),
        )

    def elements(self, row, offset=0, search=""):
        from docling_core.types.doc import ContentLayer
        from itertools import islice

        doc = self.document(row)

        def selected():
            for item, _ in doc.iterate_items(
                included_content_layers=set(ContentLayer), traverse_pictures=True
            ):
                text = getattr(item, "text", "")
                if (
                    search
                    and search.casefold() not in (text + " " + item.self_ref).casefold()
                ):
                    continue
                yield dict(
                    ref=item.self_ref,
                    label=item.label.value,
                    layer=item.content_layer.value,
                    text=text[:180],
                    pages=list(dict.fromkeys(p.page_no for p in item.prov)),
                )

        total = sum(1 for _ in selected())
        return dict(
            total=total,
            items=list(islice(selected(), max(0, offset), max(0, offset) + 100)),
        )

    def web_document(self, row):
        """Native aliases; only image URIs change in a shallow display copy, original unchanged."""
        doc = self.document(row)
        version_query = (
            f"&version={row['native_version']}" if row.get("native_version") else ""
        )

        def local_image(image, kind, index):
            return (
                image.model_copy(
                    update={
                        "uri": f"/document/{row['id']}/resource?kind={kind}&index={index}{version_query}"
                    }
                )
                if image
                else None
            )

        display = doc.model_copy(
            update={
                "pages": {
                    n: p.model_copy(update={"image": local_image(p.image, "page", n)})
                    for n, p in doc.pages.items()
                },
                "pictures": [
                    p.model_copy(update={"image": local_image(p.image, "picture", n)})
                    for n, p in enumerate(doc.pictures)
                ],
                "tables": [
                    t.model_copy(update={"image": local_image(t.image, "table", n)})
                    for n, t in enumerate(doc.tables)
                ],
            }
        )
        return display.model_dump_json(by_alias=True, exclude_computed_fields=True)

    def export_markdown(self, row):
        """Export the selected native DoclingDocument version as Markdown including speaker notes."""
        from docling_core.types.doc import ContentLayer

        doc = self.document(row)
        return doc.export_to_markdown(
            included_content_layers={ContentLayer.BODY, ContentLayer.NOTES}
        )

    def resource(self, row, kind, index):
        import base64

        doc = self.document(row)
        image = (
            doc.pages[index].image
            if kind == "page"
            else getattr(doc, {"picture": "pictures", "table": "tables"}[kind])[
                index
            ].image
        )
        uri = str(image.uri) if image else ""
        if not uri.startswith("data:image/") or ";base64," not in uri:
            raise ValueError("Keine eingebettete native Bildressource")
        prefix, data = uri.split(",", 1)
        return base64.b64decode(data, validate=True), prefix[5:].split(";")[0]

    def cells(self, row, ref, start=0, column=0, search="", offset=0):
        from docling_core.types.doc import RefItem, TableItem
        from itertools import islice

        table = RefItem(cref=ref).resolve(self.document(row))
        if not isinstance(table, TableItem):
            raise ValueError("Keine native Tabelle")
        first = max(0, start)
        left = max(0, column)
        stop = min(first + 30, table.data.num_rows)
        right = min(left + 12, table.data.num_cols)

        def selected():
            for c in table.data.table_cells:
                if search:
                    if search.casefold() not in c.text.casefold():
                        continue
                elif not (
                    c.start_row_offset_idx < stop
                    and c.end_row_offset_idx > first
                    and c.start_col_offset_idx < right
                    and c.end_col_offset_idx > left
                ):
                    continue
                yield c

        total = sum(1 for _ in selected())
        cells = [
            dict(
                c.model_dump(mode="json"),
                visible_span=None
                if search
                else dict(
                    row=max(first, c.start_row_offset_idx),
                    row_end=min(stop, c.end_row_offset_idx),
                    column=max(left, c.start_col_offset_idx),
                    column_end=min(right, c.end_col_offset_idx),
                ),
            )
            for c in islice(selected(), max(0, offset), max(0, offset) + 100)
        ]
        return dict(
            ref=ref,
            rows=table.data.num_rows,
            columns=table.data.num_cols,
            start=first,
            column=left,
            stop=stop,
            right=right,
            total=total,
            cells=cells,
        )

    def import_paths(
        self, paths, progress=lambda text: None, vision=None, *, convert=True
    ):
        from . import library

        vision = {"mode": "api", **vision} if vision is not None else None
        conv_cfg = library.workflow_settings(self).get("conversion")
        converter, config = (
            enrichment.converter(conversion=conv_cfg) if convert else (None, {})
        )
        config["state"] = (
            "pending_conversion" if (vision or {}).get("enabled", True) else "disabled"
        )
        with self.db() as db:
            before = db.execute("SELECT coalesce(max(id),0) FROM documents").fetchone()[
                0
            ]
        for selected in paths:
            path = Path(selected).absolute()
            if path.is_dir() and not path.is_symlink() and not path.is_junction():
                for parent, dirs, files in os.walk(
                    path,
                    followlinks=False,
                    onerror=lambda exc: self.import_one(
                        Path(exc.filename), converter, progress, config, exc
                    ),
                ):
                    for name in list(dirs):
                        if name in (".git", ".idea", "__pycache__", ".venv", "node_modules"):
                            dirs.remove(name)
                            continue
                        entry = Path(parent) / name
                        if (
                            entry.resolve() == self.root
                            or entry.is_symlink()
                            or entry.is_junction()
                        ):
                            dirs.remove(name)
                            self.import_one(entry, converter, progress, config)
                    for name in files:
                        if name.startswith("~$") or name in (".DS_Store", "Thumbs.db", "desktop.ini"):
                            continue
                        self.import_one(
                            Path(parent) / name, converter, progress, config
                        )
            else:
                self.import_one(path, converter, progress, config)
        with self.db() as db:
            report = {
                r["status"]: r["n"]
                for r in db.execute(
                    "SELECT status,count(*) AS n FROM documents WHERE id>? GROUP BY status",
                    (before,),
                )
            }
            pictures = [
                r["id"]
                for r in db.execute(
                    "SELECT id FROM documents WHERE id>? AND native IS NOT NULL "
                    "AND json_array_length(diagnostics,'$.pictures')>0",
                    (before,),
                )
            ]
        if pictures and vision is not None:
            plan = enrichment.import_plan(vision)
            report["vision"] = (
                self.enrich(pictures, vision, progress=progress)
                if plan == "planned"
                else {plan: len(pictures)}
            )
            if plan != "planned":
                for number in pictures:
                    self.vision_plan(self.file(number), plan, progress)
        return report

    def import_one(self, path, converter, progress, config, failure=None):
        progress(dict(phase="import_paths", document_name=path.name))
        row = dict(
            name=path.name,
            origin=str(path),
            stored=None,
            native=None,
            status="ERROR",
            error=None,
            diagnostics="{}",
        )
        try:
            if failure:
                raise failure
            # Skip just this redirected/unreadable entry, never the entire folder.
            if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
                raise ValueError("Umleitung übersprungen")
            if path.resolve().is_relative_to(self.root):
                raise ValueError("Interner Arbeitsbereich übersprungen")
            if not path.is_file():
                raise ValueError("Keine lesbare Datei")
            directory = self.root / uuid4().hex
            directory.mkdir()
            (directory / "original").mkdir()
            original = directory / "original" / path.name
            shutil.copyfile(path, original)
            row["stored"] = str(original.relative_to(self.root))
            row["status"] = "pending_conversion"
            row["diagnostics"] = json.dumps(dict(enrichment=config))
            if converter is not None:
                row = self.convert_copy(row, converter, config, progress)
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        telemetry_meta = row.pop("_telemetry", None) or {}
        with self.db() as db:
            inserted = db.execute(
                """INSERT INTO documents(id,name,origin,stored,native,status,error,diagnostics)
                   SELECT max(coalesce(max(id),0),coalesce((SELECT CAST(value AS INTEGER)
                       FROM workspace_settings WHERE name='document_id'),0))+1,
                      :name,:origin,:stored,:native,:status,:error,:diagnostics FROM documents""",
                row,
            ).lastrowid
        progress(
            dict(
                kind="inventory",
                phase="import_paths",
                document=inserted,
                document_name=path.name,
                status="success" if row["stored"] else "error",
            )
        )
        if converter is not None and row["stored"]:
            progress(
                dict(
                    kind="conversion",
                    phase="conversion",
                    document=inserted,
                    document_name=path.name,
                    status=row["status"],
                    native=bool(row["native"]),
                    **telemetry_meta,
                )
            )

    def convert_copy(self, row, converter, config, progress):
        from time import perf_counter

        t0 = perf_counter()
        try:
            original = self.artifact(row, "stored")
            timings = {}
            confidence = None
            if original.suffix.lower() == ".txt":
                from docling_core.types.doc import DocItemLabel, DoclingDocument

                raw_text = (
                    original.read_text(encoding="utf-8", errors="replace")
                    .replace("\r\n", "\n")
                    .replace("\r", "\n")
                )
                doc = DoclingDocument(name=original.stem)
                blocks = [
                    b.strip("\n")
                    for b in re.split(r"\n(?:\s*\n)+", raw_text)
                    if b.strip()
                ]
                if not blocks and raw_text.strip("\n"):
                    blocks = [raw_text.strip("\n")]
                for block in blocks:
                    doc.add_text(label=DocItemLabel.TEXT, text=block)
                row.update(status="success", error=None)
                configuration = dict(
                    format="txt",
                    source="Native plain-text loader",
                    paragraphs=len(blocks),
                )
            else:
                result = converter.convert(
                    original,
                    raises_on_error=False,
                    progress_callback=lambda e: progress(
                        dict(
                            e.model_dump(mode="json"),
                            phase="conversion",
                            document_name=row["name"],
                        )
                    ),
                )
                row.update(
                    status=result.status.value,
                    error="\n".join(e.error_message for e in result.errors) or None,
                )
                doc = result.document
                timings = {
                    k: v.model_dump(mode="json") for k, v in result.timings.items()
                }
                confidence = _native_confidence(getattr(result, "confidence", None))
                native_format = getattr(getattr(result, "input", None), "format", None)
                configuration = dict(
                    format=native_format.value if native_format else "unknown",
                    source="Native format backend",
                )
            conv_opts = (config or {}).get("conversion_options") or {}
            if configuration["format"] in ("pdf", "image"):
                configuration.update(
                    do_ocr=conv_opts.get("do_ocr", True),
                    force_full_page_ocr=conv_opts.get("force_full_page_ocr", False),
                    do_table_structure=conv_opts.get("do_table_structure", True),
                    table_mode=conv_opts.get("table_mode", "accurate"),
                    images_scale=conv_opts.get("images_scale", 1.0),
                    ocr="Native OcrAutoOptions",
                    page_images=True,
                    picture_images=True,
                )
            row["_telemetry"] = dict(
                duration_s=round(perf_counter() - t0, 2),
                items_count=len(doc.texts) + len(doc.tables) + len(doc.pictures),
                **(
                    {"confidence_grade": confidence["mean_grade"]}
                    if confidence and confidence.get("mean_grade")
                    else {}
                ),
            )
            if row["status"] in ("success", "partial_success"):
                if configuration["format"] == "pptx" and doc.pages:
                    from .office import (
                        attach_slide_views,
                        office_pdf,
                        office_renderer,
                        pptx_formatting,
                    )

                    configuration["explicit_text_formats"] = pptx_formatting(
                        original, doc
                    )
                    if office_renderer():
                        try:
                            display_pdf, identity = office_pdf(
                                original, self.root / "display"
                            )
                            configuration["slide_view"] = attach_slide_views(
                                display_pdf, identity, doc
                            )
                        except Exception as exc:
                            configuration["slide_view"] = {"status": type(exc).__name__}
                elif configuration["format"] == "docx":
                    from .office import docx_formatting

                    configuration["explicit_text_formats"] = docx_formatting(
                        original, doc
                    )
                elif configuration["format"] == "pdf" and doc.pictures and doc.pages:
                    from .office import attach_pdf_page_views

                    configuration["page_view"] = attach_pdf_page_views(
                        doc, file_digest(original)
                    )
            pictures = enrichment.pictures(doc, config, configuration=configuration)
            if row["status"] == "success" and enrichment.missing_output(
                pictures, config
            ):
                row["status"] = "partial_success"
            diagnostics_payload = dict(
                timings=timings,
                configuration=configuration,
                enrichment=config,
                pictures=pictures,
            )
            if confidence:
                diagnostics_payload["confidence"] = confidence
            row["diagnostics"] = json.dumps(diagnostics_payload)
            if doc.texts or doc.tables or doc.pictures or doc.pages:
                packed = doc.model_dump_json(
                    by_alias=True, exclude_computed_fields=True
                ).encode()
                row["version"] = sha256(packed).hexdigest()
                if row["native"]:
                    base = self.artifact(row, "native")
                    version = row["version"]
                    actual = file_digest(base)
                    self.save_version(
                        base,
                        dict(
                            kind="conversion",
                            at=datetime.now(timezone.utc).isoformat(),
                            version=version,
                            base_version=actual,
                            status=row["status"],
                            pictures=pictures,
                            diagnostics=json.loads(row["diagnostics"]),
                        ),
                        packed if version != actual else None,
                    )
                else:
                    native = original.parent.parent / "document.json"
                    native.write_bytes(packed)
                    row["native"] = str(native.relative_to(self.root))
            return row
        except Exception as exc:
            row.update(status="ERROR", error=type(exc).__name__)
            return row

    def vision_plan(self, row, reason, progress):
        with self.db() as db:
            db.execute(
                "UPDATE documents SET diagnostics=json_set(coalesce(diagnostics,'{}'),'$.vision_plan',?) WHERE id=?",
                (reason, row["id"]),
            )
        progress(
            dict(
                kind="vision",
                phase="enrich",
                document=row["id"],
                document_name=row["name"],
                reason=reason,
                status="skipped"
                if reason in ("no_pictures", "disabled", "no_vision_tasks")
                else "waiting",
            )
        )

    def convert_selected(self, numbers, vision=None, progress=lambda text: None):
        from . import library

        vision = {"mode": "api", **vision} if vision is not None else None
        conv_cfg = library.workflow_settings(self).get("conversion")
        converter, config = enrichment.converter(conversion=conv_cfg)
        plan = None
        config["state"] = "pending_conversion"
        report = []
        for number in dict.fromkeys(map(int, numbers)):
            try:
                row = self.file(number)
                progress(
                    dict(phase="conversion", document=number, document_name=row["name"])
                )
                if row["archived"]:
                    raise ValueError("Dokument zuerst aus dem Archiv wiederherstellen")
                result = self.convert_copy(dict(row), converter, config, progress)
                telemetry_meta = result.pop("_telemetry", None) or {}
                if not row["native"]:
                    with self.db() as db:
                        db.execute(
                            """UPDATE documents SET native=:native,status=:status,error=:error,
                               diagnostics=:diagnostics WHERE id=:id""",
                            result,
                        )
                else:
                    attempt = dict(
                        at=datetime.now(timezone.utc).isoformat(),
                        status=result["status"],
                        version=result.get("version"),
                    )
                    with self.db() as db:
                        db.execute(
                            """UPDATE documents SET status=?, error=?,
                               diagnostics=json_set(coalesce(diagnostics,'{}'),'$.last_conversion',json(?))
                               WHERE id=?""",
                            (
                                result["status"],
                                result.get("error"),
                                json.dumps(attempt),
                                number,
                            ),
                        )
                report.append(
                    dict(
                        id=number,
                        status=result["status"],
                        native=bool(result["native"]),
                        version=result.get("version"),
                    )
                )
                progress(
                    dict(
                        kind="conversion",
                        phase="conversion",
                        document=number,
                        document_name=row["name"],
                        status=result["status"],
                        native=bool(result["native"]),
                        **telemetry_meta,
                    )
                )
                if result["native"] and vision is not None:
                    pictures = json.loads(result["diagnostics"]).get("pictures", [])
                    if not pictures:
                        self.vision_plan(row, "no_pictures", progress)
                    else:
                        if plan is None:
                            plan = enrichment.import_plan(vision)
                        if plan == "planned":
                            report[-1]["vision"] = self.enrich(
                                [number], vision, progress=progress
                            )
                        else:
                            self.vision_plan(row, plan, progress)
            except (OSError, ValueError) as exc:
                report.append(dict(id=number, status="ERROR", error=type(exc).__name__))
        return report

    def extract(self, numbers, options, progress=lambda text: None, versions=None):
        from importlib.metadata import version as installed_version
        from . import native_graph

        progress(dict(phase="model_access"))
        access_error = None
        try:
            client = models.connect(options)
            settings = models.describe(options, client=client)
        except Exception as error:
            access_error = (
                str(error)
                if isinstance(error, models.ModelAccessError)
                else type(error).__name__
            )
        counts = {}
        for number in dict.fromkeys(map(int, numbers)):
            row = self.file(number)

            def phase(ev):
                if isinstance(ev, dict):
                    payload = dict(ev)
                    payload.setdefault("kind", "A")
                    payload.setdefault("document", number)
                    payload.setdefault("document_name", row["name"])
                    payload.setdefault("model", options.get("model"))
                    progress(payload)
                else:
                    progress(
                        dict(
                            kind="A",
                            phase=ev,
                            document=number,
                            document_name=row["name"],
                            model=options.get("model"),
                        )
                    )

            phase("document_version")
            result = dict(
                schema_version=SCHEMA_VERSION,
                provider=options["provider"],
                model=options["model"],
                status="ERROR",
                observations=[],
                relations=[],
                issues=[],
                software={
                    p: installed_version(p)
                    for p in (
                        "docling",
                        "docling-core",
                        "docling-graph",
                        "litellm",
                        "pydantic",
                    )
                },
            )
            stage = "document_version"
            try:
                requested = (versions or {}).get(str(number))
                if requested is None and row["native"]:
                    requested = self.preferred_version(row)
                active = self.version_row(row, requested or None)
                source_hash = file_digest(self.artifact(row, "stored"))
                native_hash = file_digest(self.artifact(active, "native"))
                diagnostics = json.loads(active.get("diagnostics") or "{}")
                derivation = next(
                    (
                        v
                        for v in reversed(self.versions(row))
                        if v["version"] == native_hash
                        and (
                            v["version"] != v["base_version"]
                            or v.get("kind") == "conversion"
                        )
                    ),
                    None,
                )
                result.update(
                    source_sha256=source_hash,
                    document_version=native_hash,
                    conversion=diagnostics,
                    derivation=derivation,
                )
                stage = "model_access"
                if access_error:
                    result["diagnostic"] = dict(stage=stage, reason=access_error)
                    raise ValueError("Modellzugang oder Profil nicht verfügbar")
                stage = "native_extraction"
                phase(stage)
                sources = Sources(
                    self.document(active),
                    number,
                    native_hash,
                    configuration=diagnostics.get("configuration"),
                    source_sha256=source_hash,
                )
                from . import library
                from .evidence import extraction_pages
                from .prompts_config import apply_stage_prompt

                wf_cfg = library.workflow_settings(self)
                stage_a_base = str(
                    options.get("base_prompt")
                    if "base_prompt" in options
                    else (wf_cfg.get("base_prompts") or {}).get("A", "")
                ).strip()
                stage_a_prompt = str(
                    options.get("stage_prompt")
                    if "stage_prompt" in options
                    else (wf_cfg.get("stage_prompts") or {}).get("A", "")
                ).strip()
                stage_a_lang = options.get("output_language") or wf_cfg.get("output_language", "auto")
                active_template = apply_stage_prompt(
                    UXEvidenceDocument,
                    stage_a_prompt,
                    base_override=stage_a_base,
                    output_language=stage_a_lang,
                )
                with model_source(
                    sources,
                    self.artifact(active, "native"),
                    settings["options"].get("llm_input_format", "auto"),
                ) as path:
                    request_source = file_digest(path)
                    native = native_graph.run(
                        path,
                        active_template,
                        client,
                        settings["options"],
                        progress=phase,
                    )
                result.update(
                    native_graph=native,
                    model_settings=settings,
                    diagnostic=native_graph.outcome(native),
                )
                stage = "source_resolution"
                phase(stage)
                observations, anchors, issues = observation_view(native, sources)
                inventory = ledger_coverage(sources, native.get("provenance"))
                omitted = [
                    item["ref"]
                    for item in inventory
                    if item["primary"] and item["block"] is False
                ]
                undocumented = sum(
                    item["primary"] and item["block"] is None for item in inventory
                )
                is_one_to_one = (native.get("config") or {}).get("processing_mode") == "one-to-one"
                if (
                    is_one_to_one
                    and undocumented
                    and not (native.get("provenance") or {}).get("chunks")
                    and sources.doc.pages
                ):
                    ext_pages = {
                        p
                        for p in extraction_pages(native, sources.doc)
                        if p is not None
                    }
                    if ext_pages >= set(sources.doc.pages):
                        undocumented = 0
                if undocumented:
                    issues.append(
                        dict(
                            status="MODEL_DIAGNOSTIC",
                            stage="native_extraction",
                            reason="Kein natives Quellenprotokoll für erkannte Inhalte gespeichert",
                            count=undocumented,
                        )
                    )
                if omitted:
                    issues.append(
                        dict(
                            status="MODEL_DIAGNOSTIC",
                            stage="native_extraction",
                            reason="Native Quellenelemente fehlen im Quellenprotokoll",
                            refs=omitted,
                        )
                    )
                trace_issues = [
                    dict(
                        status="MODEL_DIAGNOSTIC",
                        stage=e["stage"],
                        reason=e["event_type"],
                    )
                    for e in native["trace"]
                    if e["event_type"].endswith("_failed")
                    or (e["payload"].get("metadata") or {}).get("truncated")
                ]
                issues.extend(trace_issues)
                if native.get("salvaged"):
                    issues.append(
                        dict(
                            status="SCHEMA_SALVAGED",
                            stage="pydantic_validation",
                            reason="Mindestens ein fehlerhaftes Teil-Objekt der Modellantwort wurde automatisch bereinigt (Salvage).",
                        )
                    )
                if native["error"]:
                    issues.append(
                        dict(status="MODEL_DIAGNOSTIC", **result["diagnostic"])
                    )
                if native["last_response"].get("truncated") or any(
                    r.get("finish_reason") in ("length", "max_tokens")
                    for r in native.get("requests", [])
                ):
                    issues.append(
                        dict(
                            status="MODEL_DIAGNOSTIC",
                            reason="Native response truncated",
                        )
                    )
                graph_nodes = (native["graph"] or {}).get("nodes", [])
                graph_observations = sum(
                    n.get("__class__") == "Observation" for n in graph_nodes
                )
                if graph_observations < len(observations):
                    issues.append(
                        dict(
                            status="MODEL_DIAGNOSTIC",
                            stage="graph_conversion",
                            observations=len(observations),
                            graph_observations=graph_observations,
                            reason="Nativer Graph enthält weniger Beobachtungsknoten als die validierten Modelle",
                        )
                    )
                result.update(
                    observations=observations,
                    sources=anchors,
                    issues=issues,
                    status=(
                        "ERROR"
                        if not native["extracted"] or issues and not observations
                        else "PARTIAL"
                        if issues
                        else "UNREVIEWED"
                        if observations
                        else "NEEDS_REVIEW"
                    ),
                    input=dict(
                        contract=native["config"]["extraction_contract"],
                        processing=native["config"]["processing_mode"],
                        serializer=native["config"]["llm_input_format"],
                        source_sha256=request_source,
                        custom_stage_prompt=bool(stage_a_prompt),
                        provenance="Docling Graph one-to-one page trace"
                        if is_one_to_one
                        and not (native.get("provenance") or {}).get("chunks")
                        else "Docling Graph detailed",
                    ),
                    coverage=dict(
                        parsed=sum(1 for _ in sources.items()),
                        ledger_items=sum(item["block"] is True for item in inventory),
                        missing_ledger_items=len(omitted),
                        undocumented_ledger_items=undocumented,
                        observations=len(observations),
                        observations_resolved=sum(
                            bool(o["source_ids"]) for o in observations
                        ),
                        source_verified=len(anchors),
                        semantically_reviewed=0,
                    ),
                )
                picture_status = enrichment.pictures(
                    sources.doc,
                    (derivation or {}).get(
                        "configuration", diagnostics.get("enrichment", {})
                    ),
                    configuration=sources.configuration,
                )
                result["coverage"].update(enrichment.picture_counts(picture_status))
                result["pictures"] = picture_status
                if ((derivation or row).get("status") == "partial_success") and result[
                    "status"
                ] != "ERROR":
                    result["status"] = "PARTIAL"
                    result["partial_input"] = True
            except Exception as error:
                result["error"] = type(error).__name__
                result.setdefault(
                    "diagnostic", dict(stage=stage, reason=type(error).__name__)
                )
            with self.db() as db:
                run = db.execute(
                    "INSERT INTO runs(document,at,result) VALUES(?,?,?)",
                    (
                        number,
                        datetime.now(timezone.utc).isoformat(),
                        json.dumps(result, ensure_ascii=False),
                    ),
                ).lastrowid
            from .a_status import dimensions

            diagnostic = result["diagnostic"]
            technical = dimensions(result)
            reqs = (result.get("native_graph") or {}).get("requests", [])
            p_tok = sum(int((r.get("usage") or {}).get("prompt_tokens") or 0) for r in reqs)
            c_tok = sum(int((r.get("usage") or {}).get("completion_tokens") or 0) for r in reqs)
            t_tok = sum(int((r.get("usage") or {}).get("total_tokens") or 0) for r in reqs) or (p_tok + c_tok)
            r_tok = sum(int((r.get("usage_details") or {}).get("reasoning_tokens") or 0) for r in reqs)
            ca_tok = sum(int((r.get("usage_details") or {}).get("cached_tokens") or 0) for r in reqs)
            dur_s = round(sum(float(r.get("duration_s") or 0) for r in reqs), 2) or None
            inp_meta = result.get("input") or {}
            progress(
                dict(
                    kind="A",
                    phase=diagnostic["stage"],
                    document=number,
                    document_name=row["name"],
                    status=result["status"],
                    run=run,
                    model=options.get("model"),
                    contract=inp_meta.get("contract"),
                    serializer=inp_meta.get("serializer"),
                    duration_s=dur_s,
                    prompt_tokens=p_tok or None,
                    completion_tokens=c_tok or None,
                    total_tokens=t_tok or None,
                    reasoning_tokens=r_tok or None,
                    cached_tokens=ca_tok or None,
                    reason=diagnostic.get("reason"),
                    http_status=diagnostic.get("http_status"),
                    detail=diagnostic.get("detail"),
                    observations=len(result["observations"]),
                    resolved=result.get("coverage", {}).get("observations_resolved", 0),
                    issues=len(result["issues"]),
                    basis_eligible=technical["eligible"],
                    graph_observations=technical["graph_observations"],
                    validated=technical["validated"],
                    blockers=technical["reasons"],
                )
            )
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        return counts

    def model_input(self, number, run):
        with self.db() as db:
            row = db.execute(
                "SELECT result FROM runs WHERE document=? AND id=?", (number, run)
            ).fetchone()
        if row is None:
            raise ValueError("A-Lauf zur Modellgrundlage fehlt")
        result = json.loads(row["result"])
        graph = result.get("native_graph") or {}
        version = result.get("document_version")
        items = []
        if version:
            try:
                source = self.document(self.version_row(self.file(number), version))
                items = ledger_coverage(
                    Sources(source, number, version), graph.get("provenance")
                )
            except (OSError, ValueError):
                pass  # The historical SDK receipt is still readable without its document.
        return dict(
            version=version,
            chunks=list((graph.get("provenance") or {}).get("chunks", {}).values()),
            messages=[
                record.get("messages", []) for record in graph.get("requests", [])
            ],
            items=items,
            coverage=result.get("coverage", {}),
        )

    def results(self, number, *, messages=True, compact=False):
        from .a_status import dimensions

        with self.db() as db:
            rows = db.execute(
                "SELECT * FROM runs WHERE document=? ORDER BY id DESC", (number,)
            ).fetchall()
            runs = [
                dict(
                    id=r["id"],
                    at=r["at"],
                    result=(result := json.loads(r["result"])),
                    historical=result.get("schema_version") not in READABLE_SCHEMAS,
                    notes=[
                        dict(n)
                        for n in db.execute(
                            "SELECT * FROM notes WHERE run=? ORDER BY id", (r["id"],)
                        )
                    ],
                )
                for r in rows
            ]
        if not messages or compact:
            for run in runs:
                res = run["result"]
                ng = res.get("native_graph")
                if isinstance(ng, dict):
                    for record in ng.get("requests", []):
                        record.pop("messages", None)
                if compact and not run["historical"]:
                    run["technical"] = dimensions(res)
                    if isinstance(ng, dict):
                        res["native_graph"] = {
                            k: ng[k]
                            for k in ("config", "requests", "salvaged", "error")
                            if k in ng
                        }
        return runs
