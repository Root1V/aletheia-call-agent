# Copiloto de Atención al Cliente Bancario
#
#   make up && make migrate && make seed     # una vez
#   make dev                                 # API + portal
#
# Los puertos publicados se configuran en infra/.env. El de Redis sale por el
# 6380 porque el 6379 ya lo ocupa otro servicio en la máquina de desarrollo.

COMPOSE := docker compose -f infra/docker-compose.yml
PSQL    := docker exec -i cea-postgres psql -U cea -d cea -v ON_ERROR_STOP=1

.DEFAULT_GOAL := help
.PHONY: help up down logs migrate seed admin models audio kb replay eval-asr api web dev test lint fmt check clean reset

help:  ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

up:  ## Levanta Postgres, Redis, MinIO, Keycloak y LiveKit
	$(COMPOSE) up -d
	@echo "Esperando a Postgres..."
	@until docker exec cea-postgres pg_isready -U cea -d cea >/dev/null 2>&1; do sleep 1; done
	@echo "Infraestructura lista."

down:  ## Detiene los servicios (conserva los datos)
	$(COMPOSE) down

logs:  ## Sigue los logs de la infraestructura
	$(COMPOSE) logs -f

migrate:  ## Aplica las migraciones en orden
	@for f in infra/migrations/*.sql; do \
		echo "  aplicando $$f"; \
		$(PSQL) -q < "$$f" || exit 1; \
	done
	@echo "Migraciones aplicadas."

seed:  ## Carga el dataset sintético es-PE (reproducible por semilla)
	uv run cea-seed --customers 150

admin:  ## Crea el primer usuario del portal. USER=... NAME="..."
	@test -n "$(USER)" || (echo 'Uso: make admin USER=carlos NAME="Carlos Ruiz"'; exit 1)
	uv run python scripts/create_admin.py --username "$(USER)" --name "$(NAME)" --generate-password

models:  ## Descarga los modelos de voz a models/ (muestra sus licencias)
	uv run python scripts/fetch_models.py

audio:  ## Renderiza los guiones de evals/scenarios a audio (requiere macOS)
	uv run python scripts/make_audio.py

kb:  ## Indexa la base de conocimiento (requiere credenciales de la plataforma)
	uv run python scripts/index_kb.py

replay:  ## Reproduce un guion como llamada en vivo (SCENARIO=... VEL=...)
	uv run cea-replay --scenario $(or $(SCENARIO),disputa_cargo_no_reconocido) \
		--velocidad $(or $(VEL),1.0)

eval-asr:  ## Evalúa el reconocimiento sobre los guiones, limpio y con telefonía
	uv run python evals/runners/asr_eval.py --detalle

api:  ## Arranca la API en :8000
	uv run uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

web:  ## Arranca el portal en :5180
	cd apps/web && npm run dev

dev:  ## Arranca API y portal a la vez
	@$(MAKE) -j2 api web

test:  ## Ejecuta la suite completa
	uv run pytest -q

lint:  ## Revisa estilo y tipos
	uv run ruff check .
	cd apps/web && npx tsc -b --noEmit && npx eslint .

fmt:  ## Formatea el código Python
	uv run ruff check --fix .
	uv run ruff format .

check: lint test  ## Lint + tests

reset:  ## Recrea la base desde cero y vuelve a sembrar
	$(COMPOSE) rm -sf postgres
	docker volume rm cea_postgres_data || true
	@$(MAKE) up migrate seed
	@echo "Recordar crear el usuario:  make admin USER=... NAME=\"...\""

clean:  ## Elimina contenedores y volúmenes. DESTRUCTIVO.
	$(COMPOSE) down -v
