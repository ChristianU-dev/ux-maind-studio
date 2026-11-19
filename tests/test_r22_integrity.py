"""Native, offline counterexamples. No provider and no historical data mutation."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from docling_core.types.doc import DocItemLabel, DoclingDocument, TableCell, TableData
from docling_graph.core.converters.graph_converter import GraphConverter
from docling_graph.core.exporters.json_exporter import graph_to_dict
from ux_maind.app import interpretation, research
from ux_maind.app.evidence import SCHEMA_VERSION, Sources, observation_view
from ux_maind.app.native_graph import projection_status
from ux_maind.app.templates import UXEvidenceDocument, RelationshipProposals, FindingHypotheses
from ux_maind.app.workspace import Workspace


def project(model):
    graph, _ = GraphConverter(auto_cleanup=False, alias_llm_fn=None).pydantic_list_to_graph([model])
    return dict(extracted=[model.model_dump(mode="json")], graph=graph_to_dict(graph),
                trace=[], requests=[dict(finish_reason="stop")], last_response={}, error=None)


class R22Integrity(TestCase):
    def fixture(self, root):
        text = Path(root) / "unregistered.txt"
        text.write_text(" ".join(f"Evidence{i}." for i in range(11)), encoding="utf8")
        w = Workspace(Path(root) / "work")
        w.import_paths([text])
        row = w.file(1)
        doc = w.document(row)
        version = sha256(w.artifact(row, "native").read_bytes()).hexdigest()
        source = Sources(doc, 1, version)
        model = UXEvidenceDocument.model_validate(dict(observations=[dict(
            quote=f"Evidence{i}." if i < 10 else "Absent.", statement=f"Observation {i}",
            locator={"self_ref": doc.texts[0].self_ref}) for i in range(11)]))
        native = project(model)
        observations, anchors, issues = observation_view(native, source)
        result = dict(schema_version=SCHEMA_VERSION, status="PARTIAL", document_version=version,
                      observations=observations, sources=anchors, issues=issues,
                      native_graph=native, relations=[])
        with w.db() as db:
            run = db.execute("INSERT INTO runs(document,at,result) VALUES(1,'2026-11-17',?)",
                             (json.dumps(result),)).lastrowid
        return w, source, run, result

    def test_complete_manifest_open_gate_and_independent_primary_correction(self):
        with TemporaryDirectory() as root:
            w, sources, run, result = self.fixture(root)
            ref = dict(document=1, run=run, observation="O11")
            inputs = interpretation.plan(w, [1], basis={1: run})
            self.assertEqual((inputs["manifest"]["total"], inputs["manifest"]["offered"], inputs["manifest"]["excluded"]), (11, 10, 1))
            self.assertEqual(inputs["manifest"]["blocked"], 11)
            self.assertEqual(inputs["excluded"][0]["ref"], ref)
            with self.assertRaisesRegex(ValueError, "Quelle oder Messstelle"):
                interpretation.require_basis(inputs)
            # Missing old alias must not discard a separate, valid primary or context decision.
            result["observations"][-1]["source_ids"] = ["missing-alias"]
            anchor = sources.locate("Evidence10.", {"self_ref": sources.doc.texts[0].self_ref})
            with w.db() as db:
                db.execute("UPDATE runs SET result=? WHERE id=?", (json.dumps(result), run))
                db.execute("INSERT INTO ux_decisions(target_type,target,at,origin,action,reason,payload) VALUES('observation',?,'2026-11-17','human','corrected','Fixture',?)",
                           (json.dumps(ref, sort_keys=True), json.dumps(dict(primary=anchor, context=[dict(evidence=anchor)]))))
            entry = research.entry(w, ref)
            self.assertEqual(entry["selected_source"], anchor)
            self.assertEqual(entry["source_check"]["matches"], [anchor])
            self.assertEqual(entry["source_check"]["status"], "SOURCE_RESOLVED")
            self.assertEqual(entry["source_check"]["semantic_validation"], "NOT_PERFORMED")
            self.assertEqual(len(entry["context_decisions"]), 1)
            self.assertIn("KeyError", entry["diagnostics"])
            corrected = interpretation.plan(w, [1], basis={1: run})
            self.assertEqual(corrected["documents"][0]["technical"]["effective_resolved"], 11)
            self.assertEqual(corrected["documents"][0]["technical"]["primary_corrections"], 1)
            self.assertEqual(corrected["offered"][-1]["sources"], [anchor])
            with self.assertRaises(ValueError):
                interpretation.require_basis(corrected)  # no speculative selective release
            self.assertEqual(w.results(1)[0]["result"], result)
            # Context alone is never promoted to a primary source.
            with w.db() as db:
                db.execute("UPDATE ux_decisions SET payload=?", (json.dumps(dict(context=[dict(evidence=anchor)])),))
            self.assertFalse(research.entry(w, ref)["source_check"]["matches"])

    def test_invalid_version_and_truncated_response_keep_gate_closed(self):
        with TemporaryDirectory() as root:
            w, _, run, result = self.fixture(root)
            for version, truncated in [(result["document_version"], True), ("f" * 64, False)]:
                modified = deepcopy(result)
                modified["document_version"] = version
                modified["native_graph"]["last_response"]["truncated"] = truncated
                with w.db() as db:
                    db.execute("UPDATE runs SET result=? WHERE id=?", (json.dumps(modified), run))
                inputs = interpretation.plan(w, [1], basis={1: run})
                with self.assertRaises(ValueError):
                    interpretation.require_basis(inputs)
                if truncated:
                    self.assertIn("response_truncated", inputs["documents"][0]["technical"]["reasons"])
                else:
                    self.assertEqual(inputs["grounded"], 0)
                    self.assertTrue(all(len(e["diagnostics"]) for e in research.catalog(w, [1])["observations"]))

    def test_excluded_b_relations_keep_reason_review_and_proposal(self):
        with TemporaryDirectory() as root:
            w, _, run, _ = self.fixture(root)
            comparison = research.create(w, "comparison", {}, [1], dict(
                stage="B", status="UNREVIEWED", scope=[1], basis_runs=[run]))
            left = dict(document=1, run=run, observation="O1")
            right = dict(document=1, run=run, observation="O2")
            records = []
            for kind, target in [(None, right), ("refers_to", dict(right, observation="missing"))]:
                proposal = dict(source=left, target=target, kind=kind, rationale="Fixture")
                records.append(research.create(w, "relation", proposal, [1], dict(comparison=comparison)))
            inputs = interpretation.plan(w, [1], basis={1: run}, stage="C", b_run=comparison)
            self.assertEqual(inputs["relations"], [])
            self.assertEqual(inputs["excluded_relations"], records)
            self.assertEqual([r["reason"] for r in inputs["excluded_relation_manifest"]],
                             ["NO_RELATION", "UNRESOLVED_REFERENCE"])
            self.assertTrue(all(r["proposal"] and r["review"] == "UNREVIEWED" for r in inputs["excluded_relation_manifest"]))

    def test_native_b_c_identity_collisions_preserve_full_objects(self):
        refs = [dict(document=i + 1, run=10 + i, observation="O1") for i in range(4)]
        relation_model = RelationshipProposals.model_validate(dict(relations=[dict(
            source=refs[i], target=refs[i + 1], kind="refers_to", rationale="Shared wording") for i in (0, 2)]))
        finding_model = FindingHypotheses.model_validate(dict(findings=[dict(
            title="Shared title", valence="unclear", rationale="Distinct source", supports=[refs[i]],
            opposes=[], uncertainty="No evidenced scale") for i in (0, 2)]))
        for stage, field, model in [("B", "relations", relation_model), ("C", "findings", finding_model)]:
            native = project(model)
            report = projection_status(native, stage)
            self.assertEqual((report["source_objects"], report["projected_objects"]), (2, 2))
            self.assertFalse(report["incomplete"])
            self.assertEqual(len(native["extracted"][0][field]), 2)
            self.assertEqual(model.model_config.get("graph_id_fields"), None)
        duplicate_rel = RelationshipProposals.model_validate(dict(relations=[dict(
            source=refs[0], target=refs[1], kind="refers_to", rationale="Shared wording") for _ in range(2)]))
        dup_report = projection_status(project(duplicate_rel), "B")
        self.assertEqual((dup_report["source_objects"], dup_report["projected_objects"]), (2, 1))
        self.assertTrue(dup_report["incomplete"])
        self.assertIsNone(projection_status(None, "B"))

    def test_duplicate_text_doc_version_and_own_measurement_cell(self):
        doc = DoclingDocument(name="Unregistered layout")
        texts = [doc.add_text(DocItemLabel.TEXT, "Repeated phrase.") for _ in range(2)]
        first, second = Sources(doc, 1, "v1"), Sources(doc, 2, "v1")
        anchors = [first.locate(t.text, dict(self_ref=t.self_ref)) for t in texts]
        self.assertNotEqual(anchors[0]["evidence_id"], anchors[1]["evidence_id"])
        self.assertNotEqual(anchors[0]["evidence_id"], second.locate(texts[0].text, dict(self_ref=texts[0].self_ref))["evidence_id"])
        self.assertNotEqual(anchors[0]["evidence_id"], Sources(doc, 1, "v2").locate(texts[0].text, dict(self_ref=texts[0].self_ref))["evidence_id"])
        with self.assertRaises(ValueError): first.locate("Repeated phrase.", {})
        table = doc.add_table(data=TableData(num_rows=1, num_cols=2, table_cells=[TableCell(
            text=value, row_span=1, col_span=1, start_row_offset_idx=0, end_row_offset_idx=1,
            start_col_offset_idx=i, end_col_offset_idx=i+1) for i, value in enumerate(["0", "4"])]))
        model = UXEvidenceDocument.model_validate(dict(observations=[dict(
            quote="0", statement="Measured raw value", locator=dict(self_ref=table.self_ref,row=0,column=0),
            measurements=[dict(raw_value="4", unit="ms", locator=dict(self_ref=table.self_ref,row=0,column=0))])]))
        observations, _, _ = observation_view(dict(extracted=[model.model_dump()], trace=[]), Sources(doc, 1, "v1"))
        self.assertTrue(observations[0]["source_ids"])
        self.assertFalse(observations[0]["measurements"][0]["source_ids"])
