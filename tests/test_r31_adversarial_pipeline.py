"""US-72 (R31-B): Contamination guard for expert codebooks, wide-survey header disambiguation & adversarial pipeline tests."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from docling_core.types.doc import DocItemLabel, DoclingDocument, TableCell, TableData
from starlette.testclient import TestClient

from ux_maind.app import evidence, interpretation, research
from ux_maind.app.studio import application
from ux_maind.app.templates import (
    Attribution,
    Locator,
    Measurement,
    Observation,
    UXEvidenceDocument,
)
from ux_maind.app.workspace import Workspace


class R31AdversarialPipelineTests(unittest.TestCase):
    def test_corpus_role_contamination_guard_and_lockfile_skipping(self):
        """Reference/codebook files stay readable in Inspector but cannot contaminate blind A/B/C runs; ~$ lockfiles are skipped."""
        with TemporaryDirectory() as tmp:
            study_dir = Path(tmp) / "study_folder"
            (study_dir / ".idea").mkdir(parents=True)
            (study_dir / ".idea" / "workspace.xml").write_text("<project/>", encoding="utf-8")
            (study_dir / "~$P1_Notes.docx").write_bytes(b"\x00\x01lock")
            (study_dir / ".DS_Store").write_bytes(b"\x00\x00")
            (study_dir / "P1_Session.txt").write_text(
                "P1: Adding multiple counties in the query form is cumbersome.", encoding="utf-8"
            )
            (study_dir / "expert_codebook.csv").write_text(
                "tag,description\nQuery process complex,Inputs are hard to combine\n",
                encoding="utf-8",
            )

            app = application(Path(tmp) / "ws")
            w: Workspace = app.state.workspace
            w.import_paths([study_dir])

            items = w.files(sort="name")["items"]
            names = [it["name"] for it in items]
            self.assertEqual(names, ["expert_codebook.csv", "P1_Session.txt"])
            codebook_id = next(it["id"] for it in items if it["name"] == "expert_codebook.csv")
            primary_id = next(it["id"] for it in items if it["name"] == "P1_Session.txt")

            with TestClient(app) as client:
                token = client.get("/").text.split('name="workspace-token" content="')[1].split('"')[0]
                headers = {"x-workspace-token": token}

                # Mark expert_codebook.csv as 'reference'
                role_res = client.post(
                    "/api/corpus-role",
                    headers=headers,
                    json={"documents": [codebook_id], "corpus_role": "reference"},
                )
                self.assertEqual(role_res.status_code, 200)
                self.assertEqual(w.file(codebook_id)["corpus_role"], "reference")
                self.assertEqual(w.file(primary_id)["corpus_role"], "evidence")

                # Inspector summary & HTML view remain 100% accessible for reference files
                sum_res = client.get(f"/api/summary?id={codebook_id}")
                self.assertEqual(sum_res.status_code, 200)
                view_res = client.get(f"/document/{codebook_id}/view")
                self.assertEqual(view_res.status_code, 200)

                # Attempting Stage A extraction or workflow-preview with the reference file is blocked!
                ext_res = client.post(
                    "/api/extract",
                    headers=headers,
                    json={
                        "documents": [primary_id, codebook_id],
                        "options": {"provider": "ollama", "model": "qwen3:8b"},
                        "send": True,
                    },
                )
                self.assertEqual(ext_res.status_code, 400)
                self.assertIn("Kontaminationsschutz", ext_res.json()["error"])
                self.assertIn("expert_codebook.csv", ext_res.json()["error"])

                wf_res = client.post(
                    "/api/workflow-preview",
                    headers=headers,
                    json={"documents": [primary_id, codebook_id]},
                )
                self.assertEqual(wf_res.status_code, 400)
                self.assertIn("expert_codebook.csv", wf_res.json()["error"])

    def test_wide_survey_duplicate_headers_and_cell_header_handoff(self):
        """Wide 30-column survey CSVs preserve all column indices (>12) and disambiguate repeated 'Comments' headers."""
        doc = DoclingDocument(name="survey_wide")
        num_cols = 30
        cells = [
            TableCell(
                text="Participant",
                start_row_offset_idx=0,
                end_row_offset_idx=1,
                start_col_offset_idx=0,
                end_col_offset_idx=1,
                column_header=True,
            ),
            TableCell(
                text="P1",
                start_row_offset_idx=1,
                end_row_offset_idx=2,
                start_col_offset_idx=0,
                end_col_offset_idx=1,
            ),
        ]
        for q_idx in range(1, 15):
            sc_col = 1 + (q_idx - 1) * 2
            cm_col = sc_col + 1
            if cm_col >= num_cols:
                break
            cells.append(
                TableCell(
                    text=f"{q_idx}. Question item {q_idx} clarity",
                    start_row_offset_idx=0,
                    end_row_offset_idx=1,
                    start_col_offset_idx=sc_col,
                    end_col_offset_idx=sc_col + 1,
                    column_header=True,
                )
            )
            cells.append(
                TableCell(
                    text="Comments",
                    start_row_offset_idx=0,
                    end_row_offset_idx=1,
                    start_col_offset_idx=cm_col,
                    end_col_offset_idx=cm_col + 1,
                    column_header=True,
                )
            )
            cells.append(
                TableCell(
                    text="2",
                    start_row_offset_idx=1,
                    end_row_offset_idx=2,
                    start_col_offset_idx=sc_col,
                    end_col_offset_idx=sc_col + 1,
                )
            )
            cells.append(
                TableCell(
                    text=f"Specific feedback on item {q_idx}" if q_idx == 12 else "Same as above.",
                    start_row_offset_idx=1,
                    end_row_offset_idx=2,
                    start_col_offset_idx=cm_col,
                    end_col_offset_idx=cm_col + 1,
                )
            )
        doc.add_table(data=TableData(num_rows=2, num_cols=num_cols, table_cells=cells))

        with TemporaryDirectory() as tmp:
            orig_json = Path(tmp) / "survey.json"
            orig_json.write_text(
                doc.model_dump_json(by_alias=True, exclude_computed_fields=True), encoding="utf-8"
            )
            src = evidence.Sources(doc, 1, "v1")
            with evidence.model_source(src, orig_json, input_format="auto") as model_path:
                ms_doc = DoclingDocument.load_from_json(model_path)
                cap_texts = [t.text for t in ms_doc.texts if t.label == DocItemLabel.CAPTION]
                self.assertEqual(len(cap_texts), 1)
                # Column 24 (Question 12 Comments) must be present (no [:12] artificial truncation!)
                self.assertIn("24=Comments [12. Question item 12 clarity]", cap_texts[0])

            # Locate unique cell in column 24 and verify column_header + row_header propagate to _compact_anchor
            anc = src.locate(
                "Specific feedback on item 12",
                {"self_ref": "#/tables/0", "row": 1, "column": 24},
            )
            self.assertIsNotNone(anc)
            self.assertEqual(anc["column_header"], "Comments [12. Question item 12 clarity]")
            self.assertEqual(anc["row_header"], "P1")
            comp = interpretation._compact_anchor(anc)
            self.assertEqual(comp["column_header"], "Comments [12. Question item 12 clarity]")
            self.assertEqual(comp["row_header"], "P1")

            # Adversarial repeated cell quote ("Same as above.") with missing column must NOT guess randomly
            ambig_ext = UXEvidenceDocument(
                observations=[
                    Observation(
                        quote="Same as above.",
                        statement="Participant wrote Same as above.",
                        locator=Locator(self_ref="#/tables/0"),
                    )
                ]
            )
            ambig_obs, _, ambig_issues = evidence.observation_view(
                {"extracted": [ambig_ext.model_dump(mode="json")], "trace": []}, src
            )
            self.assertEqual(len(ambig_issues), 1)
            self.assertGreaterEqual(len(ambig_obs[0].get("candidate_anchors") or []), 2)
            self.assertGreaterEqual(int(ambig_obs[0].get("ambiguous_count") or 0), 10)

    def test_adversarial_confusing_cases_across_all_stages(self):
        """End-to-end check of inverted unanchored scales, struck-through claims, moderator vs participant roles & ligatures."""
        with TemporaryDirectory() as tmp:
            w = Workspace(Path(tmp) / "ws")
            f_notes = Path(tmp) / "P1_Moderator_Notes.txt"
            f_survey = Path(tmp) / "P1_PSSUQ_Extract.txt"
            f_notes.write_text(
                "Moderator note: Participant P1 initially clicked the wrong tab (5% error rate vs 15% baseline), "
                "later crossed out the hypothesis: Old ﬁlter button broken.",
                encoding="utf-8",
            )
            f_survey.write_text(
                "P1 response: Score 6 — The data lineage and provenance metadata tables confused me at first.",
                encoding="utf-8",
            )
            w.import_paths([f_notes, f_survey])

            # Inject strikethrough span on doc 1 text item to simulate DOCX/PPTX struck hypothesis
            from docling_core.types.doc import BaseMeta

            d1 = w.document(w.file(1))
            d1.texts[0].meta = d1.texts[0].meta or BaseMeta()
            d1.texts[0].meta.set_custom_field("ux_maind", "strikethrough_spans", ["Old filter button broken."])
            p1_native = w.artifact(w.file(1), "native")
            p1_native.write_bytes(d1.model_dump_json(by_alias=True, exclude_computed_fields=True).encode("utf-8"))

            src1 = evidence.Sources(w.document(w.file(1)), 1, evidence.file_digest(p1_native))
            src2_path = w.artifact(w.file(2), "native")
            src2 = evidence.Sources(w.document(w.file(2)), 2, evidence.file_digest(src2_path))

            # Verify strict numeric boundary ("5%" binds to "5%", NEVER inside "15%") and ligature ("filter" -> "ﬁlter")
            anc_pct = src1.locate("5%", {"self_ref": "#/texts/0"})
            self.assertIsNotNone(anc_pct)
            self.assertEqual(anc_pct["quote"], "5%")
            anc_lig = src1.locate("Old filter button broken.", {"self_ref": "#/texts/0"})
            self.assertIsNotNone(anc_lig)
            self.assertEqual(anc_lig["quote"], "Old ﬁlter button broken.")

            # Stage A run 1: Moderator note with struck-through span
            ext1 = UXEvidenceDocument(
                observations=[
                    Observation(
                        quote="Old filter button broken.",
                        statement="Crossed-out note mentioned old filter button.",
                        kind="observation",
                        negated_or_struck=True,
                        locator=Locator(self_ref="#/texts/0"),
                        context=Attribution(epistemic_role="observer_note", actor_or_speaker="Moderator"),
                    )
                ]
            )
            obs1, anc1, iss1 = evidence.observation_view(
                {"extracted": [ext1.model_dump(mode="json")], "trace": []}, src1
            )
            self.assertEqual(len(iss1), 0)

            # Stage A run 2: Participant P1 firsthand response with unanchored PSSUQ score 6 (where 1=best, 7=worst is unstated!)
            ext2 = UXEvidenceDocument(
                observations=[
                    Observation(
                        quote="Score 6 — The data lineage and provenance metadata tables confused me at first.",
                        statement="P1 reported confusion in the data lineage and provenance tables (score 6).",
                        kind="difficulty",
                        locator=Locator(self_ref="#/texts/0"),
                        context=Attribution(epistemic_role="participant_firsthand", actor_or_speaker="P1"),
                        measurements=[
                            Measurement(
                                raw_value="6",
                                numeric_value=6.0,
                                measurement_kind="rating_scale",
                                scale_direction="unknown",
                                locator=Locator(self_ref="#/texts/0"),
                            )
                        ],
                    )
                ]
            )
            obs2, anc2, iss2 = evidence.observation_view(
                {"extracted": [ext2.model_dump(mode="json")], "trace": []}, src2
            )
            self.assertEqual(len(iss2), 0)

            with w.db() as db:
                r1 = db.execute(
                    "INSERT INTO runs(document, at, result) VALUES(1, '2026-11-19T09:00:00Z', ?)",
                    (
                        json.dumps(
                            {
                                "schema_version": evidence.SCHEMA_VERSION,
                                "status": "UNREVIEWED",
                                "document_version": src1.version,
                                "observations": obs1,
                                "relations": [],
                                "sources": anc1,
                                "issues": [],
                            }
                        ),
                    ),
                ).lastrowid
                r2 = db.execute(
                    "INSERT INTO runs(document, at, result) VALUES(2, '2026-11-19T09:01:00Z', ?)",
                    (
                        json.dumps(
                            {
                                "schema_version": evidence.SCHEMA_VERSION,
                                "status": "UNREVIEWED",
                                "document_version": src2.version,
                                "observations": obs2,
                                "relations": [],
                                "sources": anc2,
                                "issues": [],
                            }
                        ),
                    ),
                ).lastrowid

            comp_c = research.create(
                w,
                "comparison",
                [],
                [1, 2],
                {
                    "origin": "model",
                    "stage": "C",
                    "status": "UNREVIEWED",
                    "observations": [
                        {"document": 1, "run": r1, "observation": "O1"},
                        {"document": 2, "run": r2, "observation": "O1"},
                    ],
                    "basis_runs": [r1, r2],
                    "basis_by_doc": {"1": r1, "2": r2},
                },
            )
            fid = research.create(
                w,
                "finding",
                {
                    "title": "Metadata provenance tables cause initial orientation friction",
                    "valence": "problem",
                    "finding_type": "usability_problem",
                    "usability_heuristic": "ISO 9241-110: Selbstbeschreibungsfähigkeit",
                    "rationale": "P1 explicitly reported confusion; struck moderator note is only historical context.",
                    "supports": [{"document": 2, "run": r2, "observation": "O1"}],
                    "qualifies": [{"document": 1, "run": r1, "observation": "O1"}],
                    "opposes": [],
                    "uncertainty": "PSSUQ numeric polarity (6) is not anchored in the excerpt.",
                },
                [1, 2],
                {
                    "origin": "model",
                    "stage": "C",
                    "comparison": comp_c,
                    "observations": [
                        {"document": 1, "run": r1, "observation": "O1"},
                        {"document": 2, "run": r2, "observation": "O1"},
                    ],
                },
            )
            g = research.graph(w, [1, 2], basis={1: r1, 2: r2}, result_runs={"B": None, "C": comp_c})
            finding_node = next(
                n for n in g["graph"]["nodes"] if n["__class__"] == "FindingNode" and n["record_id"] == fid
            )
            flags = finding_node["epistemic_flags"]
            self.assertIn("unanchored_scale_direction", flags)
            self.assertIn("contains_negated_or_struck", flags)
            # Only P1 is a firsthand participant; Moderator observer_note must NOT inflate distinct_speakers!
            self.assertEqual(finding_node["independence"]["distinct_speakers"], 1)

    def test_researcher_profiles_audit_stamp_and_installer_files(self):
        """US-74 & US-75: Researcher profile switching stamps ux_decisions.payload.reviewer and installer files exist."""
        import os

        repo_root = Path(__file__).resolve().parent.parent
        for rel in ("install.ps1", "install.sh", "start-ux-maind.cmd", "Dockerfile", "docker-compose.yml"):
            self.assertTrue((repo_root / rel).is_file(), f"Missing installer artifact: {rel}")

        with TemporaryDirectory() as tmp:
            app = application(Path(tmp) / "ws")
            w: Workspace = app.state.workspace
            f_txt = Path(tmp) / "session.txt"
            f_txt.write_text("P1: Button label is crystal clear.", encoding="utf-8")
            w.import_paths([f_txt])

            src = evidence.Sources(w.document(w.file(1)), 1, evidence.file_digest(w.artifact(w.file(1), "native")))
            ext = UXEvidenceDocument(
                observations=[
                    Observation(
                        quote="Button label is crystal clear.",
                        statement="P1 found button label clear.",
                        locator=Locator(self_ref="#/texts/0"),
                    )
                ]
            )
            obs, anc, _ = evidence.observation_view({"extracted": [ext.model_dump(mode="json")], "trace": []}, src)
            with w.db() as db:
                r1 = db.execute(
                    "INSERT INTO runs(document, at, result) VALUES(1, '2026-11-19T09:30:00Z', ?)",
                    (
                        json.dumps(
                            {
                                "schema_version": evidence.SCHEMA_VERSION,
                                "status": "UNREVIEWED",
                                "document_version": src.version,
                                "observations": obs,
                                "relations": [],
                                "sources": anc,
                                "issues": [],
                            }
                        ),
                    ),
                ).lastrowid

            with TestClient(app) as client:
                token = client.get("/").text.split('name="workspace-token" content="')[1].split('"')[0]
                headers = {"x-workspace-token": token}

                # Create and activate researcher profile 'Dr. Ada Lovelace'
                save_res = client.post(
                    "/api/researcher-save",
                    headers=headers,
                    json={"display_name": "Dr. Ada Lovelace", "role": "Zweitprüferin"},
                )
                self.assertEqual(save_res.status_code, 200)
                self.assertEqual(save_res.json()["active"]["display_name"], "Dr. Ada Lovelace")

                # Record a human decision and verify reviewer identity is stamped into ux_decisions
                dec_res = client.post(
                    "/api/ux-decision",
                    headers=headers,
                    json={
                        "target_type": "observation",
                        "target": {"document": 1, "run": r1, "observation": "O1"},
                        "action": "confirmed",
                        "reason": "Checked against audio transcript",
                    },
                )
                self.assertEqual(dec_res.status_code, 200)
                ent = research.entry(w, {"document": 1, "run": r1, "observation": "O1"})
                reviewer = ent["decisions"][-1]["payload"].get("reviewer") or {}
                self.assertEqual(reviewer.get("name"), "Dr. Ada Lovelace")
                self.assertEqual(reviewer.get("role"), "Zweitprüferin")

                # Verify OIDC env inspection never leaks secrets
                old_cid = os.environ.get("UX_MAIND_OIDC_CLIENT_ID")
                old_sec = os.environ.get("UX_MAIND_OIDC_CLIENT_SECRET")
                try:
                    os.environ["UX_MAIND_OIDC_CLIENT_ID"] = "oidc-client-demo"
                    os.environ["UX_MAIND_OIDC_CLIENT_SECRET"] = "TopSecretNeverExposeOidc99"
                    r_info = client.get("/api/researchers").json()
                    self.assertTrue(r_info["oidc"]["enabled"])
                    self.assertNotIn("TopSecretNeverExposeOidc99", json.dumps(r_info))
                finally:
                    if old_cid is None:
                        os.environ.pop("UX_MAIND_OIDC_CLIENT_ID", None)
                    else:
                        os.environ["UX_MAIND_OIDC_CLIENT_ID"] = old_cid
                    if old_sec is None:
                        os.environ.pop("UX_MAIND_OIDC_CLIENT_SECRET", None)
                    else:
                        os.environ["UX_MAIND_OIDC_CLIENT_SECRET"] = old_sec


if __name__ == "__main__":
    unittest.main()
