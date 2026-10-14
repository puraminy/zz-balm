from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "paper.yaml"
RESULTS = ROOT / "results"


def load_config():
    with CONFIG.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def version_of(command: str) -> str:
    try:
        result = subprocess.run(
            [command, "--version"], capture_output=True, text=True, timeout=10
        )
        lines = (result.stdout or result.stderr).strip().splitlines()
        return lines[0][:300] if lines else f"exit_code={result.returncode}"
    except Exception as exc:
        return f"unavailable: {type(exc).__name__}: {exc}"


def audit():
    RESULTS.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    manifest = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "source_doi": cfg["source_paper"]["doi"],
        "mode": cfg["project"]["mode"],
        "tools": {"xtb": version_of("xtb"), "lmp": version_of("lmp")},
        "scope_warning": "Environment audit only; this command does not reproduce scientific results.",
    }
    (RESULTS / "software_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (RESULTS / "config_snapshot.json").write_text(
        json.dumps(cfg, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    print(f"\nWrote audit files to: {RESULTS}")


def main():
    parser = argparse.ArgumentParser(
        description="Headless workflow for the lemon-balm corrosion-inhibitor paper."
    )
    parser.add_argument(
        "stage",
        choices=["audit", "test", "qm", "surface", "md", "analysis", "all"],
        nargs="?",
        default="audit",
    )
    stage = parser.parse_args().stage
    if stage == "audit":
        audit()
    elif stage == "test":
        import pytest
        raise SystemExit(pytest.main(["-q", str(ROOT / "tests")]))
    else:
        raise SystemExit(
            f"Stage '{stage}' is scaffolded but not implemented. "
            "See docs/REPRODUCTION_SPEC.md; no completed calculation is implied."
        )


if __name__ == "__main__":
    main()
