import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient

from ux_maind.app import library, research
from ux_maind.app.studio import application
from ux_maind.app.workspace import Workspace


class WorkspaceLibrary(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = Workspace(self.root / "work")
        self.original = self.root / "same.txt"
        self.original.write_text("A distinctive sentence.", encoding="utf-8")

    def test_inventory_native_retry_and_protected_removal(self):
        w = self.workspace
        self.assertEqual(
            w.import_paths([self.original, self.original], convert=False),
            {"pending_conversion": 2},
        )
        self.assertFalse(w.file(1)["native"])
        self.assertEqual(w.convert_selected([1])[0]["status"], "success")
        first = w.summary(w.file(1))["version"]
        self.assertEqual(w.convert_selected([1])[0]["status"], "success")
        self.assertEqual(w.summary(w.version_row(w.file(1), first))["version"], first)
        self.assertEqual(w.summary(w.file(1))["versions"][-1]["kind"], "conversion")
        original_bytes = self.original.read_bytes()
        research.create(w, "finding", {"title": "Retention fixture"}, [1])
        copy = w.artifact(w.file(2), "stored")
        with w.db() as db:
            self.assertFalse(library.preview(db, 1)["removable"])
        self.assertEqual(
            [r["status"] for r in library.remove(w, [1, 2], "remove")],
            ["BLOCKED", "REMOVED"],
        )
        self.assertFalse(copy.parent.parent.exists())
        self.assertEqual(self.original.read_bytes(), original_bytes)
        self.assertEqual(library.remove(w, [1], "archive")[0]["status"], "ARCHIVED")
        self.assertEqual(w.files()["total"], 0)
        self.assertEqual(w.files(archived=True)["total"], 1)
        self.assertEqual(len(research.objects(w, [1])), 1)
        self.assertEqual(library.remove(w, [1], "restore")[0]["status"], "RESTORED")
        w.import_paths([self.original], convert=False)
        self.assertEqual([f["id"] for f in w.files()["items"]], [1, 3])

    def test_output_picker_limits_and_byte_exact_export(self):
        w = self.workspace
        w.import_paths([self.original], convert=False)
        app = application(w.root)
        with TestClient(app) as client:
            page = client.get("/").text
            token = page.split('name="workspace-token" content="')[1].split('"')[0]
            headers = {"X-Workspace-Token": token}
            self.assertEqual(
                client.get("/api/paths").json()["output"], str(w.root / "exports")
            )
            self.assertEqual(client.post("/api/output-pick", json={}).status_code, 403)
            destination = self.root / "chosen"
            destination.mkdir()
            with patch(
                "ux_maind.app.studio.pick_paths", return_value=[str(destination)]
            ):
                selected = client.post(
                    "/api/output-pick", json={"path": str(self.root)}, headers=headers
                )
            self.assertEqual(selected.json()["output"], str(destination))
            result = client.post(
                "/api/save-export",
                json={"document": 1, "kind": "original", "path": str(self.root)},
                headers=headers,
            )
            self.assertEqual(result.status_code, 200, result.text)
            target = Path(result.json()["path"])
            self.assertEqual(target.parent, destination)
            self.assertEqual(
                hashlib.sha256(target.read_bytes()).digest(),
                hashlib.sha256(self.original.read_bytes()).digest(),
            )
            with patch("ux_maind.app.studio.pick_paths", return_value=[str(w.root)]):
                self.assertEqual(
                    client.post(
                        "/api/output-pick", json={}, headers=headers
                    ).status_code,
                    400,
                )
            self.assertEqual(client.get("/api/paths").json()["workspace"], str(w.root))

    def test_removal_refuses_misdirected_copy(self):
        w = self.workspace
        w.import_paths([self.original], convert=False)
        managed = w.artifact(w.file(1), "stored")
        with w.db() as db:
            db.execute(
                "UPDATE documents SET stored=? WHERE id=1", (str(self.original),)
            )
        self.assertEqual(library.remove(w, [1], "remove")[0]["status"], "ERROR")
        self.assertTrue(self.original.is_file())
        self.assertTrue(managed.is_file())


if __name__ == "__main__":
    unittest.main()
