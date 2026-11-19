"""Comprehensive R29 Audit & Architecture Contract Tests (B-01..B-32, US-01..US-24)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from docling_core.transforms.serializer.doclang import DocLangDocSerializer
from docling_core.types.doc import (
    ContentLayer,
    DescriptionMetaField,
    DocItemLabel,
    DoclingDocument,
    PictureMeta,
    TabularChartMetaField,
    TableCell,
    TableData,
)
from starlette.testclient import TestClient

from ux_maind.app import (
    a_status,
    enrichment,
    evidence,
    interpretation,
    library,
    prompts_config,
    receipts,
    research,
    telemetry,
)
from ux_maind.app.studio import _format_progress_label, application
from ux_maind.app.templates import UXEvidenceDocument
from ux_maind.app.workspace import Workspace


class R29StudioAuditTests(unittest.TestCase):
    def test_b01_progress_message_stays_string_and_never_dict(self):
        ev = receipts.event(
            dict(kind="A", workflow_step="A", document=1, document_name="interview.txt", status="UNREVIEWED")
        )
        msg = _format_progress_label(ev)
        self.assertIsInstance(msg, str)
        self.assertIn("interview.txt", msg)

    def test_b04_b07_compact_measurement_and_anchor_preserve_all_fields(self):
        m = {
            "raw_value": "4.5 / 5",
            "numeric_value": 4.5,
            "unit": "points",
            "scope": "Task 1 Ease",
            "measurement_kind": "rating_scale",
            "scale_direction": "higher_is_better",
            "uncertainty": " verbal estimate",
            "sources": [{"ref": "#/tables/0", "row": 1, "column": 2}],
        }
        cm = interpretation._compact_measurement(m)
        self.assertEqual(cm["numeric_value"], 4.5)
        self.assertEqual(cm["uncertainty"], " verbal estimate")
        self.assertEqual(cm["scale_direction"], "higher_is_better")

        anc = {
            "evidence_id": "abc",
            "ref": "#/texts/3",
            "modality": "text",
            "quote": "Wait",
            "row": 1,
            "row_end": 3,
            "column": 0,
            "column_end": 4,
            "track": [{"voice": "P02", "start_time": 12.0, "end_time": 15.5}],
            "outline": [{"ref": "#/texts/0", "label": "section_header", "text": "Checkout"}],
            "formatting": {"bold": True, "italic": False, "strikethrough": True},
            "strikethrough_spans": ["old label"],
            "prov": [{"page_no": 2}],
        }
        ca = interpretation._compact_anchor(anc, include_quote=False)
        self.assertEqual(ca["row_end"], 3)
        self.assertEqual(ca["column_end"], 4)
        self.assertEqual(ca["track"][0]["voice"], "P02")
        self.assertEqual(ca["outline"], ["Checkout"])
        self.assertEqual(ca["formatting"], {"bold": True, "strikethrough": True})
        self.assertEqual(ca["strikethrough_spans"], ["old label"])

    def test_b05_table_caption_exposes_source_ref_and_headers_in_doclang_and_markdown(self):
        doc = DoclingDocument(name="table_doc")
        doc.add_text(DocItemLabel.TEXT, "Intro paragraph")
        tbl = doc.add_table(
            data=TableData(
                num_rows=2,
                num_cols=2,
                table_cells=[
                    TableCell(
                        text="Participant",
                        row_span=1,
                        col_span=1,
                        start_row_offset_idx=0,
                        end_row_offset_idx=1,
                        start_col_offset_idx=0,
                        end_col_offset_idx=1,
                        column_header=True,
                    ),
                    TableCell(
                        text="Completion (s)",
                        row_span=1,
                        col_span=1,
                        start_row_offset_idx=0,
                        end_row_offset_idx=1,
                        start_col_offset_idx=1,
                        end_col_offset_idx=2,
                        column_header=True,
                    ),
                    TableCell(
                        text="P01",
                        row_span=1,
                        col_span=1,
                        start_row_offset_idx=1,
                        end_row_offset_idx=2,
                        start_col_offset_idx=0,
                        end_col_offset_idx=1,
                    ),
                    TableCell(
                        text="48.2",
                        row_span=1,
                        col_span=1,
                        start_row_offset_idx=1,
                        end_row_offset_idx=2,
                        start_col_offset_idx=1,
                        end_col_offset_idx=2,
                    ),
                ],
            )
        )
        sources = evidence.Sources(doc, 1, "v1")
        with evidence.model_source(sources, Path("doc.json"), "doclang-geo") as p_dl:
            offered = DoclingDocument.load_from_json(p_dl)
            dl_txt = DocLangDocSerializer(doc=offered).serialize().text
            self.assertIn("source_ref=#/tables/0", dl_txt)
            self.assertIn("Completion (s)", dl_txt)
        with evidence.model_source(sources, Path("doc.json"), "markdown") as p_md:
            offered_md = DoclingDocument.load_from_json(p_md).export_to_markdown()
            self.assertIn("#/tables/0", offered_md)
            self.assertIn("Completion (s)", offered_md)
        # Original document remains untouched
        self.assertEqual(len(doc.tables[0].captions), 0)
        self.assertEqual(len(doc.texts), 1)
        _ = tbl

    def test_b06_multi_row_table_context_not_dropped_when_partially_quoted(self):
        multi_table_md = (
            "| Participant | Task | Time |\n"
            "| --- | --- | --- |\n"
            "| P01 | Checkout | 42s |\n"
            "| P02 | Checkout | 95s |\n"
            "| P03 | Checkout | 118s |\n"
            "| P04 | Checkout | 31s |\n"
        )
        partial = interpretation._compact_context(
            {"document": 1, "chunk": 0, "self_refs": ["#/tables/0"], "text": multi_table_md},
            quoted_by_doc_ref={(1, "#/tables/0"): "P01 42s P02 95s"},
        )
        self.assertIn("text", partial)
        self.assertNotIn("text_omitted", partial)

        full = interpretation._compact_context(
            {"document": 1, "chunk": 0, "self_refs": ["#/tables/0"], "text": multi_table_md},
            quoted_by_doc_ref={(1, "#/tables/0"): "P01 42s P02 95s P03 118s P04 31s"},
        )
        self.assertEqual(full.get("text_omitted"), "table_covered_in_observations")

    def test_b15_chart_enables_picture_classification_automatically(self):
        conv, rec = enrichment.converter(
            vision={
                "enabled": True,
                "mode": "inline",
                "description": False,
                "classification": False,
                "chart": True,
            }
        )
        self.assertTrue(rec["classification"])
        from docling.datamodel.base_models import InputFormat

        pdf_opts = conv.format_to_options[InputFormat.PDF].pipeline_options
        self.assertTrue(pdf_opts.do_picture_classification)
        self.assertTrue(pdf_opts.do_chart_extraction)

    def test_b18_derived_matches_preserve_quote_and_chart_cell_and_reselect(self):
        doc = DoclingDocument(name="vis")
        pic = doc.add_picture()
        pic.meta = PictureMeta(
            description=DescriptionMetaField(text="Connector from Login -> Error Modal."),
            tabular_chart=TabularChartMetaField(
                title="Errors",
                chart_data=TableData(
                    num_rows=2,
                    num_cols=2,
                    table_cells=[
                        TableCell(
                            text="Step",
                            row_span=1,
                            col_span=1,
                            start_row_offset_idx=0,
                            end_row_offset_idx=1,
                            start_col_offset_idx=0,
                            end_col_offset_idx=1,
                        ),
                        TableCell(
                            text="Count",
                            row_span=1,
                            col_span=1,
                            start_row_offset_idx=0,
                            end_row_offset_idx=1,
                            start_col_offset_idx=1,
                            end_col_offset_idx=2,
                        ),
                        TableCell(
                            text="Checkout",
                            row_span=1,
                            col_span=1,
                            start_row_offset_idx=1,
                            end_row_offset_idx=2,
                            start_col_offset_idx=0,
                            end_col_offset_idx=1,
                        ),
                        TableCell(
                            text="14",
                            row_span=1,
                            col_span=1,
                            start_row_offset_idx=1,
                            end_row_offset_idx=2,
                            start_col_offset_idx=1,
                            end_col_offset_idx=2,
                        ),
                    ],
                ),
            ),
        )
        src = evidence.Sources(doc, 1, "v1")
        desc_anc = src.locate("Login -> Error Modal", {"self_ref": pic.self_ref}, "picture_description")
        self.assertEqual(desc_anc["quote"], "Login -> Error Modal")
        self.assertEqual(src.select(desc_anc)["quote"], "Login -> Error Modal")

        chart_anc = src.locate(
            "14", {"self_ref": pic.self_ref, "row": 1, "column": 1}, "chart_enrichment"
        )
        self.assertEqual(chart_anc["chart_cell"]["row"], 1)
        self.assertEqual(chart_anc["chart_cell"]["column"], 1)
        reselected = src.select(chart_anc)
        self.assertEqual(reselected["chart_cell"]["text"], "14")

    def test_r29_studio_endpoints_markdown_export_prompts_sorting_and_handout_filtering(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "ws"
            app = application(root)
            w: Workspace = app.state.workspace

            # Verify SQLite WAL mode
            with w.db() as db:
                mode = db.execute("PRAGMA journal_mode").fetchone()[0]
                self.assertEqual(mode.lower(), "wal")

            f1 = Path(tmp) / "alpha_session.txt"
            f2 = Path(tmp) / "beta_notes.txt"
            f1.write_text("Participant P1 struggled with the export button.", encoding="utf-8")
            f2.write_text("Participant P2 praised the keyboard shortcut.", encoding="utf-8")
            w.import_paths([f1, f2])

            # Add speaker note to doc 1 to verify Markdown export includes ContentLayer.NOTES
            d1 = w.document(w.file(1))
            d1.add_text(DocItemLabel.TEXT, "Moderator slide note: check contrast", content_layer=ContentLayer.NOTES)
            w.artifact(w.file(1), "native").write_bytes(
                d1.model_dump_json(by_alias=True, exclude_computed_fields=True).encode("utf-8")
            )

            # B-10: newest sort + origin search
            newest_ids = [x["id"] for x in w.files(sort="newest")["items"]]
            self.assertEqual(newest_ids, [2, 1])
            self.assertEqual(w.files(search="alpha_session")["total"], 1)

            # Store synthetic Stage A run + Stage B/C objects to verify handout filtering, correction & telemetry
            src1 = evidence.Sources(w.document(w.file(1)), 1, evidence.file_digest(w.artifact(w.file(1), "native")))
            ext1 = UXEvidenceDocument.model_validate(
                {
                    "observations": [
                        {
                            "quote": "Participant P1 struggled with the export button.",
                            "statement": "P1 struggled with export button",
                            "origin": "original",
                            "locator": {"self_ref": "#/texts/0"},
                        }
                    ]
                }
            )
            obs1, anc1, iss1 = evidence.observation_view(
                {"extracted": [ext1.model_dump(mode="json")], "trace": []}, src1
            )
            with w.db() as db:
                run1_id = db.execute(
                    "INSERT INTO runs(document,at,result) VALUES(1,'2026-11-18T10:00:00Z',?)",
                    (
                        json.dumps(
                            {
                                "schema_version": evidence.SCHEMA_VERSION,
                                "provider": "nhr_fau",
                                "model": "Qwen/Qwen3.6-35B-A3B-FP8",
                                "status": "UNREVIEWED",
                                "document_version": src1.version,
                                "observations": obs1,
                                "relations": [],
                                "sources": anc1,
                                "issues": iss1,
                                "input": {"processing": "one-to-one"},
                                "coverage": {"missing_ledger_items": 0, "undocumented_ledger_items": 1},
                                "native_graph": {
                                    "extracted": [ext1.model_dump(mode="json")],
                                    "requests": [
                                        {
                                            "finish_reason": "stop",
                                            "usage": {"prompt_tokens": 500, "completion_tokens": 120, "total_tokens": 620},
                                        }
                                    ],
                                },
                            }
                        ),
                    ),
                ).lastrowid

            # B-27: one-to-one mode with undocumented_ledger_items does not falsely block eligibility
            with w.db() as db:
                stored_res = json.loads(db.execute("SELECT result FROM runs WHERE id=?", (run1_id,)).fetchone()[0])
            self.assertTrue(a_status.dimensions(stored_res)["eligible"])

            comp_c = research.create(
                w,
                "comparison",
                [],
                [1],
                {
                    "origin": "model",
                    "stage": "C",
                    "status": "UNREVIEWED",
                    "provider": "nhr_fau",
                    "model": "Qwen/Qwen3.6-35B-A3B-FP8",
                    "observations": [{"document": 1, "run": run1_id, "observation": "O1"}],
                    "basis_runs": [run1_id],
                    "basis_by_doc": {"1": run1_id},
                    "counts": {"proposed": 2, "unresolved": 0},
                    "native_graph": {
                        "requests": [
                            {"finish_reason": "stop", "usage": {"prompt_tokens": 300, "completion_tokens": 90, "total_tokens": 390}}
                        ]
                    },
                },
            )
            f_keep = research.create(
                w,
                "finding",
                {
                    "title": "Export button lacks discoverability",
                    "valence": "problem",
                    "rationale": "P1 struggled directly.",
                    "supports": [{"document": 1, "run": run1_id, "observation": "O1"}],
                    "opposes": [],
                    "uncertainty": "Single participant session",
                },
                [1],
                {"origin": "model", "stage": "C", "comparison": comp_c, "observations": [{"document": 1, "run": run1_id, "observation": "O1"}]},
            )
            f_reject = research.create(
                w,
                "finding",
                {
                    "title": "Spurious hallucinated theme",
                    "valence": "neutral",
                    "rationale": "Weak link.",
                    "supports": [{"document": 1, "run": run1_id, "observation": "O1"}],
                    "opposes": [],
                    "uncertainty": "High",
                },
                [1],
                {"origin": "model", "stage": "C", "comparison": comp_c, "observations": [{"document": 1, "run": run1_id, "observation": "O1"}]},
            )
            research.decide(
                w,
                {
                    "target_type": "finding",
                    "target": f_keep,
                    "action": "corrected",
                    "reason": "Bounded scope to P1",
                    "payload": {"interpretation": {"scope": "Participant P1 only"}},
                },
            )
            research.decide(
                w,
                {
                    "target_type": "finding",
                    "target": f_reject,
                    "action": "rejected",
                    "reason": "Over-interpreted",
                    "payload": {},
                },
            )

            with TestClient(app) as client:
                token = client.get("/").text.split('name="workspace-token" content="')[1].split('"')[0]
                headers = {"x-workspace-token": token}

                # Custom stage prompts round-trip
                wf_res = client.post(
                    "/api/workflow-settings",
                    json={
                        "stage_prompts": {
                            "vision": "Transcribe every chart bar.",
                            "A": "Focus on time-on-task.",
                            "B": "Check task order.",
                            "C": "Highlight scope limits.",
                        }
                    },
                    headers=headers,
                )
                self.assertEqual(wf_res.status_code, 200)
                wf_json = wf_res.json()
                self.assertEqual(wf_json["stage_prompts"]["A"], "Focus on time-on-task.")
                self.assertEqual(wf_json["vision"]["prompt"], "Transcribe every chart bar.")
                sub_cls = prompts_config.apply_stage_prompt(UXEvidenceDocument, wf_json["stage_prompts"]["A"])
                self.assertIn("Focus on time-on-task.", sub_cls.model_json_schema()["description"])

                # Docling Markdown download & save-export
                md_dl = client.get("/document/1/markdown")
                self.assertEqual(md_dl.status_code, 200)
                self.assertIn("Participant P1 struggled", md_dl.text)
                self.assertIn("Moderator slide note: check contrast", md_dl.text)

                exp_md = client.post("/api/save-export", json={"kind": "markdown", "document": 1}, headers=headers)
                self.assertEqual(exp_md.status_code, 200)
                exp_ho = client.post(
                    "/api/save-export",
                    json={"kind": "handout", "documents": [1], "basis": {"1": run1_id}, "result_runs": {"B": None, "C": comp_c}},
                    headers=headers,
                )
                self.assertEqual(exp_ho.status_code, 200)

                ex_list = client.get("/api/exports-list").json()
                self.assertGreaterEqual(len(ex_list["items"]), 2)
                html_item = next(i for i in ex_list["items"] if i["suffix"] == ".html")
                served_ho = client.get(f"/api/export-file?name={html_item['filename']}")
                self.assertEqual(served_ho.status_code, 200)
                self.assertIn("Participant P1 only", served_ho.text)
                self.assertIn("Verworfene Modellvorschläge", served_ho.text)

                # Single-roundtrip workspace-bundle
                bundle = client.get("/api/workspace-bundle?documents=[1,2]").json()
                self.assertEqual(len(bundle), 2)
                self.assertEqual(bundle[0]["file"]["id"], 1)

                # Telemetry model_comparison
                tel = telemetry.study_telemetry(w, [1], basis={1: run1_id}, result_runs={"B": None, "C": comp_c})
                self.assertGreaterEqual(len(tel["model_comparison"]), 2)
                a_mc = next(m for m in tel["model_comparison"] if m["stage"] == "A")
                self.assertEqual(a_mc["anchor_rate_pct"], 100.0)

    def test_r30_schema_zero_truncation_and_salvaged_status(self):
        from docling_graph.llm_clients.schema_utils import build_compact_semantic_guide
        from ux_maind.app.templates import (
            FindingHypotheses,
            FindingProposal,
            RelationshipProposals,
            UXEvidenceDocument,
        )

        # US-32: Zero field descriptions exceed 250 chars across all Stage A, B, C templates
        for model_cls in (UXEvidenceDocument, RelationshipProposals, FindingHypotheses):
            schema = model_cls.model_json_schema()
            for def_name, def_obj in (schema.get("$defs") or {}).items():
                for prop_name, prop_obj in (def_obj.get("properties") or {}).items():
                    desc = prop_obj.get("description") or ""
                    self.assertLessEqual(
                        len(desc),
                        249,
                        f"{model_cls.__name__}.{def_name}.{prop_name} description length={len(desc)} >= 250",
                    )
            guide = build_compact_semantic_guide(schema)
            truncated_lines = [ln for ln in guide.splitlines() if ln.rstrip().endswith("...")]
            self.assertEqual(truncated_lines, [])

        # US-61: FindingProposal supports usability_heuristic
        fp = FindingProposal(
            title="Unclear status",
            valence="problem",
            usability_heuristic="H1: Visibility of System Status (Nielsen)",
            rationale="Users missed feedback.",
            supports=[{"document": 1, "run": 1, "observation": "O1"}],
            uncertainty="N=4",
        )
        self.assertEqual(fp.usability_heuristic, "H1: Visibility of System Status (Nielsen)")

        # US-34: Salvaged schema status surfaces as SCHEMA_SALVAGED
        dim_salvaged = a_status.dimensions(
            {
                "status": "UNREVIEWED",
                "observations": [{"id": "O1", "source_ids": ["S1"], "measurements": []}],
                "issues": [],
                "input": {"processing": "one-to-one"},
                "native_graph": {"salvaged": True, "requests": [{"finish_reason": "stop"}]},
            }
        )
        self.assertIn("a_schema_salvaged", dim_salvaged["reasons"])
        self.assertTrue(dim_salvaged["salvaged"])

    def test_r30_regrounding_ligatures_hyphens_word_boundary_and_forms(self):
        doc = DoclingDocument(name="r30_doc")
        # PDF ligature ﬁ + line-break hyphenation + percentage boundary trap (15% vs 5%)
        t0 = doc.add_text(
            DocItemLabel.TEXT,
            "Only 15% succeeded, whereas 5% failed to ﬁnd the button across nav-\nigation menus.",
        )
        t_scale = doc.add_text(DocItemLabel.FIELD_HINT, "1 = strongly disagree to 7 = strongly agree")
        t_hw = doc.add_text(DocItemLabel.HANDWRITTEN_TEXT, "Margin note: confusing icon")
        src = evidence.Sources(doc, 1, "v_r30")

        # US-36: "5%" must NOT match inside "15%", must bind uniquely to standalone "5%"
        anc_pct = src.locate("5%", {"self_ref": t0.self_ref}, "original")
        self.assertEqual(anc_pct["ref"], t0.self_ref)
        self.assertEqual(t0.text[anc_pct["start"] : anc_pct["end"]], "5%")

        # US-30: "find the button across navigation menus" matches PDF ligature ﬁ + hyphenated line break
        anc_lig = src.locate(
            "find the button across navigation menus", {"self_ref": t0.self_ref}, "original"
        )
        self.assertEqual(anc_lig["ref"], t0.self_ref)

        # US-38: FIELD_HINT & HANDWRITTEN_TEXT serialize cleanly in DocLang and locate accurately
        anc_scale = src.locate("1 = strongly disagree", {"self_ref": t_scale.self_ref}, "original")
        self.assertEqual(anc_scale["ref"], t_scale.self_ref)
        anc_hw = src.locate("Margin note: confusing icon", {"self_ref": t_hw.self_ref}, "original")
        self.assertEqual(anc_hw["ref"], t_hw.self_ref)
        with evidence.model_source(src, Path("r30.json"), "doclang-geo") as tmp_dl:
            dl_text = DocLangDocSerializer(doc=DoclingDocument.load_from_json(tmp_dl)).serialize().text
            self.assertIn("Margin note: confusing icon", dl_text)

        # US-39: quoted_lists handles German „..." quotes cleanly without spawning DocumentConverter
        d_list = DoclingDocument(name="de_quotes")
        t_de = d_list.add_text(
            DocItemLabel.TEXT,
            "Teilnehmer P3 sagte: „1. Filter schwer auffindbar\n2. Zurück-Button unklar“.",
        )
        src_de = evidence.Sources(d_list, 2, "v_de")
        anc_de = src_de.locate("1. Filter schwer auffindbar", None, "original")
        self.assertEqual(anc_de["ref"], t_de.self_ref)

    def test_r30_epistemics_rejected_supports_speakers_carry_forward_and_genuine_pricing(self):
        from ux_maind.app import models, terminal_ui

        # US-55: Qwen3.6-35B-A3B-FP8 recognized as multimodal
        cap = models._infer_open_multimodal("Qwen/Qwen3.6-35B-A3B-FP8")
        self.assertTrue(cap)

        # US-56: Zero fictional prices — nhr_fau is 0.00 billed and None cloud_reference when unlisted
        cost_fau = telemetry._estimate_cost("nhr_fau", "Qwen/Qwen3.6-35B-A3B-FP8", 10000, 2000)
        self.assertEqual(cost_fau["billed_usd"], 0.0)
        self.assertIsNone(cost_fau["cloud_reference_usd"])

        with TemporaryDirectory() as tmp:
            app = application(Path(tmp) / "ws_r30")
            w: Workspace = app.state.workspace
            p = Path(tmp) / "p1.txt"
            p.write_text("Ava: The filter resets unexpectedly.\nBen: Same reset happened to me.", encoding="utf-8")
            w.import_paths([p])
            src = evidence.Sources(w.document(w.file(1)), 1, evidence.file_digest(w.artifact(w.file(1), "native")))
            ext = UXEvidenceDocument.model_validate(
                {
                    "observations": [
                        {
                            "quote": "Ava: The filter resets unexpectedly.",
                            "statement": "Filter resets unexpectedly",
                            "origin": "original",
                            "context": {"actor_or_speaker": "Ava"},
                        },
                        {
                            "quote": "Ben: Same reset happened to me.",
                            "statement": "Ben experienced same reset",
                            "origin": "original",
                            "context": {"actor_or_speaker": "Ben"},
                        },
                    ]
                }
            )
            obs, anc, iss = evidence.observation_view({"extracted": [ext.model_dump(mode="json")], "trace": []}, src)
            with w.db() as db:
                r1 = db.execute(
                    "INSERT INTO runs(document,at,result) VALUES(1,'2026-11-18T11:00:00Z',?)",
                    (
                        json.dumps(
                            {
                                "schema_version": evidence.SCHEMA_VERSION,
                                "provider": "nhr_fau",
                                "model": "Qwen/Qwen3.6-35B-A3B-FP8",
                                "status": "UNREVIEWED",
                                "document_version": src.version,
                                "observations": obs,
                                "relations": [],
                                "sources": anc,
                                "issues": iss,
                            }
                        ),
                    ),
                ).lastrowid
                r2 = db.execute(
                    "INSERT INTO runs(document,at,result) VALUES(1,'2026-11-18T11:05:00Z',?)",
                    (
                        json.dumps(
                            {
                                "schema_version": evidence.SCHEMA_VERSION,
                                "provider": "nhr_fau",
                                "model": "mistralai/Mistral-Medium-3.5-128B",
                                "status": "UNREVIEWED",
                                "document_version": src.version,
                                "observations": obs,
                                "relations": [],
                                "sources": anc,
                                "issues": iss,
                            }
                        ),
                    ),
                ).lastrowid

            # Reject O2 on run r1, confirm O1 on run r1
            research.decide(
                w,
                {
                    "target_type": "observation",
                    "target": {"document": 1, "run": r1, "observation": "O1"},
                    "action": "confirmed",
                    "reason": "Verified quote",
                    "payload": {},
                },
            )
            research.decide(
                w,
                {
                    "target_type": "observation",
                    "target": {"document": 1, "run": r1, "observation": "O2"},
                    "action": "rejected",
                    "reason": "Test rejection propagation",
                    "payload": {},
                },
            )

            # US-47: Carry forward human decisions from r1 to r2 via quote fingerprint
            cf = research.carry_forward_decisions(w, 1, r2)
            self.assertGreaterEqual(cf["carried_forward"], 2)

            # US-45 & US-46: Finding referencing rejected O2 gets contains_rejected_support & distinct_speakers
            comp_id = research.create(
                w,
                "comparison",
                [],
                [1],
                {
                    "origin": "model",
                    "stage": "C",
                    "status": "UNREVIEWED",
                    "observations": [
                        {"document": 1, "run": r1, "observation": "O1"},
                        {"document": 1, "run": r1, "observation": "O2"},
                    ],
                    "basis_runs": [r1],
                    "basis_by_doc": {"1": r1},
                },
            )
            research.create(
                w,
                "finding",
                {
                    "title": "Filter state loss",
                    "valence": "problem",
                    "rationale": "Observed by Ava and Ben.",
                    "supports": [
                        {"document": 1, "run": r1, "observation": "O1"},
                        {"document": 1, "run": r1, "observation": "O2"},
                    ],
                    "opposes": [],
                    "uncertainty": "Two participants",
                },
                [1],
                {"origin": "model", "stage": "C", "comparison": comp_id, "observations": [{"document": 1, "run": r1, "observation": "O1"}, {"document": 1, "run": r1, "observation": "O2"}]},
            )
            rg = research.graph(w, [1], basis={1: r1}, result_runs={"B": None, "C": comp_id})
            fn = next(n for n in rg["graph"]["nodes"] if n["__class__"] == "FindingNode")
            self.assertIn("contains_rejected_support", fn["epistemic_flags"])
            self.assertEqual(fn["independence"]["effective_independent_supports"], 1)
            self.assertEqual(fn["independence"]["distinct_speakers"], 1)

            # US-58: terminal_ui.read_job_history reconstructs SQLite runs when job_history is empty
            hist = terminal_ui.read_job_history(w)
            self.assertGreaterEqual(len(hist), 1)

            # US-54 & US-62: Base prompt override + reset and /api/manual endpoint
            with TestClient(app) as client:
                token = client.get("/").text.split('name="workspace-token" content="')[1].split('"')[0]
                headers = {"x-workspace-token": token}

                man = client.get("/api/manual").json()
                self.assertIn("UX-mAInd", man["user_manual"])
                self.assertIn("Docling", man["system_limits"])

                wf_bp = client.post(
                    "/api/workflow-settings",
                    json={"base_prompts": {"A": "Custom Base A Prompt"}, "stage_prompts": {"A": "Extra Rule A"}},
                    headers=headers,
                ).json()
                self.assertEqual(wf_bp["base_prompts"]["A"], "Custom Base A Prompt")
                overridden_cls = prompts_config.apply_stage_prompt(
                    UXEvidenceDocument,
                    wf_bp["stage_prompts"]["A"],
                    base_override=wf_bp["base_prompts"]["A"],
                )
                desc_a = overridden_cls.model_json_schema()["description"]
                self.assertTrue(desc_a.startswith("Custom Base A Prompt"))
                self.assertIn("Extra Rule A", desc_a)

    def test_us69_fau_timeout_watchdog_and_console_diagnostics(self):
        import time as _time
        import httpx
        from unittest.mock import patch
        from ux_maind.app import models, terminal_ui

        # 1. Safe detail preservation & secret redaction in receipts
        ev = receipts.event(
            {
                "kind": "A",
                "phase": "structured_fallback",
                "status": "WARN",
                "document": 5,
                "document_name": "document_05.docx",
                "model": "deepseek-ai/DeepSeek-V4-Flash-0731",
                "http_status": 500,
                "timeout_s": 120.0,
                "attempt": 1,
                "max_attempts": 2,
                "reasoning_tokens": 4200,
                "total_tokens": 6000,
                "detail": "Zeitüberschreitung bei json_schema Bearer secret-tok-123 — Fallback",
            }
        )
        self.assertNotIn("secret-tok-123", ev["detail"])
        self.assertIn("[REDACTED]", ev["detail"])
        self.assertEqual(ev["timeout_s"], 120.0)
        self.assertEqual(ev["reasoning_tokens"], 4200)
        line = terminal_ui.format_event_line("2026-11-18T22:45:10Z", ev)
        self.assertTrue(line.startswith("✖ ") or line.startswith("⚠ "))
        self.assertIn("document_05.docx", line)
        self.assertIn("HTTP 500", line)

        # 2. Hard wall-clock timeout watchdog & live console emission without SDK retry multiplication
        with TemporaryDirectory() as root:
            p = Path(root) / "note.txt"
            p.write_text("Button is too small.", encoding="utf-8")
            w = Workspace(Path(root) / "ws")
            w.import_paths([p])

            events_seen = []

            def _stalled_call(**kwargs):
                self.assertIsInstance(kwargs["timeout"], httpx.Timeout)
                self.assertEqual(kwargs["num_retries"], 0)
                self.assertEqual(kwargs["max_retries"], 0)
                _time.sleep(2.5)
                return {"choices": []}

            t0 = _time.monotonic()
            with patch("litellm.completion", side_effect=_stalled_call):
                w.extract(
                    [1],
                    {
                        "provider": "nhr_fau",
                        "model": "synthetic-slow",
                        "key": "top-secret-key",
                        "context_limit": 32000,
                        "gleaning_enabled": False,
                        "reliability": {"timeout_s": 1, "max_retries": 0},
                    },
                    progress=lambda e: events_seen.append(receipts.event(e)),
                )
            elapsed = _time.monotonic() - t0
            self.assertLess(elapsed, 4.5)
            res = w.results(1)[0]["result"]
            self.assertEqual(res["status"], "ERROR")
            self.assertEqual(res["diagnostic"]["stage"], "api_request")
            self.assertEqual(res["diagnostic"]["reason"], "request_timeout")
            self.assertNotIn("top-secret-key", json.dumps(res) + json.dumps(events_seen))
            phases = [e.get("phase") for e in events_seen]
            self.assertIn("model_timeout", phases)

            # 3. Upstream HTTP 500 Hosted_vllmException fails fast and surfaces provider_backend_unavailable
            events_500 = []

            class _Fake500Error(RuntimeError):
                status_code = 500

            with patch(
                "litellm.completion",
                side_effect=_Fake500Error("Hosted_vllmException - Cannot connect to host a2742.nhr.fau.de:8101"),
            ):
                w.extract(
                    [1],
                    {
                        "provider": "nhr_fau",
                        "model": "Qwen/Qwen3.6-35B-A3B-FP8",
                        "key": "top-secret-key",
                        "context_limit": 32000,
                        "gleaning_enabled": False,
                        "reliability": {"timeout_s": 10, "max_retries": 2},
                    },
                    progress=lambda e: events_500.append(receipts.event(e)),
                )
            res_500 = w.results(1)[0]["result"]
            self.assertEqual(res_500["diagnostic"]["reason"], "provider_backend_unavailable")
            self.assertEqual(res_500["diagnostic"]["http_status"], 500)
            self.assertTrue(any("Upstream-Modellserver" in (e.get("detail") or "") for e in events_500))

    def test_r31a_wcag_schema_and_orphaned_display_cleanup(self):
        """US-70 & US-71: W3C WCAG 2.2 fits <=240 char schema guide and orphaned display cache is cleaned."""
        import tempfile
        from ux_maind.app import templates

        desc = templates.FindingProposal.model_fields["usability_heuristic"].description or ""
        self.assertIn("WCAG 2.2", desc)
        self.assertLessEqual(len(desc), 240)

        with TemporaryDirectory() as tmp:
            from ux_maind.app import library

            w = Workspace(Path(tmp) / "ws")
            src_file = Path(tmp) / "sample.txt"
            src_file.write_text("P1: Kontrast auf dem Button ist schwer lesbar.", encoding="utf-8")
            sha = evidence.file_digest(src_file)
            w.import_paths([src_file])
            f = w.files()["items"][0]
            disp_dir = w.root / "display" / sha[:16]
            disp_dir.mkdir(parents=True, exist_ok=True)
            (disp_dir / "display.json").write_text(json.dumps({"source_sha256": sha}), encoding="utf-8")
            (disp_dir / "derived.pdf").write_bytes(b"%PDF-1.4 dummy")
            self.assertTrue(disp_dir.is_dir())
            library.remove(w, [f["id"]], "remove")
            self.assertFalse(disp_dir.exists())


if __name__ == "__main__":
    unittest.main()
