# Release checklist

- [ ] Tests pass on a clean checkout.
- [ ] `python3 tools/verify_report.py` passes.
- [ ] The reproducibility manifest names the current commands and artifact.
- [ ] Frozen configuration, task manifests, prompts, and checker version are recorded.
- [ ] Threat-model changes are reviewed.
- [ ] No API keys, tokens, personal data, or hidden evaluation seeds are committed.
- [ ] External-effect claims state idempotency and reconciliation assumptions.
- [ ] Model-run reports include provider usage, retries, malformed outputs, dollar cap, and all offered episodes.
