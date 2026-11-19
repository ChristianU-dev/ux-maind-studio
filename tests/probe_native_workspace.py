"""Opt-in native format/OCR probe, no cloud calls; generated sources only.
Run with the locked runtime: python tests/probe_native_workspace.py --output artifacts/r13-format-check
OCR/layout weights must already be available locally or explicitly downloaded.
"""

import sys, json, time, hashlib, shutil, argparse, logging
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path.cwd()))
from ux_maind.app.workspace import Workspace
from PIL import Image, ImageDraw
from docx import Document
from docx.shared import Inches
from pptx import Presentation
from openpyxl import Workbook

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
root = parser.parse_args().output
root.mkdir(parents=True, exist_ok=True)
source = root / "input"
source.mkdir(exist_ok=True)
ocr_logger = logging.getLogger("docling.models.stages.ocr.auto_ocr_model")
ocr_logger.setLevel(logging.INFO)
ocr_logger.addHandler(logging.FileHandler(root / "ocr-engine.log", encoding="utf8"))
image = Image.new("RGB", (1000, 450), "white")
d = ImageDraw.Draw(image)
d.rectangle((70, 110, 930, 340), outline="#087f70", width=6)
d.text((150, 175), "SAVE ADDRESS", fill="black", font_size=65)
image.save(source / "button.png")
image.save(source / "button.jpg")
image.save(source / "scan.pdf", "PDF", resolution=144)
doc = Document()
doc.add_heading("Task B / Participant P2", 0)
doc.add_paragraph("Where do I change the delivery address?")
doc.add_paragraph("I do not change the delivery address here.")
doc.add_picture(str(source / "button.png"), width=Inches(5))
t = doc.add_table(rows=2, cols=2)
t.cell(0, 0).text = "Participant"
t.cell(0, 1).text = "Time"
t.cell(1, 0).text = "P2"
t.cell(1, 1).text = "12 ms"
doc.save(source / "notes.docx")
p = Presentation()
for n in [1, 2]:
    s = p.slides.add_slide(p.slide_layouts[6])
    s.shapes.add_textbox(
        Inches(1), Inches(0.5), Inches(8), Inches(2)
    ).text = f"Task {n} / Participant P{n}\nPage {n} has its own source."
    s.shapes.add_picture(
        str(source / "button.png"), Inches(1), Inches(3), width=Inches(5)
    )
p.save(source / "slides.pptx")
with ZipFile(source / "answer.odt", "w") as z:
    z.writestr("mimetype", "application/vnd.oasis.opendocument.text")
    z.writestr("Pictures/button.png", (source / "button.png").read_bytes())
    z.writestr(
        "META-INF/manifest.xml",
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"><manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/><manifest:file-entry manifest:full-path="Pictures/button.png" manifest:media-type="image/png"/></manifest:manifest>',
    )
    z.writestr(
        "content.xml",
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" office:version="1.2"><office:body><office:text><text:h text:outline-level="1">Task B / Participant P2</text:h><text:p>I change the delivery address in the account.</text:p><text:p><draw:frame draw:name="UI" svg:width="14cm" svg:height="6cm"><draw:image xlink:href="Pictures/button.png" xlink:type="simple"/></draw:frame></text:p></office:text></office:body></office:document-content>',
    )
w = Workbook()
s = w.active
s["A1"] = "Participant"
s["B1"] = "Time"
s.merge_cells("A2:D5")
s["A2"] = "Merged edge"
s.cell(1000, 1000, "17 ms")
w.save(source / "sparse.xlsx")
(source / "measure.csv").write_text("participant,time\nP2,12 ms\n", encoding="utf8")
(source / "unknown.xyz").write_text("Original available, unsupported", encoding="utf8")
(source / "literal.txt").write_text(
    "<script>not executable</script>\nTask A / Participant P1\nThe button did not respond.\nThe button did not respond.\nTask B / Participant P2\n12 ms.",
    encoding="utf8",
)
objects = [
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>",
]
for page in [1, 2]:
    content = f"BT /F1 24 Tf 50 700 Td (Page {page}: Task {page} / Participant P{page}) Tj 0 -50 Td (The button did not respond.) Tj ET".encode()
    objects.append(
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 7 0 R >> >> /Contents {4 if page == 1 else 6} 0 R >>".encode()
    )
    objects.append(
        b"<< /Length "
        + str(len(content)).encode()
        + b" >>\nstream\n"
        + content
        + b"\nendstream"
    )
objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
pdf = b"%PDF-1.4\n"
positions = [0]
for i, obj in enumerate(objects, 1):
    positions.append(len(pdf))
    pdf += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
xref = len(pdf)
pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode() + b"".join(
    f"{x:010d} 00000 n \n".encode() for x in positions[1:]
)
pdf += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
(source / "pages.pdf").write_bytes(pdf)
workspace = Workspace(root / "workspace")
events = []


def event(e):
    events.append(e)
    (root / "conversion-events.json").write_text(
        json.dumps(events, indent=2, default=str), encoding="utf8"
    )
    print(json.dumps(e, default=str), flush=True)


start = time.monotonic()
workspace.import_paths([str(source.resolve())], progress=event)
receipt = []
for row in workspace.files()["items"]:
    r = {k: row[k] for k in ["id", "name", "status", "error"]}
    r["original_unchanged"] = (
        hashlib.sha256(Path(row["origin"]).read_bytes()).digest()
        == hashlib.sha256(workspace.artifact(row, "stored").read_bytes()).digest()
    )
    if row["native"]:
        doc = workspace.document(row)
        r.update(
            texts=len(doc.texts),
            pictures=len(doc.pictures),
            tables=len(doc.tables),
            pages=len(doc.pages),
            text=" | ".join(t.text for t in doc.texts),
            diagnostics=json.loads(row["diagnostics"]),
        )
    receipt.append(r)
assert len(receipt) == 11
assert all(r["original_unchanged"] for r in receipt)
assert all(r["status"] == "success" for r in receipt if r["name"] != "unknown.xyz")
assert all(
    "SAVE ADDRESS" in r["text"]
    for r in receipt
    if r["name"] in ("button.png", "button.jpg", "scan.pdf")
)
assert any(isinstance(e, dict) and e.get("phase") == "build" for e in events)
(root / "conversion.json").write_text(
    json.dumps(
        dict(seconds=time.monotonic() - start, documents=receipt),
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf8",
)
print("CONVERSION COMPLETE", flush=True)
