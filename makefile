SHELL = /bin/bash

.EXPORT_ALL_VARIABLES:

# Define a variable for sourcing .env
LOAD_ENV := @if [ -f .env ]; then set -a; source .env; set +a; fi

.PHONY: gen-env lint publish-testpypi publish

gen-env:
	chmod +x ./gen-env.sh
	./gen-env.sh

lint: gen-env
	$(LOAD_ENV)
	py3clean . 
	ruff check . --fix
	black . --exclude ".venv"
	mypy --install-types --non-interactive .
	mypy -p talk2py --exclude .venv
	bandit -c pyproject.toml -r . --exclude ./.venv

test:
	pytest

publish-testpypi: gen-env
	$(LOAD_ENV)
	python -m build
	twine upload --repository testpypi dist/*

publish: gen-env
	$(LOAD_ENV)
	python -m build
	twine upload dist/* 