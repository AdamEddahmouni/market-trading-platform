# ──────────────────────────────────────────────────────────────────────
#  Short Squeeze Research Screener  —  Makefile
# ──────────────────────────────────────────────────────────────────────
#  Convenience wrappers around `docker compose` and local dev commands.
#
#  Quick reference:
#      make up         → frozen demo + IB Gateway (default)
#      make up-full    → full LOCAL_FULL mode (screener + live IBKR data)
#      make build      → rebuild screener image
#      make dev        → run directly (no Docker) for rapid iteration
#      make logs       → tail all services
#      make logs-*     → tail a single service (logs-screener, logs-gateway)
#      make down       → stop and remove containers
#      make clean      → down + remove volumes
#      make clean-cache→ remove user-level port cache
#      make ps         → show container status
#      make doctor     → print credential/provider report
# ──────────────────────────────────────────────────────────────────────

.PHONY: help up up-full build dev logs logs-screener logs-gateway
.PHONY: down stop clean clean-cache ps pull doctor doctor-json
.PHONY: deploy deploy-sync deploy-ib-gateway railway-sync-ib-gateway-vars check-railway-mirror tidy precommit precommit-quick install-hooks test-quick

# ── Help ──────────────────────────────────────────────────────────────

help: ## Show this help
	@printf "\033[1mShort Squeeze Research Screener \342\200\224 quick commands\033[0m\n"
	@printf "  \033[36mmake up\033[0m         Start frozen-demo + IB Gateway  (\033[33mdocker compose up\033[0m)\n"
	@printf "  \033[36mmake up-full\033[0m    Full LOCAL_FULL mode             (\033[33moverride + HEALTHY wait\033[0m)\n"
	@printf "  \033[36mmake build\033[0m      Rebuild screener image\n"
	@printf "  \033[36mmake dev\033[0m        Run directly (no Docker)\n"
	@printf "  \033[36mmake logs\033[0m       Tail all containers\n"
	@printf "  \033[36mmake logs-screener\033[0m  Tail screener logs\n"
	@printf "  \033[36mmake logs-gateway\033[0m  Tail IB Gateway logs\n"
	@printf "  \033[36mmake down\033[0m       Stop and remove containers\n"
	@printf "  \033[36mmake clean\033[0m      Down + remove named volumes\n"
	@printf "  \033[36mmake clean-cache\033[0m Remove user-level port cache\n"
	@printf "  \033[36mmake ps\033[0m         Show container status\n"
	@printf "  \033[36mmake doctor\033[0m         Print credential/provider report\n"
	@printf "  \033[36mmake doctor-json\033[0m     Print report as JSON via jq\n"
	@printf "  \033[36mmake deploy\033[0m        Sync source + deploy to Railway\n"
	@printf "  \033[36mmake deploy-ib-gateway\033[0m  Deploy IB Gateway sidecar to Railway\n"
	@printf "  \033[36mmake deploy-sync\033[0m    Sync source into .railway-deploy/ only\n"
	@printf "  \033[36mmake tidy\033[0m          Git garbage collection and cleanup\n"
	@printf "  \033[36mmake precommit\033[0m         Run import checks and lint before committing\n"
	@printf "  \033[36mmake precommit-quick\033[0m  Run import checks only (faster)\n"
	@printf "  \033[36mmake install-hooks\033[0m  Install git pre-commit hook\n"
	@printf "  \033[36mmake test-quick\033[0m      Import checks + fast smoke test\n"
	@printf "\n"

# ── Up \342\200\224 both services (frozen demo + Gateway) ────────────────────────

up: ## Start frozen demo + IB Gateway (no API keys required)
	@printf "\033[32m. Starting screener (frozen demo) + IB Gateway...\033[0m\n"
	docker compose up -d
	@printf "\n  \033[36m->\033[0m Open \033[4mhttp://127.0.0.1:8787/\033[0m\n"
	@printf "  \033[36m->\033[0m Run \033[33mmake logs\033[0m to follow output\n"
	@printf "  \033[36m->\033[0m Run \033[33mmake down\033[0m to stop\n"

