"""Offline frontend bundler using esbuild.exe with strict OSI-permissive license verification."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
OUTDIR = ROOT / "ux_maind" / "app" / "web" / "generated"
ESBUILD = FRONTEND / "node_modules" / "@esbuild" / "win32-x64" / "esbuild.exe"

ALLOWED_LICENSES = {
    "MIT",
    "ISC",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "0BSD",
    "(MIT OR Apache-2.0)",
    "MIT OR ISC",
}

PDFJS_PARTS = [
    "build/pdf.mjs",
    "build/pdf.worker.mjs",
    "web/pdf_viewer.mjs",
    "web/pdf_viewer.css",
    "web/images",
    "cmaps",
    "standard_fonts",
    "wasm",
]


def _esbuild_version() -> str:
    proc = subprocess.run(
        [str(ESBUILD), "--version"],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip() or "0.25.11"


def _iter_installed_packages(node_modules: Path) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    if not node_modules.exists():
        return found
    for child in sorted(node_modules.iterdir()):
        if child.name.startswith("."):
            continue
        if child.name.startswith("@") and child.is_dir():
            for scoped in sorted(child.iterdir()):
                if (scoped / "package.json").is_file():
                    found.append((f"{child.name}/{scoped.name}", scoped))
        elif child.is_dir() and (child / "package.json").is_file():
            found.append((child.name, child))
    return found


def main() -> int:
    if not ESBUILD.exists():
        print(f"Missing esbuild binary: {ESBUILD}", file=sys.stderr)
        return 1

    # Clean previous generated JS/CSS chunks and stale setuptools build/lib cache
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    if OUTDIR.exists():
        shutil.rmtree(OUTDIR)
    OUTDIR.mkdir(parents=True, exist_ok=True)

    meta_path = OUTDIR / ".esbuild-meta.json"
    cmd = [
        str(ESBUILD),
        "components.js",
        "src/main.jsx",
        f"--outdir={OUTDIR}",
        "--entry-names=[name]",
        "--bundle",
        "--format=esm",
        "--splitting",
        "--minify",
        "--legal-comments=eof",
        "--target=es2022",
        '--define:process.env.NODE_ENV="production"',
        f"--metafile={meta_path}",
    ]
    subprocess.run(cmd, cwd=FRONTEND, check=True)

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta_path.unlink(missing_ok=True)
    (OUTDIR / "build.json").write_text(
        json.dumps({"builder": f"esbuild {_esbuild_version()}", **meta}, indent=2),
        encoding="utf-8",
    )

    # Scan all packages referenced in metafile inputs + core direct dependencies
    bundled_pkgs: set[str] = {"pdfjs-dist"}
    for input_path in meta.get("inputs", {}):
        norm = input_path.replace("\\", "/")
        if "node_modules/" in norm:
            after = norm.split("node_modules/", 1)[1]
            parts = after.split("/")
            pkg_name = f"{parts[0]}/{parts[1]}" if parts[0].startswith("@") else parts[0]
            bundled_pkgs.add(pkg_name)

    notices = [
        "Locally built 100% open-source browser components; zero proprietary dependencies; zero runtime CDNs.\n"
    ]
    license_pattern = re.compile(r"^licen[cs]e(?:\.md|\.txt)?$", re.IGNORECASE)

    for pkg, pkg_root in _iter_installed_packages(FRONTEND / "node_modules"):
        if pkg not in bundled_pkgs:
            continue
        pkg_meta = json.loads((pkg_root / "package.json").read_text(encoding="utf-8"))
        spdx = str(pkg_meta.get("license") or "").strip()
        if spdx not in ALLOWED_LICENSES:
            raise RuntimeError(
                f"Disallowed or non-permissive license '{spdx}' in bundled package '{pkg}'"
            )
        license_file = next(
            (p for p in sorted(pkg_root.iterdir()) if p.is_file() and license_pattern.match(p.name)),
            None,
        )
        license_text = (
            license_file.read_text(encoding="utf-8", errors="replace")
            if license_file
            else "See package SPDX identifier above."
        )
        notices.append(f"\n{pkg} {pkg_meta.get('version', '')} ({spdx})\n{license_text}\n")

    (OUTDIR / "LICENSES.txt").write_text("".join(notices), encoding="utf-8")

    pdf_out = (OUTDIR / "pdfjs").resolve()
    if not str(pdf_out).startswith(str(OUTDIR.resolve()) + "\\") and not str(pdf_out).startswith(
        str(OUTDIR.resolve()) + "/"
    ):
        raise RuntimeError(f"Unsafe generated path: {pdf_out}")
    pdf_out.mkdir(parents=True, exist_ok=True)

    pdf_src = FRONTEND / "node_modules" / "pdfjs-dist"
    for part in PDFJS_PARTS:
        src = pdf_src / part
        dst = pdf_out / part
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    docs_out = OUTDIR / "docs"
    docs_out.mkdir(parents=True, exist_ok=True)
    for doc_name in ("USER_MANUAL.md", "SYSTEM_LIMITS.md"):
        doc_src = ROOT / "docs" / doc_name
        if doc_src.is_file():
            shutil.copy2(doc_src, docs_out / doc_name)

    for entry in sorted(OUTDIR.iterdir()):
        size = entry.stat().st_size if entry.is_file() else 0
        print(f"{entry.name} {size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
