.PHONY: help build up down restart-backend restart-worker restart-notification rebuild ps \
        logs logs-backend logs-worker logs-notification logs-gateway logs-db logs-redis logs-rabbitmq \
        clean migrate seed test-load db-shell db-tables

export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
RED := \033[0;31m
NC := \033[0m

POSTGRES_USER ?= claimmesh
POSTGRES_DB ?= claimmesh

help: ## Show available commands
	@echo ""
	@echo "$(BLUE)ClaimMesh - Development Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""

build: ## Build Docker images
	@echo "$(GREEN)Building Docker images...$(NC)"
	docker compose build

up: ## Start all services
	@echo "$(GREEN)Starting services...$(NC)"
	docker compose up -d --build

down: ## Stop all services
	@echo "$(YELLOW)Stopping services...$(NC)"
	docker compose down

restart-backend: ## Restart backend service
	@echo "$(YELLOW)Restarting backend service...$(NC)"
	docker compose restart backend

restart-worker: ## Restart worker service
	@echo "$(YELLOW)Restarting worker service...$(NC)"
	docker compose restart worker

restart-notification: ## Restart notification-service
	@echo "$(YELLOW)Restarting notification-service...$(NC)"
	docker compose restart notification-service

rebuild: ## Clean rebuild from scratch
	@echo "$(RED)Removing containers and volumes...$(NC)"
	docker compose down -v
	@echo "$(GREEN)Rebuilding project...$(NC)"
	docker compose up --build -d

ps: ## List running containers
	docker compose ps

logs: ## Follow logs for all services
	docker compose logs -f

logs-backend: ## Follow backend logs
	docker compose logs -f backend

logs-worker: ## Follow worker logs
	docker compose logs -f worker

logs-notification: ## Follow notification-service logs
	docker compose logs -f notification-service

logs-gateway: ## Follow KrakenD gateway logs
	docker compose logs -f gateway

logs-db: ## Follow PostgreSQL logs
	docker compose logs -f postgres

logs-redis: ## Follow Redis logs
	docker compose logs -f redis

logs-rabbitmq: ## Follow RabbitMQ logs
	docker compose logs -f rabbitmq

clean: ## Remove containers, networks and volumes
	@echo "$(RED)Cleaning Docker resources...$(NC)"
	docker compose down -v

migrate: ## Run Alembic migrations manually
	@echo "$(GREEN)Running Alembic migrations...$(NC)"
	docker compose exec backend uv run alembic upgrade head

seed: ## Load seed/fixture CSVs into the running stack
	@echo "$(GREEN)Seeding database via /upload...$(NC)"
	docker compose exec backend uv run python scripts/seed.py

test-load: ## Run the load test script against the live stack
	@echo "$(GREEN)Running load test...$(NC)"
	docker compose exec backend uv run python tests/load_tester.py

db-shell: ## Open PostgreSQL shell
	docker compose exec postgres psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

db-tables: ## Show database tables
	docker compose exec postgres psql -U $(POSTGRES_USER) -d $(POSTGRES_DB) -c "\dt"

.DEFAULT_GOAL := help
