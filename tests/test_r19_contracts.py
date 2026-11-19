"""Small R19 contract tests; no provider calls and no separate extraction engine."""

from unittest import TestCase
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from ux_maind.app.interpretation import finding_valid, relation_valid
from ux_maind.app.evidence import Sources
from ux_maind.app.research import FindingNode, ObservationNode, retain_finding_roles
from ux_maind.app.templates import FindingProposal, RelationProposal
from ux_maind.app.workspace import Workspace


R1 = dict(document=1, run=11, observation="O1")
R2 = dict(document=1, run=11, observation="O2")
R3 = dict(document=1, run=11, observation="O3")
AVAILABLE = {(1, 11, "O1"), (1, 11, "O2"), (1, 11, "O3")}


class R19ContractTests(TestCase):
    def test_typographic_hyphen_keeps_the_original_quote_and_span(self):
        from docling_core.types.doc import DocItemLabel, DoclingDocument

        doc = DoclingDocument(name="Quote")
        item = doc.add_text(DocItemLabel.TEXT, "Vorher Wort-Trennung danach")
        source = Sources(doc, 1, "version")
        anchor = source.locate("Wort‑Trennung", {"self_ref": item.self_ref})
        self.assertEqual(anchor["quote"], "Wort-Trennung")
        self.assertEqual(item.text[anchor["start"] : anchor["end"]], anchor["quote"])
        with self.assertRaises(ValueError):
            source.locate("Wort–Trennung", {"self_ref": item.self_ref})

    def test_vision_version_reads_render_receipt_of_its_conversion(self):
        with TemporaryDirectory(dir=Path.cwd()) as root:
            root = Path(root)
            workspace = Workspace(root / "workspace")
            sample = root / "sample.txt"
            sample.write_text("Source", encoding="utf8")
            workspace.import_paths([sample])
            row = workspace.file(1)
            base = workspace.artifact(row, "native")
            content = base.read_bytes()
            original = sha256(content).hexdigest()
            converted = sha256(content + b"\n").hexdigest()
            enriched = sha256(content + b"\n\n").hexdigest()
            report = {"configuration": {"slide_view": {"display_sha256": "render"}}}
            workspace.save_version(
                base,
                dict(
                    at="2026-11-16T01:00:00Z",
                    version=converted,
                    base_version=original,
                    kind="conversion",
                    diagnostics=report,
                ),
                content + b"\n",
            )
            workspace.save_version(
                base,
                dict(
                    at="2026-11-16T02:00:00Z",
                    version=enriched,
                    base_version=converted,
                ),
                content + b"\n\n",
            )
            current = workspace.version_row(row, enriched)
            import json

            self.assertEqual(json.loads(current["diagnostics"]), report)

    def test_native_graph_export_keeps_all_roles_on_shared_edge(self):
        from docling_graph.core.converters.graph_converter import GraphConverter
        from docling_graph.core.exporters.json_exporter import graph_to_dict

        source = ObservationNode(**R1)
        finding = FindingNode(record_id=1, supports=[source], qualifies=[source])
        converter = GraphConverter(auto_cleanup=False, alias_llm_fn=None)
        graph, _ = converter.pydantic_list_to_graph([source, finding])
        warnings = []
        retain_finding_roles(graph, converter.registry, [finding], warnings)
        edges = graph_to_dict(graph)["edges"]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["roles"], ["QUALIFIES", "SUPPORTS"])
        self.assertEqual(warnings, [])

    def test_existing_finding_without_new_fields_still_parses(self):
        old = dict(
            title="Sortierung irritierte",
            valence="mixed",
            rationale="Problem und spätere Korrektur",
            supports=[R1],
            opposes=[],
            relations=[],
            uncertainty="Eine Sitzung",
        )
        p = FindingProposal.model_validate(old)
        self.assertIsNone(p.finding_type)
        self.assertEqual(p.qualifies, [])
        self.assertTrue(finding_valid(p.model_dump(), AVAILABLE, set()))

    def test_new_fields_and_source_roles(self):
        proposal = FindingProposal.model_validate(
            dict(
                title="Unklare Sortierfolge",
                valence="mixed",
                rationale="Anfängliche Irritation, erfolgreiche Recovery",
                supports=[R1],
                opposes=[],
                qualifies=[R2],
                improvement_evidence=[R3],
                improvement_basis="participant_suggestion",
                improvement_hypothesis="Sortierkriterium deutlicher anzeigen",
                relations=[31],
                finding_type="friction",
                observed_effect="Nutzerin sortierte anschließend nach Datum",
                scope="Eine dokumentierte Monday-Sitzung",
                uncertainty="Kein Nachweis für andere Nutzende",
            )
        ).model_dump()
        self.assertTrue(finding_valid(proposal, AVAILABLE, {31}))
        self.assertFalse(finding_valid(proposal, AVAILABLE, set()))
        proposal["qualifies"] = [dict(document=6, run=2, observation="O99")]
        self.assertFalse(finding_valid(proposal, AVAILABLE, {31}))

    def test_nonmatching_improvement_reference_is_not_silent(self):
        p = dict(
            supports=[R1],
            opposes=[],
            qualifies=[],
            improvement_evidence=[dict(document=8, run=2, observation="O1")],
            relations=[],
        )
        self.assertFalse(finding_valid(p, AVAILABLE, set()))

    def test_relation_abstention_and_distinct_endpoints(self):
        p = RelationProposal.model_validate(
            dict(
                source=R1,
                target=R2,
                kind="recovered_by",
                rationale="Die Korrektur folgte der Hürde",
                situation="Monday-Aufgabe",
            )
        ).model_dump()
        self.assertTrue(relation_valid(p, AVAILABLE))
        p["target"] = R1
        self.assertFalse(relation_valid(p, AVAILABLE))

    def test_open_novel_relation_is_allowed(self):
        p = RelationProposal.model_validate(
            dict(
                source=R1,
                target=R2,
                kind="mitigates",
                rationale="Belegter Zusammenhang",
            )
        )
        self.assertEqual(p.kind, "mitigates")