# ── Up \342\200\224 full LOCAL_FULL (screener uses live Gateway directly) ────────

up-full: ## Start in full LOCAL_FULL mode (wait for Gateway health)
	@printf "\033[32m. Starting in\033[0m \033[1mLOCAL_FULL\033[0m \033[32mmode with live IBKR data...\033[0m\n"
	docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
	@printf "\n  \033[36m->\033[0m Open \033[4mhttp://127.0.0.1:8787/\033[0m\n"
	@printf "  \033[36m->\033[0m Screener waits for Gateway health check\n"
	@printf "  \033[36m->\033[0m Run \033[33mmake logs\033[0m to watch startup progress\n"

# ── Build ─────────────────────────────────────────────────────────────

build: ## Rebuild the screener image (no cache)
	docker compose build --no-cache
	@printf "\n  \033[32mOK\033[0m Image rebuilt.\n"

# ── Dev (no Docker) ───────────────────────────────────────────────────

dev: ## Run the screener directly (no Docker) for rapid iteration
	@printf "\033[32m. Starting screener directly (no Docker)...\033[0m\n"
	python -m apps.research_screener

# ── Logs ──────────────────────────────────────────────────────────────

logs: ## Tail container logs
	docker compose logs -f

logs-screener: ## Tail only the screener container
	docker compose logs -f screener

logs-gateway: ## Tail only the IB Gateway container
	docker compose logs -f ib-gateway

# ── Lifecycle ─────────────────────────────────────────────────────────

down: ## Stop containers and remove network
	docker compose down
	@printf "\n  \033[32mOK\033[0m Containers stopped and removed.\n"

stop: ## Stop containers without removing them
	docker compose stop
	@printf "\n  \033[32mOK\033[0m Containers stopped.\n"

clean: ## Stop, remove containers, and delete named volumes
	docker compose down -v
	@printf "\n  \033[32mOK\033[0m Containers and volumes removed.\n"

clean-cache: ## Remove the user-level IB Gateway port detection cache
	@rm -f ~/.short-squeeze/ib-gateway-port.json
	@printf "\n  \033[32mOK\033[0m Port cache cleared.\n"

ps: ## Show status of all services
	docker compose ps

pull: ## Pre-pull the IB Gateway image
	docker compose pull ib-gateway
	@printf "\n  \033[32mOK\033[0m ib-gateway image pulled.\n"

# ── Diagnostics ───────────────────────────────────────────────────────

doctor: ## Print credential/provider status report
	python -m apps.research_screener.config doctor

doctor-json: ## Print credential/provider status report as JSON, piped through jq (falls back to json.tool)
	@if command -v jq >/dev/null 2>&1; then \
		python -m apps.research_screener.config doctor --json | jq; \
	else \
		python -m apps.research_screener.config doctor --json | python -m json.tool; \
	fi

# ── Railway deploy (mirrors CI workflow) ──────────────────────────────

deploy-sync: ## Sync latest source into .railway-deploy/ (dry-run before deploy)
	@printf "\033[32m. Syncing source into .railway-deploy/...\033[0m\n"
	rsync -a --delete apps/      .railway-deploy/apps/
	rsync -a --delete src/       .railway-deploy/src/
	rsync -a --delete scripts/   .railway-deploy/scripts/
	rsync -a --delete tools/     .railway-deploy/tools/
	cp  pyproject.toml            .railway-deploy/pyproject.toml
	@printf "\n  \033[32mOK\033[0m Source synced. Run \033[33mmake deploy\033[0m to deploy.\n"

check-railway-mirror: ## Fail if .railway-deploy drifts from apps/src/scripts/tools (prep only)
	python tools/check_railway_mirror.py

