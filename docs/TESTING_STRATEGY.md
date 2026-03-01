# Testing Strategy

This document defines how we test the YouSpeak backend: unit, integration, and E2E. Use it when writing, changing, or reviewing tests and when deciding what kind of test to add.

---

## Test pyramid

We follow a **test pyramid**:

| Layer | Count | Speed | Scope | When to run |
|-------|--------|--------|--------|-------------|
| **Unit** | Many | Fast | One unit (function, class, small cluster); no real DB/HTTP | Every change, CI |
| **Integration** | Moderate | Slower | Real DB + HTTP (ASGI client); full request→response→DB | CI, before merge |
| **E2E** | Few | Slowest | Full stack, critical user flows (e.g. onboarding, teacher+student) | CI (optionally with live services) |

**Principle:** More fast, focused unit tests; fewer integration tests; few E2E tests for high-value flows. Avoid an inverted pyramid (many slow E2E, few unit tests).

---

## 1. Unit tests

**Purpose:** Verify business logic and pure functions in isolation. No database, no real HTTP, no external services.

**Where:** `tests/unit/` (and legacy `tests/unit_test.py`).

**Characteristics:**
- Use mocks/stubs for DB, external APIs, and I/O.
- No `DATABASE_URL` or `SECRET_KEY` required.
- Fast; run on every save or commit.

**Example:** Schema validation, security helpers (password hash/verify), formatters, service methods with injected mocks.

**Run:**
```bash
pytest tests/unit/ -v
```

---

## 2. Integration tests

**Purpose:** Verify that **components work together**: HTTP → app → DB (and optionally Redis, storage). One real request hits the app and we assert on status, response body, and (if needed) DB state. No browser; we use an async HTTP client against the ASGI app (or a live server in CI).

**Where:** `tests/integration/`.

**Characteristics:**
- **Real dependencies:** PostgreSQL (via `DATABASE_URL`), app secrets (`SECRET_KEY`). Optional: Redis, R2 (tests skip or are skipped when not configured).
- **Client:** `httpx.AsyncClient` with `ASGITransport(app=app)` (in-process) or live server when `TEST_USE_LIVE_SERVER=true`.
- **Fixtures:** `conftest.py` provides `async_client`, `api_base`, `registered_school`, etc. Use `requires_db` so tests are skipped when DB/secrets are missing.
- **Assert:** Observable outcomes only: status codes, response JSON shape and values, side effects visible at the API boundary. Do not assert on internal implementation (e.g. which service method was called).
- **Isolation:** Each test should be independent. Use unique data (e.g. `unique_suffix`) to avoid collisions. Prefer creating data in the test or via fixtures over shared global state.
- **Auth:** Use `registered_school["headers"]` or login flows for protected endpoints; test both success and failure (401/403, wrong password, etc.).

**What to cover per endpoint/feature:**
- Happy path: valid request → expected status and body.
- Validation: invalid/missing fields → 4xx and error detail.
- Auth: no token, invalid token, wrong role → 401/403.
- Not found / business rules: 404, 400 where applicable.

**Run:**
```bash
# Requires DATABASE_URL and SECRET_KEY in .env.
# Conftest runs `alembic upgrade head` once when DATABASE_URL is set (idempotent).
# You can still run migrations manually first: alembic upgrade head
pytest tests/integration/ -v
```

**Marking:** Tests under `tests/integration/` use `pytestmark = requires_db` (from `conftest`). The `integration` pytest marker in `pytest.ini` is available for filtering, e.g. `pytest -m integration`.

---

## 3. E2E tests

**Purpose:** Verify **critical user journeys** end-to-end (e.g. school onboarding, teacher invite → student enroll). Same as integration in terms of real DB/HTTP, but multi-step and flow-focused.

**Where:** `tests/e2e/`.

**Characteristics:**
- Full flows: register → login → create resources → assert final state.
- May depend on optional services (R2, Bedrock); use `@pytest.mark.live` or skip when env not set.
- Few tests; run in CI and before releases.

**Run:**
```bash
pytest tests/e2e/ -v
# With live services (R2, Bedrock): set env and optionally RUN_LIVE_E2E=1
```

---

## 4. Practices (all layers)

- **Behavior over implementation:** Assert outcomes (status, body, visible state), not how the code does it.
- **Required behavior is truth:** Tests encode the spec/contract. If a test fails, decide whether the requirement or the code is wrong; do not “fix” by blindly relaxing assertions or changing code without checking the requirement.
- **TDD when adding features:** Write a failing test for the required behavior, then implement until it passes, then refactor.
- **Naming:** Test names should state what is being tested and the scenario, e.g. `test_delete_my_account_wrong_password_returns_400`.
- **Cleanup:** Prefer creating fresh data per test; avoid leaving orphan records that affect other tests.

---

## 5. CI and local

- **CI:** GitHub Actions run lint, migrations, and the full test suite (unit + integration + E2E). Optional secrets enable R2-dependent and live E2E tests. See `docs/GITHUB_ACTIONS.md` and `docs/LOCAL_CI.md`.
- **Local:** `./scripts/run-ci-local.sh` runs the same pipeline (lint, Docker Compose, pytest). Without compose: ensure Postgres (and Redis if needed) and `.env` are set, then `pytest tests/`.

---

## 6. Quick reference

| Goal | Layer | Location | Requires |
|------|--------|----------|----------|
| Test a single function/class in isolation | Unit | `tests/unit/` | Nothing |
| Test an API endpoint with real DB | Integration | `tests/integration/` | DATABASE_URL, SECRET_KEY |
| Test a full user flow | E2E | `tests/e2e/` | DATABASE_URL, SECRET_KEY; optional R2/Bedrock |

When in doubt: **prefer an integration test** for endpoint behavior (status + response body + auth); add a **unit test** when you have pure logic or a small unit that can be mocked; add **E2E** only for critical, multi-step flows.
