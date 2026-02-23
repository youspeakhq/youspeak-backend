# R2 storage setup (Terraform + ECS)

## What’s already updated

- **Public URL** in `terraform/terraform.tfvars`: `storage_public_base_url` is set to your new R2 public URL (`https://pub-e5cc183f0ebf487c89df255c34fc385d.r2.dev`).
- **Account ID** and **bucket name** in tfvars: `a9edc14299c7518ddfbdd714348ceb61`, `youspeakweb` (no change if that’s still your bucket).

## How to get the R2 keys Terraform needs

You need two values from Cloudflare for the **same** R2 API token that can access the bucket `youspeakweb`:

1. **Access Key ID** (e.g. `a1b2c3d4e5f6...`)
2. **Secret Access Key** (e.g. `abcdef123456...`)

### Steps in Cloudflare

1. Open **Cloudflare Dashboard** → **R2** (or **Workers & Pages** → **R2**).
2. In the left sidebar, click **Manage R2 API Tokens** (or **R2** → **Overview** → **Manage R2 API Tokens**).
3. Click **Create API token**.
4. Set:
   - **Token name**: e.g. `youspeak-backend`
   - **Permissions**: **Object Read & Write** (or **Edit** for R2).
   - **Specify bucket(s)** (if shown): restrict to **youspeakweb** or leave “All buckets” if you prefer.
5. Click **Create API Token**.
6. On the result screen you get **Access Key ID** and **Secret Access Key**. Copy both **once** (the secret is not shown again).

## Where to put the keys (Terraform secrets)

In **`terraform/terraform.tfvars`** set (or update) the R2 variables. Keep this file private and never commit real secrets to git if it’s in the repo; use a backend or CI secrets for production.

```hcl
# R2 storage (Cloudflare)
r2_account_id           = "a9edc14299c7518ddfbdd714348ceb61"
r2_access_key_id        = "<paste Access Key ID from Cloudflare>"
r2_secret_access_key    = "<paste Secret Access Key from Cloudflare>"
r2_bucket_name          = "youspeakweb"
storage_public_base_url = "https://pub-e5cc183f0ebf487c89df255c34fc385d.r2.dev"
```

- **Account ID**: from the R2 endpoint URL (`https://<ACCOUNT_ID>.r2.cloudflarestorage.com`) — you already have `a9edc14299c7518ddfbdd714348ceb61`.
- **Bucket name**: the bucket you use, e.g. `youspeakweb`.
- **Public URL**: the public base URL for that bucket (e.g. `https://pub-e5cc183f0ebf487c89df255c34fc385d.r2.dev`).

## Next steps after updating tfvars

1. **Push Terraform secrets to AWS**  
   From repo root:
   ```bash
   cd terraform
   terraform plan -var-file=../terraform.tfvars   # optional: check changes
   terraform apply -var-file=../terraform.tfvars # or use default terraform.tfvars path
   ```
   This updates the R2-related secrets in AWS Secrets Manager (and any other Terraform-managed resources).

2. **Verify credentials**  
   From repo root:
   ```bash
   ./scripts/check_r2_credentials_terraform.sh
   ```
   This uses the Terraform-backed secrets and tests connection to the bucket (head, put, delete test object).

3. **Redeploy ECS so the app uses the new secrets**  
   - Either trigger your normal deploy (e.g. push image and update ECS service), or  
   - Force a new deployment so new tasks pull the updated secrets:
     ```bash
     aws ecs update-service --cluster youspeak-cluster --service youspeak-api-service-staging --force-new-deployment --region us-east-1
     ```
   Do the same for production if you use a production ECS service.

4. **Re-test logo upload**  
   ```bash
   ./scripts/test_school_logo_staging.sh
   ```

## Summary

| Item | Where | Action |
|------|--------|--------|
| Public URL | `terraform/terraform.tfvars` | Already set to `https://pub-e5cc183f0ebf487c89df255c34fc385d.r2.dev` |
| Access Key ID | Cloudflare → R2 → Manage R2 API Tokens → Create token | Copy into `r2_access_key_id` in tfvars |
| Secret Access Key | Same token creation screen | Copy into `r2_secret_access_key` in tfvars |
| Apply secrets | Terraform | `terraform apply` |
| Check connection | Script | `./scripts/check_r2_credentials_terraform.sh` |
| Use in app | ECS | Redeploy or force new deployment |
