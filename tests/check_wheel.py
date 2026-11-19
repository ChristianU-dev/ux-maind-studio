"""Verify built assets and prevent stale deleted modules from reappearing in a wheel."""

from pathlib import Path
from zipfile import ZipFile
import sys

wheel = next(Path(sys.argv[1]).glob("*.whl"))
expected = {
    p.as_posix()
    for p in Path("ux_maind/app").rglob("*")
    if p.is_file() and "__pycache__" not in p.parts
}
with ZipFile(wheel) as z:
    actual = {n for n in z.namelist() if n.startswith("ux_maind/app/")}
    assert actual == expected, dict(
        unexpected=sorted(actual - expected), missing=sorted(expected - actual)
    )
    for name in actual:
        assert z.read(name) == Path(name).read_bytes(), "Stale build content: " + name
    for name in ["components.js", "main.js", "main.css", "LICENSES.txt", "build.json"]:
        assert len(z.read("ux_maind/app/web/generated/" + name)) > 0
print(
    "PASS: wheel contains exactly the active product files and locally built licensed assets"
)
