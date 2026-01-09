# =============================================================================
# Microservices - Makefile
# =============================================================================
# Usage:
#   make help          - Show available commands
#   make up            - Start all services
#   make down          - Stop all services
#   make logs          - Follow logs from all services
#   make build         - Build all Docker images
# =============================================================================

.PHONY: help up down logs build rebuild clean ps shell-% test validate

# Default goal
.DEFAULT_GOAL := help

# Colors for output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

# Docker Compose command
DC := docker compose

# -----------------------------------------------------------------------------
# HELP
# -----------------------------------------------------------------------------

help: ## Show this help message
	@echo ""
	@echo "$(CYAN)Kaumer Microservices - Available Commands$(RESET)"
	@echo "==========================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# -----------------------------------------------------------------------------
# DOCKER COMPOSE COMMANDS
# -----------------------------------------------------------------------------

up: validate ## Start all services in detached mode
	@echo "$(CYAN)Starting all services...$(RESET)"
	$(DC) up -d
	@echo "$(GREEN)✅ All services started$(RESET)"
	@make ps

up-build: validate ## Build and start all services
	@echo "$(CYAN)Building and starting all services...$(RESET)"
	$(DC) up -d --build
	@echo "$(GREEN)✅ All services built and started$(RESET)"
	@make ps

down: ## Stop all services
	@echo "$(YELLOW)Stopping all services...$(RESET)"
	$(DC) down
	@echo "$(GREEN)✅ All services stopped$(RESET)"

down-v: ## Stop all services and remove volumes
	@echo "$(RED)Stopping all services and removing volumes...$(RESET)"
	$(DC) down -v --remove-orphans
	@echo "$(GREEN)✅ All services stopped and volumes removed$(RESET)"

restart: down up ## Restart all services

ps: ## Show status of all services
	@echo "$(CYAN)Service Status:$(RESET)"
	$(DC) ps

logs: ## Follow logs from all services
	$(DC) logs -f

logs-%: ## Follow logs from a specific service (e.g., make logs-rabbitmq)
	$(DC) logs -f $*

# -----------------------------------------------------------------------------
# BUILD COMMANDS
# -----------------------------------------------------------------------------

build: ## Build all Docker images
	@echo "$(CYAN)Building all images...$(RESET)"
	$(DC) build
	@echo "$(GREEN)✅ All images built$(RESET)"

build-%: ## Build a specific service (e.g., make build-bot_whatsapp)
	@echo "$(CYAN)Building $*...$(RESET)"
	$(DC) build $*
	@echo "$(GREEN)✅ $* built$(RESET)"

rebuild: ## Force rebuild all images (no cache)
	@echo "$(CYAN)Rebuilding all images (no cache)...$(RESET)"
	$(DC) build --no-cache
	@echo "$(GREEN)✅ All images rebuilt$(RESET)"

pull: ## Pull latest base images
	@echo "$(CYAN)Pulling latest images...$(RESET)"
	$(DC) pull
	@echo "$(GREEN)✅ Images pulled$(RESET)"

# -----------------------------------------------------------------------------
# DEVELOPMENT COMMANDS
# -----------------------------------------------------------------------------

shell-%: ## Open a shell in a running container (e.g., make shell-bot_whatsapp)
	$(DC) exec $* /bin/sh

exec-%: ## Execute a command in a container (e.g., make exec-postgres CMD="psql -U postgres")
	$(DC) exec $* $(CMD)

# -----------------------------------------------------------------------------
# INFRASTRUCTURE COMMANDS
# -----------------------------------------------------------------------------

infra-up: ## Start only infrastructure services (rabbitmq, redis, postgres, mongo)
	@echo "$(CYAN)Starting infrastructure services...$(RESET)"
	$(DC) up -d rabbitmq redis postgres mongo
	@echo "$(GREEN)✅ Infrastructure services started$(RESET)"

infra-down: ## Stop only infrastructure services
	@echo "$(YELLOW)Stopping infrastructure services...$(RESET)"
	$(DC) stop rabbitmq redis postgres mongo
	@echo "$(GREEN)✅ Infrastructure services stopped$(RESET)"

# -----------------------------------------------------------------------------
# DATABASE COMMANDS
# -----------------------------------------------------------------------------

db-migrate: ## Run database migrations (customize per service as needed)
	@echo "$(CYAN)Running database migrations...$(RESET)"
	@echo "$(YELLOW)Note: Implement migrations in each service's Dockerfile or entrypoint$(RESET)"

psql: ## Connect to PostgreSQL
	$(DC) exec postgres psql -U postgres

mongo-shell: ## Connect to MongoDB
	$(DC) exec mongo mongosh -u admin -p

