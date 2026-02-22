# CI/CD and Docker efficiency

Why jobs were heavy and what we changed.

---

## Why things were heavy

### 1. **Heavy dependencies at import time**

- **docling** (PDF → structured content) pulls in **torch**, **transformers**, and large CUDA/runtime libs.
- **instructor** (structured AI outputs) pulls in openai/boto and extra deps.
- The app imported these at **module load**: `app.api.v1.router` → `curriculums` → `curriculum_service` → `from docling...` and `app.utils.ai` → `import instructor`. So every process (including uvicorn) loaded torch/docling before handling any request, making **startup slow** and **/health** slow to respond.

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

### 1. **Lazy imports for heavy libs**

- **docling**: `DocumentConverter` is now imported **inside** `CurriculumService.extract_topics()` instead of at the top of `curriculum_service.py`. Docling/torch load only when a PDF extract runs.
- **instructor / boto3**: Imported **inside** `get_ai_client()` in `app/utils/ai.py`. They load only when the AI client is first used (e.g. curriculum generate or extract).
- **Result**: App startup and **/health** no longer wait on torch/docling; they respond quickly so healthchecks can pass without huge `start_period`s.

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
