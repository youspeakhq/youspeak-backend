# Cloudflare R2 storage setup

The app uses Cloudflare R2 (S3-compatible) for curriculum PDFs and school logos. Your bucket **youspeakweb** and Public Development URL are already configured in `.env.example`.

## Storage implementation (no mocks)

- **Single backend:** All file/object storage goes through `app/services/storage_service.py` → Cloudflare R2 (boto3 S3 client). There are no mock, TODO, or fallback storage implementations.
- **Call sites:** Only two endpoints write to storage:
  - **School logo:** `POST /api/v1/schools/profile/logo` → `storage.upload(..., key_prefix="logos/...")`
  - **Curriculum file:** `POST /api/v1/curriculums` → `storage.upload(..., key_prefix="curriculums/...")`
- **When R2 is not configured:** The upload endpoints return **503** (no silent fallback). Configure R2 to enable uploads.

## 1. Create an R2 API token (one-time)

1. Open [Cloudflare Dashboard](https://dash.cloudflare.com) → **R2 Object Storage**.
2. Click **Manage R2 API Tokens** (right side).
3. **Create API token**:
   - Name: e.g. `youspeak-backend`
   - Permissions: **Object Read & Write**
   - Scope: limit to the bucket **youspeakweb** (optional but recommended).
4. Copy the **Access Key ID** and **Secret Access Key** (secret is shown once).

## 2. Local / CI (.env)

Copy the values into `.env` (do not commit `.env`):

```env
R2_ACCOUNT_ID=a9edc14299c7518ddfbdd714348ceb61
R2_ACCESS_KEY_ID=<your-access-key-id>
R2_SECRET_ACCESS_KEY=<your-secret-access-key>
R2_BUCKET_NAME=youspeakweb
STORAGE_PUBLIC_BASE_URL=https://pub-2dc65d0e715b43b5ab0985e9c0eb514c.r2.dev
```

Then test the connection:

```bash
python scripts/test_r2_connection.py
```

You should see: bucket accessible, test object uploaded, and public URL checked.

## 3. ECS / Terraform (required for staging & production)

**R2 credentials must be applied via Terraform** for the API running on ECS (staging/production) to use storage. Without them, uploads on ECS return 503.

1. Add these to `terraform/terraform.tfvars` (do not commit if it contains secrets; ensure `terraform.tfvars` is in `.gitignore` or use `-var-file` with a non-committed file):

```hcl
r2_account_id           = "a9edc14299c7518ddfbdd714348ceb61"
r2_access_key_id        = "<your-r2-access-key-id>"
r2_secret_access_key    = "<your-r2-secret-access-key>"
r2_bucket_name          = "youspeakweb"
storage_public_base_url = "https://pub-2dc65d0e715b43b5ab0985e9c0eb514c.r2.dev"
```

2. Apply and regenerate the task definition:

```bash
cd terraform && terraform apply
cd .. && .aws/generate-task-definition.sh
```

3. Deploy: push to `main`/`live` so CI registers the new task definition and updates the ECS service, or run `aws ecs update-service ... --force-new-deployment` after registering the task definition.

Terraform creates four secrets in AWS Secrets Manager and grants the ECS execution role access. The generate script injects them (and `STORAGE_PUBLIC_BASE_URL`) into the task definition. If the secret *resources* already exist but have no value (e.g. staging), run a targeted apply for the R2 secret versions: `terraform apply -var=environment=staging -target=aws_secretsmanager_secret_version.r2_account_id -target=aws_secretsmanager_secret_version.r2_access_key_id -target=aws_secretsmanager_secret_version.r2_secret_access_key -target=aws_secretsmanager_secret_version.r2_bucket_name`. If tasks then fail with AccessDeniedException on R2 secrets, update the execution role policy: `terraform apply -var=environment=staging -target=aws_iam_role_policy.ecs_execution_secrets`. See **docs/ECS-CURRICULUM-PENDING.md** for full staging troubleshooting.

## 4. Production (custom domain)

The Public Development URL is rate-limited and not for production. For production:

1. In R2 bucket **Settings** → **Custom Domains** → add e.g. `storage.youspeak.com`.
2. Set `STORAGE_PUBLIC_BASE_URL=https://storage.youspeak.com` in Terraform / env.