redis-cli: ## Connect to Redis
	$(DC) exec redis redis-cli

# -----------------------------------------------------------------------------
# UTILITY COMMANDS
# -----------------------------------------------------------------------------

validate: ## Validate docker-compose.yml
	@echo "$(CYAN)Validating docker-compose.yml...$(RESET)"
	@$(DC) config --quiet 2>/dev/null && echo "$(GREEN)✅ Configuration is valid$(RESET)" || (echo "$(RED)❌ Configuration error$(RESET)" && exit 1)

clean: ## Clean up unused Docker resources
	@echo "$(YELLOW)Cleaning up Docker resources...$(RESET)"
	docker system prune -f
	@echo "$(GREEN)✅ Cleanup complete$(RESET)"

clean-all: down-v clean ## Stop everything and clean all resources
	@echo "$(RED)Removing all project images...$(RESET)"
	docker images | grep kaumer | awk '{print $$3}' | xargs -r docker rmi -f
	@echo "$(GREEN)✅ Full cleanup complete$(RESET)"

env-setup: ## Create .env from .env.example
	@if [ -f .env ]; then \
		echo "$(YELLOW)⚠️  .env already exists. Skipping...$(RESET)"; \
	else \
		cp .env.example .env; \
		echo "$(GREEN)✅ .env created from .env.example$(RESET)"; \
		echo "$(YELLOW)📝 Please edit .env and configure your values$(RESET)"; \
	fi

# -----------------------------------------------------------------------------
# HEALTHCHECK
# -----------------------------------------------------------------------------

health: ## Check health of all services
	@echo "$(CYAN)Checking service health...$(RESET)"
	@echo ""
	@echo "RabbitMQ:"
	@$(DC) exec -T rabbitmq rabbitmq-diagnostics -q ping 2>/dev/null && echo "  $(GREEN)✅ Healthy$(RESET)" || echo "  $(RED)❌ Unhealthy$(RESET)"
	@echo ""
	@echo "Redis:"
	@$(DC) exec -T redis redis-cli ping 2>/dev/null | grep -q PONG && echo "  $(GREEN)✅ Healthy$(RESET)" || echo "  $(RED)❌ Unhealthy$(RESET)"
	@echo ""
	@echo "PostgreSQL:"
	@$(DC) exec -T postgres pg_isready -U postgres 2>/dev/null && echo "  $(GREEN)✅ Healthy$(RESET)" || echo "  $(RED)❌ Unhealthy$(RESET)"
	@echo ""
	@echo "MongoDB:"
	@$(DC) exec -T mongo mongosh --eval "db.adminCommand('ping')" --quiet 2>/dev/null && echo "  $(GREEN)✅ Healthy$(RESET)" || echo "  $(RED)❌ Unhealthy$(RESET)"

# -----------------------------------------------------------------------------
# CODE QUALITY (LINTING & FORMATTING)
# -----------------------------------------------------------------------------

SERVICES := servicio_bot_whatsapp servicio_empresas servicio_mototaxis servicio_pedidos
VENV := .venv/bin

lint: ## Run Ruff linter on all services
	@echo "$(CYAN)Running Ruff linter...$(RESET)"
	@$(VENV)/ruff check $(SERVICES)
	@echo "$(GREEN)✅ All linting checks passed$(RESET)"

lint-fix: ## Fix auto-fixable linting issues
	@echo "$(CYAN)Fixing linting issues...$(RESET)"
	@$(VENV)/ruff check $(SERVICES) --fix
	@echo "$(GREEN)✅ Auto-fix complete$(RESET)"

format: ## Format code with Black
	@echo "$(CYAN)Formatting code with Black...$(RESET)"
	@$(VENV)/black $(SERVICES)
	@echo "$(GREEN)✅ Code formatted$(RESET)"

format-check: ## Check if code is properly formatted
	@echo "$(CYAN)Checking code formatting...$(RESET)"
	@$(VENV)/black --check $(SERVICES)
	@echo "$(GREEN)✅ Code is properly formatted$(RESET)"

quality: lint format-check ## Run all code quality checks
	@echo "$(GREEN)✅ All quality checks passed$(RESET)"

quality-fix: lint-fix format ## Fix all code quality issues
	@echo "$(GREEN)✅ All quality issues fixed$(RESET)"

venv-setup: ## Setup virtual environment with dev tools
	@echo "$(CYAN)Setting up virtual environment...$(RESET)"
	@python3 -m venv .venv
	@$(VENV)/pip install --upgrade pip ruff black --quiet
	@echo "$(GREEN)✅ Virtual environment ready$(RESET)"
	@echo "$(YELLOW)Run: source .venv/bin/activate$(RESET)"

