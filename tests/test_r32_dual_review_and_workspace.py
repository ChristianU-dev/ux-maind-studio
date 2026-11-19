"""R32: Permanent workspace path, workspace-r12 detection, and 1- & 2-machine Dual Review tests."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from starlette.testclient import TestClient

from ux_maind.app import dual_review, evidence, library, research, telemetry
from ux_maind.app.studio import application
from ux_maind.app.templates import Attribution, Locator, Observation, UXEvidenceDocument
from ux_maind.app.workspace import Workspace


def _build_study_workspace(root: Path) -> tuple[Workspace, dict]:
    """Create a deterministic 2-document study with 2 grounded Findings (#F1, #F2) and 0 API calls."""
    w = Workspace(root)
    doc1 = root.parent / "P1_Interview.txt"
    doc2 = root.parent / "P2_Session.txt"
    doc1.write_text(
        "P1: Die Auswahl mehrerer Landkreise im Filterdialog erfordert jedes Mal fünf Einzelklicks.\n"
        "P1: Die Export-Zusammenfassung am Ende ist sofort verständlich.",
        encoding="utf-8",
    )
    doc2.write_text(
        "P2: Ich musste jeden Landkreis einzeln suchen, eine Mehrfachauswahl fehlt spürbar.\n"
        "P2: Die tabellarische Vorschau vor dem Download gibt mir Sicherheit.",
        encoding="utf-8",
    )
    w.import_paths([doc1, doc2])

    src1 = evidence.Sources(
        w.document(w.file(1)), 1, evidence.file_digest(w.artifact(w.file(1), "native"))
    )
    src2 = evidence.Sources(
        w.document(w.file(2)), 2, evidence.file_digest(w.artifact(w.file(2), "native"))
    )

    ext1 = UXEvidenceDocument(
        observations=[
            Observation(
                quote="Die Auswahl mehrerer Landkreise im Filterdialog erfordert jedes Mal fünf Einzelklicks.",
                statement="P1 benötigt fünf Einzelklicks pro Landkreis im Filterdialog.",
                kind="difficulty",
                locator=Locator(self_ref="#/texts/0"),
                context=Attribution(epistemic_role="participant_firsthand", actor_or_speaker="P1"),
            ),
            Observation(
                quote="Die Export-Zusammenfassung am Ende ist sofort verständlich.",
                statement="P1 findet die Export-Zusammenfassung sofort verständlich.",
                kind="positive",
                locator=Locator(self_ref="#/texts/1"),
                context=Attribution(epistemic_role="participant_firsthand", actor_or_speaker="P1"),
            ),
        ]
    )
    ext2 = UXEvidenceDocument(
        observations=[
            Observation(
                quote="Ich musste jeden Landkreis einzeln suchen, eine Mehrfachauswahl fehlt spürbar.",
                statement="P2 vermisst eine Mehrfachauswahl bei der Landkreissuche.",
                kind="difficulty",
                locator=Locator(self_ref="#/texts/0"),
                context=Attribution(epistemic_role="participant_firsthand", actor_or_speaker="P2"),
            ),
            Observation(
                quote="Die tabellarische Vorschau vor dem Download gibt mir Sicherheit.",
                statement="P2 lobt die tabellarische Vorschau vor dem Download.",
                kind="positive",
                locator=Locator(self_ref="#/texts/1"),
                context=Attribution(epistemic_role="participant_firsthand", actor_or_speaker="P2"),
            ),
        ]
    )
    obs1, anc1, _ = evidence.observation_view(
        {"extracted": [ext1.model_dump(mode="json")], "trace": []}, src1
    )
    obs2, anc2, _ = evidence.observation_view(
        {"extracted": [ext2.model_dump(mode="json")], "trace": []}, src2
    )
    with w.db() as db:
        r1 = db.execute(
            "INSERT INTO runs(document, at, result) VALUES(1, '2026-11-19T10:00:00Z', ?)",
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
            "INSERT INTO runs(document, at, result) VALUES(2, '2026-11-19T10:01:00Z', ?)",
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

    all_obs_refs = [
        {"document": 1, "run": r1, "observation": "O1"},
        {"document": 1, "run": r1, "observation": "O2"},
        {"document": 2, "run": r2, "observation": "O1"},
        {"document": 2, "run": r2, "observation": "O2"},
    ]
    comp_c = research.create(
        w,
        "comparison",
        [],
        [1, 2],
        {
            "origin": "model",
            "stage": "C",
            "status": "UNREVIEWED",
            "model": "Qwen/Qwen3.6-35B-A3B-FP8",
            "provider": "nhr_fau",
            "observations": all_obs_refs,
            "basis_runs": [r1, r2],
            "basis_by_doc": {"1": r1, "2": r2},
        },
    )
    f_agree = research.create(
        w,
        "finding",
        {
            "title": "Vorschau und Export-Zusammenfassung schaffen hohe Orientierungssicherheit",
            "valence": "strength",
            "finding_type": "strength",
            "usability_heuristic": "Nielsen H1: Sichtbarkeit des Systemstatus",
            "rationale": "Beide Teilnehmenden bestätigen unabhängige Sicherheit vor dem Download.",
            "supports": [
                {"document": 1, "run": r1, "observation": "O2"},
                {"document": 2, "run": r2, "observation": "O2"},
            ],
            "opposes": [],
            "qualifies": [],
            "scope": "Export-Dialog (P1, P2)",
            "uncertainty": "Kleine Stichprobe (n=2).",
        },
        [1, 2],
        {"origin": "model", "stage": "C", "comparison": comp_c, "observations": all_obs_refs},
    )
    f_diverge = research.create(
        w,
        "finding",
        {
            "title": "Fehlende Mehrfachauswahl im Landkreis-Filter erzeugt repetitiven Klickaufwand",
            "valence": "problem",
            "finding_type": "usability_problem",
            "usability_heuristic": "Nielsen H7: Flexibilität und Effizienz der Nutzung",
            "rationale": "Einzelauswahl erzwingt wiederholte Such- und Klickschritte.",
            "supports": [
                {"document": 1, "run": r1, "observation": "O1"},
                {"document": 2, "run": r2, "observation": "O1"},
            ],
            "opposes": [],
            "qualifies": [],
            "scope": "Filterdialog (P1, P2)",
            "uncertainty": "Keine Zeitmessung erhoben.",
        },
        [1, 2],
        {"origin": "model", "stage": "C", "comparison": comp_c, "observations": all_obs_refs},
    )
    return w, {
        "basis": {1: r1, 2: r2},
        "runs": {"B": None, "C": comp_c},
        "f_agree": f_agree,
        "f_diverge": f_diverge,
    }


class R32WorkspaceAndDualReviewTests(unittest.TestCase):
    def test_default_workspace_path_legacy_r12_detection_and_explicit_override(self):
        with TemporaryDirectory() as tmp:
            fake_local = Path(tmp) / "LocalAppData"
            with patch.dict(os.environ, {"LOCALAPPDATA": str(fake_local)}):
                default_ws = library.default_workspace_path()
                self.assertEqual(default_ws, (fake_local / "UX-mAInd" / "workspace").resolve())

                # Create legacy workspace-r12 with 1 document, 1 finding & saved output path inside r12
                legacy_root = fake_local / "UX-mAInd" / "workspace-r12"
                legacy_w = Workspace(legacy_root)
                (legacy_root / "exports").mkdir(parents=True, exist_ok=True)
                legacy_w.set_setting("output", str(legacy_root / "exports"))
                sample = Path(tmp) / "note.txt"
                sample.write_text("P1: Clear navigation.", encoding="utf-8")
                legacy_w.import_paths([sample], convert=False)
                research.create(legacy_w, "finding", {"title": "Legacy Finding"}, [1])

                # Start empty default workspace -> must detect sibling workspace-r12 without mutating it
                w_default = Workspace(default_ws)
                p_info = library.paths(w_default)
                self.assertTrue(p_info["is_default_workspace"])
                self.assertEqual(p_info["current_documents"], 0)
                self.assertTrue(p_info["legacy_workspace"]["found"])
                self.assertEqual(p_info["legacy_workspace"]["documents"], 1)
                self.assertEqual(p_info["legacy_workspace"]["findings"], 1)

                # Copy migration while closed: output path must remap to workspace/exports, keeping r12 untouched
                import shutil

                shutil.rmtree(default_ws)
                shutil.copytree(legacy_root, default_ws)
                w_migrated = Workspace(default_ws)
                p_mig = library.paths(w_migrated)
                self.assertEqual(p_mig["current_documents"], 1)
                self.assertEqual(Path(p_mig["output"]).resolve(), (default_ws / "exports").resolve())

                # Explicit --workspace override must take precedence
                explicit_dir = Path(tmp) / "dev-isolated-ws"
                w_explicit = Workspace(explicit_dir)
                p_exp = library.paths(w_explicit)
                self.assertEqual(p_exp["workspace"], str(explicit_dir.resolve()))
                self.assertFalse(p_exp["is_default_workspace"])

    def test_same_machine_blinding_release_revision_and_adoption(self):
        with TemporaryDirectory() as tmp:
            w, meta = _build_study_workspace(Path(tmp) / "ws_same")
            f1, f2 = meta["f_agree"], meta["f_diverge"]

            session = dual_review.create_session(
                w,
                {
                    "mode": "same_machine",
                    "documents": [1, 2],
                    "basis": meta["basis"],
                    "result_runs": meta["runs"],
                    "finding_ids": [f1, f2],
                    "reviewer_a": {"display_name": "Chris", "short_code": "CU"},
                    "reviewer_b": {"display_name": "Alex", "short_code": "AL"},
                },
            )
            sid = session["session_id"]

            # Reviewer 1 evaluates f1 (confirmed) and f2 (corrected with secret title & rationale)
            dual_review.save_judgment(
                w, {"session_id": sid, "finding_id": f1, "action": "confirmed", "reason": "P1-OK"}
            )
            dual_review.save_judgment(
                w,
                {
                    "session_id": sid,
                    "finding_id": f2,
                    "action": "corrected",
                    "reason": "SECRET_REASON_FROM_REVIEWER_1",
                    "interpretation": {"title": "SECRET_TITLE_FROM_REVIEWER_1"},
                },
            )
            dual_review.submit_slot(w, {"session_id": sid})

            # Release MUST fail while Reviewer 2 has not yet submitted
            with self.assertRaisesRegex(ValueError, "beide Prüfer"):
                dual_review.release_comparison(w, {"session_id": sid})

            # Saved exports by Reviewer 1 must ALSO remain hidden from Reviewer 2 before release!
            app = application(w.root)
            client = TestClient(app)
            csrf = client.get("/").text.split('name="workspace-token" content="')[1].split('"')[0]
            hdrs = {"X-Workspace-Token": csrf}
            saved_r1 = client.post(
                "/api/save-export",
                json={"kind": "handout", "documents": [1, 2], "basis": meta["basis"], "result_runs": meta["runs"]},
                headers=hdrs,
            ).json()
            r1_fname = Path(saved_r1["path"]).name

            # Switch to Reviewer 2 -> ZERO leakage across graph, HTML handout, Markdown, JSON, and saved exports!
            from ux_maind.app import auth

            auth.select_profile(w, session["reviewer_b"]["id"])
            exp_list_r2 = client.get("/api/exports-list").json()
            self.assertNotIn(r1_fname, [it["filename"] for it in exp_list_r2["items"]])
            self.assertEqual(client.get(f"/api/export-file?name={r1_fname}").status_code, 403)
            g_blinded = research.graph(
                w, [1, 2], history=True, basis=meta["basis"], result_runs=meta["runs"]
            )
            html_blinded = telemetry.html_handout(
                w, [1, 2], basis=meta["basis"], result_runs=meta["runs"]
            )
            md_blinded = research.markdown_report(
                w, [1, 2], basis=meta["basis"], result_runs=meta["runs"]
            )
            for dump_str in (json.dumps(g_blinded), html_blinded, md_blinded):
                self.assertNotIn("SECRET_TITLE_FROM_REVIEWER_1", dump_str)
                self.assertNotIn("SECRET_REASON_FROM_REVIEWER_1", dump_str)
                self.assertNotIn("P1-OK", dump_str)

            f2_blinded = next(o for o in g_blinded["objects"] if o["id"] == f2)
            self.assertEqual(
                f2_blinded["effective"]["title"],
                "Fehlende Mehrfachauswahl im Landkreis-Filter erzeugt repetitiven Klickaufwand",
            )
            self.assertEqual(f2_blinded["review"], "UNREVIEWED")

            # Reviewer 2 submits agreement on f1 and different correction on f2
            dual_review.save_judgment(
                w, {"session_id": sid, "finding_id": f1, "action": "confirmed", "reason": "P2-OK"}
            )
            dual_review.save_judgment(
                w,
                {
                    "session_id": sid,
                    "finding_id": f2,
                    "action": "corrected",
                    "reason": "P2 bevorzugt Fokus auf Steuerbarkeit",
                    "interpretation": {
                        "title": "Einzelauswahl im Landkreis-Filter verletzt Steuerbarkeit",
                        "usability_heuristic": "ISO 9241-110: Steuerbarkeit",
                    },
                },
            )
            dual_review.submit_slot(w, {"session_id": sid})

            # Release comparison
            rel_state = dual_review.release_comparison(w, {"session_id": sid})
            self.assertTrue(rel_state["released"])

            # Before explicit adoption, divergent f2 is visibly marked OPEN_DISAGREEMENT
            g_rel = research.graph(
                w, [1, 2], history=True, basis=meta["basis"], result_runs=meta["runs"]
            )
            f2_rel = next(o for o in g_rel["objects"] if o["id"] == f2)
            self.assertEqual(f2_rel["dual_review"]["resolution_state"], "OPEN_DISAGREEMENT")
            self.assertIn(
                "Offene Abweichung",
                telemetry.html_handout(w, [1, 2], basis=meta["basis"], result_runs=meta["runs"]),
            )
            self.assertIn(
                "OFFENE ABWEICHUNG",
                research.markdown_report(w, [1, 2], basis=meta["basis"], result_runs=meta["runs"]),
            )

            # Post-release revision by Reviewer 1 preserves Ersturteil
            auth.select_profile(w, session["reviewer_a"]["id"])
            dual_review.save_judgment(
                w,
                {
                    "session_id": sid,
                    "finding_id": f2,
                    "action": "corrected",
                    "reason": "Schließe mich nach Vergleich der ISO-Formulierung von Alex an",
                    "interpretation": {
                        "title": "Einzelauswahl im Landkreis-Filter verletzt Steuerbarkeit",
                        "usability_heuristic": "ISO 9241-110: Steuerbarkeit",
                    },
                },
            )
            # Adopt f1 & f2 into study state
            dual_review.adopt_resolution(
                w, {"session_id": sid, "finding_id": f1, "adopt_from": "reviewer_a"}
            )
            dual_review.adopt_resolution(
                w, {"session_id": sid, "finding_id": f2, "adopt_from": "reviewer_b"}
            )

            g_final = research.graph(
                w, [1, 2], history=True, basis=meta["basis"], result_runs=meta["runs"]
            )
            f2_final = next(o for o in g_final["objects"] if o["id"] == f2)
            self.assertEqual(
                f2_final["effective"]["title"],
                "Einzelauswahl im Landkreis-Filter verletzt Steuerbarkeit",
            )
            self.assertEqual(f2_final["review"], "HUMAN_CORRECTED")
            # Ersturteil AND revision both remain traceable in Forschungs-JSON!
            self.assertEqual(
                f2_final["dual_review"]["reviewer_a"]["initial"]["reason"],
                "SECRET_REASON_FROM_REVIEWER_1",
            )
            self.assertEqual(len(f2_final["dual_review"]["reviewer_a"]["revisions"]), 1)

    def test_two_machines_roundtrip_idempotency_and_corrupt_or_foreign_rejection(self):
        with TemporaryDirectory() as tmp:
            w_m1, meta = _build_study_workspace(Path(tmp) / "ws_m1")
            w_m2 = Workspace(Path(tmp) / "ws_m2")
            f1, f2 = meta["f_agree"], meta["f_diverge"]

            session = dual_review.create_session(
                w_m1,
                {
                    "mode": "two_machines",
                    "documents": [1, 2],
                    "basis": meta["basis"],
                    "result_runs": meta["runs"],
                    "finding_ids": [f1, f2],
                    "reviewer_a": {"display_name": "Chris M1", "short_code": "M1"},
                    "reviewer_b": {"display_name": "Dana M2", "short_code": "M2"},
                },
            )
            sid = session["session_id"]

            # M1 evaluates & submits BEFORE exporting Prüfpaket -> ZIP must still contain ZERO M1 leak!
            dual_review.save_judgment(
                w_m1,
                {"session_id": sid, "finding_id": f1, "action": "confirmed", "reason": "M1_HIDDEN_NOTE"},
            )
            dual_review.save_judgment(
                w_m1,
                {
                    "session_id": sid,
                    "finding_id": f2,
                    "action": "corrected",
                    "reason": "M1_HIDDEN_CORRECTION",
                    "interpretation": {"title": "M1_SECRET_TITLE"},
                },
            )
            dual_review.submit_slot(w_m1, {"session_id": sid})

            zip_name, zip_bytes = dual_review.export_assignment_zip(w_m1, sid)
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                for member in zf.namelist():
                    if member.endswith(".json"):
                        txt = zf.read(member).decode("utf-8")
                        self.assertNotIn("M1_HIDDEN_NOTE", txt)
                        self.assertNotIn("M1_SECRET_TITLE", txt)

            # Pre-seed M2 with an unrelated local document (#1) so imported docs receive shifted IDs (#2, #3)!
            pre_doc = Path(tmp) / "existing_on_m2.txt"
            pre_doc.write_text("Lokale Vorab-Notiz auf Rechner 2.", encoding="utf-8")
            w_m2.import_paths([pre_doc], convert=False)
            self.assertEqual(w_m2.files()["total"], 1)

            # Corrupt ZIP must fail atomically on M2 leaving only the 1 pre-existing document
            with self.assertRaises(ValueError):
                dual_review.import_package(w_m2, zip_bytes[:120], "corrupt.zip")
            self.assertEqual(w_m2.files()["total"], 1)

            # Valid import onto M2 -> imports documents (#2, #3), runs, findings & Originalbelege
            imp_m2 = dual_review.import_package(w_m2, zip_bytes, zip_name)
            self.assertEqual(imp_m2["status"], "imported")
            self.assertEqual(w_m2.files()["total"], 3)
            self.assertEqual(imp_m2["imported_documents"], [2, 3])

            # Verify EVERY Originalbeleg resolves 100% (`SOURCE_RESOLVED`) in Dual-View on M2 despite shifted doc IDs!
            g_m2 = research.graph(w_m2, [2, 3])
            for f_obj in g_m2["objects"]:
                if f_obj["kind"] == "finding":
                    for sref in f_obj["effective"]["supports"]:
                        obs_entry = research.entry(w_m2, sref)
                        self.assertEqual(obs_entry["source_check"]["status"], "SOURCE_RESOLVED")

            # Re-importing same ZIP on M2 is idempotent
            imp_m2_dup = dual_review.import_package(w_m2, zip_bytes, zip_name)
            self.assertEqual(imp_m2_dup["status"], "already_imported")
            self.assertEqual(w_m2.files()["total"], 3)

            m2_findings = [f["finding_id"] for f in imp_m2["session"]["findings"]]
            dual_review.save_judgment(
                w_m2,
                {"session_id": sid, "finding_id": m2_findings[0], "action": "confirmed", "reason": "M2_AGREE"},
            )
            dual_review.save_judgment(
                w_m2,
                {"session_id": sid, "finding_id": m2_findings[1], "action": "rejected", "reason": "M2_REJECT_INITIAL"},
            )
            dual_review.submit_slot(w_m2, {"session_id": sid})

            sub_name, sub_bytes = dual_review.export_submission_json(w_m2, sid, slot="reviewer_b")

            # Foreign-session check: create another workspace M3 with different session -> must reject sub_bytes!
            w_m3, meta3 = _build_study_workspace(Path(tmp) / "ws_m3")
            dual_review.create_session(
                w_m3,
                {
                    "mode": "two_machines",
                    "documents": [1, 2],
                    "basis": meta3["basis"],
                    "result_runs": meta3["runs"],
                    "finding_ids": [meta3["f_agree"], meta3["f_diverge"]],
                    "reviewer_a": {"display_name": "A"},
                    "reviewer_b": {"display_name": "B"},
                },
            )
            with w_m3.db() as db:
                before_m3_decs = db.execute("SELECT count(*) FROM ux_decisions").fetchone()[0]
            with self.assertRaisesRegex(ValueError, "anderen Prüfauftrag"):
                dual_review.import_package(w_m3, sub_bytes, sub_name)
            with w_m3.db() as db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM ux_decisions").fetchone()[0], before_m3_decs
                )

            # Tampered JSON must be rejected on M1 with 0 partial changes
            tampered = json.loads(sub_bytes.decode("utf-8"))
            tampered["decisions"]["F1"][0]["action"] = "rejected"
            with self.assertRaisesRegex(ValueError, "Integritätsprüfung"):
                dual_review.import_package(w_m1, json.dumps(tampered).encode("utf-8"), sub_name)
            self.assertIsNone(dual_review._load_session(w_m1, sid)["submitted_b_at"])

            # Valid import on M1 + duplicate import check (0 duplicates!)
            res_sub = dual_review.import_package(w_m1, sub_bytes, sub_name)
            self.assertEqual(res_sub["status"], "imported")
            with w_m1.db() as db:
                cnt_after_first = db.execute("SELECT count(*) FROM ux_decisions").fetchone()[0]
            res_sub_dup = dual_review.import_package(w_m1, sub_bytes, sub_name)
            self.assertEqual(res_sub_dup["status"], "already_imported")
            self.assertEqual(res_sub_dup["duplicates_created"], 0)
            with w_m1.db() as db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM ux_decisions").fetchone()[0], cnt_after_first
                )

            # Release on M1 -> export comparison to M2 -> M2 inspects & submits post-release revision -> M1 imports!
            dual_review.release_comparison(w_m1, {"session_id": sid})
            cmp_name, cmp_bytes = dual_review.export_comparison_json(w_m1, sid)

            imp_cmp_m2 = dual_review.import_package(w_m2, cmp_bytes, cmp_name)
            self.assertTrue(imp_cmp_m2["session"]["released"])

            dual_review.save_judgment(
                w_m2,
                {
                    "session_id": sid,
                    "finding_id": m2_findings[1],
                    "action": "corrected",
                    "reason": "M2_REVISED_AFTER_SEEING_M1",
                    "interpretation": {"title": "M2_REVISED_CONSENSUS_TITLE"},
                },
            )
            rev_name, rev_bytes = dual_review.export_submission_json(w_m2, sid, slot="reviewer_b")
            imp_rev_m1 = dual_review.import_package(w_m1, rev_bytes, rev_name)
            self.assertEqual(imp_rev_m1["inserted_decisions"], 1)

            # Verify M2's Ersturteil ('rejected') AND revision ('corrected') both survive on M1!
            g_m1 = research.graph(
                w_m1, [1, 2], history=True, basis=meta["basis"], result_runs=meta["runs"]
            )
            f2_m1 = next(o for o in g_m1["objects"] if o["id"] == f2)
            self.assertEqual(f2_m1["dual_review"]["reviewer_b"]["initial"]["action"], "rejected")
            self.assertEqual(
                f2_m1["dual_review"]["reviewer_b"]["revisions"][0]["interpretation"]["title"],
                "M2_REVISED_CONSENSUS_TITLE",
            )


if __name__ == "__main__":
    unittest.main()
