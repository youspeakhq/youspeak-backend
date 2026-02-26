# Why curriculum ECS tasks stay PENDING on Fargate

## Root cause

Tasks stay in **PENDING** (container never reaches RUNNING) because **ECS cannot assume the IAM task role**. The service event shows:

```text
ECS was unable to assume the role 'arn:aws:iam::497068062563:role/youspeak-ecs-task-role-production'
```

- **Task definition in use:** `youspeak-curriculum-task-staging:1`
- **Task role in that definition:** `youspeak-ecs-task-role-production`
- **Execution role in that definition:** `youspeak-ecs-execution-role-production`

In this account those **production** roles **do not exist**. Only these exist:

- `youspeak-ecs-execution-role-staging`
- `youspeak-ecs-task-role-staging`

So the staging task definition points at non-existent roles → assume-role fails → container never starts → no logs, task stuck in PENDING.

## Fix

**Option A – Align with Terraform (recommended)**  
Ensure the **staging** task definition uses the **staging** IAM roles. Re-apply Terraform with the staging environment so it updates the curriculum staging task definition:

```bash
cd terraform
terraform plan   # confirm environment = staging and role names are staging
terraform apply  # updates youspeak-curriculum-task-staging with staging role ARNs
```

After apply, force a new deployment so the service picks the new task definition revision:

```bash
aws ecs update-service --cluster youspeak-cluster \
  --service youspeak-curriculum-service-staging \
  --force-new-deployment --region us-east-1
```

**Option B – Create the production roles**  
If you intend to use production role names for staging, create the missing roles and give them the same permissions and trust policy as the staging roles (including `ecs-tasks.amazonaws.com` in the trust policy). Prefer Option A unless you have a reason to use production-named roles for staging.

## Checks that led to this

1. **Task/container state:** `lastStatus: PENDING`, `startedAt: null`, container `lastStatus: PENDING` → container never ran.
2. **No log stream** for the task under `/ecs/youspeak-curriculum-api` → container never started (nothing wrote logs).
3. **Service events:** “ECS was unable to assume the role … youspeak-ecs-task-role-production”.
4. **IAM:** `aws iam get-role --role-name youspeak-ecs-task-role-production` → `NoSuchEntity`; `list-roles` shows only staging ECS roles.

## Fargate PENDING (reference)

For Fargate, task PENDING usually means one of:

- ENI not ready → we had `connectivity: CONNECTED`, so not this.
- Image pull → no `CannotPullContainerError` for this deployment; image is linux/amd64 and pull succeeded for these tasks.
- **IAM:** execution or **task** role missing/wrong trust → this matches the failure (task role missing).
- Container dependency → task def has no `dependsOn`, so not this.

So in this case the blocker is the **missing task (and execution) role** referenced by the staging task definition.

---

## After fixing IAM: Secrets Manager "no AWSCURRENT" (staging)

The **ALB does not use secrets**; the **ECS task** (curriculum service) pulls `DATABASE_URL` and R2 secrets from Secrets Manager at container start. If those secrets have no value (no `AWSCURRENT` version), tasks fail with:

```text
ResourceInitializationError: unable to pull secrets ... ResourceNotFoundException:
Secrets Manager can't find the specified secret value for staging label: AWSCURRENT
```

For secret: `youspeak/database-url-staging` (full ARN in the task definition).

**Cause:** The secret exists but has **no version with the `AWSCURRENT` staging label**. That can happen if the secret was created (e.g. by Terraform) but the secret value was never set—e.g. a targeted apply that didn’t include the secret version, or the staging DB wasn’t in state when applying.

### Fix via Terraform (recommended)

Terraform already defines the secret **and** its value in `terraform/main.tf`:

- `aws_secretsmanager_secret.database_url` – creates `youspeak/database-url-${var.environment}`
- `aws_secretsmanager_secret_version.database_url` – sets the value from the RDS instance and `var.db_password`

**Option A – Get secrets from Secrets Manager and run Terraform (recommended)**

