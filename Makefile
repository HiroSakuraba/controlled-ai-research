.PHONY: test report verify

test:
	python3 -m unittest discover -s tests -v

report:
	python3 -m controlled_ai > reports/finite-run.json

verify:
	python3 tools/verify_report.py
