#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Software factory driver: takes one GitHub issue from intake to production.

Steps: intake, workspace, spec, holdout, implement, then up to three rounds of
gates + review with at most two fix rounds in between, then ship (PR, merge),
deploy, production check, rollback on failure, and a report.

The implementer (Claude Code) never sees the holdout tests the verifier (Pi) wrote.
Every error becomes a lesson in lessons/ that later runs get in their prompts.

Examples:
  factory run fighter --issue 1
  factory run fighter --issue 1 --until holdout     stop after a step
  factory run fighter --resume fighter-1-20261126-1700
  factory queue aiventure3d 1 2 3                   several issues in order, unattended
  factory status
  factory lessons --target fighter
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = Path(os.environ.get("VAMPIRE_STATE", Path.home() / ".local/share/vampire")).resolve()
STEPS = ["intake", "workspace", "spec", "holdout", "implement", "verify", "ship", "deploy", "report"]
MAX_FIX_ROUNDS = 2
# Text Claude Code prints when the subscription or the API has no capacity left for now.
LIMIT = re.compile(r"usage limit|hit your limit|limit reached|limit will reset|rate.?limit|overloaded|out of extra usage|\b529\b", re.I)
LIMIT_WAIT, LIMIT_TRIES = 1200, 90   # check every 20 minutes for up to 30 hours