deploy: deploy-sync ## Sync latest source and deploy to Railway (mirrors CI pipeline)
	@printf "\033[32m. Deploying to Railway...\033[0m\n"
	@printf "  \033[36m2/4\033[0m Checking Railway CLI...\n"
	@if ! command -v railway >/dev/null 2>&1; then \
		printf "  Railway CLI not found, installing...\n"; \
		bash <(curl -fsSL railway.com/install.sh); \
		. "$$HOME/.railway/env" 2>/dev/null || export PATH="$$HOME/.railway/bin:$$PATH"; \
	fi
	@printf "  \033[36m3/4\033[0m Uploading to Railway...\n"
	cd .railway-deploy && railway up --detach --environment production --service short-squeeze-screener
	@printf "  \033[36m4/4\033[0m Deployment initiated.\n"
	@printf "\n  \033[36m->\033[0m Track progress at \033[4mhttps://railway.app/project/\033[0m\n"
	@printf "  \033[36m->\033[0m Or push to main and watch the GitHub Action.\n"

deploy-ib-gateway: ## Deploy IB Gateway sidecar (see docs/railway-ib-gateway.md)
	@printf "\033[32m. Deploying IB Gateway to Railway...\033[0m\n"
	@if ! command -v railway >/dev/null 2>&1; then \
		printf "  Railway CLI not found, installing...\n"; \
		bash <(curl -fsSL railway.com/install.sh); \
		. "$$HOME/.railway/env" 2>/dev/null || export PATH="$$HOME/.railway/bin:$$PATH"; \
	fi
	cd .railway-deploy/ib-gateway && railway up --detach --environment production --service ib-gateway
	@printf "\n  \033[32mOK\033[0m IB Gateway deploy initiated.\n"
	@printf "  Set TWS_USERID/TWS_PASSWORD on the ib-gateway service and IBKR_HOST=ib-gateway.railway.internal on the screener.\n"
	@printf "  Or run \033[33mmake railway-sync-ib-gateway-vars\033[0m after adding IBKR_USER_ID/IBKR_PASSWORD to .private/providers.env\n"

railway-sync-ib-gateway-vars: ## Push IBKR_USER_ID/PASSWORD from .private/providers.env → Railway ib-gateway
	@printf "\033[32m. Syncing IB Gateway credentials to Railway (ib-gateway service)...\033[0m\n"
	@PRIVATE=".private/providers.env"; \
	if [ ! -f "$$PRIVATE" ]; then \
	  printf "\033[31mMissing $$PRIVATE — add IBKR_USER_ID and IBKR_PASSWORD first.\033[0m\n"; exit 1; \
	fi; \
	USER_ID=$$(grep -E '^IBKR_USER_ID=' "$$PRIVATE" | head -1 | cut -d= -f2- | tr -d '\r' | sed 's/^["'\'']//;s/["'\'']$$//'); \
	PASS=$$(grep -E '^IBKR_PASSWORD=' "$$PRIVATE" | head -1 | cut -d= -f2- | tr -d '\r' | sed 's/^["'\'']//;s/["'\'']$$//'); \
	if [ -z "$$USER_ID" ] || [ -z "$$PASS" ]; then \
	  printf "\033[31mIBKR_USER_ID and IBKR_PASSWORD must be set in $$PRIVATE\033[0m\n"; exit 1; \
	fi; \
	if ! command -v railway >/dev/null 2>&1; then \
	  printf "  Railway CLI not found, installing...\n"; \
	  bash <(curl -fsSL railway.com/install.sh); \
	  . "$$HOME/.railway/env" 2>/dev/null || export PATH="$$HOME/.railway/bin:$$PATH"; \
	fi; \
	printf '%s' "$$USER_ID" | railway variable set TWS_USERID --stdin --skip-deploys --service ib-gateway --environment production; \
	printf '%s' "$$PASS" | railway variable set TWS_PASSWORD --stdin --skip-deploys --service ib-gateway --environment production; \
	railway redeploy --service ib-gateway --environment production --yes; \
	printf "\n  \033[32mOK\033[0m Gateway credentials updated and redeploy triggered.\n"

