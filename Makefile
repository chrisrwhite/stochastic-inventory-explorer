SHELL := /bin/bash
PY ?= python3.12
POETRY ?= poetry
BACKEND_RUN := cd backend && $(POETRY) run

# Override with `make deploy PROJECT=my-gcp-project` or export in your shell.
# See docs/deploy.md for the full Cloud Run + Cloudflare walkthrough.
PROJECT ?= your-gcp-project-id
REGION ?= us-east1
SERVICE ?= stochastic-inventory-reorder
IMAGE_TAG ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
IMAGE ?= $(REGION)-docker.pkg.dev/$(PROJECT)/$(SERVICE)/app:$(IMAGE_TAG)

.PHONY: setup setup-backend setup-frontend backend frontend test test-backend test-frontend \
	notebook fetch-open-data fetch-open-data-all fetch-open-data-iowa \
	lint format docker-build docker-run deploy tf-plan tf-apply clean

setup: setup-backend setup-frontend

setup-backend:
	cd backend && $(POETRY) install --with dev --no-root

setup-backend-full:
	cd backend && $(POETRY) install --with dev,notebook --no-root

setup-frontend:
	cd frontend && npm install

fetch-open-data:
	cd backend && $(POETRY) install --with data --no-root
	$(BACKEND_RUN) python ../scripts/fetch_open_datasets.py --dataset uci

fetch-open-data-all:
	cd backend && $(POETRY) install --with data --no-root
	$(BACKEND_RUN) python ../scripts/fetch_open_datasets.py --dataset all

fetch-open-data-iowa:
	cd backend && $(POETRY) install --with data --no-root
	$(BACKEND_RUN) python ../scripts/fetch_open_datasets.py --dataset iowa

backend:
	$(BACKEND_RUN) uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

notebook:
	cd backend && $(POETRY) install --with notebook --no-root
	cd backend && $(POETRY) run jupyter lab ../notebooks/inventory_workflow_walkthrough.ipynb

test: test-backend test-frontend

test-backend:
	$(BACKEND_RUN) pytest

test-frontend:
	cd frontend && npm test

lint:
	$(BACKEND_RUN) ruff check .
	cd frontend && npm run lint

format:
	$(BACKEND_RUN) ruff format .
	$(BACKEND_RUN) ruff check --fix .

docker-build:
	docker build -f docker/Dockerfile -t $(SERVICE):$(IMAGE_TAG) .

docker-run:
	docker run --rm -p 8080:8080 -e PORT=8080 $(SERVICE):$(IMAGE_TAG)

# Manual image push + rollout, for testing a build without going through
# `git push`. Service configuration (CPU, memory, concurrency, scaling,
# timeout, MAX_* env vars) is owned by Terraform in infra/ -- this passes
# --image only, which leaves those settings untouched. Add sizing flags in
# infra/variables.tf, not here.
deploy:
	gcloud run deploy $(SERVICE) \
		--image $(IMAGE) \
		--region $(REGION)

tf-plan:
	cd infra && terraform plan

tf-apply:
	cd infra && terraform apply

clean:
	rm -rf .venv backend/.venv frontend/node_modules frontend/dist
	find backend -type d -name __pycache__ -exec rm -rf {} +
	find backend -type d -name .pytest_cache -exec rm -rf {} +
