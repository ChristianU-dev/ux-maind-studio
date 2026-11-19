"""R23 Carbon root-cause regression tests across ingestion, anchors, B/C contracts, epistemics, and API decisions."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from docx import Document
from docling_core.types.doc import (
    BoundingBox,
    CodeItem,
    CoordOrigin,
    DescriptionMetaField,
    DocItemLabel,
    DoclingDocument,
    ImageRef,
    PictureMeta,
    ProvenanceItem,
    Size,
    TableCell,
    TableData,
)
from PIL import Image
from starlette.testclient import TestClient

from ux_maind.app import interpretation, models, native_graph, office, research
from ux_maind.app.evidence import SCHEMA_VERSION, Sources, model_source, observation_view, picture_source
from ux_maind.app.studio import application
from ux_maind.app.templates import FindingProposal, Observation, RelationProposal, UXEvidenceDocument
from ux_maind.app.workspace import Workspace


def _reply(payload):
    return {
        "choices": [
            {"message": {"content": json.dumps(payload)}, "finish_reason": "stop"}
        ]
    }


class R23CarbonTests(TestCase):
    def test_txt_tabs_avoid_code_items_and_preserve_paragraphs(self):
        with TemporaryDirectory() as root:
            src = Path(root) / "transcript.txt"
            src.write_text(
                "Moderator:\tWie war das?\n\nP1:\tKonnte Knopf nicht finden.\n\tDann neu geladen.",
                encoding="utf-8",
            )
            w = Workspace(Path(root) / "ws")
            self.assertEqual(w.import_paths([src]), {"success": 1})
            doc = w.document(w.file(1))
            self.assertFalse(any(isinstance(item, CodeItem) for item, _ in doc.iterate_items()))
            self.assertEqual(len(doc.texts), 2)
            self.assertIn("\tKonnte Knopf nicht finden.", doc.texts[1].text)

    def test_docx_uniform_and_partial_strikethrough_and_pdf_page_context(self):
        with TemporaryDirectory() as root:
            src = Path(root) / "struck.docx"
            d = Document()
            p1 = d.add_paragraph()
            r1 = p1.add_run("All deleted step")
            r1.font.strike = True
            p2 = d.add_paragraph()
            p2.add_run("Keep this ")
            r2 = p2.add_run("old value")
            r2.font.double_strike = True
            tbl = d.add_table(rows=1, cols=2)
            r3 = tbl.rows[0].cells[0].paragraphs[0].add_run("bad cell")
            r3.font.strike = True
            tbl.rows[0].cells[1].paragraphs[0].add_run("good cell")
            d.save(src)

            doc = DoclingDocument(name="struck")
            t1 = doc.add_text(DocItemLabel.PARAGRAPH, "All deleted step")
            t2 = doc.add_text(DocItemLabel.PARAGRAPH, "Keep this old value")
            doc.add_table(
                data=TableData(
                    num_rows=1,
                    num_cols=2,
                    table_cells=[
                        TableCell(text="bad cell", start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=0, end_col_offset_idx=1),
                        TableCell(text="good cell", start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=1, end_col_offset_idx=2),
                    ],
                )
            )
            annotated = office.docx_formatting(src, doc)
            self.assertGreaterEqual(annotated, 3)
            self.assertTrue(t1.formatting and t1.formatting.strikethrough)
            self.assertEqual(t2.meta.get_custom_part()["ux_maind__strikethrough_spans"], ["old value"])
            self.assertEqual(doc.tables[0].meta.get_custom_part()["ux_maind__table_strikethrough"][0]["struck"], ["bad cell"])

            pdf_doc = DoclingDocument(name="diagram.pdf")
            img = ImageRef.from_pil(Image.new("RGB", (100, 80), "white"), dpi=72)
            pdf_doc.add_page(1, Size(width=100, height=80), image=img)
            pdf_doc.add_picture(
                prov=ProvenanceItem(page_no=1, bbox=BoundingBox(l=10, t=10, r=50, b=50, coord_origin=CoordOrigin.TOPLEFT), charspan=(0, 0))
            )
            added = office.attach_pdf_page_views(pdf_doc, "abc123")
            self.assertEqual(added["pages"], 1)
            self.assertEqual(len(pdf_doc.pictures), 2)
            ps = picture_source(pdf_doc.pictures[1])
            self.assertEqual((ps["kind"], ps["origin"]), ("page_context", "native_page_render"))
            # Idempotent if run twice
            self.assertEqual(office.attach_pdf_page_views(pdf_doc, "abc123")["pages"], 0)

    def test_normalized_spans_table_pipes_scoped_measurements_and_reconciliation(self):
        doc = DoclingDocument(name="Anchors")
        doc.add_page(1, Size(width=200, height=200))
        para = doc.add_text(
            DocItemLabel.PARAGRAPH,
            "Question 1 score was \u201c7\u201d overall. Elsewhere 7 and 17 appear.",
            prov=ProvenanceItem(page_no=1, bbox=BoundingBox(l=0, t=0, r=100, b=20), charspan=(0, 62)),
        )
        tbl = doc.add_table(
            data=TableData(
                num_rows=2,
                num_cols=2,
                table_cells=[
                    TableCell(text="Metric", start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=0, end_col_offset_idx=1, column_header=True),
                    TableCell(text="Rating (1-7)", start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=1, end_col_offset_idx=2, column_header=True),
                    TableCell(text="Ease", start_row_offset_idx=1, end_row_offset_idx=2, start_col_offset_idx=0, end_col_offset_idx=1),
                    TableCell(text="Score: 7 / 7", start_row_offset_idx=1, end_row_offset_idx=2, start_col_offset_idx=1, end_col_offset_idx=2),
                ],
            )
        )
        pic = doc.add_picture()
        pic.meta = PictureMeta(description=DescriptionMetaField(text="Arrow from Export -> Error banner."))

        sources = Sources(doc, 1, "v1")
        with model_source(sources, Path("doc.json")) as ms_path:
            ms_doc = DoclingDocument.load_from_json(ms_path)
            self.assertEqual(ms_doc.tables[0].meta.get_custom_part()["ux_maind__table_headers"]["columns"]["1"], "Rating (1-7)")

        # Normalized smart quotes & table pipe separator
        norm_anchor = sources.locate('Question 1 score was "7" overall.', {"self_ref": para.self_ref})
        self.assertEqual(norm_anchor["quote"], "Question 1 score was \u201c7\u201d overall.")
        pipe_row = sources.locate("Ease | Score: 7 / 7", {"self_ref": tbl.self_ref})
        self.assertEqual(pipe_row["modality"], "table_row")

        # Table row cited with misleading column=0 and header-scoped duplicate numeric measurement
        pssuq = doc.add_table(
            data=TableData(
                num_rows=2,
                num_cols=4,
                table_cells=[
                    TableCell(text="Questions", start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=0, end_col_offset_idx=1, column_header=True),
                    TableCell(text="P1", start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=1, end_col_offset_idx=2, column_header=True),
                    TableCell(text="P2", start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=2, end_col_offset_idx=3, column_header=True),
                    TableCell(text="P3", start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=3, end_col_offset_idx=4, column_header=True),
                    TableCell(text="Q1", start_row_offset_idx=1, end_row_offset_idx=2, start_col_offset_idx=0, end_col_offset_idx=1),
                    TableCell(text="2", start_row_offset_idx=1, end_row_offset_idx=2, start_col_offset_idx=1, end_col_offset_idx=2),
                    TableCell(text="4", start_row_offset_idx=1, end_row_offset_idx=2, start_col_offset_idx=2, end_col_offset_idx=3),
                    TableCell(text="2", start_row_offset_idx=1, end_row_offset_idx=2, start_col_offset_idx=3, end_col_offset_idx=4),
                ],
            )
        )
        sources = Sources(doc, 1, "v1")

        model = UXEvidenceDocument.model_validate(
            {
                "observations": [
                    {
                        "quote": 'Question 1 score was "7" overall.',
                        "statement": "Participant rated Q1 as 7",
                        "locator": {"self_ref": para.self_ref},
                        "measurements": [
                            {"raw_value": "7", "numeric_value": 7.0, "scale_direction": "unknown"}
                        ],
                    },
                    # Gleaning duplicate should be dropped cleanly
                    {
                        "quote": 'Question 1 score was "7" overall.',
                        "statement": "Participant rated Q1 as 7",
                        "locator": {"self_ref": para.self_ref},
                    },
                    # Table cell substring measurement on coordinate-pinned cell
                    {
                        "quote": "Score: 7 / 7",
                        "statement": "Ease rated 7",
                        "locator": {"self_ref": tbl.self_ref, "row": 1, "column": 1},
                        "measurements": [
                            {"raw_value": "7", "numeric_value": 7.0, "locator": {"self_ref": tbl.self_ref, "row": 1, "column": 1}},
                            # Wrong cell coordinate must stay unresolved!
                            {"raw_value": "99", "numeric_value": 99.0, "locator": {"self_ref": tbl.self_ref, "row": 1, "column": 1}},
                        ],
                    },
                    # Mismatched declared origin on PictureItem reconciles transparently
                    {
                        "quote": "Arrow from Export -> Error banner.",
                        "statement": "Visual arrow points to error banner",
                        "origin": "original",
                        "locator": {"self_ref": pic.self_ref},
                    },
                    # PSSUQ row with misleading col=0 & header-scoped measurement "2" (exists in P1 & P3)
                    {
                        "quote": "Q1 2 4 2",
                        "statement": "Q1 ratings P1=2, P2=4, P3=2",
                        "locator": {"self_ref": pssuq.self_ref, "row": 1, "column": 0},
                        "measurements": [
                            {"raw_value": "2", "numeric_value": 2.0, "scope": "P1", "scale_direction": "unknown"},
                            {"raw_value": "2", "numeric_value": 2.0, "scope": "P3", "scale_direction": "unknown"},
                        ],
                    },
                ]
            }
        )
        obs, anchors, issues = observation_view(dict(extracted=[model.model_dump()], trace=[]), sources)
        self.assertEqual(len(obs), 4)  # Gleaning echo deduplicated
        self.assertEqual(len(obs[0]["measurements"][0]["source_ids"]), 1)
        self.assertTrue(obs[1]["measurements"][0]["source_ids"])
        self.assertFalse(obs[1]["measurements"][1]["source_ids"])
        self.assertEqual(obs[2]["origin"], "picture_description")
        self.assertEqual(obs[2]["origin_reconciled"], {"declared": "original", "resolved": "picture_description"})
        self.assertTrue(obs[3]["source_ids"])
        self.assertEqual(anchors[obs[3]["measurements"][0]["source_ids"][0]]["column"], 1)
        self.assertEqual(anchors[obs[3]["measurements"][1]["source_ids"][0]]["column"], 3)
        self.assertIn("MEASUREMENT_UNRESOLVED", {i["status"] for i in issues})
        self.assertIn("ORIGIN_RECONCILED", {i["status"] for i in issues})

    def test_planning_budget_and_stage_bc_direct_contract_defaults(self):
        profile = dict(provider="nhr_fau", model="Qwen/Qwen3.6-35B-A3B-FP8", key="synthetic")
        directory = [dict(id=profile["model"], max_input_tokens=262144, max_output_tokens=262144)]
        with patch("ux_maind.app.models.fau_entries", return_value=directory):
            client = models.connect(profile)
            desc = models.describe(profile, client=client)
            self.assertEqual(client.max_tokens, 4092)
            self.assertEqual(desc["plan_max_output_tokens"], 32768)
            self.assertIsNone(desc["wire_max_tokens"])

        with TemporaryDirectory() as root:
            src = Path(root) / "study.txt"
            src.write_text("User clicked Save and saw an error. Then closed dialog.", encoding="utf-8")
            w = Workspace(Path(root) / "ws")
            w.import_paths([src])
            a_resp = _reply({
                "observations": [
                    {"quote": "User clicked Save and saw an error.", "statement": "Save produced error", "locator": {"self_ref": "#/texts/0"}},
                    {"quote": "Then closed dialog.", "statement": "User closed dialog", "locator": {"self_ref": "#/texts/0"}},
                ]
            })
            with patch("ux_maind.app.models.fau_entries", return_value=directory), patch("litellm.completion", return_value=a_resp) as call:
                w.extract([1], dict(profile, gleaning_enabled=False))
                self.assertNotIn("max_tokens", call.call_args.kwargs)
            a_run = w.results(1)[0]
            self.assertEqual(a_run["result"]["native_graph"]["config"]["plan_max_output_tokens"], 32768)

            b_resp = _reply({
                "relations": [{
                    "source": {"document": 1, "run": a_run["id"], "observation": "O1"},
                    "target": {"document": 1, "run": a_run["id"], "observation": "O2"},
                    "kind": "followed_by",
                    "rationale": "Error occurred before closing the dialog.",
                    "situation": "Save action",
                    "inference_basis": "explicitly_reported",
                }]
            })
            # Even with options specifying extraction_contract="auto", B/C must use "direct" and single-pass unless stage_gleaning=True!
            with patch("ux_maind.app.models.fau_entries", return_value=directory), patch("litellm.completion", return_value=b_resp) as call_b:
                res_b = interpretation.run(w, [1], dict(profile, extraction_contract="auto"), stage="B")
                self.assertEqual(call_b.call_count, 1)
                self.assertEqual(res_b["status"], "UNREVIEWED")
                receipt = research.analysis_run(w, res_b["comparison"])
                self.assertEqual(receipt["metadata"]["native_graph"]["config"]["extraction_contract"], "direct")
                self.assertFalse(receipt["metadata"]["native_graph"]["config"]["gleaning_enabled"])

    def test_ux_decision_partial_gate_and_dependent_visual_overlap(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            src = root / "doc.txt"
            src.write_text("First quote. Second quote.", encoding="utf-8")
            app = application(root / "ws")
            w = app.state.workspace
            w.import_paths([src])
            doc = DoclingDocument(name="VisualOverlap")
            doc.add_page(1, Size(width=100, height=100))
            t1 = doc.add_text(DocItemLabel.PARAGRAPH, "First quote. Second quote.", prov=ProvenanceItem(page_no=1, bbox=BoundingBox(l=0, t=0, r=50, b=20), charspan=(0, 26)))
            p_slide = doc.add_picture(prov=ProvenanceItem(page_no=1, bbox=BoundingBox(l=0, t=0, r=100, b=100), charspan=(0, 26)))
            p_slide.meta = PictureMeta(description=DescriptionMetaField(text="First quote."))
            p_slide.meta.set_custom_field("ux_maind", "slide_context", True)
            content = doc.model_dump_json(by_alias=True, exclude_computed_fields=True).encode()
            ver = sha256(content).hexdigest()
            base = w.artifact(w.file(1), "native")
            derived = base.parent / "enrichment" / ver / "document.json"
            derived.parent.mkdir(parents=True)
            derived.write_bytes(content)

            sources = Sources(doc, 1, ver)
            obs_model = UXEvidenceDocument.model_validate({
                "observations": [
                    {
                        "quote": "First quote.",
                        "statement": "Original text quote",
                        "origin": "original",
                        "locator": {"self_ref": t1.self_ref},
                        "negated_or_struck": True,
                        "measurements": [{"raw_value": "First", "numeric_value": 5.0}],
                        "context_reference": {"kind": "ellipsis", "cue": "Same as above", "target_self_ref": "#/texts/999"},
                    },
                    {
                        "quote": "First quote.",
                        "statement": "Slide rendering of same quote",
                        "origin": "picture_description",
                        "locator": {"self_ref": p_slide.self_ref},
                    },
                    {
                        "quote": "Missing quote.",
                        "statement": "Unresolved item",
                        "origin": "original",
                        "locator": {"self_ref": t1.self_ref},
                    },
                ]
            })
            obs, anchors, issues = observation_view(dict(extracted=[obs_model.model_dump()], trace=[]), sources)
            run_payload = dict(
                schema_version=SCHEMA_VERSION,
                status="PARTIAL",
                document_version=ver,
                observations=obs,
                sources=anchors,
                issues=issues,
                native_graph=dict(extracted=[obs_model.model_dump()], trace=[], requests=[dict(finish_reason="stop")], last_response={}, error=None),
                relations=[],
            )
            with w.db() as db:
                run_id = db.execute("INSERT INTO runs(document,at,result) VALUES(1,'2026-11-17',?)", (json.dumps(run_payload),)).lastrowid

            # Unresolved O3 keeps default gate closed unless allow_partial=True or O3 is rejected by human
            planned = interpretation.plan(w, [1], basis={1: run_id})
            with self.assertRaises(ValueError):
                interpretation.require_basis(planned, allow_partial=False)
            interpretation.require_basis(planned, allow_partial=True)

            # Create a finding referencing both original and slide_context on page 1
            ref1 = dict(document=1, run=run_id, observation="O1")
            ref2 = dict(document=1, run=run_id, observation="O2")
            ref3 = dict(document=1, run=run_id, observation="O3")
            f_id = research.create(w, "finding", dict(title="Overlap finding", valence="unclear", rationale="Test", supports=[ref1, ref2], opposes=[], uncertainty="Limit"), [1], dict(scope=[1], basis_runs=[run_id]))

            g = research.graph(w, [1], history=True, basis={1: run_id})
            f_node = next(n for n in g["graph"]["nodes"] if n.get("__class__") == "FindingNode")
            self.assertIn("dependent_visual_overlap", f_node["epistemic_flags"])
            self.assertIn("unanchored_scale_direction", f_node["epistemic_flags"])
            self.assertIn("contains_negated_or_struck", f_node["epistemic_flags"])
            self.assertIn("unresolved_context_reference", f_node["epistemic_flags"])
            self.assertEqual(f_node["independence"]["raw_supports"], 2)
            self.assertEqual(f_node["independence"]["effective_independent_supports"], 1)

            with TestClient(app) as client:
                token = re.search(r'name="workspace-token"\s+content="([^"]+)"', client.get("/").text).group(1)
                headers = {"X-Workspace-Token": token}
                # Reject unresolved O3 via restored /api/ux-decision
                dec1 = client.post("/api/ux-decision", json=dict(target_type="observation", target=ref3, action="rejected", reason="Not in text"), headers=headers)
                self.assertEqual(dec1.status_code, 200)
                dec2 = client.post("/api/ux-decision", json=dict(target_type="finding", target=f_id, action="confirmed", reason="Verified"), headers=headers)
                self.assertEqual(dec2.status_code, 200)

            after = interpretation.plan(w, [1], basis={1: run_id})
            self.assertTrue(after["documents"][0]["technical"]["eligible"])
            self.assertTrue(after["documents"][0]["technical"].get("human_reconciled"))
            g2 = research.graph(w, [1], basis={1: run_id})
            f_node2 = next(n for n in g2["graph"]["nodes"] if n.get("__class__") == "FindingNode")
            self.assertEqual(f_node2["review"], "HUMAN_CONFIRMED")
            self.assertNotIn("technical_source_only", f_node2["epistemic_flags"])

    def test_single_table_symbolic_ref_comma_row_and_adjacent_odt_spans(self):
        # 1) Single table symbolic ref "table" -> REF_RECONCILED, plus comma row & header-scoped duplicate values
        doc1 = DoclingDocument(name="SingleCSV")
        tbl = doc1.add_table(
            TableData(
                num_rows=2,
                num_cols=3,
                table_cells=[
                    TableCell(start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=0, end_col_offset_idx=1, text="SumTime", column_header=True),
                    TableCell(start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=1, end_col_offset_idx=2, text="SingleTime", column_header=True),
                    TableCell(start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=2, end_col_offset_idx=3, text="Task", column_header=True),
                    TableCell(start_row_offset_idx=1, end_row_offset_idx=2, start_col_offset_idx=0, end_col_offset_idx=1, text="03:01.59"),
                    TableCell(start_row_offset_idx=1, end_row_offset_idx=2, start_col_offset_idx=1, end_col_offset_idx=2, text="03:01.59"),
                    TableCell(start_row_offset_idx=1, end_row_offset_idx=2, start_col_offset_idx=2, end_col_offset_idx=3, text="T1"),
                ],
            )
        )
        src1 = Sources(doc1, 1, "v1")
        extracted1 = UXEvidenceDocument.model_validate({
            "observations": [
                {
                    "quote": "T1",
                    "statement": "Symbolic table ref resolves when unique",
                    "origin": "original",
                    "locator": {"self_ref": "table", "row": 1, "column": 2},
                },
                {
                    "quote": "03:01.59, 03:01.59, T1",
                    "statement": "Comma-joined row with two equal times",
                    "origin": "original",
                    "locator": {"row": 1},
                    "measurements": [
                        {"raw_value": "03:01.59", "scope": "SumTime"},
                        {"raw_value": "03:01.59", "scope": "SingleTime"},
                    ],
                },
            ]
        })
        obs1, anchors1, issues1 = observation_view(dict(extracted=[extracted1.model_dump()], trace=[]), src1)
        self.assertEqual(len(obs1[0]["source_ids"]), 1)
        self.assertEqual(anchors1[obs1[0]["source_ids"][0]]["ref"], tbl.self_ref)
        self.assertTrue(any(i["status"] == "REF_RECONCILED" and i["resolved_ref"] == tbl.self_ref for i in issues1))
        self.assertEqual(len(obs1[1]["source_ids"]), 1)
        self.assertEqual(anchors1[obs1[1]["source_ids"][0]]["modality"], "table_row")
        self.assertEqual([anchors1[m["source_ids"][0]]["column"] for m in obs1[1]["measurements"]], [0, 1])

        # 2) Two tables must NOT guess "#/tables/0" for symbolic "table"
        doc2 = DoclingDocument(name="TwoTables")
        for _ in range(2):
            doc2.add_table(TableData(num_rows=1, num_cols=1, table_cells=[TableCell(start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=0, end_col_offset_idx=1, text="val")]))
        src2 = Sources(doc2, 2, "v1")
        obs2, _, issues2 = observation_view(
            dict(extracted=[{"observations": [{"quote": "val", "statement": "Ambiguous", "origin": "original", "locator": {"self_ref": "table", "row": 0, "column": 0}, "context": {}, "context_reference": None, "measurements": []}]}], trace=[]),
            src2,
        )
        self.assertEqual(obs2[0]["source_ids"], [])
        self.assertTrue(any(i["status"] == "UNRESOLVED" for i in issues2))

        # 3) Adjacent ODT paragraphs (prov=[]) resolve multi-paragraph quote + measurement in 2nd paragraph, while ellipsis fails
        odt_doc = DoclingDocument(name="OdtP3")
        q_item = odt_doc.add_text(DocItemLabel.PARAGRAPH, "2. It was simple to use this system.")
        c_item = odt_doc.add_text(DocItemLabel.PARAGRAPH, "1 -- nan")
        odt_src = Sources(odt_doc, 3, "v1")
        odt_extracted = UXEvidenceDocument.model_validate({
            "observations": [
                {
                    "quote": "2. It was simple to use this system.\n1 -- nan",
                    "statement": "Q2 rated 1",
                    "origin": "original",
                    "locator": {"self_ref": q_item.self_ref},
                    "measurements": [{"raw_value": "1", "numeric_value": 1.0, "scope": "PSSUQ Q2"}],
                },
                {
                    "quote": "2. It was simple ... nan",
                    "statement": "Ellipsis omission must stay unresolved",
                    "origin": "original",
                    "locator": {"self_ref": q_item.self_ref},
                },
            ]
        })
        odt_obs, odt_anchors, odt_issues = observation_view(dict(extracted=[odt_extracted.model_dump()], trace=[]), odt_src)
        self.assertEqual(len(odt_obs[0]["source_ids"]), 2)
        self.assertEqual([odt_anchors[eid]["ref"] for eid in odt_obs[0]["source_ids"]], [q_item.self_ref, c_item.self_ref])
        self.assertEqual(len(odt_obs[0]["measurements"][0]["source_ids"]), 1)
        self.assertEqual(odt_anchors[odt_obs[0]["measurements"][0]["source_ids"][0]]["ref"], c_item.self_ref)
        self.assertEqual(odt_obs[1]["source_ids"], [])
        self.assertTrue(any(i["observation"] == "O2" and i["status"] == "UNRESOLVED" for i in odt_issues))

        # 4) _compact_context omits redundant table text already covered in observations
        comp_tbl = interpretation._compact_context(
            {"document": 1, "chunk": 0, "self_refs": ["#/tables/0"], "text": "SumTime SingleTime Task | 03:01.59 ..."},
            quoted_by_doc_ref={(1, "#/tables/0"): "03:01.59, 03:01.59, T1"},
        )
        self.assertEqual(comp_tbl.get("text_omitted"), "table_covered_in_observations")
        self.assertNotIn("text", comp_tbl)

    def test_provider_presets_trial_key_separation_and_drive_sync_hash(self):
        self.assertEqual(models.PRESETS["gemini"]["key_env"], "GEMINI_TRIAL_KEY")
        self.assertEqual(models.ENV_ALIASES["gemini"][0], "GEMINI_TRIAL_KEY")
        self.assertIn("nhr_fau", models.PROVIDER_CATALOG_INFO)
        self.assertIn("anthropic", models.PROVIDER_CATALOG_INFO)

        import importlib.util

        sync_path = Path(__file__).resolve().parent.parent / "scripts" / "sync_google_drive.py"
        if sync_path.is_file():
            spec = importlib.util.spec_from_file_location("sync_google_drive", sync_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            files = mod.collect_tracked_files()
            self.assertTrue(any(p.name == "models.py" for p in files))
            self.assertFalse(any(p.name.startswith(".env") or ".venv" in p.parts for p in files))
            h1 = mod.compute_tree_hash(files[:5])
            h2 = mod.compute_tree_hash(files[:5])
            self.assertEqual(h1, h2)
            self.assertNotIn("AIzaSyDummyKey123456789012345", mod._redact("key=AIzaSyDummyKey123456789012345"))

    def test_r25_scale_not_applicable_human_note_handoff_and_markdown_report(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "study.txt"
            src.write_text("Status: four working, two stuck, four done.", encoding="utf-8")
            app = application(root / "work")
            w = app.state.workspace
            w.import_paths([src])
            doc = DoclingDocument(name="R25Doc")
            doc.add_page(1, Size(width=100, height=100))
            t1 = doc.add_text(
                DocItemLabel.PARAGRAPH,
                "Status: four working, two stuck, four done.",
                prov=ProvenanceItem(page_no=1, bbox=BoundingBox(l=0, t=0, r=80, b=20), charspan=(0, 43)),
            )
            p_emb = doc.add_picture(
                prov=ProvenanceItem(page_no=1, bbox=BoundingBox(l=10, t=30, r=50, b=70), charspan=(0, 0))
            )
            p_emb.meta = PictureMeta(description=DescriptionMetaField(text="Primary screenshot: Export Button hidden"))
            p_slide = doc.add_picture(
                prov=ProvenanceItem(page_no=1, bbox=BoundingBox(l=0, t=0, r=100, b=100), charspan=(0, 0))
            )
            p_slide.meta = PictureMeta(description=DescriptionMetaField(text="Full slide: Export Button hidden"))
            p_slide.meta.set_custom_field("ux_maind", "slide_context", True)

            content = doc.model_dump_json(by_alias=True, exclude_computed_fields=True).encode()
            ver = sha256(content).hexdigest()
            derived = w.artifact(w.file(1), "native").parent / "enrichment" / ver / "document.json"
            derived.parent.mkdir(parents=True)
            derived.write_bytes(content)

            sources = Sources(doc, 1, ver)
            obs_model = UXEvidenceDocument.model_validate(
                {
                    "observations": [
                        {
                            "quote": "Status: four working, two stuck, four done.",
                            "statement": "Counts of task states",
                            "origin": "original",
                            "locator": {"self_ref": t1.self_ref},
                            "measurements": [
                                {
                                    "raw_value": "four",
                                    "numeric_value": 4.0,
                                    "measurement_kind": "count",
                                    "scale_direction": "not_applicable",
                                    "scope": "working",
                                },
                                {
                                    "raw_value": "four",
                                    "numeric_value": 4.0,
                                    "measurement_kind": "count",
                                    "scale_direction": "not_applicable",
                                    "scope": "done",
                                },
                            ],
                        },
                        {
                            "quote": "Export Button hidden",
                            "statement": "Screenshot shows hidden export button",
                            "origin": "picture_description",
                            "locator": {},
                        },
                    ]
                }
            )
            obs, anchors, issues = observation_view(dict(extracted=[obs_model.model_dump()], trace=[]), sources)
            self.assertEqual(issues, [])
            # Ordered K-occurrence binding maps the two "four"s to distinct spans (8,12) and (33,37)
            m_spans = [[anchors[m["source_ids"][0]]["start"], anchors[m["source_ids"][0]]["end"]] for m in obs[0]["measurements"]]
            self.assertEqual(m_spans, [[8, 12], [33, 37]])
            # Single-page embedded + slide_context disambiguates to the primary embedded picture
            self.assertEqual(len(obs[1]["source_ids"]), 1)
            self.assertEqual(anchors[obs[1]["source_ids"][0]]["ref"], p_emb.self_ref)

            run_payload = dict(
                schema_version=SCHEMA_VERSION,
                status="UNREVIEWED",
                document_version=ver,
                observations=obs,
                sources=anchors,
                issues=[],
                native_graph=dict(extracted=[obs_model.model_dump()], trace=[], requests=[dict(finish_reason="stop")], last_response={}, error=None),
                relations=[],
            )
            with w.db() as db:
                run_id = db.execute("INSERT INTO runs(document,at,result) VALUES(1,'2026-11-18',?)", (json.dumps(run_payload),)).lastrowid

            ref1 = dict(document=1, run=run_id, observation="O1")
            ref2 = dict(document=1, run=run_id, observation="O2")
            f_id = research.create(
                w,
                "finding",
                dict(
                    title="Export-Aktion schwer auffindbar",
                    valence="negative",
                    rationale="Belegt in Statuszählung und Screenshot.",
                    supports=[ref1, ref2],
                    opposes=[],
                    uncertainty="Kleine Stichprobe",
                ),
                [1],
                dict(scope=[1], basis_runs=[run_id]),
            )

            # Count measurement with scale_direction='not_applicable' must NOT raise unanchored_scale_direction
            g = research.graph(w, [1], basis={1: run_id})
            f_node = next(n for n in g["graph"]["nodes"] if n.get("__class__") == "FindingNode")
            self.assertNotIn("unanchored_scale_direction", f_node["epistemic_flags"])

            with TestClient(app) as client:
                token = re.search(r'name="workspace-token"\s+content="([^"]+)"', client.get("/").text).group(1)
                headers = {"X-Workspace-Token": token}
                note_txt = "Wichtiger Hinweis für Synthese: P1 nutzte Zoom 125%."
                r_dec = client.post(
                    "/api/ux-decision",
                    json=dict(target_type="observation", target=ref1, action="confirmed", reason=note_txt),
                    headers=headers,
                )
                self.assertEqual(r_dec.status_code, 200)
                r_fdec = client.post(
                    "/api/ux-decision",
                    json=dict(target_type="finding", target=f_id, action="confirmed", reason="Für Abschlussbericht freigegeben."),
                    headers=headers,
                )
                self.assertEqual(r_fdec.status_code, 200)

                # Verify human note propagates into Stage B/C compact observation handoff
                planned_after = interpretation.plan(w, [1], basis={1: run_id})
                comp_obs = interpretation._compact_observation(planned_after["offered"][0])
                self.assertEqual(comp_obs["human_review"]["latest_action"], "confirmed")
                self.assertIn(note_txt, comp_obs["human_review"]["researcher_notes"])

                # Verify Markdown report export (DE + EN) and safe /api/profiles env_status
                from urllib.parse import urlencode

                q_de = urlencode(dict(documents=json.dumps([1]), basis=json.dumps({"1": run_id}), lang="de"))
                rep_de = client.get(f"/api/ux-report?{q_de}")
                self.assertEqual(rep_de.status_code, 200)
                self.assertIn("Export-Aktion schwer auffindbar", rep_de.text)
                self.assertIn("Für Abschlussbericht freigegeben.", rep_de.text)
                self.assertIn(note_txt, rep_de.text)

                q_en = urlencode(dict(documents=json.dumps([1]), basis=json.dumps({"1": run_id}), lang="en"))
                rep_en = client.get(f"/api/ux-report?{q_en}")
                self.assertEqual(rep_en.status_code, 200)
                self.assertIn("# UX-mAInd · Source-Grounded Usability Study Report", rep_en.text)

                prof = client.get("/api/profiles").json()
                self.assertIn("env_status", prof)
                self.assertIsInstance(prof["env_status"]["nhr_fau"]["configured"], bool)

    def test_native_webvtt_track_source_and_confidence_report(self):
        from ux_maind.app.evidence import model_source
        from ux_maind.app.workspace import _native_confidence

        class DummyConfidence:
            def model_dump(self, mode="json"):
                return {
                    "mean_grade": "good",
                    "low_grade": "fair",
                    "mean_score": 0.882356,
                    "low_score": 0.792259,
                    "parse_score": 1.0,
                    "layout_score": 0.784441,
                    "table_score": float("nan"),
                    "ocr_score": 0.862626,
                }

        cleaned = _native_confidence(DummyConfidence())
        self.assertEqual(cleaned["mean_grade"], "good")
        self.assertEqual(cleaned["parse_score"], 1.0)
        self.assertNotIn("table_score", cleaned)
        self.assertIsNotNone(json.dumps(cleaned, allow_nan=False))

        with TemporaryDirectory() as folder:
            root = Path(folder)
            vtt_path = root / "interview_p04.vtt"
            vtt_path.write_text(
                "WEBVTT\n\n"
                "00:00:01.000 --> 00:00:05.500\n"
                "<v Moderator>Welcome to usability session P04.</v>\n\n"
                "00:00:06.000 --> 00:00:12.200\n"
                "<v Participant P04>I clicked the filter icon twice, but nothing changed.</v>\n",
                encoding="utf-8",
            )
            app = application(root / "ws")
            w = app.state.workspace
            w.import_paths([vtt_path])
            row = w.file(1)
            self.assertEqual(row["status"], "success")
            doc = w.document(row)
            native_path = w.artifact(row, "native")
            src = Sources(doc, 1, "v1")

            # Markdown serialization copy must expose speaker voice + timecode without mutating stored doc
            with model_source(src, native_path, "markdown") as md_src_path:
                md_doc = DoclingDocument.load_from_json(md_src_path)
                exported_md = md_doc.export_to_markdown()
                self.assertIn("Voice: Participant P04 | 6.0s-12.2s", exported_md)
            self.assertNotIn("Voice:", doc.texts[1].text)

            # Docling JSON serialization copy must expose native ux_maind__track_source metadata
            with model_source(src, native_path, "auto") as json_src_path:
                json_doc = DoclingDocument.load_from_json(json_src_path)
                custom = json_doc.texts[1].meta.get_custom_part()
                self.assertEqual(custom["ux_maind__track_source"][0]["voice"], "Participant P04")

            # Quote resolution preserves native TrackSource on the anchor (even if LLM echoed the cue prefix)
            extracted = UXEvidenceDocument.model_validate(
                {
                    "observations": [
                        {
                            "quote": "I clicked the filter icon twice, but nothing changed.",
                            "statement": "Filter button gives no visual feedback",
                            "origin": "original",
                            "locator": {"self_ref": "#/texts/1"},
                        },
                        {
                            "quote": "[Voice: Participant P04 | 6.0s-12.2s] I clicked the filter icon twice, but nothing changed.",
                            "statement": "Prefixed quote still resolves deterministically",
                            "origin": "original",
                            "locator": {"self_ref": "#/texts/1"},
                        },
                    ]
                }
            )
            obs, anchors, issues = observation_view(
                dict(extracted=[extracted.model_dump()], trace=[]), src
            )
            self.assertEqual(issues, [])
            self.assertEqual(len(obs[0]["source_ids"]), 1)
            anchor = anchors[obs[0]["source_ids"][0]]
            self.assertEqual(anchor["track"][0]["voice"], "Participant P04")
            self.assertEqual(anchor["track"][0]["start_time"], 6.0)
            self.assertEqual(obs[0]["source_ids"], obs[1]["source_ids"])

            with TestClient(app) as client:
                orig_html = client.get("/document/1/original-view")
                self.assertEqual(orig_html.status_code, 200)
                self.assertIn('id="original-text"', orig_html.text)
                self.assertIn("Participant P04", orig_html.text)

    def test_r27_dynamic_catalog_telemetry_handout_and_safe_console(self):
        from unittest.mock import patch
        from urllib.parse import urlencode
        from ux_maind.app import library
        from ux_maind.app.evidence import file_digest

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "session.txt"
            src.write_text("Participant P2 hesitated at the ambiguous Save Draft button.", encoding="utf-8")
            out_dir = root / "exports"
            out_dir.mkdir(parents=True, exist_ok=True)
            app = application(root / "work")
            w = app.state.workspace
            library.output_directory(w, out_dir)
            w.import_paths([src])
            doc = w.document(w.file(1))
            ver = file_digest(w.artifact(w.file(1), "native"))
            sources = Sources(doc, 1, ver)

            extracted = UXEvidenceDocument.model_validate(
                {
                    "observations": [
                        {
                            "quote": "Participant P2 hesitated at the ambiguous Save Draft button.",
                            "statement": "Save Draft label caused hesitation",
                            "origin": "original",
                            "locator": {"self_ref": "#/texts/0"},
                        }
                    ]
                }
            )
            obs, anchors, _ = observation_view(dict(extracted=[extracted.model_dump()], trace=[]), sources)
            run_payload = dict(
                schema_version=SCHEMA_VERSION,
                status="UNREVIEWED",
                provider="nhr_fau",
                model="Qwen/Qwen3.6-35B-A3B-FP8",
                document_version=ver,
                observations=obs,
                sources=anchors,
                issues=[],
                native_graph=dict(
                    extracted=[extracted.model_dump()],
                    trace=[],
                    requests=[
                        dict(
                            finish_reason="stop",
                            reasoning_present=True,
                            usage=dict(prompt_tokens=1200, completion_tokens=300, total_tokens=1500),
                        )
                    ],
                    last_response={},
                    error=None,
                ),
                relations=[],
            )
            with w.db() as db:
                a_run_id = db.execute(
                    "INSERT INTO runs(document,at,result) VALUES(1,'2026-11-18T10:00:00Z',?)",
                    (json.dumps(run_payload),),
                ).lastrowid

            ref1 = dict(document=1, run=a_run_id, observation="O1")
            c_comp_id = research.create(
                w,
                "comparison",
                dict(stage="C", findings=1),
                [1],
                dict(
                    stage="C",
                    scope=[1],
                    basis_runs=[a_run_id],
                    provider="nhr_fau",
                    model="Qwen/Qwen3.6-35B-A3B-FP8",
                    status="UNREVIEWED",
                    counts=dict(proposed=1),
                    native_graph=dict(
                        requests=[
                            dict(
                                finish_reason="stop",
                                usage=dict(prompt_tokens=800, completion_tokens=200, total_tokens=1000),
                            )
                        ]
                    ),
                ),
            )
            research.create(
                w,
                "finding",
                dict(
                    title="Ambiguous Save Draft Action",
                    valence="problem",
                    rationale="Direct hesitation observed.",
                    supports=[ref1],
                    opposes=[],
                    uncertainty="Single session",
                ),
                [1],
                dict(scope=[1], basis_runs=[a_run_id], comparison=c_comp_id, stage="C"),
            )

            secret_val = "sk-SuperSecretNeverExpose999"
            with patch.dict("os.environ", {"CUSTOM_TEST_API_KEY": secret_val}, clear=False):
                with TestClient(app) as client:
                    token = re.search(r'name="workspace-token"\s+content="([^"]+)"', client.get("/").text).group(1)
                    headers = {"X-Workspace-Token": token}

                    # 1) /api/profiles exposes variable name but NEVER secret value
                    prof = client.get("/api/profiles")
                    self.assertEqual(prof.status_code, 200)
                    self.assertIn("CUSTOM_TEST_API_KEY", prof.json()["detected_env_vars"])
                    self.assertNotIn(secret_val, prof.text)

                    # 2) /api/model-catalog dynamically enriches live provider models
                    fake_http_resp = {
                        "data": [
                            {"id": "Qwen/Qwen3.6-35B-A3B-FP8", "max_model_len": 262144},
                            {"id": "google/gemma-4-E4B-it", "max_model_len": 131072, "supports_vision": True},
                        ]
                    }
                    with patch("ux_maind.app.models.directory_page", return_value=fake_http_resp):
                        cat = client.post(
                            "/api/model-catalog",
                            json={"provider": "nhr_fau", "key_env": "CUSTOM_TEST_API_KEY"},
                            headers=headers,
                        )
                    self.assertEqual(cat.status_code, 200)
                    cat_data = cat.json()
                    self.assertEqual(len(cat_data["models"]), 2)
                    by_id = {m["id"]: m for m in cat_data["models"]}
                    self.assertEqual(by_id["Qwen/Qwen3.6-35B-A3B-FP8"]["context_limit"], 262144)
                    self.assertTrue(by_id["google/gemma-4-E4B-it"]["supports_vision"])
                    self.assertEqual(by_id["Qwen/Qwen3.6-35B-A3B-FP8"]["input_cost_per_1m"], 0.0)

                    # 3) /api/ux-telemetry aggregates tokens & reference costs accurately
                    q = urlencode(
                        dict(
                            documents=json.dumps([1]),
                            basis=json.dumps({"1": a_run_id}),
                            result_runs=json.dumps({"C": c_comp_id}),
                        )
                    )
                    tel = client.get(f"/api/ux-telemetry?{q}").json()
                    self.assertEqual(tel["summary"]["prompt_tokens"], 2000)
                    self.assertEqual(tel["summary"]["completion_tokens"], 500)
                    self.assertEqual(tel["summary"]["total_tokens"], 2500)
                    self.assertEqual(tel["summary"]["billed_usd"], 0.0)
                    # Unlisted academic model must never invent a fictional fallback cloud price (`US-56`)
                    self.assertIsNone(tel["summary"]["cloud_reference_usd"])

                    # 4) /api/ux-handout & save-export kind="handout" produce printable CSP-clean HTML
                    ho = client.get(f"/api/ux-handout?{q}&lang=de")
                    self.assertEqual(ho.status_code, 200)
                    self.assertIn("Ambiguous Save Draft Action", ho.text)
                    self.assertIn("@media print", ho.text)
                    self.assertNotIn("<script", ho.text.lower())

                    saved_ho = client.post(
                        "/api/save-export",
                        json=dict(
                            kind="handout",
                            documents=[1],
                            basis={"1": a_run_id},
                            result_runs={"C": c_comp_id},
                            lang="en",
                        ),
                        headers=headers,
                    )
                    self.assertEqual(saved_ho.status_code, 200)
                    saved_path = Path(saved_ho.json()["path"])
                    self.assertTrue(saved_path.is_file())
                    self.assertIn("Source-Grounded Study Handout", saved_path.read_text(encoding="utf-8"))

    def test_r28_docling_conversion_settings_terminal_ledger_and_grounding_upgrades(self):
        from docling_core.types.doc import DocItemLabel, DoclingDocument, TableCell, TableData
        from starlette.testclient import TestClient
        from ux_maind.app import conversion_config, interpretation, library, receipts, studio, terminal_ui
        from ux_maind.app.evidence import Sources, observation_view
        from ux_maind.app.templates import UXEvidenceDocument

        # 1) Native Docling conversion settings validation & zero-hardcoding workflow persistence
        norm = conversion_config.normalize_conversion_settings(
            dict(
                do_ocr=False,
                force_full_page_ocr=True,
                ocr_lang="de, en",
                ocr_scale=2.5,
                table_mode="fast",
                extract_form_fields=True,
                images_scale=1.5,
                heading_hierarchy=True,
                do_code_enrichment=True,
                document_timeout=120,
                num_threads=8,
            )
        )
        self.assertFalse(norm["do_ocr"])
        self.assertTrue(norm["force_full_page_ocr"])
        self.assertEqual(norm["ocr_lang"], ["de", "en"])
        self.assertEqual(norm["table_mode"], "fast")
        self.assertEqual(norm["images_scale"], 1.5)
        self.assertEqual(norm["num_threads"], 8)
        with self.assertRaises(ValueError):
            conversion_config.normalize_conversion_settings(dict(table_mode="invalid"))

        # 2) Unicode ellipsis, math minus, HTML entity unescaping, multi-cell row & candidate_anchors
        doc = DoclingDocument(name="r28_grounding")
        t0 = doc.add_text(DocItemLabel.TEXT, "I think it's… a great flow, score value − 1.")
        doc.add_text(DocItemLabel.TEXT, "Repeated label: Pack north kit")
        doc.add_text(DocItemLabel.TEXT, "Another slide: Pack north kit")
        t3 = doc.add_text(DocItemLabel.TEXT, "Gender:")
        tbl = doc.add_table(
            data=TableData(
                num_rows=3,
                num_cols=3,
                table_cells=[
                    TableCell(text="●", start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=0, end_col_offset_idx=1, column_header=True),
                    TableCell(text="Segment", start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=1, end_col_offset_idx=2, column_header=True),
                    TableCell(text="Fläche", start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=2, end_col_offset_idx=3, column_header=True),
                    TableCell(text="●", start_row_offset_idx=1, end_row_offset_idx=2, start_col_offset_idx=0, end_col_offset_idx=1),
                    TableCell(text="Nav&gt;Menu works clearly in testing.", start_row_offset_idx=1, end_row_offset_idx=2, start_col_offset_idx=1, end_col_offset_idx=2),
                    TableCell(text="134", start_row_offset_idx=1, end_row_offset_idx=2, start_col_offset_idx=2, end_col_offset_idx=3),
                    TableCell(text="Inf", start_row_offset_idx=2, end_row_offset_idx=3, start_col_offset_idx=0, end_col_offset_idx=1),
                    TableCell(text="CS-3 fast workflow.", start_row_offset_idx=2, end_row_offset_idx=3, start_col_offset_idx=1, end_col_offset_idx=2),
                    TableCell(text="27", start_row_offset_idx=2, end_row_offset_idx=3, start_col_offset_idx=2, end_col_offset_idx=3),
                ],
            )
        )
        sources = Sources(doc, 1, "v_r28")
        model = UXEvidenceDocument.model_validate(
            dict(
                observations=[
                    # Ellipsis \u2026 <-> ... and math minus \u2212 <-> -
                    dict(
                        quote="I think it's... a great flow, score value - 1.",
                        statement="Positive flow",
                        locator=dict(self_ref=t0.self_ref),
                    ),
                    # Off-by-one unknown self_ref on short unique label ('Gender:')
                    dict(
                        quote="Gender:",
                        statement="Demographic field",
                        locator=dict(self_ref="#/texts/99"),
                    ),
                    # Bullet-column shift (declared col=0 instead of col=1) + HTML &gt; + sibling-cell metric '134'
                    dict(
                        quote="Nav>Menu works clearly in testing.",
                        statement="Navigation clear",
                        locator=dict(self_ref=tbl.self_ref, row=1, column=0),
                        measurements=[dict(raw_value="134", scope="Segmentfläche")],
                    ),
                    # Multi-cell contiguous prefix span of row 2 + sibling metric '27'
                    dict(
                        quote="Inf CS-3 fast workflow.",
                        statement="CS-3 fast",
                        locator=dict(self_ref=tbl.self_ref, row=2, column=0),
                        measurements=[dict(raw_value="27", scope="Age")],
                    ),
                    # Genuinely ambiguous multi-location quote -> UNRESOLVED with candidate_anchors
                    dict(
                        quote="Pack north kit",
                        statement="Ambiguous kit label",
                        locator=dict(),
                    ),
                ]
            )
        )
        obs, anchors, issues = observation_view(dict(extracted=[model.model_dump()], trace=[]), sources)
        self.assertTrue(obs[0]["source_ids"])
        self.assertTrue(obs[1]["source_ids"])
        self.assertTrue(obs[2]["source_ids"])
        self.assertTrue(obs[2]["measurements"][0]["source_ids"])
        self.assertTrue(obs[3]["source_ids"])
        self.assertTrue(obs[3]["measurements"][0]["source_ids"])
        self.assertFalse(obs[4]["source_ids"])
        self.assertEqual(len(obs[4].get("candidate_anchors", [])), 2)
        for anc in anchors.values():
            self.assertEqual(sources.select(anc)["evidence_id"], anc["evidence_id"])

        # 3) _compact_context keeps unquoted rows of large tables when <45% covered
        large_tbl_chunk = dict(
            document=1,
            name="study.xlsx",
            chunk="c1",
            self_refs=["#/tables/0"],
            text="Row 1 alpha beta\n" + "\n".join(f"Row {i} unquoted participant data metric {i*10}" for i in range(2, 20)),
        )
        compacted = interpretation._compact_context(large_tbl_chunk, {(1, "#/tables/0"): "Row 1 alpha beta"})
        self.assertIn("text", compacted)
        self.assertNotIn("text_omitted", compacted)

        # 4) Studio /api/workflow-settings (conversion + vision prompt) & /api/job-history endpoints
        with TemporaryDirectory(dir=Path.cwd()) as root:
            w_dir = Path(root) / "ws"
            app = studio.application(w_dir)
            w = app.state.workspace
            ev = receipts.event(
                dict(
                    kind="A",
                    phase="source_resolution",
                    document=1,
                    document_name="interview.pdf",
                    status="UNREVIEWED",
                    observations=12,
                    resolved=12,
                    total_tokens=4200,
                    model="Qwen/Qwen3.6-35B-A3B-FP8",
                )
            )
            line = terminal_ui.format_event_line("2026-11-18T14:00:00Z", ev)
            self.assertIn("Belege 12/12 verankert", line)
            self.assertIn("4,200 Tokens", line)
            self.assertIn("Qwen/Qwen3.6-35B-A3B-FP8", line)
            terminal_ui.append_job_history(
                w,
                dict(
                    action="workflow",
                    state="FINISHED",
                    started="2026-11-18T14:00:00Z",
                    ended="2026-11-18T14:01:00Z",
                    documents=[dict(document=1, document_name="interview.pdf", status="UNREVIEWED")],
                    events=[dict(at="2026-11-18T14:00:00Z", **ev)],
                ),
            )
            with TestClient(app, base_url="http://127.0.0.1:8465") as client:
                token = re.search(r'name="workspace-token" content="([^"]+)"', client.get("/").text)[1]
                headers = {"x-workspace-token": token}
                wf_res = client.post(
                    "/api/workflow-settings",
                    json=dict(
                        conversion=dict(table_mode="fast", images_scale=1.75),
                        vision=dict(scale=2.5, prompt="Custom UX slide inspection prompt"),
                    ),
                    headers=headers,
                )
                self.assertEqual(wf_res.status_code, 200)
                wf_json = wf_res.json()
                self.assertEqual(wf_json["conversion"]["table_mode"], "fast")
                self.assertEqual(wf_json["conversion"]["images_scale"], 1.75)
                self.assertEqual(wf_json["vision"]["scale"], 2.5)
                self.assertEqual(wf_json["vision"]["prompt"], "Custom UX slide inspection prompt")
                self.assertTrue(wf_json["vision"]["default_prompt"])

                hist = client.get("/api/job-history").json()
                self.assertEqual(len(hist["history"]), 1)
                self.assertEqual(hist["history"][0]["action"], "workflow")
                clr = client.post("/api/job-history-clear", json={}, headers=headers)
                self.assertEqual(clr.status_code, 200)
                self.assertEqual(client.get("/api/job-history").json()["history"], [])




