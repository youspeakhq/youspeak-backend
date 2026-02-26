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

To set the staging secret value with Terraform, run apply with **environment=staging** and the required variables (including `db_password`). That updates (or creates) the secret and sets its value so `AWSCURRENT` exists.

```bash
cd terraform
# Required: TF_VAR_db_password, TF_VAR_secret_key, and any other vars your backend/workspace expects
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
