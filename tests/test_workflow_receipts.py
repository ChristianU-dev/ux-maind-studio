import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
import unittest

from starlette.testclient import TestClient

from ux_maind.app import enrichment, library
from ux_maind.app.studio import application


class WorkflowReceipts(unittest.TestCase):
    def test_mixed_native_job_remains_available_without_open_document(self):
        with TemporaryDirectory() as name:
            folder = Path(name).resolve()
            good = folder / "good.txt"
            good.write_text("Document is usable.", encoding="utf-8")
            broken = folder / "broken.docx"
            broken.write_bytes(b"invalid archive")
            app = application(folder / "work")
            w = app.state.workspace
            w.import_paths([good, broken], convert=False)
            with TestClient(app) as client:
                token = (
                    client.get("/")
                    .text.split('name="workspace-token" content="')[1]
                    .split('"')[0]
                )
                response = client.post(
                    "/api/convert",
                    json={"documents": [1, 2], "vision": {"enabled": False}},
                    headers={"X-Workspace-Token": token},
                )
                self.assertEqual(response.status_code, 200, response.text)
                until = monotonic() + 25
                while True:
                    job = client.get("/api/status").json()
                    if not job["busy"]:
                        break
                    self.assertLess(monotonic(), until, "Native job did not finish")
                    sleep(0.04)
                self.assertEqual(job["state"], "PARTIAL")
                self.assertEqual(
                    [d["document_name"] for d in job["documents"]],
                    ["good.txt", "broken.docx"],
                )
                self.assertEqual(
                    job["documents"][0]["steps"]["conversion"]["status"], "success"
                )
                self.assertEqual(
                    job["documents"][1]["steps"]["conversion"]["status"], "failure"
                )
                self.assertEqual(
                    job["documents"][0]["steps"]["vision"]["reason"], "no_pictures"
                )
                self.assertNotIn("A", job["documents"][0]["steps"])
            with TestClient(application(w.root)) as client:
                self.assertEqual(client.get("/api/status").json(), job)

    def test_workflow_uses_existing_profiles_and_keeps_model_roles_independent(self):
        with TemporaryDirectory() as name:
            w = application(Path(name) / "work").state.workspace
            for profile, model in (("text", "text-model"), ("vision", "vision-model")):
                w.save_profile(
                    profile,
                    dict(
                        provider="custom", model=model, base_url="http://127.0.0.1:1234"
                    ),
                )
            settings = library.workflow_settings(
                w, {"profiles": {"A": "text", "vision": "vision"}}
            )
            self.assertEqual(
                settings["profiles"],
                {"A": "text", "B": "", "C": "", "vision": "vision"},
            )
            self.assertEqual(
                enrichment.manual_plan(
                    dict(mode="api", profile=dict(provider="custom"), send=True)
                ),
                "model_missing",
            )
            self.assertTrue(settings["vision"]["enabled"])
            self.assertNotIn("base_url", json.dumps(w.setting("workflow")))
            w.delete_profile("vision")
            current = library.workflow_settings(w)
            self.assertEqual(current["profiles"]["vision"], "")
            self.assertEqual(current["profiles"]["A"], "text")
