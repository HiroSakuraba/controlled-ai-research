.PHONY: test report verify provider-report live-dry

test:
	python3 -m unittest discover -s tests -v

report:
	python3 -m controlled_ai.landscape > reports/perturbation-map.json
	python3 -m controlled_ai > reports/finite-run.json

provider-report:
	python3 -m controlled_ai.providers

verify:
	python3 tools/verify_report.py

live-dry:
	python3 -m controlled_ai.live --dry-run --episodes 16 --cap-usd 1.00

replay-check:
	python3 -m unittest tests.test_replay_regression -v
