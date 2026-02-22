# What's Next – YouSpeak Backend

Summary of current state and recommended next steps (as of this snapshot).

---

## Test results (latest run)

| Suite | Result | Notes |
|-------|--------|--------|
| **Unit tests** | 27 passed, 1 warning | All unit tests pass. One `RuntimeWarning` in `test_add_teacher_to_classroom_already_assigned` (coroutine not awaited in mock). |
| **Integration tests** | 46 passed, 11 failed, 76 errors | Require `DATABASE_URL` and `REDIS_URL`. Many errors are `OSError` (e.g. multipart/connection) when DB or Redis are not available or config differs. Run with Postgres + Redis (e.g. `./scripts/run-ci-local.sh` or CI in Docker). |
| **E2E** | 3 tests | `test_live_bedrock_extraction` needs R2 + Bedrock configured; others can pass with full stack. |
| **R2 connection** | Script exists | `python scripts/test_r2_connection.py` – requires `.env` with `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`. |

**Recommendation:** Run full CI locally with Docker: `./scripts/run-ci-local.sh` (compose up → test container → down). That matches GitHub Actions and validates integration + R2 when configured in the test image.

---

## R2 storage (Cloudflare)

- **Terraform:** R2 variables are in `terraform.tfvars` (account id, access key id, secret, bucket, public URL). Applied; four secrets exist in AWS Secrets Manager.
- **ECS task definition:** Regenerated with R2 secrets and `STORAGE_PUBLIC_BASE_URL`. ECS tasks will receive R2 env when the new definition is deployed.
- **Local:** Add the same R2 vars to `.env` to run `scripts/test_r2_connection.py` and to test logo/curriculum uploads locally.

---

## Next steps (priority order)

1. **Deploy the new ECS task definition**  
   So staging/production use R2:
   - Register: `aws ecs register-task-definition --cli-input-json file://.aws/task-definition.json`
   - Force new deployment for staging (and production if desired):  
     `aws ecs update-service --cluster youspeak-cluster --service youspeak-api-service-staging --task-definition youspeak-api-task --force-new-deployment`  
   Or push to `main`/`live` and let CI deploy (ensure the repo’s task definition file is the one you just generated).

2. **Re-apply Terraform if you only just added the R2 Access Key ID**  
   So the secret in Secrets Manager has the real value:  
   `cd terraform && terraform apply -auto-approve`  
   Then regenerate the task definition again and deploy (step 1).

3. **Run full CI locally**  
   `./scripts/run-ci-local.sh`  
   Ensures compose + test container (lint, migrate, pytest) pass before pushing. Fix any failures (e.g. dependency or env) so CI stays green.

4. **Optional: Local R2 check**  
   In `.env` set `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `STORAGE_PUBLIC_BASE_URL`, then run:
   ```bash
   python scripts/test_r2_connection.py
   ```

5. **Production storage URL**  
   The Public Development URL is rate-limited. For production, add a custom domain in R2 (e.g. `storage.youspeak.com`), then set `STORAGE_PUBLIC_BASE_URL` in Terraform/task env and re-apply / regenerate task definition. See `docs/STORAGE-R2.md`.

6. **Admin activity log**  
   `GET /admin/activity` and `POST /admin/activity` use the real `ActivityLog` model (paginated list and create). Leaderboard uses real data from Arena/classes.

7. **Security**  
   Ensure `terraform.tfvars` (and any file with secrets) is not committed. Add to `.gitignore` if needed. Rotate any secret that may have been exposed.

---

## Quick reference

| Goal | Command / action |
|------|-------------------|
| Run unit tests only | `pytest tests/unit/ -v` |
| Run full CI locally (Docker) | `./scripts/run-ci-local.sh` |
| Run CI without Docker | `./scripts/run-ci-local.sh --no-compose` (needs local Postgres + Redis) |
| Test R2 connectivity | `python scripts/test_r2_connection.py` (needs R2 in `.env`) |
| Apply Terraform | `cd terraform && terraform apply -auto-approve` |
| Regenerate ECS task definition | `./aws/generate-task-definition.sh` |
| R2 setup details | `docs/STORAGE-R2.md` |
