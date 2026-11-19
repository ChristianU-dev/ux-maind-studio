"""Opt-in Windows/LibreOffice integration, synthetic files only, no model calls.
Run: python tests/probe_original_workspace.py --output artifacts/my-original-probe
Set UX_MAIND_SOFFICE when the official renderer is not installed on PATH.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path.cwd()))
from docx import Document
from docx.shared import Inches
from pptx import Presentation
from pptx.util import Inches as SlideInches
from PIL import Image
import pypdfium2 as pdfium
from starlette.testclient import TestClient
from ux_maind.app.studio import application, office_renderer

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
root = parser.parse_args().output.resolve()
root.mkdir(parents=True, exist_ok=True)
source = root / "input"
source.mkdir(exist_ok=True)
quote = "Ich finde die Schaltflaeche nicht."
picture = source / "synthetic.png"
Image.new("RGB", (240, 120), "#007d70").save(picture)
doc = Document()
doc.add_heading("Aufgabe A / P1", 0)
doc.add_paragraph(quote)
t = doc.add_table(rows=2, cols=2)
t.style = "Table Grid"
for c, v in zip(
    [*t.rows[0].cells, *t.rows[1].cells], ["Person", "Dauer", "P1", "2,4 s"]
):
    c.text = v
doc.add_picture(str(picture), width=Inches(2))
doc.add_page_break()
doc.add_heading("Aufgabe B / P2", 0)
doc.add_paragraph(quote)
doc.save(source / "repeat.docx")
p = Presentation()
s = p.slides.add_slide(p.slide_layouts[6])
b = s.shapes.add_textbox(SlideInches(1), SlideInches(1), SlideInches(7), SlideInches(1))
b.text = "Aufgabe D / P4"
b = s.shapes.add_textbox(SlideInches(2), SlideInches(2), SlideInches(6), SlideInches(1))
b.text = quote
b.rotation = 15
s.shapes.add_picture(str(picture), SlideInches(1), SlideInches(4), width=SlideInches(2))
p.save(source / "rotated.pptx")
app = application(root / "workspace")
w = app.state.workspace
renderer = office_renderer()
assert renderer, "LibreOffice missing"
odt = subprocess.run(
    [
        renderer,
        "-env:UserInstallation=" + (root / "fixture-profile").as_uri(),
        "--headless",
        "--convert-to",
        "odt",
        "--outdir",
        str(source),
        str(source / "repeat.docx"),
    ],
    capture_output=True,
    text=True,
    timeout=60,
)
assert odt.returncode == 0 and (source / "repeat.odt").is_file(), odt.stderr
w.import_paths(
    [
        str(source / "repeat.docx"),
        str(source / "repeat.odt"),
        str(source / "rotated.pptx"),
    ]
)
version_executable = (
    Path(renderer).with_suffix(".com") if sys.platform == "win32" else Path(renderer)
)
receipt = dict(
    renderer=subprocess.check_output(
        [str(version_executable), "--version"], text=True, timeout=15
    ).strip(),
    cases=[],
)
with TestClient(app) as client:
    for row in w.files()["items"]:
        before = w.artifact(row, "stored").read_bytes()
        start = time.monotonic()
        result = client.get(f"/document/{row['id']}/office-pdf")
        assert result.status_code == 200, result.text
        pdf = pdfium.PdfDocument(result.content)
        texts = [page.get_textpage().get_text_range() for page in pdf]
        assert sum(text.count(quote) for text in texts) == (
            2 if row["name"] in ("repeat.docx", "repeat.odt") else 1
        ), texts
        assert w.artifact(row, "stored").read_bytes() == before
        native = w.document(row)
        refs = [
            dict(ref=t.self_ref, prov=[v.model_dump(mode="json") for v in t.prov])
            for t in native.texts
            if t.text == quote
        ]
        receipt["cases"].append(
            dict(
                name=row["name"],
                status=row["status"],
                seconds=time.monotonic() - start,
                pages=len(pdf),
                texts=texts,
                refs=refs,
                headers={k: v for k, v in result.headers.items() if k.startswith("x-")},
                source_sha256=hashlib.sha256(before).hexdigest(),
                source_unchanged=True,
            )
        )
(root / "receipt.json").write_text(
    json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf8"
)
print(json.dumps(receipt, ensure_ascii=False, indent=2))
