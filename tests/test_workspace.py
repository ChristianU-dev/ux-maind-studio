"""Current R12 product behavior; synthetic sources and controlled native model responses."""

import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch
from starlette.testclient import TestClient
from ux_maind.app.workspace import Workspace
from ux_maind.app.models import connect, PRESETS
from ux_maind.app.studio import application


class CurrentWorkspace(unittest.TestCase):
    def test_free_import_survives_individual_errors_and_preserves_original(self):
        from docx import Document

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "input"
            source.mkdir()
            (source / "nested").mkdir()
            (source / "01-unreadable.txt").write_text("cannot copy", encoding="utf8")
            (source / "unknown.xyz").write_bytes(b"not a recognized format")
            (source / "document.json").write_text(
                "This is the original, not native JSON.", encoding="utf8"
            )
            (source / "nested" / "plain.txt").write_text(
                "The button does not respond. 12 ms.", encoding="utf8"
            )
            doc = Document()
            doc.add_heading("Task B / Participant P2", 0)
            doc.add_paragraph("The button does not respond.")
            doc.save(source / "office.docx")
            workspace = Workspace(root / "work")
            copy = shutil.copyfile

            def copying(src, dest):
                if src.name == "01-unreadable.txt":
                    raise PermissionError("synthetic unreadable")
                return copy(src, dest)

            with patch("shutil.copyfile", side_effect=copying):
                workspace.import_paths([str(source)])
            rows = workspace.files()["items"]
            self.assertEqual(len(rows), 5)
            self.assertTrue(next(r for r in rows if r["name"] == "plain.txt")["native"])
            self.assertTrue(
                next(r for r in rows if r["name"] == "office.docx")["native"]
            )
            self.assertIn(
                "PermissionError",
                next(r for r in rows if r["name"] == "01-unreadable.txt")["error"],
            )
            original = next(r for r in rows if r["name"] == "document.json")
            self.assertEqual(
                workspace.artifact(original, "stored").read_text(),
                "This is the original, not native JSON.",
            )
            self.assertTrue(
                next(r for r in rows if r["name"] == "unknown.xyz")["stored"]
            )
            workspace.import_paths([str(workspace.root)])
            self.assertIn(
                "Interner Arbeitsbereich", workspace.files()["items"][-1]["error"]
            )

            def unreadable_walk(folder, *, followlinks, onerror):
                onerror(
                    PermissionError(
                        13, "Synthetic blocked directory", str(source / "locked")
                    )
                )
                return iter(())

            with patch("os.walk", side_effect=unreadable_walk):
                workspace.import_paths(
                    [str(source), str(source / "nested" / "plain.txt")]
                )
            self.assertIn("PermissionError", workspace.files()["items"][-2]["error"])
            self.assertTrue(workspace.files()["items"][-1]["native"])

    def test_partial_conversion_sparse_native_view_and_current_api(self):
        from docling_core.types.doc import (
            DoclingDocument,
            DocItemLabel,
            TableData,
            TableCell,
        )

        doc = DoclingDocument(name="partial")
        from docling_core.types.doc import ImageRef, Size
        from PIL import Image

        doc.add_page(
            1,
            Size(width=100, height=100),
            ImageRef.from_pil(Image.new("RGB", (100, 100), "white"), dpi=72),
        )
        doc.add_text(
            label=DocItemLabel.TEXT,
            text="<script>literal</script> Available despite error",
        )
        for n in range(120):
            doc.add_text(label=DocItemLabel.TEXT, text=f"Native element {n}")
        doc.add_table(
            data=TableData(
                num_rows=1000,
                num_cols=1000,
                table_cells=[
                    TableCell(
                        text="17 ms",
                        start_row_offset_idx=999,
                        end_row_offset_idx=1000,
                        start_col_offset_idx=999,
                        end_col_offset_idx=1000,
                    )
                ],
            )
        )
        result = SimpleNamespace(
            document=doc,
            timings={},
            status=SimpleNamespace(value="partial_success"),
            errors=[SimpleNamespace(error_message="synthetic conversion fault")],
        )
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.pdf"
            source.write_text("unmodified original", encoding="utf8")
            app = application(root / "work")
            workspace = app.state.workspace
            with (
                patch(
                    "docling.document_converter.DocumentConverter.convert",
                    return_value=result,
                ),
                patch.object(
                    TableData,
                    "grid",
                    new_callable=PropertyMock,
                    side_effect=AssertionError("dense grid"),
                ),
            ):
                workspace.import_paths([str(source)])
                row = workspace.files()["items"][0]
                self.assertEqual(row["status"], "partial_success")
                self.assertTrue(row["native"])
                with TestClient(app) as client:
                    page = client.get(f"/document/{row['id']}/view")
                    self.assertEqual(page.status_code, 200)
                    self.assertIn("&lt;script&gt;", page.text)
                    self.assertNotIn("Native element 119", page.text)
                    tail = client.get(f"/document/{row['id']}/view?offset=100")
                    self.assertIn("Native element 119", tail.text)
                    table = client.get(
                        f"/document/{row['id']}/cells",
                        params={"ref": "#/tables/0", "start": 999, "column": 999},
                    )
                    self.assertEqual(table.status_code, 200)
                    self.assertIn("17 ms", table.text)
                    self.assertIn("999", table.text)
                    self.assertIn("sandbox", page.headers["content-security-policy"])
                    original_view = client.get(f"/document/{row['id']}/original-view")
                    self.assertIn("PDF.js", original_view.text)
                    self.assertEqual(
                        client.get(f"/document/{row['id']}/web").status_code, 200
                    )
                    self.assertEqual(
                        client.get(f"/document/{row['id']}/original").content,
                        b"unmodified original",
                    )
                    self.assertEqual(
                        client.post("/api/import", json={"paths": []}).status_code, 403
                    )
                    self.assertEqual(
                        client.get(
                            "/", headers={"Host": "foreign.invalid"}
                        ).status_code,
                        400,
                    )

    def test_model_error_is_visible_without_exposing_key(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.txt"
            source.write_text("Synthetic UX content.", encoding="utf8")
            workspace = Workspace(root / "work")
            workspace.import_paths([str(source)])
            row = workspace.files()["items"][0]
            log = io.StringIO()
            with (
                patch(
                    "litellm.completion", side_effect=RuntimeError("synthetic-secret")
                ) as completion,
                redirect_stdout(log),
                redirect_stderr(log),
            ):
                workspace.extract(
                    [row["id"]],
                    {
                        "provider": "nhr_fau",
                        "model": "synthetic",
                        "key": "synthetic-secret",
                        "context_limit": 32000,
                    },
                )
            result = workspace.results(row["id"])
            self.assertGreater(completion.call_count, 0)
            self.assertEqual(result[0]["result"]["status"], "ERROR")
            self.assertNotIn("synthetic-secret", json.dumps(result) + log.getvalue())

    def test_native_clients_all_existing_providers(self):
        for provider in (p for p in PRESETS if p != "custom"):
            with self.subTest(provider=provider):
                client = connect(
                    {
                        "provider": provider,
                        "model": "synthetic",
                        "key": "fake",
                        "max_output_tokens": 10000,
                        "context_limit": 32000,
                    }
                )
                self.assertEqual(client.provider, provider)
                self.assertEqual(client.max_tokens, 10000)


if __name__ == "__main__":
    unittest.main()
