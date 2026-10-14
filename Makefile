APP_VERSION := 0.1.0

.PHONY: help env web-install api-test worker-test web-test test compose-up compose-down lint

help:
	@echo RoadVision $(APP_VERSION)
	@echo Targets:
	@echo   env            Copy .env.example to .env if missing
	@echo   web-install    Install frontend dependencies
	@echo   api-test       Run API tests
	@echo   worker-test    Run worker tests
	@echo   web-test       Run frontend tests
	@echo   test           Run API, worker, and web tests
	@echo   compose-up     Build and start Docker Compose
	@echo   compose-down   Stop Docker Compose

env:
	@test -f .env || cp .env.example .env

web-install:
	cd apps/web && npm install

api-test:
	cd services/api && python -m pytest tests -q

worker-test:
	cd services/worker && python -m pytest tests -q

web-test:
	cd apps/web && npm test

test: api-test worker-test web-test

compose-up:
	docker compose up --build

compose-down:
	docker compose down
