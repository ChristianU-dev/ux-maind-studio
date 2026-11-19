"""Version and stage boundaries of the standard research job."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from ux_maind.app import a_status, workflow
from ux_maind.app.workspace import Workspace


class Workflow(TestCase):
    def test_projection_loss_does_not_discard_a_basis(self):
        from docling_graph.core.converters.graph_converter import GraphConverter
        from ux_maind.app.templates import UXEvidenceDocument

        # Two repeated pairs and one repeated triple mirror the native A #25
        # identity collision without bringing original study text into Git.
        statements = ["first"] * 2 + ["second"] * 2 + ["third"] * 3
        statements += [f"observation {i}" for i in range(12)]
        model = UXEvidenceDocument.model_validate(
            {
                "observations": [
                    dict(
                        quote=text, statement=text, locator={"self_ref": f"#/texts/{i}"}
                    )
                    for i, text in enumerate(statements)
                ]
            }
        )
        native, _ = GraphConverter().pydantic_list_to_graph([model])
        self.assertEqual(len(native), 19)
        result = dict(
            status="PARTIAL",
            observations=[dict(source_ids=[str(i)]) for i in range(19)],
            native_graph=dict(
                extracted=[model.model_dump()],
                graph={"nodes": [data for _, data in list(native.nodes(data=True))[:15]]},
                requests=[dict(finish_reason="stop")],
            ),
            issues=[dict(status="MODEL_DIAGNOSTIC", stage="graph_conversion")],
        )
        technical = a_status.dimensions(result)
        self.assertTrue(technical["eligible"])
        self.assertEqual(
            (technical["resolved"], technical["graph_observations"]), (19, 15)
        )
        basis, outcomes = {}, {}
        workflow.record_a(
            lambda event: None,
            basis,
            outcomes,
            {
                "document": 1,
                "status": "PARTIAL",
                "run": 25,
                "basis_eligible": technical["eligible"],
            },
        )
        self.assertEqual(basis, {1: 25})
        result["native_graph"]["requests"].append(dict(finish_reason="length"))
        self.assertIn("response_truncated", a_status.dimensions(result)["reasons"])
        result["observations"][-1]["source_ids"] = []
        self.assertIn("a_source_open", a_status.dimensions(result)["reasons"])

    def test_reuse_starts_at_b_and_pins_c_to_new_b(self):
        workspace = Mock()
        documents = [dict(id=1)]
        counts = dict(proposed=0, unresolved=0)
        with patch(
            "ux_maind.app.interpretation.run",
            side_effect=[
                dict(status="NO_PROPOSALS", comparison=19, counts=counts),
                dict(status="NO_PROPOSALS", comparison=20, counts=counts),
            ],
        ) as native:
            final = workflow.run(
                workspace,
                documents,
                dict(A={}, B={}, C={}),
                {},
                reuse=dict(basis={1: 25}, versions={"1": "stored"}),
            )
        workspace.extract.assert_not_called()
        workspace.convert_selected.assert_not_called()
        workspace.enrich.assert_not_called()
        self.assertEqual(final["basis"], {1: 25})
        self.assertEqual(native.call_args.kwargs["b_run"], 19)

    def test_resume_uses_an_eligible_a_checkpoint_at_the_same_version(self):
        workspace = Mock()
        workspace.results.return_value = [
            {"id": 25, "result": {"observations": [{"id": "O1"}]}}
        ]
        resume = dict(
            phase="A",
            checked=True,
            pending=[1],
            versions={"1": "stored"},
            a_attempts={"1": 25},
        )
        document = dict(
            technical={"eligible": True},
            coverage_status="PARTIAL",
            document_version="stored",
        )
        outcome = dict(
            status="NO_PROPOSALS", comparison=19, counts=dict(proposed=0, unresolved=0)
        )
        with (
            patch(
                "ux_maind.app.research.catalog", return_value={"documents": [document]}
            ),
            patch("ux_maind.app.interpretation.run", return_value=outcome),
        ):
            final = workflow.run(
                workspace, [dict(id=1)], dict(A={}, B={}, C={}), {}, resume=resume
            )
        workspace.extract.assert_not_called()
        self.assertEqual(final["basis"], {1: 25})

    def test_open_a_b_and_c_stop_before_the_next_stage(self):
        documents = [dict(id=1, native="base.json", status="success")]
        workspace = Mock()
        workspace.file.return_value = documents[0]
        workspace.latest_conversion.return_value = "base"
        workspace.preferred_version.return_value = "base"
        stages, vision = dict(A={}, B={}, C={}), dict(enabled=False)

        def incomplete(numbers, profile, versions, progress):
            progress(dict(document=1, status="PARTIAL", run=7, resolved=1))

        def complete(numbers, profile, versions, progress):
            progress(dict(document=1, status="UNREVIEWED", run=8, resolved=1))

        counts = dict(proposed=1, unresolved=0, null_decisions=0)
        with patch(
            "ux_maind.app.interpretation.run",
            side_effect=[
                dict(status="ERROR", comparison=9, counts=counts),
                dict(status="UNREVIEWED", comparison=10, counts=counts),
                dict(status="PARTIAL", comparison=11, counts=counts),
                dict(status="UNREVIEWED", comparison=12, counts=counts),
            ],
        ) as native:
            workspace.extract.side_effect = incomplete
            first = workflow.run(workspace, documents, stages, vision)
            self.assertEqual(first["review"]["phase"], "A")
            native.assert_not_called()

            workspace.extract.side_effect = complete
            second = workflow.run(
                workspace, documents, stages, vision, resume=first["review"]
            )
            self.assertEqual(second["review"]["phase"], "B")
            self.assertEqual(
                [call.kwargs["stage"] for call in native.call_args_list], ["B"]
            )

            third = workflow.run(
                workspace, documents, stages, vision, resume=second["review"]
            )
            self.assertEqual(third["review"]["phase"], "C")
            done = workflow.run(
                workspace, documents, stages, vision, resume=third["review"]
            )
        self.assertEqual(done["c_run"], 12)
        self.assertEqual(done["b_run"], 10)
        self.assertEqual(done["basis"], {1: 8})
        self.assertEqual(native.call_args.kwargs["b_run"], 10)

    def test_waiting_vision_retries_only_open_document_and_preserves_other_version(
        self,
    ):
        documents = [dict(id=n, native="base.json", status="success") for n in (1, 2)]
        workspace = Mock()
        workspace.file.side_effect = lambda n: documents[n - 1]
        workspace.latest_conversion.side_effect = lambda row: f"base-{row['id']}"
        workspace.preferred_version.return_value = "base"

        def enrich(numbers, vision, progress, versions, automatic, retry):
            self.assertTrue(automatic)
            if retry:
                self.assertEqual(numbers, [2])
                self.assertEqual(versions, {"2": "partial-2"})
                progress(dict(document=2, status="success", version="new-2"))
            else:
                progress(dict(document=1, status="success", version="complete-1"))
                progress(
                    dict(document=2, status="partial_success", version="partial-2")
                )

        def extract(numbers, profile, progress, versions):
            self.assertEqual(versions, {"1": "complete-1", "2": "new-2"})
            for n in numbers:
                progress(dict(document=n, run=n, status="UNREVIEWED", resolved=1))

        workspace.enrich.side_effect = enrich
        workspace.extract.side_effect = extract
        stages = dict(A={}, B={}, C={})
        vision = dict(enabled=True)
        first = workflow.run(workspace, documents, stages, vision)
        self.assertEqual(first["status"], "WAITING_REVIEW")
        self.assertEqual(first["review"]["pending"], [2])
        workspace.extract.assert_not_called()
        outcome = dict(
            status="UNREVIEWED", comparison=3, counts=dict(proposed=1, unresolved=0)
        )
        with patch("ux_maind.app.interpretation.run", return_value=outcome) as analyze:
            final = workflow.run(
                workspace, documents, stages, vision, resume=first["review"]
            )
        self.assertEqual(final["status"], "UNREVIEWED")
        self.assertEqual(final["basis"], {1: 1, 2: 2})
        workspace.convert_selected.assert_not_called()
        self.assertEqual(analyze.call_args.kwargs["b_run"], 3)

    def test_native_pptx_structure_retains_explicit_strike(self):
        from pptx import Presentation
        from pptx.oxml.ns import qn
        from pptx.util import Inches

        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "format.pptx"
            pptx = Presentation()
            slide = pptx.slides.add_slide(pptx.slide_layouts[6])
            shape = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(3), Inches(1))
            run = shape.text_frame.paragraphs[0].add_run()
            run.text = "Dismissed option"
            run.font.bold = True
            run._r.find(qn("a:rPr")).set("strike", "sngStrike")
            pptx.save(source)
            workspace = Workspace(Path(tmp) / "workspace")
            with patch("ux_maind.app.office.office_renderer", return_value=None):
                self.assertEqual(workspace.import_paths([source]), {"success": 1})
            item = workspace.document(workspace.file(1)).texts[0]
            self.assertTrue(item.formatting.strikethrough)
            self.assertTrue(item.formatting.bold)
            self.assertEqual(item.prov[0].page_no, 1)

    def test_native_retry_input_keeps_successful_image_metadata(self):
        from docling_core.types.doc import (
            DescriptionMetaField,
            DoclingDocument,
            PictureMeta,
        )
        from ux_maind.app.enrichment import retry_input

        doc = DoclingDocument(name="Native pictures")
        first = doc.add_picture()
        first.meta = PictureMeta(
            description=DescriptionMetaField(text="Preserved native result")
        )
        second = doc.add_picture()
        second.meta = PictureMeta(description=DescriptionMetaField(text=""))
        source = retry_input(doc, Path("selected-version.json"))
        retried = DoclingDocument.model_validate_json(source.stream.read())
        self.assertEqual(
            retried.pictures[0].meta.description.text, "Preserved native result"
        )
        self.assertIsNone(retried.pictures[1].meta.description)
        self.assertEqual(doc.pictures[1].meta.description.text, "")
