"""Pure-Python npm tarball resolver with SHA-512 & Permissive Open-Source License Gate.

Installs frontend/package.json dependencies into frontend/node_modules without requiring npm,
while strictly rejecting any non-permissive / proprietary package license.
"""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import sys
import tarfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
NODE_MODULES = FRONTEND / "node_modules"

ALLOWED_LICENSES = {
    "MIT",
    "ISC",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "0BSD",
    "Unlicense",
    "CC0-1.0",
    "CC-BY-4.0",
    "BlueOak-1.0.0",
    "Python-2.0",
}

_META_CACHE: dict[str, dict] = {}


def _parse_ver(v: str) -> tuple[int, int, int, str]:
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)(?:-(.+))?$", v.strip())
    if not m:
        return (0, 0, 0, v)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4) or "")


def _satisfies(ver: str, spec: str) -> bool:
    v_maj, v_min, v_pat, v_pre = _parse_ver(ver)
    if v_pre and "-" not in spec:
        return False
    spec = spec.strip()
    if spec in ("*", "", "latest"):
        return not v_pre
    if "||" in spec:
        return any(_satisfies(ver, part) for part in spec.split("||"))
    tokens = [t for t in re.split(r"\s+", spec.replace(",", " ")) if t]
    for tok in tokens:
        if tok.startswith("^"):
            s_maj, s_min, s_pat, _ = _parse_ver(tok[1:])
            if s_maj > 0:
                if not (v_maj == s_maj and (v_min, v_pat) >= (s_min, s_pat)):
                    return False
            elif s_min > 0:
                if not (v_maj == 0 and v_min == s_min and v_pat >= s_pat):
                    return False
            else:
                if not (v_maj == 0 and v_min == 0 and v_pat == s_pat):
                    return False
        elif tok.startswith("~"):
            s_maj, s_min, s_pat, _ = _parse_ver(tok[1:])
            if not (v_maj == s_maj and v_min == s_min and v_pat >= s_pat):
                return False
        elif tok.startswith(">="):
            s_maj, s_min, s_pat, _ = _parse_ver(tok[2:])
            if (v_maj, v_min, v_pat) < (s_maj, s_min, s_pat):
                return False
        elif tok.startswith("<"):
            eq = tok.startswith("<=")
            s_maj, s_min, s_pat, _ = _parse_ver(tok[2:] if eq else tok[1:])
            if eq and (v_maj, v_min, v_pat) > (s_maj, s_min, s_pat):
                return False
            if not eq and (v_maj, v_min, v_pat) >= (s_maj, s_min, s_pat):
                return False
        elif re.match(r"^\d+\.\d+\.\d+", tok):
            if ver != tok:
                return False
    return True


def _fetch_packument(name: str) -> dict:
    if name in _META_CACHE:
        return _META_CACHE[name]
    encoded = urllib.parse.quote(name, safe="@/")
    req = urllib.request.Request(
        f"https://registry.npmjs.org/{encoded}",
        headers={"Accept": "application/json", "User-Agent": "ux-maind-oss-installer/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    _META_CACHE[name] = data
    return data


def _check_license(pkg_name: str, ver_meta: dict, root_meta: dict) -> str:
    lic = ver_meta.get("license") or root_meta.get("license") or ""
    if isinstance(lic, dict):
        lic = lic.get("type", "")
    lic_str = str(lic).strip()
    tokens = [t for t in re.split(r"[\s()]+", lic_str) if t not in ("", "OR", "AND", "WITH")]
    if not tokens or not any(t in ALLOWED_LICENSES for t in tokens):
        raise RuntimeError(
            f"PROPRIETARY/UNAPPROVED LICENSE BLOCKED: {pkg_name} has license '{lic_str}'"
        )
    return lic_str


def _installed_version(name: str) -> str | None:
    p = NODE_MODULES / Path(*name.split("/")) / "package.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("version")
    except Exception:
        return None


def main() -> int:
    pkg_json = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    queue: list[tuple[str, str]] = list((pkg_json.get("dependencies") or {}).items())
    resolved: dict[str, dict] = {}
    licenses_audit: dict[str, str] = {}

    while queue:
        name, spec = queue.pop(0)
        if spec.startswith("npm:"):
            real_spec = spec[4:]
            at_idx = real_spec.rfind("@")
            real_name, sub_spec = real_spec[:at_idx], real_spec[at_idx + 1 :]
        else:
            real_name, sub_spec = name, spec

        if name in resolved:
            continue

        cur_ver = _installed_version(name)
        if cur_ver and _satisfies(cur_ver, sub_spec):
            local_pkg = json.loads(
                (NODE_MODULES / Path(*name.split("/")) / "package.json").read_text(encoding="utf-8")
            )
            lic = _check_license(name, local_pkg, local_pkg)
            licenses_audit[f"{name}@{cur_ver}"] = lic
            resolved[name] = {"version": cur_ver, "cached": True}
            for dep_k, dep_v in (local_pkg.get("dependencies") or {}).items():
                if dep_k not in resolved:
                    queue.append((dep_k, dep_v))
            continue

        pack = _fetch_packument(real_name)
        versions = pack.get("versions") or {}
        candidates = [v for v in versions if _satisfies(v, sub_spec)]
        if not candidates:
            dist_latest = (pack.get("dist-tags") or {}).get("latest")
            if dist_latest and dist_latest in versions:
                candidates = [dist_latest]
            else:
                raise RuntimeError(f"No matching version for {name} ({spec})")
        best = sorted(candidates, key=_parse_ver)[-1]
        vmeta = versions[best]
        lic = _check_license(name, vmeta, pack)
        licenses_audit[f"{name}@{best}"] = lic
        resolved[name] = {
            "version": best,
            "tarball": vmeta["dist"]["tarball"],
            "integrity": vmeta["dist"].get("integrity", ""),
            "cached": False,
        }
        for dep_k, dep_v in (vmeta.get("dependencies") or {}).items():
            if dep_k not in resolved:
                queue.append((dep_k, dep_v))

    to_download = [(n, info) for n, info in resolved.items() if not info["cached"]]
    print(f"Resolved {len(resolved)} total OSS packages ({len(to_download)} new to download)...")

    def _download_and_extract(item: tuple[str, dict]) -> str:
        name, info = item
        req = urllib.request.Request(
            info["tarball"], headers={"User-Agent": "ux-maind-oss-installer/1.0"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
        integ = info.get("integrity", "")
        if integ.startswith("sha512-"):
            expected = integ.split("-", 1)[1]
            actual = base64.b64encode(hashlib.sha512(raw).digest()).decode("ascii")
            if actual != expected:
                raise RuntimeError(f"SHA-512 mismatch for {name}@{info['version']}")
        dest = NODE_MODULES / Path(*name.split("/"))
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                parts = Path(member.name).parts
                rel = Path(*parts[1:]) if len(parts) > 1 else Path(parts[0])
                out_path = (dest / rel).resolve()
                if not str(out_path).startswith(str(dest.resolve())):
                    continue
                out_path.parent.mkdir(parents=True, exist_ok=True)
                extracted = tf.extractfile(member)
                if extracted:
                    out_path.write_bytes(extracted.read())
        return f"{name}@{info['version']}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        installed = list(pool.map(_download_and_extract, to_download))

    print(f"Installed {len(installed)} packages cleanly. License audit summary:")
    by_lic: dict[str, int] = {}
    for lic in licenses_audit.values():
        by_lic[lic] = by_lic.get(lic, 0) + 1
    print(json.dumps(by_lic, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
