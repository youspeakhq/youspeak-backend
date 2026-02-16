#!/usr/bin/env bash
# Run CI checks locally (lint, Docker Compose, tests) without pushing.
# Usage: ./scripts/run-ci-local.sh [--no-compose]
#   --no-compose  Skip Docker Compose; run only lint and pytest (requires local postgres/redis or services).
set -e
cd "$(dirname "$0")/.."
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SKIP_COMPOSE=false
for arg in "$@"; do
  [ "$arg" = "--no-compose" ] && SKIP_COMPOSE=true
done

run_lint() {
  echo -e "${YELLOW}[1/4] Linting...${NC}"
  python -m pip install -q -r requirements.txt -r requirements-dev.txt
  flake8 app --count --select=E9,F63,F7,F82 --show-source --statistics
  flake8 app --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
  echo -e "${GREEN}Lint OK${NC}"
}

run_docker_compose() {
  echo -e "${YELLOW}[2/4] Docker Compose (build, up, health, smoke)...${NC}"
  docker compose up -d --build
  for i in $(seq 1 60); do
    curl -sf http://localhost:8000/health >/dev/null 2>&1 && break
    sleep 2
  done
  if ! curl -sf http://localhost:8000/health >/dev/null; then
    echo -e "${RED}API not healthy${NC}"
    docker compose logs api
    docker compose down -v
    exit 1
  fi
  curl -sf http://localhost:8000/docs >/dev/null && echo "Docs OK"
  echo -e "${YELLOW}Running migrations (ensure enum values)...${NC}"
  export DATABASE_URL=postgresql://youspeak_user:youspeak_password@localhost:5455/youspeak_db
  alembic upgrade head 2>/dev/null || true
  echo -e "${GREEN}Docker Compose OK${NC}"
}

run_tests_against_compose() {
  echo -e "${YELLOW}[3/4] Pytest (against Docker Compose API at localhost:8000)...${NC}"
  export DATABASE_URL=postgresql://youspeak_user:youspeak_password@localhost:5455/youspeak_db
  export REDIS_URL=redis://localhost:6379/0
  export SECRET_KEY=dev-secret-key-change-in-production-min-32-characters-long
  export ENVIRONMENT=test
  export TEST_USE_LIVE_SERVER=true
  pytest tests/ -v --cov=app --cov-report=term --no-cov-on-fail
  echo -e "${GREEN}Pytest done${NC}"
}

run_tests_standalone() {
  echo -e "${YELLOW}[3/4] Pytest (standalone, no compose)...${NC}"
  export DATABASE_URL="${DATABASE_URL:-postgresql://test_user:test_password@localhost:5432/test_db}"
  export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
  export SECRET_KEY="${SECRET_KEY:-test-secret-key-for-ci-pipeline-min-32-chars}"
  export ENVIRONMENT=test
  alembic upgrade head 2>/dev/null || true
  pytest tests/ -v --cov=app --cov-report=term --no-cov-on-fail
  echo -e "${GREEN}Pytest done${NC}"
}

stop_compose() {
  echo -e "${YELLOW}[4/4] Stopping Docker Compose...${NC}"
  docker compose down -v
  echo -e "${GREEN}Done.${NC}"
}

# --- main ---
if [ -z "$(command -v python)" ] && [ -n "$(command -v python3)" ]; then
  alias python=python3
fi
if ! python -c "import flake8" 2>/dev/null; then
  echo "Installing dev deps..."
  pip install -q -r requirements.txt -r requirements-dev.txt
fi

run_lint
if [ "$SKIP_COMPOSE" = true ]; then
  run_tests_standalone
else
  run_docker_compose
  run_tests_against_compose
  stop_compose
fi
echo -e "${GREEN}Local CI checks finished.${NC}"