"""Automated SPDX / OSI Open-Source License Audit for UX-mAInd (Python + Frontend + Optional Tools).

Verifies that zero proprietary software packages are required or bundled by UX-mAInd.
"""

from __future__ import annotations

from importlib.metadata import distributions
import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parent.parent

# OSI-approved / standard permissive & weak-copyleft open-source license markers
APPROVED_OPEN_SOURCE_MARKERS = (
    "mit",
    "apache",
    "bsd",
    "isc",
    "mpl",
    "mozilla public license",
    "lgpl",
    "lesser general public license",
    "python software foundation",
    "psf",
    "cc0",
    "cc-by",
    "unlicense",
    "artistic",
    "zlib",
    "0bsd",
    "public domain",
    "hpnd",
    "CMU",
    "boost",
)

PROPRIETARY_MARKERS = (
    "proprietary",
    "commercial",
    "all rights reserved",
    "closed source",
    "non-commercial",
    "busl",
    "bsl-1.1",
    "sspl",
)


def _extract_dist_license(dist) -> str:
    meta = dist.metadata
    lic_expr = (meta.get("License-Expression") or "").strip()
    if lic_expr:
        return lic_expr
    classifiers = [
        c.split("::")[-1].strip()
        for c in (meta.get_all("Classifier") or [])
        if c.startswith("License ::")
    ]
    if classifiers:
        return " | ".join(classifiers)
    raw_lic = (meta.get("License") or "").strip()
    if raw_lic:
        first_line = next((ln.strip() for ln in raw_lic.splitlines() if ln.strip()), "")
        return first_line[:120]
    return "UNKNOWN"


def _is_approved_oss(lic_text: str) -> bool:
    low = lic_text.lower()
    if any(p in low for p in PROPRIETARY_MARKERS) and not any(
        ok in low for ok in ("mit", "apache", "bsd", "mpl", "lgpl")
    ):
        return False
    return any(ok.lower() in low for ok in APPROVED_OPEN_SOURCE_MARKERS)


def run_audit() -> dict:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    direct_py_specs = pyproject.get("project", {}).get("dependencies", [])
    direct_py_names = {
        spec.split(">=")[0].split("==")[0].split("<")[0].split("[")[0].strip().lower().replace("_", "-")
        for spec in direct_py_specs
    }

    installed_by_name = {}
    for d in distributions():
        name = (d.metadata.get("Name") or "").strip()
        if not name:
            continue
        norm = name.lower().replace("_", "-")
        installed_by_name[norm] = dict(
            name=name,
            version=d.version,
            license=_extract_dist_license(d),
        )

    direct_python = []
    violations = []
    for req_name in sorted(direct_py_names):
        info = installed_by_name.get(req_name)
        if not info:
            violations.append(f"Missing installed metadata for {req_name}")
            continue
        ok = _is_approved_oss(info["license"])
        entry = {**info, "osi_approved": ok}
        direct_python.append(entry)
        if not ok:
            violations.append(f"Non-approved Python license: {info['name']} -> {info['license']}")

    pkg_json = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    pkg_lock_path = ROOT / "frontend" / "package-lock.json"
    pkg_lock_pkgs = (
        json.loads(pkg_lock_path.read_text(encoding="utf-8")).get("packages") or {}
        if pkg_lock_path.is_file()
        else {}
    )
    js_deps = {
        **(pkg_json.get("dependencies") or {}),
        **(pkg_json.get("devDependencies") or {}),
    }
    frontend_packages = []
    for pkg_name in sorted(js_deps):
        p_meta_path = ROOT / "frontend" / "node_modules" / pkg_name / "package.json"
        if p_meta_path.is_file():
            p_meta = json.loads(p_meta_path.read_text(encoding="utf-8"))
        elif f"node_modules/{pkg_name}" in pkg_lock_pkgs:
            p_meta = pkg_lock_pkgs[f"node_modules/{pkg_name}"]
        else:
            violations.append(f"Missing frontend metadata for {pkg_name}")
            continue
        lic = str(p_meta.get("license") or "UNKNOWN")
        ok = _is_approved_oss(lic)
        entry = dict(name=pkg_name, version=p_meta.get("version"), license=lic, osi_approved=ok)
        frontend_packages.append(entry)
        if not ok:
            violations.append(f"Non-approved JS license: {pkg_name} -> {lic}")

    optional_external = [
        dict(
            name="LibreOffice (headless soffice)",
            purpose="Local .docx/.pptx/.odt display PDF rendering (optional; never required for core Docling parsing)",
            license="MPL-2.0",
            osi_approved=True,
        ),
        dict(
            name="Ollama",
            purpose="100% local on-premise open-weights LLM/VLM inference (optional)",
            license="MIT",
            osi_approved=True,
        ),
    ]

    report = dict(
        project="ux-maind",
        project_license=pyproject.get("project", {}).get("license", {}),
        zero_proprietary_dependencies=len(violations) == 0,
        violations=violations,
        direct_python_dependencies=direct_python,
        frontend_dependencies=frontend_packages,
        optional_system_tools=optional_external,
    )
    if (ROOT / "artifacts").is_dir():
        out_dir = ROOT / "artifacts" / "r29-evaluation"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "open_source_license_audit.json"
        out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    res = run_audit()
    print(
        f"Open-Source Audit: zero_proprietary={res['zero_proprietary_dependencies']} "
        f"| Python={len(res['direct_python_dependencies'])} "
        f"| Frontend={len(res['frontend_dependencies'])} "
        f"| Violations={len(res['violations'])}"
    )
    if res["violations"]:
        for v in res["violations"]:
            print("VIOLATION:", v, file=sys.stderr)
        sys.exit(1)
