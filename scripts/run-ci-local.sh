#!/usr/bin/env bash
# Run CI locally using Docker Compose (same as GitHub Actions: compose + test job).
# Uses docker-compose.ci.yml so API runs with ENVIRONMENT=test (no create_all);
# Alembic in the test container is the single source of schema, avoiding duplicate table/column errors.
#
# Usage: ./scripts/run-ci-local.sh [--no-compose]
#   (default)    Full CI: compose up → smoke test → run test container → compose down
#   --no-compose  Skip compose; run lint + pytest on host (needs local postgres/redis or services).
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

run_compose_and_test_container() {
  echo -e "${YELLOW}[1/4] Create .env for Docker Compose...${NC}"
  [ -f .env ] || cp .env.example .env

  echo -e "${YELLOW}[2/4] Docker Compose: build and start (api, postgres, redis) with CI override...${NC}"
  docker compose -f docker-compose.yml -f docker-compose.ci.yml up -d --build

  echo -e "${YELLOW}Waiting for API health...${NC}"
  for i in $(seq 1 60); do
    curl -sf http://localhost:8000/health >/dev/null 2>&1 && break
    sleep 2
  done
  if ! curl -sf http://localhost:8000/health >/dev/null; then
    echo -e "${RED}API not healthy${NC}"
    docker compose -f docker-compose.yml -f docker-compose.ci.yml logs api
    docker compose -f docker-compose.yml -f docker-compose.ci.yml down -v
    exit 1
  fi
  echo -e "${GREEN}API healthy${NC}"

  echo -e "${YELLOW}Smoke test...${NC}"
  curl -sf http://localhost:8000/docs >/dev/null && echo "Docs OK"
  curl -sf http://localhost:8000/api/v1/health >/dev/null 2>&1 || curl -sf http://localhost:8000/health >/dev/null && echo "Health OK"

  echo -e "${YELLOW}[3/4] Run tests inside Compose (flake8, alembic, pytest)...${NC}"
  docker compose -f docker-compose.yml -f docker-compose.ci.yml run --rm test
  echo -e "${GREEN}Test container passed${NC}"

  echo -e "${YELLOW}[4/4] Stopping Docker Compose...${NC}"
  docker compose -f docker-compose.yml -f docker-compose.ci.yml down -v
  echo -e "${GREEN}Done.${NC}"
}

run_lint() {
  echo -e "${YELLOW}[1/3] Linting...${NC}"
  python3 -m flake8 app --count --select=E9,F63,F7,F82 --show-source --statistics
  python3 -m flake8 app --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
  echo -e "${GREEN}Lint OK${NC}"
}

check_db_reachable() {
  local url="${1:-$DATABASE_URL}"
  local host="localhost" port="5432"
  if [[ "$url" =~ postgresql(\+asyncpg)?://[^/@]*@?([^:/]+):([0-9]+)/ ]]; then
    host="${BASH_REMATCH[2]}"
    port="${BASH_REMATCH[3]}"
  fi
  if command -v nc >/dev/null 2>&1; then
    nc -z "$host" "$port" 2>/dev/null && return 0
  fi
  if python3 -c "
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(('$host', $port))
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
    return 0
  fi
  return 1
}

run_tests_standalone() {
  echo -e "${YELLOW}[2/3] Migrations + pytest (standalone)...${NC}"
  export DATABASE_URL="${DATABASE_URL:-postgresql://test_user:test_password@localhost:5432/test_db}"
  export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
  export SECRET_KEY="${SECRET_KEY:-test-secret-key-for-ci-pipeline-min-32-chars}"
  export ENVIRONMENT=test

  if ! check_db_reachable; then
    echo -e "${RED}Database not reachable at $DATABASE_URL${NC}"
    echo "Start Postgres (e.g. Docker, or: brew services start postgresql@15) or run full CI with Docker: ./scripts/run-ci-local.sh"
    exit 1
  fi

  echo "Running migrations..."
  python3 -m alembic upgrade head || { echo -e "${RED}Migrations failed${NC}"; exit 1; }

  python3 -m pytest tests/ -v --tb=short --cov=app --cov-report=term
  echo -e "${GREEN}Pytest done${NC}"
}

# --- main ---
if [ "$SKIP_COMPOSE" = true ]; then
  if [ -z "$(command -v python)" ] && [ -n "$(command -v python3)" ]; then
    alias python=python3 2>/dev/null || true
  fi
  if ! python3 -c "import flake8" 2>/dev/null; then
    echo "Install dev deps: pip install -r requirements.txt -r requirements-dev.txt"
    exit 1
  fi
  run_lint
  run_tests_standalone
else
  run_compose_and_test_container
fi
echo -e "${GREEN}Local CI finished.${NC}"
