# CI/CD and Docker efficiency

Why jobs were heavy and what we changed.

**Current architecture:** The curriculum is a **microservice** with its own image and `services/curriculum/requirements.txt` (instructor, docling → torch, etc.). The **core API** image uses only root `requirements.txt` and does **not** include torch/docling. See `docs/DEPENDENCIES.md` for the dependency split.

---

## Why things were heavy (historically)

### 1. **Heavy dependencies at import time**

- **docling** (PDF → structured content) pulls in **torch**, **transformers**, and large CUDA/runtime libs.
- **instructor** (structured AI outputs) pulls in openai/boto and extra deps.
- Previously the app imported these at **module load**: `app.api.v1.router` → `curriculums` → `curriculum_service` → `from docling...` and `app.utils.ai` → `import instructor`. So every process (including uvicorn) loaded torch/docling before handling any request, making **startup slow** and **/health** slow to respond.

### 2. **Duplicate work in CI**

- **test** job: installs deps with pip, runs flake8, migrations, starts API, runs pytest.
- **docker-compose** job: builds **api** and **test** images from scratch (no cache), starts compose, runs `docker compose run test` (flake8 + alembic + pytest again).
- So we ran **pytest twice** and built **two heavy images** with no layer reuse between jobs or between runs.

### 3. **Test image rebuilt from zero**

- The **test** stage in the Dockerfile was `FROM python:3.9-slim` and did `pip install -r requirements.txt -r requirements-dev.txt`, re-downloading torch/docling and everything else. That added ~5+ minutes and a lot of image size on every build.

### 4. **No Docker layer cache in compose job**

- `docker compose up -d --build` had no `cache_from`/`cache_to`, so every run did a full rebuild with no reuse of previous layers.

---

## Changes made

### 1. **Lazy imports and microservice split**

- **Microservice split**: Curriculum now runs as a separate service with its own image and deps (instructor, docling → torch). Core API image has no torch/docling.
- **Within curriculum**: `DocumentConverter` is imported **inside** the extract flow; instructor is used in the curriculum AI client. So curriculum startup and healthchecks can stay manageable.
- **Result**: Core API startup and **/health** are fast; curriculum carries the heavy deps in isolation.

### 2. **Test stage reuses builder**

- **test** stage is now `FROM builder` and only runs `pip install -r requirements-dev.txt` (pytest, flake8, etc.). It no longer reinstalls `requirements.txt`.
- **Result**: Test image build reuses the builder’s pip layer; big time and size savings on every compose build.

### 3. **Docker layer cache (GHA) for compose**

- **docker-compose.yml**: `api` and `test` services have `cache_from: type=gha` and `cache_to: type=gha,mode=max`.
- **Workflow**: docker-compose job runs `docker/setup-buildx-action@v3` before `docker compose up -d --build`.
- **Result**: Compose builds in CI reuse layers from the GitHub Actions cache where possible, cutting rebuild time on later runs.

### 4. **Healthcheck tuning (already in place)**

- API healthcheck uses a long `start_period` and retries so that even with cold cache or slow runner, the API has time to start. With lazy imports, startup should usually be well under that window.

---

## Duplicate test runs (optional follow-up)

- **test** job: full pytest against a live API (uvicorn in process).
- **docker-compose** job: full flake8 + alembic + pytest inside the test container against the api container.

So we run the full test suite twice. Options if you want to trim time:

1. **Keep both** (current): Maximum coverage (host + container paths); more CI time.
2. **Compose as smoke only**: In compose job, run only a short smoke (e.g. `pytest tests/ -k "health or smoke"` or a few critical tests) and rely on the **test** job for full pytest.
3. **Single source of truth**: Remove full pytest from one of the two (e.g. only run full pytest in the **test** job and in compose only run flake8 + alembic + one smoke test).

---

## Summary

| Area              | Before                         | After                                      |
|-------------------|--------------------------------|--------------------------------------------|
| App startup       | Loaded torch/docling on import | Lazy load; /health fast                     |
| Test Docker stage | Reinstalled all deps           | Reuses builder; only dev deps added        |
| Compose build     | No cache                       | GHA cache_from/cache_to + Buildx           |
| Healthcheck       | Needed long start_period       | Same config; now usually passes earlier    |

No secrets are stored in the repo; CI uses GitHub Secrets and optional R2/AWS env for tests (see GITHUB_ACTIONS.md).
