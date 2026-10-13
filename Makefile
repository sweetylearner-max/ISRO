# ExoSeer — developer convenience targets.
#
# Backend runs from backend/.venv; frontend from frontend/ via npm.
# `make warm` pre-fetches the gallery stars so the MAST cache is hot before a demo.

# The local backend usually serves on :8000, but may run on :8010 if 8000 is taken.
# Override per invocation, e.g.  make warm BACKEND_URL=http://localhost:8010
BACKEND_URL ?= http://localhost:8000

# Gallery star IDs to pre-warm (AGENTS.md §9.4). Space-separated; multi-word IDs
# are quoted so the shell keeps each as one argument.
WARM_TARGETS := "Kepler-8 b" "Kepler-10 b" "Kepler-90" "Kepler-7 b" "TRAPPIST-1" "KIC 9246715"

.PHONY: install dev-backend dev-frontend test warm compose

## install: set up the backend virtualenv + deps and install frontend packages.
install:
	cd backend && python3.11 -m venv .venv && \
		./.venv/bin/pip install --upgrade pip && \
		./.venv/bin/pip install -r requirements.txt
	cd frontend && npm install

## dev-backend: run the FastAPI app locally with autoreload on :8000.
dev-backend:
	cd backend && ./.venv/bin/uvicorn app.main:app --reload --port 8000

## dev-frontend: run the Next.js dev server (:3000).
dev-frontend:
	cd frontend && npm run dev

## test: run the backend test suite against cached fixtures.
test:
	cd backend && ./.venv/bin/python -m pytest tests/

## warm: POST /analyze for each gallery star to pre-warm the MAST cache before a demo.
##       Uses BACKEND_URL (default http://localhost:8000).
warm:
	@echo "Pre-warming ExoSeer cache via $(BACKEND_URL) ..."
	@for target in $(WARM_TARGETS); do \
		echo "  -> $$target"; \
		curl -s -X POST "$(BACKEND_URL)/analyze" \
			-H "Content-Type: application/json" \
			-d "{\"source\": \"mast\", \"target\": \"$$target\"}" \
			-o /dev/null -w "     HTTP %{http_code}\n" || true; \
	done
	@echo "Done. Give jobs a moment to finish, then re-run gallery stars for hot results."

## compose: build and run the whole app (backend + frontend) with Docker.
compose:
	docker compose up --build
