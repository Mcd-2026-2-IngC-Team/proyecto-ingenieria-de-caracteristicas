# `make help` lists every rule with its description ("## ..." at the end of the line).
.DEFAULT_GOAL := help
# Rules run one after another even with -j: `download` already works in parallel,
# and `process` must wait for its raw data.
.NOTPARALLEL:
.PHONY: help requirements test lint format clean nb \
	data download ingest ingest-dcah ingest-mg-streets process verify-data backup \
	snapshot extract-images requirements-ocr ocr ocr-image

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "%-20s %s\n", $$1, $$2}'

# --- Environment and code ------------------------------------------------------

requirements: ## Install Python dependencies (creates .venv)
	uv sync

test: ## Run tests
	uv run pytest tests

lint: ## Check formatting and lint with ruff
	uv run ruff format --check
	uv run ruff check

format: ## Fix lint and format with ruff
	uv run ruff check --fix
	uv run ruff format

clean: ## Delete caches and data/raw, data/interim, data/processed
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf data/raw/* data/interim/* data/processed/*

nb: ## Export a marimo notebook with outputs (NOTEBOOK=notebooks/<name>, without -marimo.py)
	uv run marimo export ipynb $(NOTEBOOK)-marimo.py -o $(NOTEBOOK).ipynb --include-outputs

# --- Reproducible pipeline -----------------------------------------------------

data: download process ## Download every raw source and build the processed datasets

download: ## Download every raw source in parallel, each with its FUENTE.txt
	uv run python -m project_name.jobs.download_job

ingest: ## Download DENUE Sonora raw data
	uv run python -m project_name.jobs.ingest_denue_sonora_job

ingest-dcah: ## Download Sonora's colonias (INEGI DCAH 2025) raw data
	uv run python -m project_name.jobs.ingest_dcah_job

ingest-mg-streets: ## Download Sonora's streets (INEGI geostatistical framework 2025) raw data
	uv run python -m project_name.jobs.ingest_mg_streets_job

process: ## Process DENUE Sonora data into data/processed
	uv run python -m project_name.jobs.process_denue_sonora_job

verify-data: ## Verify data/external against data/external.sha256 (see data/SNAPSHOT.md)
	uv run python -m project_name.jobs.snapshot_external_job --verify

backup: DEST = backups
backup: ## Back up data/ as a tar.gz in DEST (default backups/)
	mkdir -p "$(DEST)"
	tar -czf "$(DEST)/data_$$(date +%Y%m%d_%H%M%S).tar.gz" data

# --- Acquisition: already run and not reproducible (paid scraper, expiring URLs,
#     hardware-dependent OCR); its outputs live in the data/external snapshot.

snapshot: ## Freeze data/external: data/external.sha256 + tar.gz in backups/
	uv run python -m project_name.jobs.snapshot_external_job --write

extract-images: SOURCE = data/external/dataset_facebook-posts-scraper_2024-04-07-to-2024-12-31.csv
extract-images: DEST = data/external/facebook/images
extract-images: COLUMN = media/0/photo_image/uri
extract-images: ID_COLUMN = postId
extract-images: ON_EXISTS = skip
extract-images: ## Download images referenced by a CSV column (override SOURCE, DEST, COLUMN, ID_COLUMN)
	uv run python -m project_name.jobs.extract_images_job \
		--source "$(SOURCE)" --dest "$(DEST)" --column "$(COLUMN)" --id-column "$(ID_COLUMN)" --on-exists "$(ON_EXISTS)"

# TORCH: cpu (PyPI) or rocm (AMD GPUs, e.g. Yuca). Empty DEVICE = ocr.device from params.yml.
TORCH ?= cpu
DEVICE ?=
OCR_JOB = uv run --extra ocr --extra $(TORCH) python -m project_name.jobs.ocr_images_job \
	$(if $(DEVICE),--device "$(DEVICE)")

requirements-ocr: ## Install the heavy OCR dependencies (TORCH=cpu|rocm)
	uv sync --extra ocr --extra $(TORCH)

ocr: MANIFEST = data/external/facebook/images/dataset_facebook-posts-scraper_2025-10-23-to-2026-09-14/manifest_media-0-photo_image-uri.csv
ocr: requirements-ocr ## Run OCR over the images of a manifest (override MANIFEST, TORCH, DEVICE)
	$(OCR_JOB) --manifest "$(MANIFEST)"

ocr-image: requirements-ocr ## Run OCR on one image and print its text (IMAGE=...; override TORCH, DEVICE)
	$(OCR_JOB) --image "$(IMAGE)"
