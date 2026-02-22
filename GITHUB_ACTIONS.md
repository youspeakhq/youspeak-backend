# GitHub Actions CI/CD Setup

This doc gets the pipeline working so that **merge to `main`** deploys to **staging API** and **merge to `live`** deploys to **live API**.

---

## 1. One-time: Terraform (staging + outputs)

Ensure Terraform has been applied so staging and production resources exist:

```bash
cd terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan
cd ..
```

This creates (among other things) the **staging** ALB, target group, and ECS service so `main` branch deploys have somewhere to go.

---

## 2. GitHub repository secrets

**Do not share GitHub or AWS tokens with anyone** (including in chat). Configure secrets on your machine only.

### Option A: Set secrets via CLI (recommended)

From the repo root, after Terraform apply and with [GitHub CLI](https://cli.github.com/) installed:

```bash
gh auth login   # one-time: authenticate so gh can write to your repo
./.aws/set-github-secrets.sh
```

The script reads `PRIVATE_SUBNET_IDS` and `ECS_SECURITY_GROUP` from Terraform, and uses `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` from your environment or prompts you once. It then runs `gh secret set` for all four secrets so they never leave your machine.

To use env vars instead of typing: `export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...` then run the script.

### Option B: Set secrets in the GitHub UI

From the repo root:

```bash
./.aws/print-github-secrets.sh
```

Add the printed values in the repo: **Settings → Secrets and variables → Actions → New repository secret.**

| Secret name             | Where to get it |
|-------------------------|------------------|
| `AWS_ACCESS_KEY_ID`     | IAM user → Security credentials → Create access key |
| `AWS_SECRET_ACCESS_KEY` | Same as above (save when created) |
| `PRIVATE_SUBNET_IDS`    | Output of `./.aws/print-github-secrets.sh` (comma-separated subnet IDs). Required for the one-off migration task. |
| `ECS_SECURITY_GROUP`   | Output of `./.aws/print-github-secrets.sh` (single security group ID). Required for the one-off migration task. |

### Optional: R2 and live E2E tests

To run **R2-dependent** integration tests (curriculum upload, merge proposal) and **live E2E** tests (Bedrock generation/extraction) in CI, add these secrets. If omitted, those tests are skipped and the pipeline still passes.

| Secret name             | Purpose |
|-------------------------|--------|
| `R2_ACCOUNT_ID`         | Cloudflare R2 account ID (Dashboard → R2 → Overview). Enables curriculum upload tests. |
| `R2_ACCESS_KEY_ID`      | R2 API token access key. |
| `R2_SECRET_ACCESS_KEY`  | R2 API token secret. |
| `RUN_LIVE_E2E`          | Set to `1` to run live Bedrock E2E tests. Requires `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` with Bedrock access (same as deploy). |

The **test** job and **Docker Compose** job both receive these env vars from secrets when set; the Compose job appends R2 vars to `.env` so the api and test containers see them.

### Docker Compose job and schema (docker-compose.ci.yml)

The **Docker Compose** job uses an override file `docker-compose.ci.yml` so the API service runs with `ENVIRONMENT=test`. That way the app does **not** run `create_all()` on startup; the test container then runs `alembic upgrade head` as the single source of schema. This avoids "relation X already exists" errors that occur when the API (with `ENVIRONMENT=development`) creates tables and Alembic later tries to create the same ones. To run the same flow locally: `./scripts/run-ci-local.sh` (it uses the same override).

### Build and Push job: Docker layer cache

The **Build and Push Docker Image** job uses ECR as a registry cache (`ref=.../youspeak-backend:cache`) with `mode=max`, so layers (including the builder stage that runs `pip install -r requirements.txt`) are reused when inputs are unchanged.

- **Next push with no change to `requirements.txt`**  
  The `COPY requirements.txt` and `RUN pip install ...` layers are restored from cache; the step is skipped and **nothing is re-downloaded**.

- **First run or when the cache image does not exist**  
  There is no cache to pull, so the build continues without cache and you see a full pip download. The job then pushes the new cache to `:cache` for the next run.

- **Push that only adds or changes a line in `requirements.txt`**  
  Only the changed layer and everything after it re-run. The Dockerfile uses `RUN --mount=type=cache,target=/root/.cache/pip`, and with `mode=max` that cache can be restored from the registry, so pip may only download the new or changed package(s). If the mount cache is not restored (e.g. first time after a change), pip will re-download all packages for that run; the next run with the same `requirements.txt` will then hit the layer cache again.

---

## 3. Task definition in the repo

The workflow deploys using **`.aws/task-definition.json`** and only replaces the container image. The file in the repo must already contain valid ARNs (execution role, Secrets Manager secrets) for your AWS account.

From repo root, after Terraform apply:

```bash
./.aws/generate-task-definition.sh
```

Then **commit and push** the updated file:

```bash
git add .aws/task-definition.json
git commit -m "chore: update ECS task definition for CI/CD"
git push
```

Do **not** commit `.env.production.local` or `terraform.tfvars`; only the task definition JSON (it references secrets by ARN, not by value).

---

## 4. Branch behaviour

- **Push/merge to `main`**  
  - Tests run → image built and pushed to ECR → **run DB migrations** (one-off ECS task) → deploy to **staging**  
  - ECS service: `youspeak-api-service-staging`  
  - Staging URL (Terraform is the source of truth):  
    - With custom domain: `terraform output -raw api_staging_url_https` (e.g. `https://api-staging.<domain_name>`)  
    - Without custom domain: `http://$(terraform output -raw alb_staging_dns_name)`  
  - To show the correct "View deployment" link in GitHub, set the **repository variable** `STAGING_API_URL` (Settings → Secrets and variables → Actions → Variables) to that Terraform output. The deploy-staging job uses `url: ${{ vars.STAGING_API_URL }}` for the staging environment.

- **Push/merge to `live`**  
  - Same flow → **run DB migrations** (one-off ECS task) → deploy to **live**  
  - ECS service: `youspeak-api-service-production`  
  - Live URL: `http://<alb_dns_name>` from `terraform output alb_dns_name`

Migrations run **once per deploy** as a short-lived ECS task (`alembic upgrade head`) before the service is updated. The workflow uses the **same network configuration as the target ECS service** (from `describe-services`), so the migration task can reach RDS/Redis. If the service cannot be described (e.g. first run), it falls back to `PRIVATE_SUBNET_IDS` and `ECS_SECURITY_GROUP` secrets. If those are not set, the migration step is skipped (with a warning). On migration failure, the last 50 CloudWatch log lines for the task are printed to help debug connection errors. The migration task **must** have a non-empty security group (RDS allows ingress only from the ECS security group). If the ECS service returns empty `securityGroups`, the workflow falls back to the `ECS_SECURITY_GROUP` secret; if that is unset, migrations are skipped or the step fails with instructions to set it from Terraform.

---

## 5. Optional: production approval

To require approval before live deploys:

1. **Settings → Environments → production** (or create it).
2. Under **Environment protection rules**, add **Required reviewers**.
3. The **Deploy to Live API** job uses `environment: production`, so it will wait for approval.

---

## 6. If something fails

- **“Configure AWS credentials” fails: “The request signature we calculated does not match the signature you provided”**  
  This almost always means `AWS_SECRET_ACCESS_KEY` in GitHub Secrets is wrong or corrupted (e.g. pasted with an extra newline or space).  
  - **Fix:** Re-set the secrets so there is no trailing newline. Best way: use the script (it uses `echo -n`):  
    `export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... && ./.aws/set-github-secrets.sh`  
  - If you set secrets in the GitHub UI, copy the Secret Access Key again from IAM (or create a **new access key** and use that). When pasting, ensure no extra space or newline at the end.  
  - If the key contains special characters, create a new key pair in IAM and set the new values in GitHub.

- **Build fails**  
  - Check that Dockerfile and tests pass locally.  
  - Confirm `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set and have ECR access.

- **Docker layer caching**  
  - The pipeline uses ECR as a remote build cache (`youspeak-backend:cache`). Subsequent builds reuse layers when `requirements.txt` and earlier Dockerfile steps are unchanged, reducing build time.

- **Deploy fails: “task definition invalid”**  
  - Run `./.aws/generate-task-definition.sh` again and commit the new `.aws/task-definition.json`.  
  - Ensure the file has no placeholder like `YOUR_ACCOUNT_ID`; it must have real ARNs.

- **Deploy fails: “service not found”**  
  - For staging: run `terraform apply` so the staging ECS service and ALB exist.  
  - For live: ensure the production ECS service was created (e.g. via GET_LIVE steps or Terraform).

- **Deploy fails: “subnets/security group” or migration task exits (e.g. code None / connection failed)**  
  - The migration task must run with the **ECS security group** so it can reach RDS. Re-run `./.aws/set-github-secrets.sh` (or `./.aws/print-github-secrets.sh` and set `PRIVATE_SUBNET_IDS` and `ECS_SECURITY_GROUP` in GitHub).  
  - Confirm Terraform state: run `./.aws/terraform-status.sh` from repo root to print `private_subnet_ids`, `ecs_security_group_id`, and other outputs; ensure GitHub secret `ECS_SECURITY_GROUP` matches `terraform output -raw ecs_security_group_id`.

- **Migration task exited with code null**  
  - The workflow now prints **Task stoppedReason** and **Container reason** and waits 20s then fetches **CloudWatch logs** for the failed task. Check that output for the root cause (e.g. "Essential container in task exited", OutOfMemoryError, or a Python traceback).  
  - If the container was **out of memory**, increase task memory: in `.aws/generate-task-definition.sh` set `memory` to `2048`, run the script, commit the updated `.aws/task-definition.json`, and redeploy.  
  - If logs show **missing env / Secrets Manager**, ensure the ECS execution role in Terraform has `secretsmanager:GetSecretValue` on the task definition’s secret ARNs (see Terraform `ecs_execution_secrets` policy).

---

## Confirm Terraform status

From the repo root, run:

```bash
./.aws/terraform-status.sh
```

This validates Terraform, prints key outputs (private subnets, ECS security group, cluster name, staging ALB DNS, ECR URL), and runs a plan (no apply). Use it to confirm infrastructure before deploying and to verify the values that must be set as GitHub secrets (`PRIVATE_SUBNET_IDS`, `ECS_SECURITY_GROUP`) so the migration one-off task can reach RDS.

---

## Quick checklist

- [ ] Terraform applied (staging + production resources)
- [ ] GitHub secrets set: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `PRIVATE_SUBNET_IDS`, `ECS_SECURITY_GROUP`
- [ ] `.aws/task-definition.json` generated and committed (no placeholders)
- [ ] (Optional) R2 secrets `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` to run curriculum upload tests in CI
- [ ] (Optional) `RUN_LIVE_E2E=1` to run live Bedrock E2E tests in CI
- [ ] Push to `main` deploys to staging; push to `live` deploys to live
