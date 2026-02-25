# YouSpeak Backend – project rules

Read this at session start for non-trivial work. After any correction, add a short lesson here (one line per lesson).

---

## Testing strategy

- **Follow [docs/TESTING_STRATEGY.md](docs/TESTING_STRATEGY.md) for all test work.** It defines unit vs integration vs E2E and when to use each.
- **Integration tests:** Real DB + HTTP (async client vs ASGI app). Live under `tests/integration/`. Require `DATABASE_URL` and `SECRET_KEY`; use `requires_db` from `conftest.py`. Assert status, response body, and observable behavior only; no implementation details.
- **Unit tests:** Isolated logic, mocks for I/O; no DB. Live under `tests/unit/`.
- **E2E tests:** Full critical flows; few tests in `tests/e2e/`.
- When adding or changing behavior: prefer an integration test for endpoint behavior; add unit tests for pure logic; add E2E only for critical multi-step flows.
- Test behavior, not implementation. Required behavior is the source of truth; never relax assertions or change code without checking the requirement.

---

## Lessons (add below after corrections)

<!-- One line per lesson. Example:
- Never X. Do Y instead.
-->
