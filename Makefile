# Nova — client-side quality gates. No network needed beyond initial `make setup`.
# Everything calls the project venv explicitly: bare `python`/`pytest` on a pyenv
# machine resolves to a shim without nova installed (see CLAUDE.md).

VENV ?= .venv
PY := $(VENV)/bin/python

.PHONY: setup hooks test lint lint-fix importlint secretscan check

setup: ## create venv, install dev deps, install git hooks
	test -d $(VENV) || python3 -m venv $(VENV)
	$(PY) -m pip install -e '.[dev]'
	$(MAKE) hooks

hooks: ## route git hooks to the committed .githooks/ directory
	git config core.hooksPath .githooks
	@echo "hooks installed (git config core.hooksPath -> .githooks)"

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check .

lint-fix:
	$(PY) -m ruff check . --fix

importlint: ## C0 contract: contract modules never import feature modules
	$(VENV)/bin/lint-imports

secretscan: ## scan all tracked files for secret patterns + stray transcripts
	$(PY) scripts/check_staged.py --all

check: lint importlint secretscan test ## the full gate; runs in seconds
