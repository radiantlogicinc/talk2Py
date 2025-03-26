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
	isort . --skip .venv
	black . --exclude ".venv"
	flake8 . --ignore E501,E122,W503,E402,F401,E203 --exclude .venv
	pylint --recursive=y --ignore=.venv .
	mypy --install-types --non-interactive .
	mypy . --exclude .venv
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