from __future__ import annotations

import argparse
import json
import platform
import re
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


TOOL_PROBES = {
    "xtb": (["xtb", "--version"], r"(?im)\b(?:xtb\s+)?version\s*[:=]?\s*(\d+\.\d+(?:\.\d+)?(?:[-+][\w.]+)?)"),
    "lmp": (["lmp", "-help"], r"Large-scale Atomic/Molecular Massively Parallel Simulator\s*-\s*([^\r\n]+)"),
}


def probe_tool(command: str) -> dict:
    argv, pattern = TOOL_PROBES[command]
    report = {"command": argv, "status": "error", "version": None, "returncode": None}
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL
        )
    except FileNotFoundError as exc:
        return {**report, "status": "missing", "error": str(exc)}
    except subprocess.TimeoutExpired:
        return {**report, "status": "timeout", "error": "Probe exceeded 10 seconds"}
    except OSError as exc:
        return {**report, "error": f"{type(exc).__name__}: {exc}"}

    report["returncode"] = result.returncode
    output = result.stdout + "\n" + result.stderr
    if result.returncode != 0:
        report["error"] = "Probe exited unsuccessfully"
    else:
        match = re.search(pattern, output)
        if match:
            report.update(status="ok", version=match.group(1).strip())
            return report
        report["error"] = "Probe succeeded but version was not recognized"
    report["stdout"] = result.stdout[:4000]
    report["stderr"] = result.stderr[:4000]
    return report


def audit():
    RESULTS.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    manifest = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "source_doi": cfg["source_paper"]["doi"],
        "mode": cfg["project"]["mode"],
        "tools": {tool: probe_tool(tool) for tool in TOOL_PROBES},
        "scope_warning": "Environment audit only; this command does not reproduce scientific results.",
    }
    manifest["schema_version"] = 2
    manifest["status"] = (
        "ok" if all(tool["status"] == "ok" for tool in manifest["tools"].values()) else "error"
    )
    (RESULTS / "software_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (RESULTS / "config_snapshot.json").write_text(
        json.dumps(cfg, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    print(f"\nWrote audit files to: {RESULTS}")
    return 0 if manifest["status"] == "ok" else 1


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
    parser.add_argument('--preflight', action='store_true', help='Validate QM inputs without running engines')
    args = parser.parse_args()
    stage = args.stage
    if args.preflight and stage != 'qm':
        parser.error('--preflight is only supported for qm')
    if stage == "audit":
        raise SystemExit(audit())
    elif stage == "test":
        import pytest
        raise SystemExit(pytest.main(["-q", str(ROOT / "tests")]))
    elif stage == 'qm' and args.preflight:
        from .qm import run_preflight
        raise SystemExit(run_preflight())
    else:
        raise SystemExit(
            f"Stage '{stage}' is scaffolded but not implemented. "
            "See docs/REPRODUCTION_SPEC.md; no completed calculation is implied."
        )


if __name__ == "__main__":
    main()
