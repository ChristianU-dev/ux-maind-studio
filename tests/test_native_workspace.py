"""R13 current workspace boundaries: no credentials, native references and sparse access."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, PropertyMock
from starlette.testclient import TestClient
from ux_maind.app.models import profile_options, connect, describe
from ux_maind.app.workspace import Workspace
from ux_maind.app.studio import application


class NativeWorkspace(unittest.TestCase):
    def test_fau_reference_and_shared_window_are_distinct(self):
        profile = dict(provider="nhr_fau", model="Qwen/Qwen3.6-35B-A3B-FP8")
        directory = [
            dict(id=profile["model"], max_input_tokens=262144, max_output_tokens=262144)
        ]
        with patch("ux_maind.app.models.fau_entries", return_value=directory):
            client = connect(dict(profile, key="synthetic"))
            self.assertEqual(client.context_limit, 262144)
            self.assertEqual(client.max_tokens, 4092)
            self.assertIsNone(describe(profile, client=client)["wire_max_tokens"])
            with patch(
                "litellm.completion",
                return_value={
                    "choices": [
                        {"message": {"content": "{}"}, "finish_reason": "stop"},
                    ]
                },
            ) as call:
                client.get_json_response(
                    "Test.", '{"type":"object"}', structured_output=False
                )
                self.assertNotIn("max_tokens", call.call_args.kwargs)
            self.assertIn(
                "Anbietergrenze unbekannt",
                describe(profile, client=client)["sources"]["max_output_tokens"],
            )
            explicit = connect(
                dict(profile, key="synthetic", generation={"max_tokens": 40000})
            )
            self.assertEqual(explicit.max_tokens, 40000)
            with self.assertRaises(ValueError):
                connect(
                    dict(
                        profile,
                        key="synthetic",
                        context_limit=262144,
                        max_output_tokens=262144,
                    )
                )

    def test_profiles_reopen_without_credentials_and_native_parameters(self):
        with tempfile.TemporaryDirectory() as root:
            w = Workspace(root)
            raw = dict(
                provider="custom",
                model="free-model-id",
                base_url="http://127.0.0.1:9123/v1",
                key_env="SYNTHETIC_KEY",
                key="not-stored",
                generation=dict(temperature=0.3, top_p=0.8, top_k=12, max_tokens=777),
                context_limit=12000,
                max_output_tokens=900,
            )
            w.save_profile("One", raw)
            reopened = Workspace(root).profiles()
            self.assertNotIn("not-stored", json.dumps(reopened))
            with patch.dict("os.environ", {"SYNTHETIC_KEY": "runtime-only"}):
                client = connect(reopened[0]["options"])
                self.assertEqual(
                    client.model_config.connection.api_key.get_secret_value(),
                    "runtime-only",
                )
                self.assertEqual(client.max_tokens, 777)
                self.assertEqual(client.context_limit, 12000)
                self.assertEqual(client.generation.top_k, 12)
            w.save_profile("One", dict(raw, model="changed"))
            self.assertEqual(
                Workspace(root).profiles()[0]["options"]["model"], "changed"
            )
            w.delete_profile("One")
            self.assertEqual(w.profiles(), [])
            with self.assertRaises(ValueError):
                profile_options(dict(raw, provider="nhr_fau"))
            with self.assertRaises(ValueError):
                profile_options(dict(raw, generation=dict(reasoning_effort="high")))
            automatic = describe(dict(provider="nhr_fau", model="unknown-fau-model"))
            self.assertIn("unbekannt", automatic["sources"]["context_limit"])
            self.assertIn("Reasoning-Parameter", automatic["thinking"])
            self.assertIsNone(automatic["provider_limits"]["context_limit"])

    def test_preview_and_request_use_same_fau_model_metadata_with_explicit_discovery(
        self,
    ):
        profile = dict(provider="nhr_fau", model="synthetic-fau")
        directory = [
            dict(id="synthetic-fau", max_model_len=64000, max_output_tokens=8000)
        ]
        with (
            patch.dict("os.environ", {"LLMAPI_KEY": "test-key"}),
            patch("ux_maind.app.models.fau_entries", return_value=directory),
        ):
            preview = describe(profile, discover_limits=True)
            actual = describe(profile, client=connect(profile))
        self.assertEqual(preview["context_limit"], actual["context_limit"])
        self.assertEqual(preview["max_output_tokens"], actual["max_output_tokens"])
        self.assertEqual(preview["wire_max_tokens"], actual["wire_max_tokens"])
        self.assertNotIn("context_limit", preview["options"])
        self.assertNotIn("max_output_tokens", preview["options"])
        self.assertEqual(preview["sources"]["context_limit"], "FAU-Modellverzeichnis")

    def test_profile_http_and_explicit_fau_model_directory(self):
        import re
        import io
        from ux_maind.app.models import fau_models, FAU

        with tempfile.TemporaryDirectory() as root:
            app = application(root)
            with TestClient(app) as client:
                token = re.search(
                    r'name="workspace-token"\s+content="([^"]+)"', client.get("/").text
                ).group(1)
                headers = {"X-Workspace-Token": token}
                profile = dict(
                    provider="ollama",
                    model="free:local",
                    key="must-not-persist",
                    generation=dict(temperature=0.2),
                )
                self.assertEqual(
                    client.post(
                        "/api/profile-save",
                        json=dict(name="Local", options=profile),
                        headers=headers,
                    ).status_code,
                    200,
                )
                self.assertNotIn("must-not-persist", client.get("/api/profiles").text)
                self.assertEqual(
                    client.post(
                        "/api/model-preview", json=profile, headers=headers
                    ).json()["options"]["model"],
                    "free:local",
                )
                client.post(
                    "/api/profile-delete", json=dict(name="Local"), headers=headers
                )
                self.assertEqual(client.get("/api/profiles").json()["profiles"], [])
        with (
            patch.dict("os.environ", {"R13_TEST_KEY": "runtime-only"}),
            patch(
                "urllib.request.urlopen",
                return_value=io.StringIO('{"data":[{"id":"free-model"}]}'),
            ) as call,
        ):
            self.assertEqual(
                fau_models(
                    dict(provider="nhr_fau", model="anything", key_env="R13_TEST_KEY")
                ),
                ["free-model"],
            )
            request = call.call_args.args[0]
            self.assertEqual(request.full_url, FAU + "/models")
            self.assertEqual(request.get_header("Authorization"), "Bearer runtime-only")
            from urllib.request import HTTPRedirectHandler

            redirected = HTTPRedirectHandler().redirect_request(
                request, None, 302, "", {}, "https://foreign.invalid/models"
            )
            self.assertIsNone(redirected.get_header("Authorization"))

    def test_empty_and_truncated_native_replies_remain_errors(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "synthetic.txt"
            source.write_text("Synthetic source statement.", encoding="utf8")
            w = Workspace(Path(root) / "work")
            w.import_paths([str(source)])
            for content, finish in [("", "stop"), ('{"observations":[', "length")]:
                with (
                    self.subTest(finish=finish),
                    patch(
                        "litellm.completion",
                        return_value={
                            "choices": [
                                {
                                    "message": {"content": content},
                                    "finish_reason": finish,
                                }
                            ]
                        },
                    ),
                ):
                    w.extract(
                        [1],
                        dict(
                            provider="nhr_fau",
                            model="synthetic",
                            key="dummy-secret",
                            context_limit=32000,
                        ),
                    )
                    r = w.results(1)[0]["result"]
                    self.assertEqual(r["status"], "ERROR")
                    self.assertEqual(r["observations"], [])
                    self.assertNotIn("dummy-secret", json.dumps(r))
                    self.assertIn(
                        "pipeline_failed",
                        [event["event_type"] for event in r["native_graph"]["trace"]],
                    )
                    self.assertEqual(
                        r["native_graph"]["last_response"].get("truncated", False),
                        finish == "length",
                    )

    def test_custom_openai_client_uses_same_native_pipeline(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "source.txt"
            p.write_text("Synthetic statement.", encoding="utf8")
            w = Workspace(Path(root) / "work")
            w.import_paths([str(p)])
            reply = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "observations": [
                                        dict(
                                            statement="Synthetic",
                                            quote="Synthetic statement.",
                                        )
                                    ],
                                }
                            )
                        },
                        "finish_reason": "stop",
                    }
                ]
            }
            with patch("litellm.completion", return_value=reply) as call:
                w.extract(
                    [1],
                    dict(
                        provider="custom",
                        model="unchanged-model-id",
                        base_url="http://192.0.2.1:9123/v1",
                        key_env="",
                        context_limit=32000,
                        gleaning_enabled=False,
                    ),
                )
                self.assertEqual(
                    call.call_args.kwargs["api_base"], "http://192.0.2.1:9123/v1"
                )
                self.assertEqual(
                    call.call_args.kwargs["model"], "openai/unchanged-model-id"
                )
                self.assertEqual(call.call_args.kwargs["api_key"], "local")
            r = w.results(1)[0]["result"]
            self.assertEqual(r["status"], "UNREVIEWED")
            self.assertEqual(r["provider"], "custom")
            self.assertEqual(r["coverage"]["source_verified"], 1)

    def test_untrusted_html_svg_originals_remain_inert_downloads(self):
        with tempfile.TemporaryDirectory() as root:
            app = application(root)
            w = app.state.workspace
            with TestClient(app) as client:
                for n, extension in enumerate(["html", "svg"], 1):
                    content = (
                        b"<svg><script>unsafe()</script></svg>"
                        if extension == "svg"
                        else b"<html><script>unsafe()</script></html>"
                    )
                    name = "original." + extension
                    (Path(root) / name).write_bytes(content)
                    with w.db() as db:
                        db.execute(
                            "INSERT INTO documents(name,stored,status) VALUES(?,?,?)",
                            (name, name, "unsupported"),
                        )
                    preview = client.get(f"/document/{n}/original-view")
                    self.assertNotIn("<script>", preview.text)
                    self.assertNotIn("<svg>", preview.text)
                    download = client.get(f"/document/{n}/original")
                    self.assertEqual(download.content, content)
                    self.assertIn("attachment", download.headers["content-disposition"])
                    self.assertEqual(
                        download.headers["x-content-type-options"], "nosniff"
                    )

    def test_aliases_resources_sparse_window_merges_and_api(self):
        from docling_core.types.doc import (
            DoclingDocument,
            DocItemLabel,
            TableData,
            TableCell,
            ImageRef,
            Size,
        )
        from PIL import Image

        doc = DoclingDocument(name="Native fixture")
        doc.add_page(
            1,
            Size(width=100, height=100),
            ImageRef.from_pil(Image.new("RGB", (100, 100), "white"), dpi=72),
        )
        doc.add_text(label=DocItemLabel.TEXT, text="<script>literal</script>")
        doc.add_table(
            data=TableData(
                num_rows=1000,
                num_cols=1000,
                table_cells=[
                    TableCell(
                        text="Merged header",
                        start_row_offset_idx=0,
                        end_row_offset_idx=4,
                        start_col_offset_idx=0,
                        end_col_offset_idx=4,
                        row_span=4,
                        col_span=4,
                        column_header=True,
                    ),
                    TableCell(
                        text="17 ms",
                        start_row_offset_idx=999,
                        end_row_offset_idx=1000,
                        start_col_offset_idx=999,
                        end_col_offset_idx=1000,
                    ),
                ],
            )
        )
        with tempfile.TemporaryDirectory() as root:
            app = application(root)
            w = app.state.workspace
            p = Path(root) / "document.json"
            p.write_text(
                doc.model_dump_json(exclude_computed_fields=True), encoding="utf8"
            )  # R12 cref file accepted by native loader
            with w.db() as db:
                db.execute(
                    "INSERT INTO documents(name,native,status) VALUES('fixture','document.json','partial_success')"
                )
            row = w.file(1)
            before = p.read_bytes()
            with patch.object(
                TableData,
                "grid",
                new_callable=PropertyMock,
                side_effect=AssertionError("full grid"),
            ):
                web = json.loads(w.web_document(row))
                self.assertIn("$ref", web["body"]["children"][0])
                self.assertNotIn("cref", web["body"]["children"][0])
                self.assertIn("/document/1/resource", web["pages"]["1"]["image"]["uri"])
                self.assertTrue(w.resource(row, "page", 1)[0].startswith(b"\x89PNG"))
                page = w.document(row).pages[1]
                original_image = page.image
                for uri in [
                    "file:///C:/private-image.png",
                    "https://foreign.invalid/image.png",
                ]:
                    page.image = original_image.model_copy(update={"uri": uri})
                    with self.assertRaises(ValueError):
                        w.resource(row, "page", 1)
                page.image = original_image
                data = w.cells(row, "#/tables/0", start=2, column=2)
                self.assertEqual(
                    data["cells"][0]["visible_span"],
                    dict(row=2, row_end=4, column=2, column_end=4),
                )
                self.assertEqual(
                    w.cells(row, "#/tables/0", search="17 ms")["cells"][0][
                        "start_row_offset_idx"
                    ],
                    999,
                )
                with w.db() as db:
                    db.execute(
                        "INSERT INTO runs(document,at,result) VALUES(1,'synthetic',?)",
                        (
                            json.dumps(
                                dict(
                                    information=[dict(text="proposal")],
                                    graph=dict(nodes=[], edges=[]),
                                )
                            ),
                        ),
                    )
                with w.db() as db:
                    db.execute(
                        "INSERT INTO notes(run,item,at,text) VALUES(?,?,?,?)",
                        (
                            1,
                            0,
                            "historical",
                            "AUTOMATED export check, not a human research review",
                        ),
                    )
                with TestClient(app) as client:
                    self.assertEqual(client.get("/document/1/web").status_code, 200)
                    self.assertIn("&lt;script&gt;", client.get("/document/1/view").text)
                    self.assertEqual(
                        client.get("/api/elements?id=1").json()["items"][0]["ref"],
                        "#/texts/0",
                    )
                    self.assertEqual(
                        client.get(
                            "/api/cells?id=1&ref=%23/tables/0&start=999&column=999"
                        ).json()["cells"][0]["text"],
                        "17 ms",
                    )
                    self.assertEqual(
                        client.post("/api/profile-save", json={}).status_code, 403
                    )
                    exported = client.get("/document/1/export")
                    self.assertIn("attachment", exported.headers["content-disposition"])
                    self.assertIn(
                        "AUTOMATED export check", exported.json()[0]["notes"][0]["text"]
                    )
                    self.assertEqual(
                        client.get("/document/1/export?graph=1").json(),
                        dict(nodes=[], edges=[]),
                    )
            self.assertEqual(p.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
