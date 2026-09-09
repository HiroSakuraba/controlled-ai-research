#!/usr/bin/env python3
"""Verify that reports/finite-run.json matches the current deterministic model."""
import json, pathlib, subprocess, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
def normalized(obj):
    obj=dict(obj); obj.pop('generated_utc',None)
    usage=dict(obj.get('usage',{})); usage.pop('experiment_wall_seconds',None); obj['usage']=usage
    return obj
current=json.loads(subprocess.check_output([sys.executable,'-m','controlled_ai'],cwd=ROOT,text=True))
recorded=json.loads((ROOT/'reports'/'finite-run.json').read_text())
if normalized(current)!=normalized(recorded):
    print('reports/finite-run.json is stale; run: python -m controlled_ai > reports/finite-run.json',file=sys.stderr); sys.exit(1)
print('finite report matches current deterministic model')