The script reads `youspeak/secret-key-staging` from Secrets Manager and uses it for Terraform. For the DB password it looks for:

1. **youspeak/db-password-staging** – plain password for the staging RDS (create this once in Secrets Manager), or  
2. **youspeak/database-url-staging** – if it already has a full postgres URL, the script parses the password from it.

Then run:

```bash
./scripts/terraform-apply-staging-from-secrets.sh
```

Preview only: `./scripts/terraform-apply-staging-from-secrets.sh --plan-only`.

If you don’t yet have a DB password in Secrets Manager, create **youspeak/db-password-staging** with the desired staging RDS password (AWS Console → Secrets Manager → Store a new secret → Other type of secret → plaintext), then run the script again.

**Option B – Pass variables yourself**

```bash
cd terraform
export TF_VAR_db_password='your-staging-db-password'
export TF_VAR_secret_key='your-app-secret-key'
terraform apply -var="environment=staging"
```

If you only want to ensure the **database URL secret** (and not change other resources), you can target the secret and its version. The version depends on the staging RDS instance being in state (e.g. `youspeak-db-staging`); otherwise the URL would be wrong.

```bash
terraform apply -var="environment=staging" \
  -target=aws_secretsmanager_secret.database_url \
  -target=aws_secretsmanager_secret_version.database_url
```

After the secret has a value, force a new ECS deployment so tasks retry:

```bash
aws ecs update-service --cluster youspeak-cluster \
  --service youspeak-curriculum-service-staging \
  --force-new-deployment --region us-east-1
```

### Fix without Terraform (manual)

If you prefer not to run Terraform, put the staging database URL into the secret manually:

```bash
aws secretsmanager put-secret-value \
  --secret-id "youspeak/database-url-staging" \
  --secret-string "postgresql://youspeak_user:YOUR_PASSWORD@youspeak-db-staging.xxxx.us-east-1.rds.amazonaws.com:5432/youspeak_db?sslmode=require" \
  --region us-east-1
```

Or in the AWS Console: Secrets Manager → `youspeak/database-url-staging` → **Store a new secret value**, then run the `aws ecs update-service` command above.

**Confirm which secrets have values:** run `./scripts/confirm-and-set-staging-secrets.sh` (no args). To set the DB secret from env: `export DATABASE_URL='...'` then `./scripts/confirm-and-set-staging-secrets.sh --set-db`.

---

## ECS services and Secrets Manager state (what exists, what happened)

### ECS services (cluster: youspeak-cluster)

| Service | Task definition | Desired | Running | Secrets used (from task def) |
|--------|------------------|---------|---------|------------------------------|
| youspeak-api-service-staging | youspeak-api-task:**47** | 1 | 1 | **Production** ARNs: database-url-production, redis-url-production, secret-key-production, resend-api-key-production, r2-*-production |
| youspeak-api-service-production | youspeak-api-task:1 | 1 | 0 | Production ARNs (same as above) |
| youspeak-curriculum-service-staging | youspeak-curriculum-task-staging:**3** | 1 | 0 | **Staging** ARNs: database-url-staging, r2-*-staging (no REDIS_URL/SECRET_KEY in task def) |
| youspeak-curriculum-service-production | youspeak-curriculum-task:1 | 1 | 0 | Production ARNs (curriculum) |

So **API “staging”** is wired to **production** secrets (task def :47). Curriculum staging is correctly wired to **staging** secret names.

### Secrets Manager: what exists and what has a value

**Staging secrets (only these exist as active secrets):**

| Secret name | Versions (AWSCURRENT) | Notes |
|-------------|------------------------|--------|
| youspeak/secret-key-staging | 1 | Has value ✓ |
| youspeak/database-url-staging | 1 | Set via `set-all-staging-secrets-from-env.sh` or manual |
| youspeak/redis-url-staging | 1 | Set via script or manual |
| youspeak/r2-bucket-name-staging | 1 | Set via script (from .env `R2_BUCKET_NAME`) |
| youspeak/r2-account-id-staging, r2-access-key-id-staging, r2-secret-access-key-staging | 0 or 1 | **Required for curriculum.** Set via Terraform (`terraform.tfvars` + targeted apply for `aws_secretsmanager_secret_version.r2_*`) or `set-all-staging-secrets-from-env.sh` with R2_* in .env |

