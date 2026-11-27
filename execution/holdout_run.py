#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Runs hidden acceptance tests written in pytest, Vitest or both, and writes one result file
in Jest's JSON format, which is what the factory driver reads.

Run it from the root of the target checkout:

  holdout_run.py --dir holdout --out /tmp/holdout.json

Files named test_*.py or *_test.py under --dir go to `uv run pytest`; files ending in .test.ts
go to `pnpm exec vitest run`. A kind with no files is skipped. From a pytest failure only the
exception message is passed on, never the traceback, because the traceback shows test source.

Exit code 0 when every test passed, 1 otherwise, 2 when nothing could be run.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def run(cmd: list[str], timeout: int) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
        return p.returncode, p.stdout
    except subprocess.TimeoutExpired as e:
        return 124, f"{e.stdout or ''}\ntimed out after {timeout} s"


def pytest_results(test_dir: Path, tmp: Path, timeout: int) -> tuple[list[dict], str]:
    xml = tmp / "pytest.xml"
    rc, out = run(["uv", "run", "pytest", str(test_dir), "-q", "-p", "no:cacheprovider", f"--junitxml={xml}",
                   "-o", "junit_family=xunit2", "-o", "junit_logging=no"], timeout)
    if not xml.exists():
        return [{"name": "pytest", "status": "failed", "message": f"pytest produced no result (exit {rc}): {out.strip().splitlines()[-1] if out.strip() else ''}",
                 "assertionResults": []}], out
    files: dict[str, dict] = {}
    for case in ET.parse(xml).getroot().iter("testcase"):
        f = files.setdefault(case.get("classname", "?"), {"name": case.get("classname", "?"), "status": "passed", "message": "", "assertionResults": []})
        bad = case.find("failure") if case.find("failure") is not None else case.find("error")
        if case.find("skipped") is not None:
            f["assertionResults"].append({"fullName": case.get("name", "?"), "status": "pending", "failureMessages": []})
        elif bad is not None:
            f["status"] = "failed"
            f["assertionResults"].append({"fullName": case.get("name", "?"), "status": "failed",
                                          "failureMessages": [(bad.get("message") or "failed").strip()]})
        else:
            f["assertionResults"].append({"fullName": case.get("name", "?"), "status": "passed", "failureMessages": []})
    return list(files.values()), out


def vitest_results(test_dir: Path, tmp: Path, timeout: int) -> tuple[list[dict], str]:
    js = tmp / "vitest.json"
    rc, out = run(["pnpm", "exec", "vitest", "run", str(test_dir), "--reporter=json", f"--outputFile={js}"], timeout)
    if not js.exists():
        return [{"name": "vitest", "status": "failed", "message": f"vitest produced no result (exit {rc}): {out.strip().splitlines()[-1] if out.strip() else ''}",
                 "assertionResults": []}], out
    return json.loads(js.read_text()).get("testResults", []), out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="directory with the tests, relative to the current directory")
    ap.add_argument("--out", required=True, help="result file to write, Jest JSON format")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per test runner (default 900)")
    a = ap.parse_args()
    d = Path(a.dir)
    py = [p for p in d.rglob("*.py") if p.name.startswith("test_") or p.name.endswith("_test.py")] if d.exists() else []
    ts = list(d.rglob("*.test.ts")) if d.exists() else []
    if not py and not ts:
        print(f"no test files under {d}")
        return 2
    results: list[dict] = []
    with tempfile.TemporaryDirectory() as t:
        for found, fn in ((py, pytest_results), (ts, vitest_results)):
            if found:
                res, out = fn(d, Path(t), a.timeout)
                results += res
                print(out[-6000:])
    tests = [x for r in results for x in r.get("assertionResults", [])]
    passed = sum(x["status"] == "passed" for x in tests)
    failed = sum(x["status"] == "failed" for x in tests) + sum(1 for r in results if r.get("status") == "failed" and not r.get("assertionResults"))
    Path(a.out).write_text(json.dumps({"numTotalTests": len(tests), "numPassedTests": passed, "numFailedTests": failed,
                                       "success": failed == 0 and passed > 0, "testResults": results}, indent=1))
    print(f"{passed} of {len(tests)} tests passed, {failed} failed ({len(py)} pytest files, {len(ts)} vitest files)")
    return 0 if failed == 0 and passed > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
