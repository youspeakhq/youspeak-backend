# Run CI Locally (Before Pushing)

Run the same checks as GitHub Actions on your machine so you can fix failures without pushing.

---

## Option 1: Script (recommended)

Runs lint, Docker Compose (build → up → health check), pytest against the composed API, then tears down.

**Requirements:** Docker running, Python 3.9+ with pip.

```bash
./scripts/run-ci-local.sh
```

- **Lint** – flake8 (same as CI).
- **Docker Compose** – `docker compose up -d --build`, wait for `http://localhost:8000/health`, smoke check `/docs`.
- **Pytest** – tests run against the API at `localhost:8000` (same as integration test in CI).
- **Teardown** – `docker compose down -v`.

Without Docker Compose (lint + pytest only; you need Postgres/Redis or use `--no-compose` and accept possible test failures):

```bash
./scripts/run-ci-local.sh --no-compose
```

---

## Option 2: act (full workflow simulation)

[act](https://github.com/nektos/act) runs your GitHub Actions workflow in Docker, so you can run the same jobs as on GitHub.

**Install:** `brew install act` (macOS) or see [act installation](https://github.com/nektos/act#installation).

**List jobs for a push event:**

```bash
act push --list
```

**Run only the test and Docker Compose jobs** (no AWS secrets needed):

```bash
act push -j test -j "Docker Compose"
```

**Docker Compose job under act:** The runner image must have Docker (for `docker compose`). If the job fails with "docker: not found", use a full image:

```bash
act push -j test -j "Docker Compose" -P ubuntu-latest=catthehacker/ubuntu:full-22.04
```

**Run the whole pipeline (build-and-push and deploy will fail without AWS secrets):**

```bash
act push
```

Use fake secrets to avoid early exits if you only care about test/docker-compose:

```bash
act push -j test -j "Docker Compose" -s AWS_ACCESS_KEY_ID=dummy -s AWS_SECRET_ACCESS_KEY=dummy -s PRIVATE_SUBNET_IDS=subnet-dummy -s ECS_SECURITY_GROUP=sg-dummy
```

(Deploy jobs will still fail when they try to use AWS; the point is to run test + Docker Compose locally.)

---

## Summary

| Goal                         | Command |
|-----------------------------|--------|
| Lint + Compose + tests      | `./scripts/run-ci-local.sh` |
| Lint + tests only          | `./scripts/run-ci-local.sh --no-compose` |
| Simulate CI with act        | `act push -j test -j "Docker Compose"` |
