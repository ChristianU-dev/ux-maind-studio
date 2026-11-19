"""Serve an isolated copy of the recorded R18a A-läufe for the R18c browser suite."""

import argparse
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from pathlib import Path
import json, shutil
import uvicorn

sys.path.insert(0, str(Path.cwd()))
from ux_maind.app import research
from ux_maind.app.studio import application

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--workspace", type=Path, required=True)
parser.add_argument("--port", type=int, default=18789)
parser.add_argument("--model-port", type=int, default=18790)
args = parser.parse_args()
root = args.workspace.resolve()
if root.exists():
    parser.error("A new test workspace is required")
shutil.copytree(args.source, root)
app = application(root)
w = app.state.workspace
catalog = research.catalog(w, [1, 2])
left = [
    e["ref"]
    for e in catalog["observations"]
    if e["ref"]["document"] == 1 and e["source_check"]["matches"]
]
right = [
    e["ref"]
    for e in catalog["observations"]
    if e["ref"]["document"] == 2 and e["source_check"]["matches"]
]
if not any(
    x["kind"] == "relation" and x["metadata"].get("origin") == "probe"
    for x in research.objects(w, [1, 2])
):
    research.create(
        w,
        "relation",
        dict(
            source=left[0],
            target=dict(document=2, run=99999, observation="O99"),
            kind="invented",
            rationale="Intentionally unresolved fixture",
        ),
        [1, 2],
        {"origin": "probe"},
    )
for name in ("b-model", "c-fail", "c-model"):
    w.save_profile(
        name,
        dict(
            provider="custom",
            model=name,
            base_url=f"http://127.0.0.1:{args.model_port}/v1",
            gleaning_enabled=False,
            extraction_contract="direct",
        ),
    )
w.set_setting("workflow", dict(profiles=dict(A="b-model", B="b-model", C="c-fail")))


class Reply(BaseHTTPRequestHandler):
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        model = req.get("model")
        fields = list(
            (req.get("response_format") or {})
            .get("json_schema", {})
            .get("schema", {})
            .get("properties", {})
        )
        if model == "b-model":
            answer = dict(
                relations=[
                    dict(
                        source=left[0],
                        target=right[0],
                        kind="qualifies",
                        rationale="Grounded synthetic cross-document probe",
                    ),
                    dict(
                        source=left[0],
                        target=left[1],
                        kind=None,
                        rationale="No inferred relation in this probe",
                    ),
                ]
            )
        elif model == "c-model":
            objects = research.objects(w, [1, 2])
            relation = next(
                o["id"]
                for o in reversed(objects)
                if o["kind"] == "relation"
                and o["metadata"].get("stage") == "B"
                and o["effective"]["kind"]
            )
            answer = dict(
                findings=[
                    dict(
                        title="Speichern: qualifizierende Belege",
                        valence="mixed",
                        rationale="Die Belegrollen überlappen in dieser Gegenprobe.",
                        supports=[left[0], right[0]],
                        opposes=[left[0]],
                        uncertainty="Synthetische Ergebnisprobe",
                        relations=[relation],
                    )
                ]
            )
        else:
            answer = None
        if answer is None:
            data = {
                "error": {
                    "message": "synthetic-stage-failure",
                    "type": "invalid_request_error",
                }
            }
        else:
            data = dict(
                id="sample",
                created=1,
                object="chat.completion",
                model=model,
                choices=[
                    dict(
                        index=0,
                        message=dict(role="assistant", content=json.dumps(answer)),
                        finish_reason="stop",
                    )
                ],
                usage=dict(prompt_tokens=80, completion_tokens=55, total_tokens=135),
            )
        packed = json.dumps(data).encode()
        status = 200 if answer is not None else 422
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(packed)))
        self.end_headers()
        self.wfile.write(packed)
        with (root / "calls.jsonl").open("a", encoding="utf8") as out:
            out.write(
                json.dumps(dict(model=model, fields=fields, status=status)) + "\n"
            )


service = ThreadingHTTPServer(("127.0.0.1", args.model_port), Reply)
Thread(target=service.serve_forever, daemon=True).start()
uvicorn.run(app, host="127.0.0.1", port=args.port)
