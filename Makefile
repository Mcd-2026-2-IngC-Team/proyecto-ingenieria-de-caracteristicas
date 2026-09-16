#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_NAME = project_name
PYTHON_VERSION = 3.13
PYTHON_INTERPRETER = python

# Override on the command line: make backup DEST=/path/to/dest
DEST ?= backups

#################################################################################
# COMMANDS                                                                      #
#################################################################################


## Install Python dependencies
.PHONY: requirements
requirements:
	uv sync
	

.PHONY: nb
nb:
	uv run marimo export ipynb $(NOTEBOOK)-marimo.py -o $(NOTEBOOK).ipynb --include-outputs

.PHONY: clean
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf data/raw/*
	rm -rf data/interim/*
	rm -rf data/processed/*

.PHONY: lint
lint:
	uv run ruff format --check
	uv run ruff check

.PHONY: format
format:
	uv run ruff check --fix
	uv run ruff format

## Run tests
.PHONY: test
test:
	uv run pytest tests


## Set up Python interpreter environment
.PHONY: create_environment
create_environment:
	uv venv --python $(PYTHON_VERSION)
	@echo ">>> New uv virtual environment created. Activate with:"
	@echo ">>> Windows: .\\\\.venv\\\\Scripts\\\\activate"
	@echo ">>> Unix/macOS: source ./.venv/bin/activate"
	



#################################################################################
# PROJECT RULES                                                                 #
#################################################################################


## Make dataset
.PHONY: data
data: requirements
	$(PYTHON_INTERPRETER) project_name/dataset.py

## Download DENUE Sonora raw data
.PHONY: ingest
ingest:
	uv run python -m project_name.jobs.ingest_denue_sonora_job

## Process DENUE Sonora data into data/processed
.PHONY: process
process:
	uv run python -m project_name.jobs.process_denue_sonora_job

## Backup data/ to DEST as a tar.gz archive (override with make backup DEST=/path/to/dest)
.PHONY: backup
backup:
	mkdir -p "$(DEST)"
	tar -czf "$(DEST)/data_$$(date +%Y%m%d_%H%M%S).tar.gz" data

# Target-specific (unconditional `=`, not `?=`) so DEST doesn't inherit the
# global default from `backup` above; command-line overrides still win either way.
# e.g make extract-images SOURCE=data/external/dataset_facebook-posts-scraper_2025-10-23-to-2026-09-14.csv
extract-images: SOURCE = data/external/dataset_facebook-posts-scraper_2024-04-07-to-2024-12-31.csv
extract-images: DEST = data/external/facebook/images
extract-images: COLUMN = media/0/photo_image/uri
extract-images: ID_COLUMN = postId
extract-images: ON_EXISTS = skip

## Download images referenced by a CSV column (override SOURCE/DEST/COLUMN/ID_COLUMN)
.PHONY: extract-images
extract-images:
	uv run python -m project_name.jobs.extract_images_job \
		--source "$(SOURCE)" --dest "$(DEST)" --column "$(COLUMN)" --id-column "$(ID_COLUMN)" --on-exists "$(ON_EXISTS)"


#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys; \
lines = '\n'.join([line for line in sys.stdin]); \
matches = re.findall(r'\n## (.*)\n[\s\S]+?\n([a-zA-Z_-]+):', lines); \
print('Available rules:\n'); \
print('\n'.join(['{:25}{}'.format(*reversed(match)) for match in matches]))
endef
export PRINT_HELP_PYSCRIPT

help:
	@$(PYTHON_INTERPRETER) -c "${PRINT_HELP_PYSCRIPT}" < $(MAKEFILE_LIST)
