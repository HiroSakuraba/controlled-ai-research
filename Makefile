.PHONY: test report verify provider-report

test:
	python3 -m unittest discover -s tests -v

report:
	python3 -m controlled_ai > reports/finite-run.json

provider-report:
	python3 -m controlled_ai.providers

verify:
	python3 tools/verify_report.py
