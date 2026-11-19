from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from docling_core.types.doc import (
    BoundingBox,
    DoclingDocument,
    DocItemLabel,
    DescriptionMetaField,
    ImageRef,
    PictureMeta,
    ProvenanceItem,
    Size,
    TableCell,
    TableData,
)
from PIL import Image
from starlette.testclient import TestClient

from ux_maind.app import interpretation, research
from ux_maind.app.evidence import (
    SCHEMA_VERSION,
    Sources,
    ledger_coverage,
    model_source,
    observation_view,
)
from ux_maind.app.studio import application
from ux_maind.app.templates import UXEvidenceDocument

OPTIONS = dict(
    provider="custom",
    model="synthetic",
    base_url="https://example.invalid/v1",
    context_limit=32000,
    extraction_contract="direct",
    gleaning_enabled=False,
)


def reply(value):
    return {
        "choices": [
            {"message": {"content": json.dumps(value)}, "finish_reason": "stop"}
        ]
    }


class EvidenceTests(TestCase):
    def test_picture_provenance_reaches_native_requests_and_research_export(self):
        from ux_maind.app.workspace import Workspace

        with TemporaryDirectory(dir=Path.cwd()) as folder:
            root = Path(folder)
            source = root / "source.txt"
            original, extra = "Save failed.", "An arrow points to the retry control."
            source.write_text(original, encoding="utf-8")
            app = application(root / "workspace")
            workspace: Workspace = app.state.workspace
            workspace.import_paths([source])
            base = workspace.artifact(workspace.file(1), "native")
            doc = DoclingDocument(name="Two pictures")
            doc.add_page(1, Size(width=50, height=50))
            box = BoundingBox(l=5, t=5, r=20, b=20)
            prov = ProvenanceItem(page_no=1, bbox=box, charspan=(0, len(original)))
            paragraph = doc.add_text(DocItemLabel.PARAGRAPH, original, prov=prov)
            picture = ImageRef.from_pil(Image.new("RGB", (32, 32)), dpi=96)
            full = doc.add_picture(image=picture, prov=prov)
            embedded = doc.add_picture(image=picture, prov=prov)
            full.meta = PictureMeta(
                description=DescriptionMetaField(text=f"{original} {extra}")
            )
            full.meta.set_custom_field("ux_maind", "slide_context", True)
            embedded.meta = PictureMeta(
                description=DescriptionMetaField(text="The button is grey.")
            )
            content = doc.model_dump_json(
                by_alias=True, exclude_computed_fields=True
            ).encode()
            version = sha256(content).hexdigest()
            render = dict(
                renderer="LibreOffice",
                source_sha256=sha256(source.read_bytes()).hexdigest(),
                display_sha256=sha256(b"display derivative").hexdigest(),
            )
            workspace.save_version(
                base,
                dict(
                    at="2026-11-16T01:00:00Z",
                    version=version,
                    base_version=sha256(base.read_bytes()).hexdigest(),
                    kind="conversion",
                    diagnostics={"configuration": {"slide_view": render}},
                ),
                content,
            )
            observations = [
                dict(
                    quote=quote,
                    statement=statement,
                    origin=origin,
                    locator={"self_ref": item.self_ref},
                )
                for item, quote, statement, origin in (
                    (paragraph, original, original, "original"),
                    (
                        full,
                        original,
                        "The rendering repeats that error.",
                        "picture_description",
                    ),
                    (full, extra, extra, "picture_description"),
                    (
                        embedded,
                        "The button is grey.",
                        "The button appears grey.",
                        "picture_description",
                    ),
                )
            ]
            for format in ("markdown", "doclang", "doclang-geo"):
                with (
                    self.subTest(format=format),
                    patch(
                        "litellm.completion",
                        return_value=reply(dict(observations=observations)),
                    ) as call,
                ):
                    workspace.extract(
                        [1],
                        dict(OPTIONS, llm_input_format=format),
                        versions={"1": version},
                    )
                    messages = str(call.call_args.kwargs["messages"])
                    for value in (
                        "slide_context",
                        "original_embedded",
                        version,
                        render["display_sha256"],
                        extra,
                    ):
                        self.assertIn(value, messages)
            entries = research.catalog(workspace, [1])["observations"]
            by_quote = {e["raw"]["statement"]: e["ref"] for e in entries}
            first, overlap, distinct = (
                by_quote[key]
                for key in (original, "The rendering repeats that error.", extra)
            )
            relation = dict(
                source=first,
                target=overlap,
                kind="same_event",
                rationale="The render repeats the original error.",
            )
            with patch(
                "litellm.completion", return_value=reply(dict(relations=[relation]))
            ) as call:
                b = interpretation.run(workspace, [1], OPTIONS, stage="B")
                messages = str(call.call_args.kwargs["messages"])
                for value in (
                    "renderer_derived",
                    "original_embedded",
                    extra,
                    render["display_sha256"],
                ):
                    self.assertIn(value, messages)
                self.assertIn(
                    "no separate event or sequence", str(call.call_args.kwargs)
                )
            finding = dict(
                title="Save failed",
                valence="negative",
                rationale="The same error appears twice. The arrow adds retry context.",
                uncertainty="One incident",
                supports=[first],
                opposes=[],
                qualifies=[overlap, distinct],
            )
            with patch(
                "litellm.completion", return_value=reply(dict(findings=[finding]))
            ) as call:
                c = interpretation.run(
                    workspace, [1], OPTIONS, stage="C", b_run=b["comparison"]
                )
                messages = str(call.call_args.kwargs["messages"])
                for value in (
                    "renderer_derived",
                    "original_embedded",
                    extra,
                    render["display_sha256"],
                ):
                    self.assertIn(value, messages)
                self.assertIn("overlapping support", str(call.call_args.kwargs))
            self.assertEqual((b["status"], c["status"]), ("UNREVIEWED", "UNREVIEWED"))
            with TestClient(app) as client:
                export = client.get(
                    "/api/ux-export", params={"documents": "[1]"}
                ).json()
                graph = client.get("/api/ux-graph", params={"documents": "[1]"}).json()
            anchors = [
                e["picture_sources"][0]["picture_source"]
                for e in export["observations"]
                if e["picture_sources"]
            ]
            self.assertEqual(
                {a["kind"] for a in anchors}, {"embedded", "slide_context"}
            )
            sources = {
                n["ref"]: n["picture_source"]
                for n in graph["graph"]["nodes"]
                if n["__class__"] == "PictureSourceNode"
            }
            self.assertEqual(
                sources[full.self_ref]["display_sha256"], render["display_sha256"]
            )
            self.assertEqual(sources[full.self_ref]["pages"], [1])
            self.assertEqual(sources[embedded.self_ref]["document_version"], version)
            self.assertEqual(len(sources), 2)

    def test_native_fragments_and_derived_picture_refs_without_format_assumptions(self):
        doc = DoclingDocument(name="Source roles")
        doc.add_page(1, Size(width=50, height=50))
        box = BoundingBox(l=5, t=5, r=20, b=20)
        first, second = [
            doc.add_text(
                DocItemLabel.PARAGRAPH,
                text,
                prov=ProvenanceItem(page_no=1, bbox=box, charspan=(0, len(text))),
            )
            for text in ("Could not save.", "Then recovered.")
        ]
        pictures = [doc.add_picture(), doc.add_picture()]
        for picture in pictures:
            picture.meta = PictureMeta(
                description=DescriptionMetaField(text="3 tasks. 3 tasks in view.")
            )
        sources = Sources(doc, 1, "v1")
        (match,) = sources.occurrences(
            "Could not save. Then recovered.", {}, "original"
        )
        self.assertEqual([a["ref"] for a in match], [first.self_ref, second.self_ref])
        (partial,) = sources.occurrences(
            "not save. Then", {"self_ref": second.self_ref}, "original"
        )
        self.assertEqual([a["quote"] for a in partial], ["not save.", "Then"])
        self.assertFalse(
            list(
                sources.occurrences("Could not print. Then recovered.", {}, "original")
            )
        )
        with self.assertRaisesRegex(ValueError, "mehreren Fundstellen"):
            sources.locate("3 tasks", {}, "picture_description")
        self.assertEqual(
            sources.locate(
                "3 tasks", {"self_ref": pictures[1].self_ref}, "picture_description"
            )["ref"],
            pictures[1].self_ref,
        )
        with model_source(sources, Path("document.json")) as path:
            offered = DoclingDocument.load_from_json(path)
            self.assertEqual(
                offered.pictures[1].meta.get_custom_part()["ux_maind__source_ref"],
                pictures[1].self_ref,
            )
            self.assertNotIn("ux_maind__source_ref", pictures[1].meta.get_custom_part())

    def test_native_description_lists_and_caption_ownership(self):
        doc = DoclingDocument(name="Display evidence")
        caption = doc.add_text(DocItemLabel.CAPTION, "Screenshot after saving")
        doc.add_text(DocItemLabel.PARAGRAPH, "Unrelated note")
        picture = doc.add_picture(caption=caption)
        picture.meta = PictureMeta(
            description=DescriptionMetaField(
                text='Visible lines:\n\n- "Änderungen gespeichert."\n- "Zur Übersicht."'
            )
        )
        sources = Sources(doc, 1, "v1")
        anchor = sources.locate(
            "Änderungen gespeichert. Zur Übersicht.", {}, "picture_description"
        )
        self.assertEqual(anchor["ref"], picture.self_ref)
        with self.assertRaises(ValueError):
            sources.locate(
                "Zur Übersicht. Änderungen gespeichert.", {}, "picture_description"
            )
        via_caption = sources.picture_sources([sources.locate(caption.text, {})])
        self.assertEqual(
            [(a["ref"], a["modality"]) for a in via_caption],
            [(picture.self_ref, "picture")],
        )
        self.assertEqual(
            sources.picture_sources([sources.locate("Unrelated note", {})]), []
        )
        inventory = {row["ref"]: row for row in ledger_coverage(sources, None)}
        self.assertTrue(inventory[picture.self_ref]["primary"])
        self.assertIsNone(inventory[picture.self_ref]["block"])

    def test_ledger_separates_heading_context_from_missing_and_ambiguous_refs(self):
        doc = DoclingDocument(name="Heading context")
        title = doc.add_title("Unique title")
        one = doc.add_heading("Repeated heading")
        two = doc.add_heading("Repeated heading")
        text = doc.add_text(DocItemLabel.PARAGRAPH, "Reported event")
        ledger = dict(
            chunks={
                "0": dict(
                    chunk_id=0,
                    doc_item_refs=[text.self_ref],
                    headings=["Unique title", "Repeated heading"],
                    page_numbers=[],
                )
            }
        )
        rows = {
            r["ref"]: r for r in ledger_coverage(Sources(doc, 1, "version"), ledger)
        }
        self.assertEqual(rows[title.self_ref]["chunks"], [0])
        self.assertTrue(rows[title.self_ref]["as_heading"])
        self.assertTrue(rows[text.self_ref]["block"])
        self.assertFalse(rows[text.self_ref]["as_heading"])
        self.assertFalse(rows[one.self_ref]["block"])
        self.assertFalse(rows[two.self_ref]["block"])

    def test_page_trace_scopes_identical_native_quotes(self):
        doc = DoclingDocument(name="Repeated source")
        for page in (1, 3):
            doc.add_page(page, Size(width=80, height=80))
            doc.add_text(
                DocItemLabel.TEXT,
                "Same statement.",
                prov=ProvenanceItem(
                    page_no=page,
                    bbox=BoundingBox(l=2, t=3, r=30, b=8),
                    charspan=(0, 15),
                ),
            )
        model = UXEvidenceDocument.model_validate(
            {
                "observations": [
                    {"statement": "Same statement.", "quote": "Same statement."}
                ]
            }
        ).model_dump()
        receipt = dict(
            extracted=[model, model],
            trace=[
                dict(
                    event_type="extraction_completed",
                    payload=dict(
                        source_type="page", source_id=index, parsed_model=model
                    ),
                )
                for index in (0, 1)
            ],
        )
        observations, anchors, issues = observation_view(
            receipt, Sources(doc, 1, "pages")
        )
        self.assertFalse(issues)
        self.assertEqual(
            [anchors[o["source_ids"][0]]["prov"][0]["page_no"] for o in observations],
            [1, 3],
        )
        self.assertEqual(len(anchors), 2)

    def test_ambiguity_and_stored_cell_distinguish_zero_from_blank(self):
        doc = DoclingDocument(name="Synthetic measurements")
        one = doc.add_text(label=DocItemLabel.PARAGRAPH, text="Same. Same.")
        two = doc.add_text(label=DocItemLabel.PARAGRAPH, text="Same.")
        table = doc.add_table(
            data=TableData(
                num_rows=100001,
                num_cols=2,
                table_cells=[
                    TableCell(
                        text=value,
                        start_row_offset_idx=100000,
                        end_row_offset_idx=100001,
                        start_col_offset_idx=col,
                        end_col_offset_idx=col + 1,
                    )
                    for col, value in [(0, "0"), (1, "")]
                ],
            ),
        )
        source = Sources(doc, 1, "version")
        for locator in ({}, {"self_ref": one.self_ref}):
            with self.assertRaises(ValueError):
                source.locate("Same.", locator)
        picked = source.select(dict(ref=one.self_ref, quote="Same.", start=6, end=11))
        other = source.locate("Same.", {"self_ref": two.self_ref})
        self.assertNotEqual(picked["evidence_id"], other["evidence_id"])
        self.assertEqual(source.select(picked), picked)
        self.assertNotEqual(
            source.select(dict(ref=one.self_ref, start=6, end=11))["evidence_id"],
            Sources(doc, 1, "other version").select(
                dict(ref=one.self_ref, start=6, end=11)
            )["evidence_id"],
        )
        self.assertEqual(source.locate("0", {})["column"], 0)
        blank = source.locate(
            "", {"self_ref": table.self_ref, "row": 100000, "column": 1}
        )
        self.assertEqual(blank["quote"], "")
        self.assertEqual(blank["column"], 1)
        with self.assertRaises(ValueError):
            source.locate("", {"self_ref": table.self_ref, "row": 99999, "column": 1})

    def test_docx_native_table_visible_in_place_and_full_row_bound(self):
        from docx import Document

        with TemporaryDirectory() as root:
            src = Path(root) / "cover.docx"
            document = Document()
            document.add_heading("Things to carry into cover", level=2)
            table = document.add_table(rows=0, cols=3)
            for values in [
                ("From", "Keep or ask", "Owner / next"),
                ("Eli, on screen", "Short personal list", "Keep the Person route"),
                ("Nia, on call", "Step-free equipment access?", "Tess / venue answer"),
                ("Eli, about Sam", "Which room names?", "Tess / ask Sam"),
            ]:
                for cell, text in zip(table.add_row().cells, values, strict=True):
                    cell.text = text
            document.add_paragraph("For the afternoon colleague:")
            document.save(src)
            app = application(Path(root) / "work")
            workspace = app.state.workspace
            self.assertEqual(workspace.import_paths([src]), {"success": 1})
            row = workspace.file(1)
            source = Sources(
                workspace.document(row), 1, workspace.summary(row)["version"]
            )
            anchor = source.locate(
                "Nia, on call Step-free equipment access? Tess / venue answer", {}
            )
            self.assertEqual(anchor["modality"], "table_row")
            self.assertEqual(
                (anchor["ref"], anchor["row"], anchor["column_end"]),
                ("#/tables/0", 2, 3),
            )
            self.assertEqual(source.select(anchor), anchor)
            with self.assertRaises(ValueError):
                source.locate(
                    "Nia, on call Step-free equipment access? Tess / ask Sam", {}
                )
            with TestClient(app) as client:
                html = client.get("/document/1/view").text
                self.assertLess(
                    html.index("Things to carry into cover"), html.index("Keep or ask")
                )
                self.assertLess(
                    html.index("Tess / ask Sam"),
                    html.index("For the afternoon colleague:"),
                )

    def test_native_pipeline_views_and_interpretation_share_versioned_evidence(self):
        with TemporaryDirectory(dir=Path.cwd()) as folder:
            root = Path(folder)
            app = application(root / "workspace")
            workspace = app.state.workspace
            source = root / "source.txt"
            original = "Could not find Save. After Settings, saved successfully."
            source.write_text(original, encoding="utf-8")
            self.assertEqual(workspace.import_paths([source]), {"success": 1})
            row = workspace.file(1)
            base = workspace.artifact(row, "native")
            doc = DoclingDocument(name="derived fixture")
            doc.add_text(DocItemLabel.TEXT, original)
            doc.add_text(DocItemLabel.TEXT, "Marker for the selected document version.")
            content = doc.model_dump_json(
                by_alias=True, exclude_computed_fields=True
            ).encode()
            version = sha256(content).hexdigest()
            derived = base.parent / "enrichment" / version / "document.json"
            derived.parent.mkdir(parents=True)
            derived.write_bytes(content)
            historical = '{"information":[{"text":"original schema"}],"opaque":true}'
            with workspace.db() as db:
                db.execute(
                    "INSERT INTO runs(document,at,result) VALUES(1,'R15',?)",
                    (historical,),
                )
                db.execute(
                    "INSERT INTO notes(run,item,at,text) VALUES(1,0,'R15','retained note')"
                )
            proposals = {
                "observations": [
                    {
                        "quote": original,
                        "statement": "Could not find Save",
                        "kind": "difficulty",
                    },
                    {
                        "quote": original,
                        "statement": "Saved after Settings",
                        "kind": "recovery",
                    },
                ]
            }
            with patch("litellm.completion", return_value=reply(proposals)) as call:
                self.assertEqual(
                    workspace.extract([1], OPTIONS, versions={"1": version}),
                    {"UNREVIEWED": 1},
                )
                reported = workspace.results(1)[0]["result"]
                self.assertEqual(reported["schema_version"], SCHEMA_VERSION)
                self.assertEqual(reported["document_version"], version)
                self.assertIn("<doclang", str(call.call_args.kwargs["messages"]))
                self.assertEqual(
                    call.call_args.kwargs["response_format"]["type"], "json_schema"
                )
                self.assertEqual(len(reported["native_graph"]["graph"]["nodes"]), 2)
                self.assertTrue(reported["native_graph"]["provenance"]["chunks"])
            a, b = [e["ref"] for e in research.catalog(workspace, [1])["observations"]]
            before = research.graph(workspace, [1])
            self.assertEqual(before["analysis"]["status"], "NOT_RUN")
            self.assertEqual(before["graph"]["edges"], [])
            relation = dict(
                source=b, target=a, kind="recovers", rationale="Saved after Settings"
            )
            with patch(
                "litellm.completion", return_value=reply(dict(relations=[relation]))
            ):
                first = interpretation.run(workspace, [1], OPTIONS, stage="B")
            self.assertEqual(first["status"], "UNREVIEWED")
            graph = research.graph(workspace, [1])
            self.assertEqual(graph["analysis"]["stages"]["C"], [])
            self.assertEqual(len(graph["graph"]["edges"]), 2)
            with patch("litellm.completion", return_value=reply(dict(unexpected=[]))):
                failed = interpretation.run(
                    workspace, [1], OPTIONS, stage="C", b_run=first["comparison"]
                )
            self.assertEqual(failed["status"], "ERROR")
            self.assertEqual(
                research.graph(workspace, [1])["analysis"]["stages"]["B"][0]["id"],
                first["comparison"],
            )
            finding = dict(
                title="Save action was recovered",
                valence="mixed",
                rationale="The source records both.",
                uncertainty="One interaction",
                supports=[b],
                opposes=[a],
                relations=[first["saved"][0]["id"]],
            )
            with patch(
                "litellm.completion", return_value=reply(dict(findings=[finding]))
            ):
                outcome = interpretation.run(
                    workspace,
                    [1],
                    dict(OPTIONS, model="synthetic-c"),
                    stage="C",
                    b_run=first["comparison"],
                )
            self.assertEqual(outcome["status"], "UNREVIEWED")
            self.assertEqual(len(outcome["saved"]), 1)
            receipt = research.analysis_run(workspace, outcome["comparison"])
            self.assertEqual(receipt["metadata"]["b_run"], first["comparison"])
            self.assertEqual(receipt["metadata"]["model"], "synthetic-c")
            self.assertEqual(
                receipt["metadata"]["inputs"]["relations"][0]["review"], "UNREVIEWED"
            )
            with TestClient(app) as client:
                result = client.get("/api/ux-graph", params={"documents": "[1]"}).json()
                self.assertEqual(result["analysis"]["status"], "UNREVIEWED")
                observations = result["observations"]
                left, right = (e["source_check"]["matches"][0] for e in observations)
                self.assertEqual(left["evidence_id"], right["evidence_id"])
                self.assertTrue(result["graph"]["edges"])
                self.assertEqual(
                    client.get(
                        "/document/1/native", params={"version": version}
                    ).content,
                    content,
                )
                marker = "Marker for the selected document version."
                self.assertNotIn(marker, client.get("/document/1/view").text)
                self.assertIn(
                    marker,
                    client.get("/document/1/view", params={"version": version}).text,
                )
                self.assertIn(
                    marker,
                    client.get("/document/1/web", params={"version": version}).text,
                )
                history = client.get(
                    "/api/ux-history", params={"documents": "[1]"}
                ).json()
                self.assertEqual(
                    history["runs"][0]["notes"][0]["text"], "retained note"
                )
                self.assertEqual(history["runs"][0]["result"], json.loads(historical))
                # A stored R18c decision must still be applied after removal of the editor.
                with workspace.db() as db:
                    db.execute(
                        """INSERT INTO ux_decisions(target_type,target,at,origin,action,reason,payload)
                           VALUES('observation',?,'2026-11-15','automated','open','Regression',?)""",
                        (json.dumps(a, sort_keys=True), json.dumps({"primary": left})),
                    )
                entry = research.entry(workspace, a)
                self.assertEqual(entry["selected_source"], left)
                self.assertEqual(entry["document_version"], version)
                export = client.get(
                    "/api/ux-export", params={"documents": "[1]"}
                ).json()
                stored = next(e for e in export["observations"] if e["ref"] == a)
                self.assertEqual(stored["decisions"][0]["payload"]["primary"], left)
                self.assertEqual(stored["selected_source"], left)
            self.assertEqual(
                workspace.artifact(row, "stored").read_text(encoding="utf-8"), original
            )

    def test_native_spreadsheet_origin_recovers_a_distant_merged_range(self):
        from openpyxl import Workbook
        from ux_maind.app.workspace import Workspace

        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "times.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Trial times"
            sheet["B1"] = "Time (ms)"
            sheet.merge_cells("H8200:I8200")
            sheet["H8200"] = 0
            workbook.save(source)
            ws = Workspace(root / "workspace")
            self.assertEqual(ws.import_paths([source]), {"success": 1})
            sources = Sources(ws.document(ws.file(1)), 1, "fixed")
            anchor = sources.locate("0", {})
            self.assertEqual(anchor["row"], 0)
            self.assertEqual(
                anchor["worksheet"],
                dict(
                    name="Trial times",
                    page=1,
                    row=8199,
                    row_end=8200,
                    column=7,
                    column_end=9,
                ),
            )

    def test_failed_optional_enrichment_keeps_base_and_reopenable_diagnostic(self):
        from ux_maind.app.workspace import Workspace

        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = Path("tests/fixtures/w1_picture.docx")
            ws = Workspace(root / "workspace")
            ws.import_paths([source])
            original = ws.artifact(ws.file(1), "native")
            before = original.read_bytes()
            with patch(
                "docling.document_converter.DocumentConverter.convert",
                side_effect=OSError("test-credential-never-persist"),
            ):
                failures = ws.enrich(
                    [1], dict(mode="inline", description=False, chart=True)
                )
            self.assertEqual(failures["error"], 1)
            reopened = Workspace(ws.root)
            diagnostic = reopened.summary(reopened.file(1))["diagnostics"][
                "enrichment_errors"
            ][0]
            self.assertEqual(diagnostic["error"], "OSError")
            self.assertTrue(diagnostic["configuration"]["chart"])
            self.assertNotIn("test-credential-never-persist", json.dumps(diagnostic))
            self.assertEqual(original.read_bytes(), before)
