.PHONY: demo-up demo-down demo-clean demo-logs demo-test demo-chaos-test
.PHONY: py-compile py_compile relay-pytest relay_pytest
.PHONY: ci-local

COMPOSE ?= docker compose
COMPOSE_FILE ?= docker/docker-compose.yml
COMPOSE_PROJECT_NAME ?= altezhong_demo

TAIL ?= 200
SINCE ?=

CI_OUTPUT_DIR ?= ci-output
FULL ?= 0

demo-up:
	COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) $(COMPOSE) -f $(COMPOSE_FILE) --profile demo up -d --wait

demo-down:
	COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) $(COMPOSE) -f $(COMPOSE_FILE) --profile demo down

demo-clean:
	COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) $(COMPOSE) -f $(COMPOSE_FILE) --profile demo down -v --remove-orphans

demo-logs:
	COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) $(COMPOSE) -f $(COMPOSE_FILE) --profile demo logs --no-color --tail $(TAIL) $(if $(SINCE),--since $(SINCE),)

demo-test:
	COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) $(COMPOSE) -f $(COMPOSE_FILE) --profile demo up -d --wait
	COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) $(COMPOSE) -f $(COMPOSE_FILE) --profile demo run --rm tester

demo-chaos-test:
	COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) $(COMPOSE) -f $(COMPOSE_FILE) --profile demo --profile chaos up -d --wait
	COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) $(COMPOSE) -f $(COMPOSE_FILE) --profile demo --profile chaos run --rm tester

py-compile:
	python -m py_compile scripts/run_demo_servers.py
	python -m py_compile scripts/test_feature_similarity.py
	python -m py_compile scripts/ci/validate_trivyignore.py

py_compile: py-compile

relay-pytest:
	python -m pip install --upgrade pip
	python -m pip install -r pc/relay/requirements.txt
	cd pc/relay && python -m pytest tests/ -v

relay_pytest: relay-pytest

ci-local:
	mkdir -p $(CI_OUTPUT_DIR)
	$(MAKE) py-compile > $(CI_OUTPUT_DIR)/static-check.log 2>&1
	$(MAKE) relay-pytest >> $(CI_OUTPUT_DIR)/static-check.log 2>&1
	cat $(CI_OUTPUT_DIR)/static-check.log
	@if [ "$(FULL)" = "1" ]; then \
		status=0; \
		$(MAKE) demo-test > $(CI_OUTPUT_DIR)/e2e-demo.log 2>&1 || status=$$?; \
		cat $(CI_OUTPUT_DIR)/e2e-demo.log; \
		$(MAKE) demo-logs > $(CI_OUTPUT_DIR)/demo-logs.txt || true; \
		$(MAKE) demo-clean || true; \
		exit $$status; \
	else \
		echo "ci-local: FULL=0, skipping demo-test/trivy/clang-tidy. Run: make ci-local FULL=1" > $(CI_OUTPUT_DIR)/ci-local.note; \
		cat $(CI_OUTPUT_DIR)/ci-local.note; \
	fi
