"""Add a test observation anchored to an existing R18a Vision derivative."""

import argparse
import sys
from datetime import datetime, timezone
import json
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from ux_maind.app.workspace import Workspace
from ux_maind.app.evidence import SCHEMA_VERSION, Sources

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--workspace", type=Path, required=True)
root = parser.parse_args().workspace.resolve()
if not (root / "calls.jsonl").is_file():
    parser.error("Use only a test workspace from probe_r18c_analysis.py")
w = Workspace(root)
row = w.file(2)
before = w.results(2)[0]["result"]
if before.get("model") != "fixture-image-reference":
    version = before["document_version"]
    doc = w.document(w.version_row(row, version))
    picture = next(
        p
        for p in doc.pictures
        if p.meta and p.meta.description and p.meta.description.text
    )
    quote = picture.meta.description.text
    anchor = Sources(doc, 2, version).locate(
        quote, {"self_ref": picture.self_ref}, "picture_description"
    )
    result = dict(
        schema_version=SCHEMA_VERSION,
        status="UNREVIEWED",
        provider="fixture",
        model="fixture-image-reference",
        document_version=version,
        sources={"P1": anchor},
        relations=[],
        observations=[
            dict(
                id="O-picture",
                statement="Bildbeleg auf gespeichertem R18a-Derivat",
                quote=quote,
                source_ids=["P1"],
                measurements=[],
                context=None,
            )
        ],
    )
    with w.db() as db:
        db.execute(
            "INSERT INTO runs(document,at,result) VALUES(?,?,?)",
            (2, datetime.now(timezone.utc).isoformat(), json.dumps(result)),
        )
