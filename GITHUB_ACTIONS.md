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
  - Staging URL: `http://<alb_staging_dns>` from `terraform output alb_staging_dns_name`

- **Push/merge to `live`**  
  - Same flow → **run DB migrations** (one-off ECS task) → deploy to **live**  
  - ECS service: `youspeak-api-service-production`  
  - Live URL: `http://<alb_dns_name>` from `terraform output alb_dns_name`

Migrations run **once per deploy** as a short-lived ECS task (`alembic upgrade head`) before the service is updated. If `PRIVATE_SUBNET_IDS` or `ECS_SECURITY_GROUP` are not set, the migration step is skipped (with a warning).

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

- **Deploy fails: “task definition invalid”**  
  - Run `./.aws/generate-task-definition.sh` again and commit the new `.aws/task-definition.json`.  
  - Ensure the file has no placeholder like `YOUR_ACCOUNT_ID`; it must have real ARNs.

- **Deploy fails: “service not found”**  
  - For staging: run `terraform apply` so the staging ECS service and ALB exist.  
  - For live: ensure the production ECS service was created (e.g. via GET_LIVE steps or Terraform).

- **Deploy fails: “subnets/security group”**  
  - Re-run `./.aws/print-github-secrets.sh` and update `PRIVATE_SUBNET_IDS` and `ECS_SECURITY_GROUP` in GitHub secrets.

---

## Quick checklist

- [ ] Terraform applied (staging + production resources)
- [ ] GitHub secrets set: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `PRIVATE_SUBNET_IDS`, `ECS_SECURITY_GROUP`
- [ ] `.aws/task-definition.json` generated and committed (no placeholders)
- [ ] Push to `main` deploys to staging; push to `live` deploys to live
