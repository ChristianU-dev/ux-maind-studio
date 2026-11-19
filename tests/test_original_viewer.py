"""R14 current native SDK boundary and secure original/derivative display; no cloud calls."""

import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from ux_maind.app.models import connect, describe, profile_options
from ux_maind.app.studio import application


class OriginalViewer(unittest.TestCase):
    def test_native_parameters_reach_sdk_or_are_explicitly_filtered(self):
        raw = dict(
            provider="custom",
            model="free-id",
            base_url="http://127.0.0.1:9123/v1",
            context_limit=123456,
            max_output_tokens=16000,
            generation=dict(max_tokens=12000, temperature=0.3, top_p=0.8, top_k=7),
        )
        reply = {
            "choices": [
                {"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}
            ]
        }
        with self.assertRaisesRegex(ValueError, "Ausgabebudget"):
            profile_options(dict(raw, max_output_tokens=1000))
        for supported in [
            ["temperature", "max_tokens", "top_p", "top_k"],
            ["max_tokens"],
        ]:
            with (
                self.subTest(supported=supported),
                patch("litellm.get_supported_openai_params", return_value=supported),
                patch("litellm.completion", return_value=reply) as sdk,
            ):
                client = connect(raw, preview=True)
                self.assertEqual(client.context_limit, 123456)
                self.assertEqual(client.model_config.max_output_tokens, 16000)
                self.assertEqual(
                    client.get_json_response("Synthetic only", '{"type":"object"}'),
                    {"ok": True},
                )
                sent = sdk.call_args.kwargs
                self.assertNotIn("context_limit", sent)
                self.assertNotIn("max_output_tokens", sent)
                self.assertEqual(sent["max_tokens"], 12000)
                for name in ["temperature", "top_p", "top_k"]:
                    self.assertEqual(name in sent, name in supported)
                self.assertNotIn("reasoning_effort", sent)
                preview = describe(raw)
                self.assertIn(
                    "entfernt" if "top_k" not in supported else "SDK-Eingang",
                    preview["parameter_support"]["top_k"],
                )
        # The unknown library fallback must not reject a larger explicit user budget.
        raw.pop("max_output_tokens")
        self.assertEqual(connect(raw, preview=True).max_tokens, 12000)

    def test_pdf_bytes_derivative_cache_identity_and_missing_renderer(self):
        with tempfile.TemporaryDirectory() as root:
            app = application(root)
            w = app.state.workspace
            source = Path(root) / "source.docx"
            source.write_bytes(b"synthetic original")
            renderer = Path(root) / "soffice.exe"
            renderer.write_bytes(b"controlled executable identity")
            with w.db() as db:
                db.execute(
                    "INSERT INTO documents(name,stored,status) VALUES('source.docx','source.docx','failure')"
                )
            output = b"%PDF-1.4\ncontrolled test bytes\n%%EOF"

            def convert(args, **kwargs):
                self.assertNotIn("shell", kwargs)
                self.assertIn("--headless", args)
                folder = Path(args[args.index("--outdir") + 1])
                (folder / "source.pdf").write_bytes(output)
                return SimpleNamespace(returncode=0)

            with TestClient(app) as client:
                with patch("ux_maind.app.office.office_renderer", return_value=None):
                    failed = client.get("/document/1/office-pdf")
                    self.assertEqual(failed.status_code, 400)
                    self.assertIn("LibreOffice nicht installiert", failed.text)
                with (
                    patch(
                        "ux_maind.app.office.office_renderer",
                        return_value=str(renderer),
                    ),
                    patch("subprocess.run", side_effect=convert) as call,
                ):
                    first = client.get("/document/1/office-pdf")
                    self.assertEqual(first.content, output)
                    self.assertEqual(
                        first.headers["x-source-sha256"],
                        hashlib.sha256(source.read_bytes()).hexdigest(),
                    )
                    self.assertEqual(
                        client.get("/document/1/office-pdf").content, output
                    )
                    self.assertEqual(call.call_count, 1)
                    source.write_bytes(b"changed source same filename")
                    second = client.get("/document/1/office-pdf")
                    self.assertNotEqual(
                        first.headers["x-source-sha256"],
                        second.headers["x-source-sha256"],
                    )
                    self.assertEqual(call.call_count, 2)
                self.assertEqual(client.get("/document/1/pdf").status_code, 400)
                source.write_bytes(output)
                self.assertEqual(client.get("/document/1/pdf").content, output)
                self.assertIn(
                    "text/html", client.get("/assets/pdf.html").headers["content-type"]
                )
                self.assertEqual(
                    len(list((Path(root) / "display").glob("*/display.json"))), 2
                )

    def test_saved_profile_reopens_without_storing_key(self):
        with tempfile.TemporaryDirectory() as root:
            app = application(root)
            w = app.state.workspace
            w.save_profile(
                "Local", dict(provider="ollama", model="free:local", key="never-export")
            )
            with TestClient(app) as client:
                r = client.get("/api/profiles")
                self.assertEqual(r.status_code, 200)
                self.assertNotIn("never-export", r.text)
                self.assertEqual(r.json()["profiles"][0]["name"], "Local")
                from ux_maind.app.workspace import Workspace

                self.assertEqual(Workspace(root).profiles(), w.profiles())
