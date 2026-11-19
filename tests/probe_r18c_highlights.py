"""Prepare isolated Highlight browser fixtures from the existing native probes."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from shutil import copytree
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path.cwd()))
from docx import Document
from docling_core.types.doc import PictureMeta, TableCell, TableData
from ux_maind.app.evidence import SCHEMA_VERSION, Sources
from ux_maind.app.research import create
from ux_maind.app.workspace import Workspace


def store(w, row, sources, anchor, statement):
    result = dict(
        schema_version=SCHEMA_VERSION,
        status="UNREVIEWED",
        provider="fixture",
        model="highlight-fixture",
        document_version=sources.version,
        sources={"anchor": anchor},
        observations=[
            dict(
                id="HL",
                statement=statement,
                source_ids=["anchor"],
                measurements=[],
                context=None,
            )
        ],
        relations=[],
    )
    with w.db() as db:
        run = db.execute(
            "INSERT INTO runs(document,at,result) VALUES(?,?,?)",
            (
                row["id"],
                datetime.now(timezone.utc).isoformat(),
                json.dumps(result),
            ),
        ).lastrowid
    return dict(document=row["id"], run=run, observation="HL")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Existing isolated R18c findings probe",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    copytree(args.source, args.output)
    w = Workspace(args.output)
    document = Document()
    quote = "P1 saved the form after retrying."
    document.add_heading("Office evidence probe", 0)
    document.add_paragraph(quote)
    with TemporaryDirectory(dir=args.output.parent) as inputs:
        demo = Path(inputs) / "office-highlight.docx"
        document.save(demo)
        report = w.import_paths([demo])
        if report != {"success": 1}:
            raise RuntimeError(f"Office fixture conversion failed: {report}")
    row = w.files(search=demo.name)["items"][0]
    office = Sources(w.document(row), row["id"], w.summary(row)["version"])
    ref = store(w, row, office, office.locate(quote, {}), quote)

    row = w.file(2)
    summary = w.summary(row)
    version = summary["preferred_version"] or summary["version"]
    doc = w.document(w.version_row(row, version))
    picture = next(pic for pic in doc.pictures if any(p.page_no == 2 for p in pic.prov))
    if picture.meta is None:
        picture.meta = PictureMeta()
    table = TableData(
        num_rows=3,
        num_cols=2,
        table_cells=[
            TableCell(
                text=value,
                start_row_offset_idx=r,
                end_row_offset_idx=r + 1,
                start_col_offset_idx=c,
                end_col_offset_idx=c + 1,
                column_header=r == 0,
            )
            for r, values in enumerate((("Person", "Items"), ("P1", "0"), ("P2", "7")))
            for c, value in enumerate(values)
        ],
    )
    picture.meta.tabular_chart = PictureMeta.model_validate(
        {
            "tabular_chart": {
                "title": "Synthetische native Chartdaten",
                "chart_data": table,
            },
        }
    ).tabular_chart
    content = doc.model_dump_json(by_alias=True, exclude_computed_fields=True).encode()
    version = sha256(content).hexdigest()
    w.save_version(
        w.artifact(row, "native"),
        dict(
            version=version,
            base_version=summary["base_version"],
            at=datetime.now(timezone.utc).isoformat(),
            status="success",
            configuration={"model": "synthetic-chart-fixture"},
            pictures=[{"ref": picture.self_ref, "chart": True}],
        ),
        content,
    )
    sources = Sources(doc, row["id"], version)
    store(
        w,
        row,
        sources,
        sources.select({"ref": picture.self_ref, "modality": "picture_enrichment"}),
        "Synthetischer Diagrammbeleg",
    )

    create(
        w,
        "finding",
        dict(
            title="Veralteter Quellenlauf",
            rationale="Synthetischer Negativtest",
            supports=[dict(ref, run=999999)],
            opposes=[],
        ),
        [ref["document"]],
        {"origin": "manual"},
    )


if __name__ == "__main__":
    main()
