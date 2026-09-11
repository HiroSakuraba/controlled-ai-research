"""Committed run transcripts and free replay.

One JSONL file per paid run, written under reports/transcripts/. The first
record is a run header carrying everything needed to interpret the rest:
pinned model, prompt file hashes, fixture seed and evaluation commitment,
arms, roles, horizon and the source commit. Each later record is one episode,
with every step's observation state, chosen action, raw model text and monitor
verdict, plus a digest of the episode's verified ledger events.

Committed transcripts make the paid run reproducible without an API key:

    python3 -m controlled_ai.live --replay reports/transcripts/<file>.jsonl

replays the recorded responses through the same runner and analysis, so anyone
can check the published numbers, or swap in a different monitor, arm or scoring
rule and see what changes without spending anything.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .adapters import AdapterError, Decision, Usage, parse_action

SCHEMA = "controlled-ai-transcript-v1"


def source_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True, timeout=5, cwd=str(Path(__file__).resolve().parents[1]))
        return out.stdout.strip() or None
    except Exception:
        return None


def prompt_digests():
    root = Path(__file__).resolve().parents[1] / "prompts"
    digests = {}
    for path in sorted(root.glob("*.txt")):
        digests[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def run_id(model, seed, commitment):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = hashlib.sha256(("%s|%s|%s" % (model, seed, commitment)).encode()).hexdigest()[:8]
    return "%s-%s-%s" % (stamp, (model or "local").replace(".", "-"), tag)


def default_path(model, seed, commitment, root="reports/transcripts"):
    return str(Path(root) / (run_id(model, seed, commitment) + ".jsonl"))


def write_header(path, **fields):
    """First line of the file. Call once, before any episode is appended."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "record": "run_header",
        "schema": SCHEMA,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_commit": source_commit(),
        "prompt_sha256": prompt_digests(),
        **fields,
    }
    with dest.open("w") as fh:
        fh.write(json.dumps(header, sort_keys=True, default=str) + "\n")
    return header


def append_episode(path, header, events):
    if not path:
        return None
    steps = [
        {"step": e[2].get("step"), "state": e[2].get("state"),
         "action": e[2].get("action"), "raw_response": e[2].get("raw"),
         "monitor": e[2].get("monitor")}
        for e in events if e[1] == "decision"
    ]
    record = dict(header, record="episode", steps=steps,
                  actor_errors=[e[2] for e in events if e[1] == "actor_error"],
                  events_digest=hashlib.sha256(
                      json.dumps(events, sort_keys=True, default=str).encode()).hexdigest()[:16])
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True, default=str) + "\n")
    return str(dest)


def load(path):
    """Return (header, episodes) from a committed transcript."""
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not rows or rows[0].get("record") != "run_header":
        raise ValueError("transcript is missing its run header")
    return rows[0], [r for r in rows[1:] if r.get("record") == "episode"]


class ReplayIndex:
    """Recorded responses keyed by cell, so a replay needs no network."""

    def __init__(self, path):
        self.header, episodes = load(path)
        self.cells = {}
        for ep in episodes:
            key = (ep["episode"], ep["arm"], ep["role"])
            self.cells[key] = [s.get("raw_response") for s in ep["steps"]]

    def actor(self, episode, arm, role):
        return ReplayActor(self.cells.get((episode, arm, role), []))


class ReplayActor:
    """Returns the recorded raw text in order. Usage is zero: nothing is bought."""

    def __init__(self, raws):
        self.raws = list(raws)
        self.i = 0
        self.last_reported_model = "replay"

    def decide(self, observation):
        if self.i >= len(self.raws):
            raise AdapterError("replay exhausted at step %d" % self.i)
        raw = self.raws[self.i]
        self.i += 1
        if raw is None:
            raise AdapterError("recorded response was unparseable")
        return Decision(parse_action(raw), raw, Usage(0, 0, 0))
