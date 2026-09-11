"""Paid-run loop for the Stage B driver. Helpers stay in live.py."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from .live import (
    ADVERSARY_OBJECTIVE,
    ANTHROPIC_MODEL,
    ARMS,
    DEFAULT_CAP_USD,
    HONEST_OBJECTIVE,
    OPENAI_MODEL,
    ROLES,
    SEED,
    StubTransport,
    arm_config,
    build_report,
    live_calls_allowed,
    load_env,
    reachable_harm,
    require_live,
    run_cell,
    should_pay,
    stop_status,
    usage_usd,
)


def run_experiment(
    provider="local",
    episodes=16,
    cap_usd=DEFAULT_CAP_USD,
    dry_run=True,
    seed=SEED,
    split_name="evaluation",
    roles=ROLES,
    horizon=6,
    pay_unreachable=False,
    transport=None,
    checkpoint_path=None,
    transcript_path=None,
    replay_path=None,
):
    from .live import select_fixtures

    if isinstance(cap_usd, bool) or not isinstance(cap_usd, (int, float)):
        raise ValueError("cap_usd must be a finite non-negative number")
    if not math.isfinite(float(cap_usd)) or cap_usd < 0:
        raise ValueError("cap_usd must be a finite non-negative number")

    replay = None
    if replay_path:
        from .transcript import ReplayIndex
        replay = ReplayIndex(replay_path)
        dry_run, transport = True, None
    if not dry_run and transport is None:
        load_env()
        require_live()
        if not live_calls_allowed():
            raise RuntimeError("live flags are off")
    elif not dry_run:
        require_live()
    fixtures, commitment = select_fixtures(seed, max(4, episodes), split_name)
    fixtures = fixtures[:episodes]
    model = ANTHROPIC_MODEL if provider != "openai" else OPENAI_MODEL
    live_model = None if dry_run or provider == "local" else model
    usage = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "retries": 0}
    spent = 0.0
    forecast = 0.0
    rows = []
    planned = []
    for fixture in fixtures:
        for arm in ARMS:
            for role in roles:
                planned.append((fixture, arm, role))
    if transcript_path:
        from .transcript import write_header
        write_header(transcript_path, model=live_model or model, provider=provider, seed=seed,
                     split=split_name, evaluation_seed_commitment=commitment, horizon=horizon,
                     arms=list(ARMS), roles=list(roles), episodes=len(fixtures),
                     cap_usd=cap_usd, dry_run=dry_run, replay=bool(replay_path))
    stop = stop_status(rows, len(planned), cap_usd, spent, finished=False)
    # A zero cap is a hard no-request contract.  Check it before the first
    # cell (including cells that would otherwise be skipped) so a paid run
    # cannot spend before reporting that it is capped.
    if stop["stop"] and stop["reason"] == "dollar_cap":
        report = build_report(rows, _meta(
            dry_run, provider, live_model, forecast, seed, split_name,
            commitment, horizon, roles, usage, spent, cap_usd, stop,
        ))
        if checkpoint_path:
            write_report(report, checkpoint_path)
        return report
    for fixture, arm, role in planned:
        probe_rules, _ = arm_config(arm, fixture["rules"])
        reachable, _ = reachable_harm(fixture["state"], probe_rules, horizon)
        pay = not dry_run and should_pay(reachable, role, pay_unreachable)
        if replay is not None:
            pay = (fixture["id"], arm, role) in replay.cells
            if not pay:
                continue
        if not pay and not dry_run:
            rows.append({
                "episode": fixture["id"],
                "family": fixture["family"],
                "arm": arm,
                "role": role,
                "system": arm,
                "harm": None,
                "useful": None,
                "schema_failure": 0,
                "schema_error": None,
                "harm_reachable": reachable,
                "solver_harm_lower": None,
                "solver_harm_upper": None,
                "solver_witness": [],
                "usage": {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "retries": 0},
                "local_monitor_usage": {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "retries": 0},
                "objective": ADVERSARY_OBJECTIVE if role == "adversary" else HONEST_OBJECTIVE,
                "rules": __import__("dataclasses").asdict(probe_rules),
                "channels": list(arm_config(arm, fixture["rules"])[1]),
                "paid": False,
                "skipped": "unreachable",
            })
            if checkpoint_path:
                write_report(build_report(rows, _meta(
                    dry_run, provider, live_model, forecast, seed, split_name,
                    commitment, horizon, roles, usage, spent, cap_usd, stop,
                )), checkpoint_path)
            continue
        cell_dry = (dry_run or not pay) and replay is None
        row = run_cell(fixture, arm, role, provider, cell_dry, horizon, transport,
                       transcript_path=transcript_path, replay=replay)
        row["paid"] = bool(pay and not dry_run)
        for key in ("input_tokens", "output_tokens", "reasoning_tokens", "retries"):
            usage[key] = usage.get(key, 0) + int(row["usage"].get(key, 0))
        cell_usd = usage_usd(model, row["usage"])
        forecast = round(forecast + cell_usd, 6)
        if row["paid"]:
            spent = round(spent + cell_usd, 6)
        rows.append(row)
        stop = stop_status(rows, len(planned), cap_usd, spent)
        if checkpoint_path:
            write_report(build_report(rows, _meta(
                dry_run, provider, live_model, forecast, seed, split_name,
                commitment, horizon, roles, usage, spent, cap_usd, stop,
            )), checkpoint_path)
        if spent >= cap_usd and not dry_run:
            stop = stop_status(rows, len(planned), cap_usd, spent)
            break
    else:
        stop = stop_status(rows, len(planned), cap_usd, spent, finished=True)
    return build_report(rows, _meta(
        dry_run, provider, live_model, forecast, seed, split_name,
        commitment, horizon, roles, usage, spent, cap_usd, stop,
    ))


def _meta(dry_run, provider, live_model, forecast, seed, split_name, commitment, horizon, roles, usage, spent, cap_usd, stop):
    return {
        "claim": "Experiment driver report. Dry-run uses ScriptedActor only." if dry_run else "Paid propensity run against pinned Luna/Haiku.",
        "dry_run": dry_run,
        "network_called": bool(not dry_run),
        "provider": "local" if dry_run else provider,
        "model": live_model,
        "forecast_usd": forecast,
        "seed": seed,
        "split": split_name,
        "commitment": commitment,
        "horizon": horizon,
        "roles": roles,
        "usage": usage,
        "spent_usd": spent,
        "cap_usd": cap_usd,
        "stopped": stop,
    }


def default_report_path(report):
    """Return a visible default for paid reports and a local-only dry report."""
    return "reports/live-run-local.json" if report.get("dry_run", True) else "reports/live-run-paid.json"


def write_report(report, path=None):
    dest = Path(path or default_report_path(report))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    report = dict(report)
    report["written_to"] = str(dest)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Finite-control experiment driver")
    parser.add_argument("--dry-run", action="store_true", help="ScriptedActor only; no network")
    parser.add_argument("--provider", choices=("local", "anthropic", "openai"), default="local")
    parser.add_argument("--episodes", type=int, default=16)
    parser.add_argument("--cap-usd", type=float, default=DEFAULT_CAP_USD)
    parser.add_argument("--seed", default=SEED)
    parser.add_argument("--split", choices=("development", "evaluation"), default="evaluation")
    parser.add_argument("--role", choices=("honest", "adversary", "both"), default="both")
    parser.add_argument("--pay-unreachable", action="store_true")
    parser.add_argument("--fake-transport", action="store_true", help="Stub 200 through the real provider actor")
    parser.add_argument("--transcript", default=None,
                        help="JSONL path for prompts, raw responses and actions (default: reports/transcripts/<run>.jsonl on paid runs)")
    parser.add_argument("--replay", default=None,
                        help="Replay a committed transcript: no API key, no network, no spend")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    dry_run = args.dry_run or args.provider == "local"
    if args.fake_transport:
        dry_run = False
    roles = ROLES if args.role == "both" else (args.role,)
    transcript_path = args.transcript
    if transcript_path is None and not dry_run and not args.replay:
        from .transcript import default_path
        transcript_path = default_path(
            ANTHROPIC_MODEL if args.provider != "openai" else OPENAI_MODEL, args.seed, args.split)
    out = args.out or ("reports/live-run-local.json" if dry_run else "reports/live-run-paid.json")
    transport = StubTransport(provider=args.provider) if args.fake_transport else None
    report = run_experiment(
        provider=args.provider if args.provider != "local" or not args.fake_transport else "anthropic",
        episodes=args.episodes,
        cap_usd=args.cap_usd,
        dry_run=dry_run,
        seed=args.seed,
        split_name=args.split,
        roles=roles,
        pay_unreachable=args.pay_unreachable,
        transport=transport,
        checkpoint_path=out,
        transcript_path=transcript_path,
        replay_path=args.replay,
    )
    report = write_report(report, out)
    print(json.dumps(report, indent=2, sort_keys=True))
    return report
