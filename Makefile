SHELL := /bin/zsh

ENV_FILE ?= .env
EXPORT_ZIP ?= /Users/min/Downloads/ecoauc-export-27178494880-gucci.zip
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: help sync db-check migrate import import-dry-run dev smoke-estimate

define with_env
	set -a; \
	source "$(ENV_FILE)"; \
	set +a; \
	$(1)
endef

help:
	@echo "Targets:"
	@echo "  make sync             Install Python dependencies with uv"
	@echo "  make db-check         Check DATABASE_URL connectivity"
	@echo "  make migrate          Apply Supabase/Postgres schema"
	@echo "  make import           Import EcoAuc export ZIP/CSV"
	@echo "  make import-dry-run   Parse export without writing to DB"
	@echo "  make dev              Run FastAPI dev server"
	@echo "  make smoke-estimate   Call local /price-estimate endpoint"
	@echo ""
	@echo "Variables:"
	@echo "  ENV_FILE=$(ENV_FILE)"
	@echo "  EXPORT_ZIP=$(EXPORT_ZIP)"
	@echo "  HOST=$(HOST)"
	@echo "  PORT=$(PORT)"

sync:
	uv sync

db-check:
	$(call with_env,uv run luxury-price-ai db-check)

migrate:
	$(call with_env,uv run luxury-price-ai migrate)

import:
	$(call with_env,uv run luxury-price-ai import "$(EXPORT_ZIP)")

import-dry-run:
	uv run luxury-price-ai import --dry-run "$(EXPORT_ZIP)"

dev:
	$(call with_env,uv run uvicorn luxury_price_ai.api:app --host "$(HOST)" --port "$(PORT)" --reload)

smoke-estimate:
	@set -a; \
	source "$(ENV_FILE)" 2>/dev/null || true; \
	set +a; \
	if [[ -n "$$APP_API_KEY" ]]; then auth_header=(-H "X-API-Key: $$APP_API_KEY"); else auth_header=(); fi; \
	curl -X POST "http://$(HOST):$(PORT)/price-estimate" \
	  -H "content-type: application/json" \
	  "$${auth_header[@]}" \
	  -d '{"brand":"CHANEL","category":"バッグ","shape":"ショルダーバッグ","rank":"AB","title":"CHANEL マトラッセ キャビアスキン 黒 ゴールド金具","limit":20}'
