#!/usr/bin/env python3
"""Offline metadata and layout checks for the RO eToll HACS repository."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "ro_etoll"
VERSION = "1.0.2"
NAME = "RO eToll"

def inspect_repository(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    def need(path: str) -> Path:
        f = root / path
        if not f.is_file():
            errors.append(f"Missing repository file: {path}")
        return f
    manifest_file = need("custom_components/ro_etoll/manifest.json")
    hacs_file = need("hacs.json")
    version_file = need("custom_components/ro_etoll/const.py")
    for path in ("README.md","LICENSE.txt","docs/licenta-originala-ro.md",".github/workflows/validate.yml",
                 "VALIDATION.md","HACS_PUBLISHING.md",
                 "custom_components/ro_etoll/__init__.py",
                 "custom_components/ro_etoll/brand/icon.png"):
        need(path)
    license_path = root / "LICENSE.txt"
    if license_path.is_file():
        license_text = license_path.read_text(encoding="utf-8")
        if not license_text.startswith("MIT License") or (
            "Permission is hereby granted, free of charge" not in license_text
            or "Copyright (c) 2024 [cnecrea]" not in license_text
        ):
            errors.append("Standard English MIT license text or original attribution missing")
    if manifest_file.is_file():
        try:
            m = json.loads(manifest_file.read_text(encoding="utf-8"))
            missing = {"domain","name","version","codeowners",
                       "documentation","issue_tracker"} - set(m)
            if missing:
                errors.append("Missing manifest keys: "+", ".join(sorted(missing)))
            if m.get("domain") != DOMAIN or m.get("name") != NAME:
                errors.append("Manifest domain or name incorrect")
            if m.get("version") != VERSION:
                errors.append("Manifest version incorrect")
            expected = ["domain","name"]+sorted(k for k in m if k not in ("domain","name"))
            if list(m) != expected:
                errors.append("Manifest keys should be domain, name, alphabetical")
            if not {"binary_sensor","sensor"}.issubset(set(m.get("dependencies", []))):
                errors.append("Missing sensor or binary_sensor dependency")
            if not m.get("codeowners"):
                errors.append("Manifest codeowners empty")
            if not re.fullmatch(r"\d+\.\d+\.\d+",str(m.get("version",""))):
                errors.append("Manifest version not semantic")
        except (ValueError, UnicodeError) as e:
            errors.append(f"Invalid manifest JSON: {e}")
    if version_file.is_file() and f'VERSION = "{VERSION}"' not in version_file.read_text(encoding="utf-8"):
        errors.append("VERSION constant differs from manifest")
    if hacs_file.is_file():
        try:
            j=json.loads(hacs_file.read_text(encoding="utf-8"))
            if j.get("name") != NAME or j.get("render_readme") is not True:
                errors.append("HACS name or render_readme incorrect")
        except (ValueError,UnicodeError) as e:
            errors.append(f"Invalid hacs.json: {e}")
    parent=root/"custom_components"
    if parent.is_dir():
        dirs=sorted(x.name for x in parent.iterdir() if x.is_dir())
        if dirs != [DOMAIN]:
            errors.append(f"Unexpected custom_components directories: {dirs}")
    return errors

if __name__=="__main__":
    issues=inspect_repository()
    for issue in issues:
        print("FAIL:",issue,file=sys.stderr)
    if issues:
        raise SystemExit(1)
    print("PASS: RO eToll HACS packaging checks")
