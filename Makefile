.PHONY: test report verify provider-report live-dry live-fake live-pilot

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

live-fake:
	python3 -m controlled_ai.live --fake-transport --provider anthropic --episodes 4 --cap-usd 0.50

live-pilot:
	python3 -m controlled_ai.pilot --fake-transport --episodes 4 --cap-usd 0.50 --force

replay-check:
	python3 -m unittest tests.test_replay_regression -v

expanded-report:
	python3 -m controlled_ai.expanded > reports/expanded-testing.json