# ── Maintenance ───────────────────────────────────────────────────────

tidy: ## Run git garbage collection and prune stale objects
	@printf "\033[32m. Running git gc (aggressive)...\033[0m\n"
	git gc --aggressive --prune=now
	@printf "\033[32m. Pruning stale remote-tracking branches...\033[0m\n"
	git remote prune origin 2>/dev/null || true
	@printf "\n  \033[32mOK\033[0m Repository cleaned.\n"

# ── Pre-commit checks ───────────────────────────────────────────────

PRECOMMIT_IMPORTS = \
	apps.research_screener.config \
	apps.research_screener.credentials \
	apps.research_screener.ibkr_gateway \
	apps.research_screener.__main__

precommit-quick: ## Run Python import checks only (fast, no Makefile validation)
	@printf "\033[32m. Import checks...\033[0m\n"
	@fail=0; \
	for mod in $(PRECOMMIT_IMPORTS); do \
		printf "  \033[36mimport\033[0m  %s ... " "$$mod"; \
		if python -c "import $$mod" 2>/dev/null; then \
			printf "\033[32mOK\033[0m\n"; \
		else \
			printf "\033[31mFAIL\033[0m\n"; \
			python -c "import $$mod" 2>&1 | head -3; \
			fail=1; \
		fi; \
	done; \
	if [ "$$fail" -ne 0 ]; then \
		printf "\n  \033[31mFAILED\033[0m \342\200\224 fix import errors before committing.\n"; \
		exit 1; \
	fi
	@printf "\n  \033[32mOK\033[0m All imports passed.\n"

precommit: precommit-quick ## Run import checks and verify Makefile is valid
	@printf "  \033[36mmake help\033[0m ... "; \
	if make help >/dev/null 2>&1; then \
		printf "\033[32mOK\033[0m\n"; \
	else \
		printf "\033[31mFAIL\033[0m\n"; \
		exit 1; \
	fi
	@printf "\n  \033[32mOK\033[0m All pre-commit checks passed.\n"

# ── Testing ────────────────────────────────────────────────────────

test-quick: precommit-quick ## Run import checks and a fast smoke test
	@printf "  \033[36mpytest\033[0m  smoke tests ... "; \
	if python -m pytest tests/test_serialization.py tests/test_contract_validation.py \
		-q --tb=short --no-header --basetemp=.pytest-tmp \
		>/dev/null 2>&1; then \
		printf "\033[32mOK\033[0m\n"; \
	else \
		printf "\033[31mFAIL\033[0m\n"; \
		python -m pytest tests/test_serialization.py tests/test_contract_validation.py \
			-q --tb=short --no-header --basetemp=.pytest-tmp; \
		exit 1; \
	fi
	@printf "\n  \033[32mOK\033[0m Quick tests passed.\n"

install-hooks: ## Install git pre-commit hook that runs 'make precommit'
	@printf "\033[32m. Installing git pre-commit hook...\033[0m\n"
	@mkdir -p .git/hooks
	@printf '#!/bin/sh\n# Installed by `make install-hooks`\n# Runs import checks before every commit.\n# Bypass: SKIP_CHECKS=1 git commit  or  git commit --no-verify\n\nif [ -n "$$SKIP_CHECKS" ]; then exit 0; fi\n\ncd "$$(git rev-parse --show-toplevel)/short-squeeze-core"\nmake precommit\nexit $?\n' > .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
	@printf "\n  \033[32mOK\033[0m Pre-commit hook installed at .git/hooks/pre-commit\n"
	@printf "  Bypass with \033[33mSKIP_CHECKS=1 git commit\033[0m or \033[33mgit commit --no-verify\033[0m\n"
