.PHONY: dev test lint format clean docker-up docker-down help

# ===========================
# Development
# ===========================

dev: ## Start backend dev server
	cd backend && uv run uvicorn eng_memory_os.cmd.api_server:create_app --factory --reload --port 8000

dev-frontend: ## Start frontend dev server
	cd frontend && npm run dev

dev-all: ## Start all services via docker-compose
	docker-compose up --build

dev-local: ## Start databases in Docker, run app services (API, Worker, UI) locally in parallel
	python ../run_local.py


# ===========================
# Testing
# ===========================

test: ## Run all tests
	cd backend && uv run pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	cd backend && uv run pytest tests/unit/ -v --tb=short

test-integration: ## Run integration tests (requires Docker services)
	cd backend && uv run pytest tests/integration/ -v --tb=short

test-e2e: ## Run end-to-end tests
	cd backend && uv run pytest tests/e2e/ -v --tb=short

test-cov: ## Run tests with coverage report
	cd backend && uv run pytest tests/ -v --cov=src/eng_memory_os --cov-report=term-missing --cov-report=html

# ===========================
# Code Quality
# ===========================

lint: ## Run linter
	cd backend && uv run ruff check src/ tests/

lint-fix: ## Run linter with auto-fix
	cd backend && uv run ruff check src/ tests/ --fix

format: ## Format code
	cd backend && uv run ruff format src/ tests/

typecheck: ## Run type checker
	cd backend && uv run pyright src/

quality: lint typecheck ## Run all quality checks

# ===========================
# Docker
# ===========================

docker-up: ## Start all Docker services
	docker-compose up -d

docker-up-local-llm: ## Start all Docker services including Ollama
	docker-compose --profile local-llm up -d

docker-down: ## Stop all Docker services
	docker-compose down

docker-clean: ## Stop services and remove volumes
	docker-compose down -v

docker-build: ## Build all Docker images
	docker-compose build

# ===========================
# Database
# ===========================

db-migrate: ## Run database migrations
	cd backend && uv run alembic upgrade head

db-revision: ## Create a new migration revision
	cd backend && uv run alembic revision --autogenerate -m "$(msg)"

db-downgrade: ## Downgrade database by one revision
	cd backend && uv run alembic downgrade -1

# ===========================
# Setup
# ===========================

setup: ## Initial project setup
	cd backend && uv sync
	cd frontend && npm install
	cp -n .env.example .env || true
	@echo "Setup complete. Edit .env with your API keys."

clean: ## Clean build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/dist backend/build
	rm -rf frontend/.next frontend/out

# ===========================
# Help
# ===========================

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