class Stop(Exception):
    """The run cannot continue without a person."""


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def say(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def sh(cmd: str | list[str], cwd: Path | None = None, timeout: int = 900, check: bool = False,
       log: Path | None = None, stdin: str | None = None) -> tuple[int, str]:
    """Runs a command with stdin closed unless given. Returns (exit code, combined output)."""
    args = cmd if isinstance(cmd, list) else ["bash", "-c", cmd]
    try:
        p = subprocess.run(args, cwd=cwd, timeout=timeout, text=True, input=stdin,
                           stdin=None if stdin is not None else subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        rc, out = p.returncode, p.stdout
    except subprocess.TimeoutExpired as e:
        rc, out = 124, f"{e.stdout or ''}\ntimed out after {timeout} s"
    if log:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(f"$ {cmd}\n(exit {rc})\n{out}")
    if check and rc != 0:
        raise RuntimeError(f"command failed ({rc}): {cmd}\n{tail(out, 30)}")
    return rc, out


def tail(text: str, lines: int = 40) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


# ---------------------------------------------------------------- run state

class Run:
    def __init__(self, run_id: str, target: str):
        self.id = run_id
        self.target_name = target
        self.cfg = tomllib.loads((ROOT / "targets" / f"{target}.toml").read_text())
        self.dir = STATE / "runs" / run_id          # logs and state, readable by all agents
        self.hidden = STATE / "hidden" / run_id     # holdout tests and the verifier workspace
        self.impl = STATE / "work" / run_id / "impl"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.hidden.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "state.json"
        self.s = json.loads(self.path.read_text()) if self.path.exists() else {
            "run": run_id, "target": target, "status": "running", "started": now(),
            "steps": {}, "events": [], "cost": {"claude": 0.0, "pi": 0.0},
            "human_touches": {"intake": 1, "escalations": 0}, "lessons": [],
        }

    @property
    def repo(self) -> Path:
        return Path(self.cfg["path"]).expanduser().resolve()

    @property
    def holdout_ws(self) -> Path:
        return self.hidden / "ws"

    @property
    def holdout_tests(self) -> Path:
        return self.hidden / "tests"

    def save(self) -> None:
        self.path.write_text(json.dumps(self.s, indent=1))

    def step(self, name: str, fn):
        """Runs fn once; a finished step is skipped on resume and its data returned."""
        done = self.s["steps"].get(name)
        if done and done["status"] == "ok":
            return done["data"]
        say(f"step {name}")
        t = time.time()
        try:
            data = fn()
        except Exception as e:
            self.s["steps"][name] = {"status": "failed", "seconds": round(time.time() - t), "error": str(e)[:2000]}
            self.save()
            raise
        self.s["steps"][name] = {"status": "ok", "seconds": round(time.time() - t), "data": data}
        self.save()
        return data

    def data(self, name: str):
        return self.s["steps"][name]["data"]

    def log(self, name: str) -> Path:
        return self.dir / "logs" / name

    @contextlib.contextmanager
    def hidden_locked(self):
        """While the implementer runs, the holdout directory cannot be entered."""
        os.chmod(self.hidden, 0o000)
        try:
            yield
        finally:
            os.chmod(self.hidden, 0o700)


# ---------------------------------------------------------------- agents

def render(name: str, **values: str) -> str:
    text = (ROOT / "prompts" / f"{name}.md").read_text()
    values.setdefault("notes", "(none)")
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{(\w+)\}\}", text)
    if left:
        raise RuntimeError(f"prompt {name}: no value for {left}")
    return text


def claude(run: Run, label: str, prompt: str, cwd: Path, tools: list[str], schema: dict | None = None,
           resume: str | None = None, model: str | None = None, timeout: int = 5400) -> dict:
    """Headless Claude Code. Returns {text, structured, session}."""
    cmd = ["claude", "-p", "--output-format", "json", "--permission-mode", "acceptEdits",
           "--settings", json.dumps({"permissions": {"deny": [f"Read(//{str(STATE / 'hidden').lstrip('/')}/**)"]}})]
    if tools:
        cmd += ["--allowedTools", *tools]
    if schema:
        cmd += ["--json-schema", json.dumps(schema)]
    if resume:
        cmd += ["--resume", resume]
    if model:
        cmd += ["--model", model]
    (run.log(f"{label}.prompt.md")).parent.mkdir(parents=True, exist_ok=True)
    run.log(f"{label}.prompt.md").write_text(prompt)
    for attempt in range(LIMIT_TRIES + 1):
        rc, out = sh(cmd, cwd=cwd, timeout=timeout, stdin=prompt)
        run.log(f"{label}.out.json").write_text(out)
        try:
            d = json.loads(out[out.index("{"):])
        except ValueError:
            d = None
        failed = d is None or rc != 0 or d.get("is_error")
        said = str(d.get("result")) if d else tail(out, 10)
        if not (failed and LIMIT.search(said[:2000]) and attempt < LIMIT_TRIES):
            break
        # Out of capacity: wait and go on, in the same session when there is one, so finished work is kept.
        say(f"claude {label}: no capacity ({' '.join(said.split())[:120]}); waiting {LIMIT_WAIT // 60} min (attempt {attempt + 1})")
        run.s["events"].append({"at": now(), "agent": "claude", "label": label, "waited_for_limit": LIMIT_WAIT})
        run.save()
        time.sleep(LIMIT_WAIT)
        sid = d.get("session_id") if d else None
        if sid and (d.get("num_turns") or 0) > 1:
            if "--resume" in cmd:
                cmd[cmd.index("--resume") + 1] = sid
            else:
                cmd += ["--resume", sid]
            prompt = "You were stopped by a usage limit before finishing. Continue the task you were given and finish it."
    if d is None:
        raise RuntimeError(f"claude {label}: no JSON result (exit {rc}): {tail(out, 10)}")
    run.s["cost"]["claude"] += d.get("total_cost_usd") or 0
    denials = [x.get("tool_input", {}).get("command") or x.get("tool_name") for x in d.get("permission_denials", [])]
    run.s["events"].append({"at": now(), "agent": "claude", "label": label, "seconds": round((d.get("duration_ms") or 0) / 1000),
                            "turns": d.get("num_turns"), "cost": d.get("total_cost_usd"), "denied": denials[:20]})
    run.save()
    if rc != 0 or d.get("is_error"):
        raise RuntimeError(f"claude {label} failed: {d.get('subtype')} {str(d.get('result'))[:500]}")
    if schema and not d.get("structured_output"):
        raise RuntimeError(f"claude {label}: no structured output: {str(d.get('result'))[:500]}")
    return {"text": d.get("result", ""), "structured": d.get("structured_output"), "session": d.get("session_id")}


def pi(run: Run, label: str, prompt: str, cwd: Path, timeout: int = 3600) -> str:
    """Headless Pi with the verifier model. Returns the last assistant text."""
    v = run.cfg["verifier"]
    pfile = run.log(f"{label}.prompt.md")
    pfile.parent.mkdir(parents=True, exist_ok=True)
    pfile.write_text(prompt)
    cmd = ["pi", "-p", "--mode", "json", "--no-session", "--no-mcp", "--no-skills", "-nc", "-np", "-ne",
           "--model", v["model"], "--thinking", v.get("thinking", "high")]
    for ext in v.get("extensions", []):
        cmd += ["-e", str(Path(ext).expanduser())]
    cmd += [f"@{pfile}", "Follow the instructions in the attached file."]
    t = time.time()
    rc, out = sh(cmd, cwd=cwd, timeout=timeout)   # sh closes stdin: Pi hangs on an open one
    run.log(f"{label}.out.jsonl").write_text(out)
    cost, text, turns = 0.0, "", 0
    for line in out.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "message_end" and e.get("message", {}).get("role") == "assistant":
            m = e["message"]
            turns += 1
            cost += ((m.get("usage") or {}).get("cost") or {}).get("total") or 0
            parts = [c.get("text", "") for c in m.get("content", []) if c.get("type") == "text"]
            text = "\n".join(parts) or text
    run.s["cost"]["pi"] += cost
    run.s["events"].append({"at": now(), "agent": "pi", "label": label, "seconds": round(time.time() - t), "turns": turns, "cost": round(cost, 4)})
    run.save()
    if rc != 0 or turns == 0:
        raise RuntimeError(f"pi {label} failed (exit {rc}, {turns} turns): {tail(out, 5)[:800]}")
    return text


# ---------------------------------------------------------------- lessons

def lesson_files(target: str | None = None, role: str | None = None) -> list[dict]:
    out = []
    for f in sorted((ROOT / "lessons").glob("*.md")):
        head, _, body = f.read_text().partition("\n---\n")
        meta = dict(line.split(": ", 1) for line in head.splitlines() if ": " in line)
        if target and meta.get("target") not in (target, "any"):
            continue
        if role and meta.get("role") != role:
            continue
        rule = re.search(r"\*\*Rule:\*\*\s*(.+)", body)
        out.append({"id": f.stem, "file": f, "meta": meta, "body": body, "rule": rule.group(1).strip() if rule else ""})
    return out


def lessons_for(target: str, role: str) -> str:
    rules = [f"- {l['rule']}" for l in lesson_files(target, role) if l["rule"]]
    return "\n".join(rules) if rules else "- (none recorded yet)"


LESSON_SCHEMA = {
    "type": "object", "required": ["same_as", "slug", "what", "cause", "rule"],
    "properties": {
        "same_as": {"type": ["string", "null"], "description": "id of the existing lesson this repeats, or null"},
        "slug": {"type": "string", "description": "3 to 6 lowercase words joined by hyphens"},
        "what": {"type": "string"}, "cause": {"type": "string"},
        "rule": {"type": "string", "description": "one imperative sentence the agent in that role can follow next time"},
    },
}


def record_lesson(run: Run, role: str, step: str, evidence: str) -> None:
    """Writes or updates a lesson. Never raises: a lost lesson must not stop a run."""
    try:
        existing = lesson_files(run.target_name)
        index = "\n".join(f"- {l['id']} (role {l['meta'].get('role')}): {l['rule']}" for l in existing) or "(none)"
        try:
            d = claude(run, f"lesson-{step}-{int(time.time())}", render("lesson", role=role, step=step, evidence=evidence[:6000], existing=index),
                       cwd=run.dir, tools=[], schema=LESSON_SCHEMA, model="haiku", timeout=300)["structured"]
        except Exception as e:  # keep the raw facts when the summary fails
            d = {"same_as": None, "slug": f"unsummarised-{step}", "what": evidence[:1500], "cause": f"not analysed ({e})"[:200], "rule": ""}
        same = next((l for l in existing if l["id"] == d.get("same_as")), None)
        if same:
            seen = int(same["meta"].get("seen", "1")) + 1
            text = same["file"].read_text()
            text = re.sub(r"^seen: \d+", f"seen: {seen}", text, count=1, flags=re.M)
            same["file"].write_text(text.rstrip() + f"\n- Seen again in {run.id}, step {step}: {d['what']}\n")
            lid = same["id"]
        else:
            lid = f"{dt.date.today()}-{re.sub(r'[^a-z0-9-]', '', d['slug'].lower())[:50]}"
            f = ROOT / "lessons" / f"{lid}.md"
            n = 2
            while f.exists():
                f = ROOT / "lessons" / f"{lid}-{n}.md"
                n += 1
            lid = f.stem
            f.parent.mkdir(exist_ok=True)
            f.write_text(f"target: {run.target_name}\nrole: {role}\nstep: {step}\nseen: 1\nfirst_run: {run.id}\n---\n"
                         f"**What happened:** {d['what']}\n\n**Cause:** {d['cause']}\n\n**Rule:** {d['rule']}\n")
        run.s["lessons"].append({"id": lid, "step": step, "repeat": bool(same)})
        run.save()
        say(f"lesson {'repeated' if same else 'recorded'}: {lid}")
    except Exception as e:
        say(f"could not record lesson for {step}: {e}")


# ---------------------------------------------------------------- steps

def step_intake(run: Run, issue: int) -> dict:
    _, out = sh(["gh", "issue", "view", str(issue), "-R", run.cfg["repo"], "--json", "title,body,url"], check=True)
    d = json.loads(out[out.index("{"):out.rindex("}") + 1])   # gh may print notices around the JSON
    (run.dir / "issue.md").write_text(f"# {d['title']}\n\n{d['body']}\n")
    return {"issue": issue, "title": d["title"], "url": d["url"]}


def step_workspace(run: Run) -> dict:
    repo, base = run.repo, run.cfg.get("base", "main")
    sh(["git", "fetch", "origin", base], cwd=repo, check=True)
    _, sha = sh(["git", "rev-parse", f"origin/{base}"], cwd=repo, check=True)
    sha, branch = sha.strip(), f"factory/{run.id}"
    run.impl.parent.mkdir(parents=True, exist_ok=True)
    if not run.impl.exists():
        sh(["git", "worktree", "add", "-b", branch, str(run.impl), sha], cwd=repo, check=True)
    if not run.holdout_ws.exists():
        sh(["git", "worktree", "add", "--detach", str(run.holdout_ws), sha], cwd=repo, check=True)
    for ws in (run.impl, run.holdout_ws):
        sh(run.cfg["install"], cwd=ws, check=True, log=run.log(f"install-{ws.name}.log"))
    return {"base_sha": sha, "branch": branch}


SPEC_SCHEMA = {"type": "object", "required": ["spec_md"], "properties": {"spec_md": {"type": "string"}}}


def step_spec(run: Run) -> dict:
    prompt = render("spec", notes=run.cfg.get("notes", "(none)"), issue=(run.dir / "issue.md").read_text(), context=run.cfg.get("context", ""),
                    lessons=lessons_for(run.target_name, "spec"))
    d = claude(run, "spec", prompt, cwd=run.impl, tools=["Read", "Glob", "Grep"], schema=SPEC_SCHEMA,
               model=run.cfg.get("implementer", {}).get("model"), timeout=1800)
    (run.dir / "spec.md").write_text(d["structured"]["spec_md"])
    return {"chars": len(d["structured"]["spec_md"])}


def collect_holdout(run: Run) -> list[str]:
    """Moves the verifier's tests out of its workspace and resets everything else it touched."""
    hd = run.cfg["holdout"]["dir"]
    src = run.holdout_ws / hd
    files = [p for p in src.rglob("*") if p.is_file()] if src.exists() else []
    if not any(p.name.endswith(tuple(run.cfg["holdout"]["suffixes"])) for p in files):
        raise RuntimeError(f"the verifier wrote no test files under {hd}")
    if run.holdout_tests.exists():
        shutil.rmtree(run.holdout_tests)
    shutil.copytree(src, run.holdout_tests)
    shutil.rmtree(src)
    _, dirty = sh(["git", "status", "--porcelain"], cwd=run.holdout_ws)
    if dirty.strip():
        say(f"verifier changed files outside {hd}; discarded:\n{dirty.strip()}")
        sh("git checkout -- . && git clean -fdq", cwd=run.holdout_ws, check=True)
    return sorted(str(p.relative_to(src)) for p in files)


def step_holdout(run: Run) -> dict:
    hd = run.cfg["holdout"]
    prompt = render("holdout", notes=run.cfg.get("notes", "(none)"), spec=(run.dir / "spec.md").read_text(), dir=hd["dir"], run=hd["run"].replace("{factory}", str(ROOT)).replace("{out}", "/tmp/holdout.json"),
                    lessons=lessons_for(run.target_name, "holdout"))
    pi(run, "holdout", prompt, cwd=run.holdout_ws, timeout=run.cfg["verifier"].get("timeout", 3600))
    return {"files": collect_holdout(run)}


IMPL_SCHEMA = {
    "type": "object", "required": ["summary", "disputes"],
    "properties": {
        "summary": {"type": "string"},
        "disputes": {"type": "array", "description": "Hidden acceptance tests you believe contradict the spec. Empty unless you are sure.",
                     "items": {"type": "object", "required": ["about", "reason"], "properties": {"about": {"type": "string"}, "reason": {"type": "string"}}}},
    },
}


def commit(run: Run, message: str) -> str:
    sh(["git", "add", "-A"], cwd=run.impl, check=True)
    rc, _ = sh(["git", "diff", "--cached", "--quiet"], cwd=run.impl)
    if rc != 0:
        sh(["git", "commit", "-q", "-m", message], cwd=run.impl, check=True)
    _, sha = sh(["git", "rev-parse", "HEAD"], cwd=run.impl, check=True)
    return sha.strip()


def step_implement(run: Run) -> dict:
    impl = run.cfg["implementer"]
    prompt = render("implement", notes=run.cfg.get("notes", "(none)"), spec=(run.dir / "spec.md").read_text(), lessons=lessons_for(run.target_name, "implement"),
                    checks="\n".join(f"- `{c}`" for c in run.cfg["gates"].values()))
    with run.hidden_locked():
        d = claude(run, "implement", prompt, cwd=run.impl, tools=impl["allowed_tools"], schema=IMPL_SCHEMA, model=impl.get("model"),
                   timeout=impl.get("timeout", 5400))
    sha = commit(run, f"{run.data('intake')['title']}\n\nImplemented by the factory, run {run.id}.")
    if sha == run.data("workspace")["base_sha"]:
        raise RuntimeError("the implementer changed nothing")
    return {"session": d["session"], "summary": d["structured"]["summary"], "sha": sha}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def gate_smoke(run: Run, n: int) -> str | None:
    sm = run.cfg["smoke"]
    port = free_port()
    url = f"http://localhost:{port}"
    out_dir = run.dir / f"smoke-{n}"
    server = subprocess.Popen(["bash", "-c", sm["serve"].replace("{port}", str(port))], cwd=run.impl, start_new_session=True,
                              stdin=subprocess.DEVNULL, stdout=open(run.log(f"serve-{n}.log"), "w"), stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(url, timeout=2)
                break
            except OSError:
                time.sleep(1)
        else:
            return "the dev server did not answer within 60 s:\n" + tail(run.log(f"serve-{n}.log").read_text(), 15)
        rc, out = sh(sm["run"].replace("{url}", url).replace("{out}", str(out_dir)), cwd=run.impl, timeout=sm.get("timeout", 900),
                     log=run.log(f"smoke-{n}.log"))
        return None if rc == 0 else tail(out, 30)
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(server.pid, signal.SIGTERM)


def clean_failure(msg: str) -> str:
    """Keeps the assertion message, drops stack frames and code frames that would show test source."""
    keep = []
    for line in msg.splitlines():
        if re.match(r"\s*(at |❯|\d+\s*\||\|)", line) or "holdout" in line:
            break
        keep.append(line)
    return " ".join(" ".join(keep).split())[:700]


def run_holdout(run: Run, sha: str, n: int) -> dict:
    """Runs the hidden tests against a commit, in the verifier workspace. Returns counts, safe descriptions and raw output."""
    hd = run.cfg["holdout"]
    ws, dest, out_file = run.holdout_ws, run.holdout_ws / hd["dir"], run.hidden / f"holdout-{n}.json"
    sh("git checkout -q -- . && git clean -fdq", cwd=ws, check=True)
    sh(["git", "checkout", "-q", "--detach", sha], cwd=ws, check=True)
    sh(run.cfg["install"], cwd=ws, check=True)
    shutil.copytree(run.holdout_tests, dest)
    out_file.unlink(missing_ok=True)
    rc, out = sh(hd["run"].replace("{factory}", str(ROOT)).replace("{out}", str(out_file)), cwd=ws, timeout=hd.get("timeout", 1800))
    (run.hidden / f"holdout-{n}.log").write_text(out)
    shutil.rmtree(dest)
    if not out_file.exists():
        return {"passed": 0, "total": 0, "failures": [f"the hidden tests could not be run: {clean_failure(tail(out, 6))}"], "raw": tail(out, 80)}
    res = json.loads(out_file.read_text())
    failures, passed, total = [], 0, 0
    for f in res.get("testResults", []):
        tests = f.get("assertionResults", [])
        if not tests and f.get("status") == "failed":
            total += 1
            failures.append(f"a hidden test file failed to load: {clean_failure(f.get('message', ''))}")
        for t in tests:
            total += 1
            if t["status"] == "passed":
                passed += 1
            elif t["status"] == "failed":
                failures.append(f"{t['fullName']}: {clean_failure((t.get('failureMessages') or ['failed'])[0])}")
    return {"passed": passed, "total": total, "failures": failures, "raw": tail(out, 120)}


def gates(run: Run, n: int, sha: str) -> dict:
    """Returns {failures: [{gate, text}], holdout: 'x of y'}. Build failure skips the rest."""
    fails = []
    cmds = run.cfg["gates"]
    for name, cmd in cmds.items():
        rc, out = sh(cmd, cwd=run.impl, timeout=1200, log=run.log(f"gate-{name}-{n}.log"))
        say(f"  gate {name}: {'ok' if rc == 0 else 'FAILED'}")
        if rc != 0:
            fails.append({"gate": name, "text": tail(out, 40)})
            if name == next(iter(cmds)):
                return {"failures": fails, "holdout": "not run"}
    err = gate_smoke(run, n)
    say(f"  gate smoke: {'ok' if not err else 'FAILED'}")
    if err:
        fails.append({"gate": "smoke", "text": err})
    h = run_holdout(run, sha, n)
    say(f"  gate holdout: {h['passed']} of {h['total']} passed")
    if h["failures"] or h["total"] == 0:
        fails.append({"gate": "holdout", "text": f"{h['passed']} of {h['total']} hidden acceptance tests passed. Failures:\n" +
                      "\n".join(f"- {x}" for x in h["failures"])})
    return {"failures": fails, "holdout": f"{h['passed']} of {h['total']}"}


def review(run: Run, n: int, sha: str) -> dict:
    ws, base = run.holdout_ws, run.data("workspace")["base_sha"]
    sh("git checkout -q -- . && git clean -fdq", cwd=ws, check=True)
    sh(["git", "checkout", "-q", "--detach", sha], cwd=ws, check=True)
    _, diff = sh(["git", "diff", f"{base}..{sha}", "--", ".", *[f":(exclude){x}" for x in run.cfg.get("review_exclude", [])]], cwd=ws, check=True)
    (run.dir / f"diff-{n}.patch").write_text(diff)
    out = ws / "review.json"
    out.unlink(missing_ok=True)
    pi(run, f"review-{n}", render("review", notes=run.cfg.get("notes", "(none)"), spec=(run.dir / "spec.md").read_text(), diff=str(run.dir / f"diff-{n}.patch"),
                                  lessons=lessons_for(run.target_name, "review")), cwd=ws, timeout=1800)
    if not out.exists():
        raise RuntimeError("the reviewer wrote no review.json")
    d = json.loads(out.read_text())
    out.unlink()
    sh("git checkout -q -- . && git clean -fdq", cwd=ws)
    (run.dir / f"review-{n}.json").write_text(json.dumps(d, indent=1))
    return {"verdict": d.get("verdict"), "findings": d.get("findings", [])}


def amend(run: Run, n: int, sha: str, disputes: list[dict], raw: str) -> dict:
    """One chance for the verifier to correct its own tests after the implementer disputes them."""
    hd = run.cfg["holdout"]
    ws, dest = run.holdout_ws, run.holdout_ws / hd["dir"]
    sh("git checkout -q -- . && git clean -fdq", cwd=ws, check=True)
    sh(["git", "checkout", "-q", "--detach", sha], cwd=ws, check=True)
    shutil.copytree(run.holdout_tests, dest)
    backup = run.hidden / f"tests-before-amend-{n}"
    shutil.copytree(run.holdout_tests, backup, dirs_exist_ok=True)
    out = ws / "amend.json"
    pi(run, f"amend-{n}", render("amend", notes=run.cfg.get("notes", "(none)"), spec=(run.dir / "spec.md").read_text(), dir=hd["dir"],
                                 disputes="\n".join(f"- {d['about']}: {d['reason']}" for d in disputes), output=raw,
                                 run=hd["run"].replace("{factory}", str(ROOT)).replace("{out}", "/tmp/holdout.json")), cwd=ws)
    d = json.loads(out.read_text()) if out.exists() else {"changed": False, "reason": "the verifier wrote no amend.json"}
    out.unlink(missing_ok=True)
    collect_holdout(run)
    return {"changed": bool(d.get("changed")), "reason": str(d.get("reason", ""))[:1500]}


def describe(fails: list[dict], findings: list[dict]) -> str:
    parts = [f"### Gate `{f['gate']}` failed\n\n```\n{f['text']}\n```" for f in fails]
    if findings:
        parts.append("### The independent reviewer rejected the change\n\n" +
                     "\n".join(f"- {x.get('file', '')}: {x.get('issue', x)}" for x in findings))
    return "\n\n".join(parts)


def step_verify(run: Run) -> dict:
    """Gates and review, with at most MAX_FIX_ROUNDS fix rounds. Raises Stop when they are used up."""
    sha, session = run.data("implement")["sha"], run.data("implement")["session"]
    amended = None
    for n in range(MAX_FIX_ROUNDS + 1):
        if n > 0:
            fx = run.step(f"fix-{n}", lambda: fix(run, n, session, problem))
            sha = fx["sha"]
            if fx["disputes"] and not amended and any(f["gate"] == "holdout" for f in g["failures"]):
                amended = run.step(f"amend-{n}", lambda: amend(run, n, sha, fx["disputes"], run_holdout(run, sha, 90 + n)["raw"]))
                if amended["changed"]:
                    record_lesson(run, "holdout", f"amend-{n}", f"The verifier changed its hidden tests after a dispute.\nDispute: {fx['disputes']}\nReason: {amended['reason']}")
        g = run.step(f"gates-{n}", lambda: gates(run, n, sha))
        r = {"verdict": "skipped", "findings": []}
        if not g["failures"]:
            r = run.step(f"review-{n}", lambda: review(run, n, sha))
            say(f"  review: {r['verdict']}")
        blocking = [x for x in r["findings"] if x.get("severity") == "blocking"] if r["verdict"] == "reject" else []
        if not g["failures"] and r["verdict"] in ("approve", "reject") and not blocking:
            return {"sha": sha, "fix_rounds": n, "holdout": g["holdout"], "review": r, "amended": amended}
        problem = describe(g["failures"], blocking)
        (run.dir / f"problem-{n}.md").write_text(problem)
        if f"lesson-{n}" not in run.s["steps"]:
            record_lesson(run, "implement", f"verify-{n}", problem)
            run.s["steps"][f"lesson-{n}"] = {"status": "ok", "seconds": 0, "data": None}
            run.save()
        if n == MAX_FIX_ROUNDS:
            raise Stop(f"Still failing after {MAX_FIX_ROUNDS} fix rounds.\n\n{problem}")
    raise AssertionError("unreachable")


def fix(run: Run, n: int, session: str, problem: str) -> dict:
    impl = run.cfg["implementer"]
    prompt = render("fix", notes=run.cfg.get("notes", "(none)"), problem=problem, round=str(n), rounds=str(MAX_FIX_ROUNDS), lessons=lessons_for(run.target_name, "implement"))
    with run.hidden_locked():
        d = claude(run, f"fix-{n}", prompt, cwd=run.impl, tools=impl["allowed_tools"], schema=IMPL_SCHEMA, resume=session, model=impl.get("model"),
                   timeout=impl.get("timeout", 5400))
    sha = commit(run, f"Fix round {n}\n\n{d['structured']['summary'][:400]}")
    return {"sha": sha, "summary": d["structured"]["summary"], "disputes": d["structured"]["disputes"]}


def step_ship(run: Run) -> dict:
    repo, intake, ws, v = run.cfg["repo"], run.data("intake"), run.data("workspace"), run.data("verify")
    sh(["git", "push", "-u", "origin", ws["branch"]], cwd=run.impl, check=True)
    body = (f"Closes #{intake['issue']}\n\n{run.data('implement')['summary']}\n\n## Evidence\n\n"
            f"- Gates: {', '.join(run.cfg['gates'])}, smoke: passed\n- Hidden acceptance tests (written by {run.cfg['verifier']['model']} from the spec): {v['holdout']} passed\n"
            f"- Independent diff review: {v['review']['verdict']}\n- Fix rounds: {v['fix_rounds']}\n"
            + (f"- Hidden tests amended after a dispute: {v['amended']['reason']}\n" if v.get("amended") and v["amended"]["changed"] else "")
            + f"\nFactory run `{run.id}`.\n")
    def find_pr() -> str | None:   # by branch, so a resumed run does not open a second one
        _, out = sh(["gh", "pr", "list", "-R", repo, "--head", ws["branch"], "--state", "all", "--json", "url", "--jq", ".[0].url"])
        m = re.search(r"https://\S+/pull/\d+", out)
        return m.group(0) if m else None
    pr = find_pr()
    if not pr:
        sh(["gh", "pr", "create", "-R", repo, "--head", ws["branch"], "--base", run.cfg.get("base", "main"),
            "--title", intake["title"], "--body", body], cwd=run.impl, check=True)
        pr = find_pr()   # gh prints notices after the URL, so its output is not parsed
    if not pr:
        raise RuntimeError("the pull request was not created")
    _, out = sh(["gh", "pr", "view", pr, "-R", repo, "--json", "state", "--jq", ".state"])
    merged = "MERGED" in out
    if not merged:
        sh(["gh", "pr", "merge", pr, "-R", repo, "--squash"], check=True)
    sh(["git", "push", "-q", "origin", "--delete", ws["branch"]], cwd=run.impl)   # the local branch stays with its worktree
    _, out = sh(["gh", "pr", "view", pr, "-R", repo, "--json", "mergeCommit", "--jq", ".mergeCommit.oid"], check=True)
    sha = re.search(r"\b[0-9a-f]{40}\b", out)
    if not sha:
        raise RuntimeError(f"no merge commit for {pr}: {out[:300]}")
    return {"pr": pr, "merge_sha": sha.group(0)}


def prod_check(run: Run, sha: str, label: str) -> str | None:
    """None when production runs the given commit, is healthy and loads in a browser without errors."""
    dep = run.cfg["deploy"]
    for _ in range(12):
        _, status = sh(["coolify", "status", dep["coolify_app"]])
        if sha[:7] in status and "running:healthy" in status:
            break
        time.sleep(10)
    else:
        return f"Coolify does not report commit {sha[:7]} as running and healthy:\n{status}"
    rc, out = sh(["node", "--input-type=module", "-", dep["url"], str(run.dir / f"prod-{label}.png")], cwd=run.repo, timeout=120,
                 stdin=(ROOT / "execution" / "browser_check.mjs").read_text())
    run.log(f"prod-check-{label}.log").write_text(out)
    return None if rc == 0 else f"browser check of {dep['url']} failed:\n{tail(out, 20)}"


def step_deploy(run: Run) -> dict:
    dep, sha = run.cfg["deploy"], run.data("ship")["merge_sha"]
    if run.s.get("reverted"):   # a resumed run must not deploy the revert and then "roll back" a second time
        raise Stop(f"The merge {sha[:7]} was already reverted by this run ({run.s['reverted'][:7]}). Fix the cause, land the change again "
                   "by hand, then mark the deploy step as done in the run state or start a new run.")
    rc, out = sh(["coolify", "deploy", dep["coolify_app"], "--timeout", "1200"], timeout=1300, log=run.log("deploy.log"))
    err = f"deployment failed:\n{tail(out, 20)}" if rc != 0 else prod_check(run, sha, "after")
    if not err:
        return {"deployed": sha, "rolled_back": False}
    say("production check failed, rolling back")
    record_lesson(run, "implement", "deploy", err)
    base = run.cfg.get("base", "main")
    rb = STATE / "work" / run.id / "rollback"
    sh(["git", "fetch", "origin", base], cwd=run.repo, check=True)
    if rb.exists():
        sh(["git", "worktree", "remove", "--force", str(rb)], cwd=run.repo)
        shutil.rmtree(rb, ignore_errors=True)
    sh(["git", "worktree", "add", "--detach", str(rb), f"origin/{base}"], cwd=run.repo, check=True)
    sh(["git", "revert", "--no-edit", sha], cwd=rb, check=True)
    sh(["git", "push", "origin", f"HEAD:{base}"], cwd=rb, check=True)
    _, rsha = sh(["git", "rev-parse", "HEAD"], cwd=rb, check=True)
    run.s["reverted"] = rsha.strip()
    run.save()
    rc, out = sh(["coolify", "deploy", dep["coolify_app"], "--timeout", "1200"], timeout=1300, log=run.log("rollback.log"))
    rerr = f"rollback deployment failed:\n{tail(out, 20)}" if rc != 0 else prod_check(run, rsha.strip(), "rollback")
    raise Stop(f"Production failed after deploying {sha[:7]} and the merge was reverted ({rsha.strip()[:7]}).\n\n{err}\n\n"
               + (f"The rollback also failed:\n{rerr}" if rerr else "Production is back on the previous version."))


def summary(run: Run) -> dict:
    s = run.s
    return {
        "run": run.id, "target": run.target_name, "issue": s["steps"].get("intake", {}).get("data", {}).get("url"),
        "status": s["status"], "started": s["started"], "ended": s.get("ended"),
        "seconds": {k: v["seconds"] for k, v in s["steps"].items() if v.get("seconds")},
        "cost_usd": {k: round(v, 2) for k, v in s["cost"].items()},
        "human_touches": s["human_touches"],
        "verify": {k: v for k, v in (s["steps"].get("verify", {}).get("data") or {}).items() if k != "review"},
        "ship": s["steps"].get("ship", {}).get("data"), "deploy": s["steps"].get("deploy", {}).get("data"),
        "lessons": s["lessons"], "stopped_because": s.get("stopped_because"),
    }


def publish(run: Run) -> None:
    """Writes the run summary and lessons to the factory repo and pushes them."""
    (ROOT / "runs").mkdir(exist_ok=True)
    (ROOT / "runs" / f"{run.id}.json").write_text(json.dumps(summary(run), indent=1) + "\n")
    sh(["git", "add", "runs", "lessons"], cwd=ROOT)
    rc, _ = sh(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if rc != 0:
        sh(["git", "commit", "-q", "-m", f"Run {run.id}: {run.s['status']}"], cwd=ROOT)
        rc, out = sh(["git", "push", "-q", "origin", "HEAD"], cwd=ROOT)
        if rc != 0:
            say(f"could not push the run summary: {tail(out, 3)}")


def step_report(run: Run) -> dict:
    v, ship = run.data("verify"), run.data("ship")
    repeats = [l["id"] for l in run.s["lessons"] if l["repeat"]]
    text = (f"Shipped by factory run `{run.id}`.\n\n- PR: {ship['pr']}\n- Live: {run.cfg['deploy']['url']} (commit {ship['merge_sha'][:7]})\n"
            f"- Hidden acceptance tests: {v['holdout']} passed, review: {v['review']['verdict']}, fix rounds: {v['fix_rounds']}\n"
            f"- Cost: Claude {run.s['cost']['claude']:.2f} USD (subscription, nominal), Pi {run.s['cost']['pi']:.2f} USD\n"
            f"- Lessons recorded: {len(run.s['lessons'])}"
            + (f"\n- Repeated lessons, candidates for a code gate: {', '.join(repeats)}" if repeats else "")
            + ("\n\nReviewer notes:\n" + "\n".join(f"- {x.get('file', '')}: {x.get('issue', '')}" for x in v["review"]["findings"]) if v["review"]["findings"] else ""))
    sh(["gh", "issue", "comment", str(run.data("intake")["issue"]), "-R", run.cfg["repo"], "--body", text])
    with contextlib.suppress(Exception):   # bring the local checkout up to date if it is clean and on the base branch
        sh(["git", "pull", "-q", "--ff-only"], cwd=run.repo)
    return {"comment": text}


def escalate(run: Run, reason: str) -> None:
    run.s["status"], run.s["stopped_because"] = "escalated", reason[:4000]
    run.s["human_touches"]["escalations"] += 1
    intake = run.s["steps"].get("intake", {}).get("data")
    if os.environ.get("VAMPIRE_NO_ISSUE"):   # while debugging the driver itself
        say(f"stopped (no issue opened): {reason[:1500]}")
    elif intake:
        ws = run.s["steps"].get("workspace", {}).get("data") or {}
        body = (f"The factory stopped on #{intake['issue']} and needs a person.\n\n{reason[:6000]}\n\n"
                f"- Run: `{run.id}`\n- Branch: `{ws.get('branch')}` (worktree `{run.impl}`)\n- Logs: `{run.dir}`\n\n"
                f"To continue after fixing the cause: `factory run {run.target_name} --resume {run.id}`.")
        rc, out = sh(["gh", "issue", "create", "-R", run.cfg["repo"], "--label", "needs-human",
                      "--title", f"Factory stopped: {intake['title']}", "--body", body])
        say(f"escalated: {out.strip().splitlines()[-1] if rc == 0 else out}")


def cmd_run(a) -> int:
    if a.resume:
        run = Run(a.resume, a.resume.split("-")[0] if not a.target else a.target)
        a.issue = a.issue or (run.s["steps"].get("intake", {}).get("data") or {}).get("issue")
        run.s["status"] = "running"
        run.s.pop("stopped_because", None)
    else:
        if not a.issue:
            sys.exit("give --issue N or --resume RUN")
        run = Run(f"{a.target}-{a.issue}-{dt.datetime.now():%Y%m%d-%H%M}", a.target)
    os.chmod(run.hidden, 0o700)
    say(f"run {run.id}, logs in {run.dir}")
    plan = [("intake", lambda: step_intake(run, a.issue)), ("workspace", lambda: step_workspace(run)), ("spec", lambda: step_spec(run)),
            ("holdout", lambda: step_holdout(run)), ("implement", lambda: step_implement(run)), ("verify", lambda: step_verify(run)),
            ("ship", lambda: step_ship(run)), ("deploy", lambda: step_deploy(run)), ("report", lambda: step_report(run))]
    try:
        for name, fn in plan:
            run.step(name, fn)
            if a.until == name:
                say(f"stopped after {name} as asked")
                run.s["status"] = "paused"
                run.save()
                return 0
        run.s["status"] = "shipped"
    except Stop as e:
        escalate(run, str(e))
    except Exception as e:
        failed = next((k for k, v in run.s["steps"].items() if v["status"] == "failed"), "driver")
        record_lesson(run, "driver", failed, f"Step {failed} raised: {e}")
        escalate(run, f"Step `{failed}` crashed:\n\n```\n{str(e)[:3000]}\n```")
    run.s["ended"] = now()
    run.save()
    publish(run)
    print(json.dumps(summary(run), indent=1))
    return 0 if run.s["status"] == "shipped" else 1


def runs_for(target: str, issue: int) -> list[dict]:
    """State of every run of this issue, oldest first."""
    out = []
    for p in sorted((STATE / "runs").glob(f"{target}-{issue}-*/state.json"), key=lambda p: p.stat().st_mtime):
        with contextlib.suppress(ValueError):
            out.append(json.loads(p.read_text()))
    return out


def cmd_queue(a) -> int:
    """Runs the issues one after another. Stops at the first one that does not ship."""
    for issue in a.issues:
        runs = runs_for(a.target, issue)
        if any(r["status"] == "shipped" for r in runs):
            say(f"issue {issue}: already shipped, skipped")
            continue
        last = runs[-1] if runs else None
        # A run that stopped for any reason other than used-up fix rounds is worth one automatic resume.
        final = lambda r: r.get("reverted") or "fix rounds" in (r.get("stopped_because") or "")   # a resume cannot help these
        resume = last["run"] if last and not final(last) and not a.fresh else None
        for attempt in (1, 2):
            say(f"queue: issue {issue}, {'resuming ' + resume if resume else 'new run'}")
            rc = cmd_run(argparse.Namespace(target=a.target, issue=issue, resume=resume, until=None))
            if rc == 0:
                break
            last = runs_for(a.target, issue)[-1]
            if attempt == 2 or final(last):
                say(f"queue: stopped at issue {issue} ({last['run']}); not started: {a.issues[a.issues.index(issue) + 1:]}")
                return 1
            resume = last["run"]
            time.sleep(60)
    say("queue: every issue shipped")
    return 0


def cmd_status(a) -> int:
    runs = sorted((STATE / "runs").glob("*/state.json"), key=lambda p: p.stat().st_mtime)
    if a.run:
        runs = [p for p in runs if p.parent.name == a.run]
    for p in runs[-(1 if not a.run and not a.all else 100):]:
        s = json.loads(p.read_text())
        steps = " ".join(f"{k}:{v['status']}({v.get('seconds', 0)}s)" for k, v in s["steps"].items() if not k.startswith("lesson-"))
        print(f"{s['run']}  {s['status']}  claude {s['cost']['claude']:.2f} USD  pi {s['cost']['pi']:.2f} USD  lessons {len(s['lessons'])}\n  {steps}")
        if s.get("stopped_because"):
            print("  stopped: " + s["stopped_because"].splitlines()[0][:200])
    return 0


def cmd_lessons(a) -> int:
    for l in lesson_files(a.target, a.role):
        m = l["meta"]
        print(f"{l['id']}  [{m.get('target')}/{m.get('role')}, seen {m.get('seen')}]\n  {l['rule']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="factory", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="take one issue to production (WRITES: pushes, merges and deploys the target)")
    r.add_argument("target", nargs="?", help="name of a file in targets/ without .toml")
    r.add_argument("--issue", type=int, help="issue number in the target repository")
    r.add_argument("--resume", metavar="RUN", help="continue a run after its last finished step")
    r.add_argument("--until", choices=STEPS, help="stop after this step")
    r.set_defaults(fn=cmd_run)
    q = sub.add_parser("queue", help="take several issues to production in order; stops at the first that does not ship "
                                     "(WRITES like run). Shipped issues are skipped, a crashed run is resumed once")
    q.add_argument("target")
    q.add_argument("issues", nargs="+", type=int)
    q.add_argument("--fresh", action="store_true", help="start new runs instead of resuming unfinished ones")
    q.set_defaults(fn=cmd_queue)
    s = sub.add_parser("status", help="show the latest run, one run, or all runs")
    s.add_argument("run", nargs="?")
    s.add_argument("--all", action="store_true")
    s.set_defaults(fn=cmd_status)
    le = sub.add_parser("lessons", help="list recorded lessons")
    le.add_argument("--target")
    le.add_argument("--role", choices=["spec", "holdout", "implement", "review", "driver"])
    le.set_defaults(fn=cmd_lessons)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