**Production secrets:**  
`youspeak/database-url-production`, `youspeak/redis-url-production`, `youspeak/secret-key-production` (and likely resend, r2) are **scheduled for deletion** (DeletedDate 2026-02-26). They are not in the normal “active” list; until the deletion date they can still be used (so API staging task :47 can still run if it started when they had values).

### What happened to those secrets

1. **Staging**
   - Terraform (or a partial apply with `environment=staging`) created the **secret resources** (e.g. `youspeak/database-url-staging`, redis, r2-*) but **did not** create `aws_secretsmanager_secret_version` for them. Secret versions for `database_url` and `redis_url` in Terraform depend on the RDS and ElastiCache instances being in state; staging RDS/Redis are **not** in Terraform state, so those version resources were never applied. The **secret_key** staging version was applied (or set manually), so only `youspeak/secret-key-staging` has a value.
   - Result: staging secret **names** exist, but only secret-key has AWSCURRENT. Curriculum (and API if switched to staging) tasks that pull database-url, redis-url, or R2 staging secrets get ResourceInitializationError (no AWSCURRENT).

2. **Production**
   - Production secrets were **marked for deletion** (scheduled 2026-02-26). So production secret **names** no longer appear in the active list; they exist only in a “pending deletion” state. API staging currently uses those production ARNs and still shows 1 running task—either the task started when values existed, or they remain usable until the deletion date.

To get curriculum staging running: set values for all staging secrets, then force a new ECS deployment.

### One-shot: set all staging secrets and deploy

From repo root, ensure `.env` (or your environment) has staging values for at least:

- `DATABASE_URL` (postgres URL for staging RDS or local)
- `SECRET_KEY` (or leave as-is if `youspeak/secret-key-staging` already has a value)
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` (required by curriculum task def)

Then run:

```bash
./scripts/set-all-staging-secrets-from-env.sh
```

This script:

1. Loads `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, and R2_* from `.env` (if not already set).
2. For each staging secret that has no AWSCURRENT, calls `put-secret-value` with the env value.
3. Verifies all required secrets have AWSCURRENT (database-url, secret-key, and all four R2 staging secrets).
4. Forces a new ECS deployment for `youspeak-curriculum-service-staging`.

If you only want to set secrets without triggering deploy: `./scripts/set-all-staging-secrets-from-env.sh --no-deploy`.

**Confirm current state:** `./scripts/confirm-and-set-staging-secrets.sh` (lists all staging secrets including R2).

---

## After secrets: ECS execution role must allow GetSecretValue on R2

If tasks fail with **AccessDeniedException** when pulling R2 staging secrets (e.g. `youspeak/r2-account-id-staging`), the staging **execution** role was applied when R2 was not configured, so its inline policy does not include the R2 secret ARNs. Fix by re-applying the secrets policy with R2 vars set (e.g. from `terraform.tfvars`):

```bash
cd terraform
terraform apply -var=environment=staging -target=aws_iam_role_policy.ecs_execution_secrets -auto-approve
```

Then force a new deployment so new tasks use the updated role.

---

## Scripts reference

| Script | Purpose |
|--------|--------|
| `scripts/confirm-and-set-staging-secrets.sh` | List staging secrets (database, redis, secret-key, R2) and whether each has AWSCURRENT. Optional `--set-db` sets `youspeak/database-url-staging` from `DATABASE_URL`. |
| `scripts/set-all-staging-secrets-from-env.sh` | Set all staging secrets from env (or .env), verify, then force ECS deploy for curriculum staging. Use `--no-deploy` to skip deploy. |
| `scripts/terraform-apply-staging-from-secrets.sh` | Read secret-key and DB password from Secrets Manager, then run `terraform apply -var=environment=staging`. Use when DB is in state and you want Terraform to manage secret versions. |
