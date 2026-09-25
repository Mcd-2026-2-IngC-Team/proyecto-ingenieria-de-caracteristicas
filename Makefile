# `make help` lists every rule with its description ("## ..." at the end of the line),
# grouped by the "##@" section headers.
.DEFAULT_GOAL := help
.PHONY: help requirements test lint format clean nb \
	data download validate verify-data backup dictionary \
	snapshot extract-images requirements-ocr ocr ocr-image

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} /^##@/ {printf "\n%s\n", substr($$0, 5); next} /^[a-zA-Z_-]+:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

##@ Environment and code

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

nb: ## Export notebooks/marimo/NOTEBOOK.py to notebooks/ with outputs
	uv run marimo export ipynb notebooks/marimo/$(NOTEBOOK).py -o notebooks/$(NOTEBOOK).ipynb --include-outputs

##@ Reproducible pipeline

data: download ## Download every raw source and build the processed datasets
	uv run python -m project_name.jobs.process_publicaciones_aguah_job
	uv run python -m project_name.jobs.process_colonias_hermosillo_job
	uv run python -m project_name.jobs.process_ubicaciones_aviso_job
	uv run python -m project_name.jobs.process_baches_job
	uv run python -m project_name.jobs.process_subcuencas_job
	uv run python -m project_name.jobs.validate_data_job

download: ## Download every raw source in parallel, each with its FUENTE.txt
	uv run python -m project_name.jobs.download_job

validate: ## Check data/processed against the quality rules in project_name/schemas.py
	uv run python -m project_name.jobs.validate_data_job

verify-data: ## Check data/external against its snapshot checksums (data/SNAPSHOT.md)
	uv run python -m project_name.jobs.snapshot_external_job --verify

dictionary: ## Regenerate the data dictionaries in references/
	uv run python -m project_name.metadata.dictionary

backup: DEST = backups
backup: ## Back up data/ as a tar.gz in DEST (default backups/)
	mkdir -p "$(DEST)"
	tar -czf "$(DEST)/data_$$(date +%Y%m%d_%H%M%S).tar.gz" data

##@ Acquisition (already run, not reproducible; outputs in the data/external snapshot)
# Paid scraper, expiring image URLs and hardware-dependent OCR. See slurm/README.md.

snapshot: ## Freeze data/external: data/external.sha256 + tar.gz in backups/
	uv run python -m project_name.jobs.snapshot_external_job --write

extract-images: SOURCE = data/external/dataset_facebook-posts-scraper_2024-04-07-to-2024-12-31.csv
extract-images: DEST = data/external/facebook/images
extract-images: COLUMN = media/0/photo_image/uri
extract-images: ID_COLUMN = postId
extract-images: ON_EXISTS = skip
extract-images: ## Download the images a CSV column links to (SOURCE, DEST, COLUMN, ID_COLUMN)
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
