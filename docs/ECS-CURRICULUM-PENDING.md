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
