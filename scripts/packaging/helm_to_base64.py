#!/usr/bin/env python3
"""Zip infra/kubernetes/helm for Bastion clipboard transfer (chart + values files)."""
from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELM_DIR = ROOT / "infra" / "kubernetes" / "helm"
OUT = ROOT / "helm_base64_latest.txt"


def main() -> int:
    if not HELM_DIR.is_dir():
        raise SystemExit(f"Helm dir not found: {HELM_DIR}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(HELM_DIR.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(HELM_DIR.parent).as_posix())

    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    OUT.write_text(encoded, encoding="utf-8")
    print(f"Wrote {OUT} ({len(encoded)} chars)")
    print()
    print("=== LAPTOP: copy helm_base64_latest.txt to Jump VM clipboard ===")
    print()
    print("=== VM (PowerShell) ===")
    print(r'  $b = Get-Content -Raw helm_base64.txt')
    print(r'  [IO.File]::WriteAllBytes("helm.zip", [Convert]::FromBase64String($b.Trim()))')
    print(r'  Expand-Archive -Force helm.zip -DestinationPath .')
    print()
    print("=== VM: deploy Non-Prod (use values-nonprod.yaml, NOT values-staging.yaml) ===")
    print(r'  .\helm upgrade --install quanthire-nonprod .\kubernetes\helm\quanthire `')
    print(r'    -f .\kubernetes\helm\quanthire\values-nonprod.yaml `')
    print(r'    -n quanthire-nonprod --create-namespace')
    print()
    print("Dry-run first:")
    print(r'  .\helm upgrade --install quanthire-nonprod .\kubernetes\helm\quanthire `')
    print(r'    -f .\kubernetes\helm\quanthire\values-nonprod.yaml `')
    print(r'    -n quanthire-nonprod --create-namespace --dry-run --debug')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
