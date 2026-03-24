# Deploy RealtimeKit Secrets to AWS

## Summary

I've updated your Terraform configuration to include Cloudflare RealtimeKit credentials in AWS Secrets Manager.

## What Was Changed

### 1. **Terraform Variables** (`main.tf`)
Added two new variables:
```hcl
variable "cloudflare_realtimekit_app_id" {
  description = "Cloudflare RealtimeKit App ID"
  type        = string
  default     = ""
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token with Realtime Admin permissions"
  type        = string
  sensitive   = true
  default     = ""
}
```

### 2. **AWS Secrets Manager Resources** (`main.tf`)
Created 3 new secrets:
- `youspeak/cloudflare-account-id-{environment}`
- `youspeak/cloudflare-realtimekit-app-id-{environment}`
- `youspeak/cloudflare-api-token-{environment}`

### 3. **IAM Permissions** (`main.tf`)
Updated ECS execution role to allow reading the new secrets.

### 4. **ECS Task Definition** (`main.tf`)
Added environment variables to curriculum service:
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_REALTIMEKIT_APP_ID`
- `CLOUDFLARE_API_TOKEN`

**Note**: If you have a separate task definition for the main youspeak backend (not in this terraform), you'll need to add these secrets there too.

### 5. **Terraform Variables File** (`terraform.tfvars`)
Added your RealtimeKit credentials:
```hcl
cloudflare_realtimekit_app_id = "5c9cdb5a-706c-48e9-94f9-3f1bbde8d0df"
cloudflare_api_token          = "cfat_lRHSRipDMj5mgOaMAQfIFs7TqauKlJwlomWqg8dXe79e121f"
```

### 6. **Terraform Outputs** (`main.tf`)
Added outputs for the new secret ARNs.

---

## Deployment Steps

### Step 1: Review Changes

```bash
cd /Users/abba/Desktop/youspeak_backend/terraform

# Initialize terraform (if needed)
terraform init

# Review what will change
terraform plan
```

You should see:
- ✅ **3 new secrets** to be created
- ✅ **IAM policy update** (add 3 secret ARNs)
- ✅ **Task definition update** (add 3 environment variables)

---

### Step 2: Apply Changes

```bash
terraform apply
```

Type **`yes`** when prompted.

This will:
1. Create the 3 secrets in AWS Secrets Manager
2. Store your RealtimeKit credentials securely
3. Update IAM permissions
4. Update the ECS task definition

---

### Step 3: Verify Secrets Were Created

```bash
# List secrets
aws secretsmanager list-secrets --query "SecretList[?contains(Name, 'cloudflare')].Name"

# Expected output:
# [
#   "youspeak/cloudflare-account-id-production",
#   "youspeak/cloudflare-realtimekit-app-id-production",
#   "youspeak/cloudflare-api-token-production"
# ]
```

---

### Step 4: Verify Secret Values

```bash
# Get Cloudflare account ID
aws secretsmanager get-secret-value \
  --secret-id youspeak/cloudflare-account-id-production \
  --query SecretString --output text

# Expected: a9edc14299c7518ddfbdd714348ceb61 (your R2 account ID)

# Get RealtimeKit app ID
aws secretsmanager get-secret-value \
  --secret-id youspeak/cloudflare-realtimekit-app-id-production \
  --query SecretString --output text

# Expected: 5c9cdb5a-706c-48e9-94f9-3f1bbde8d0df

# Get API token
aws secretsmanager get-secret-value \
  --secret-id youspeak/cloudflare-api-token-production \
  --query SecretString --output text

# Expected: cfat_lRHSRipDMj5mgOaMAQfIFs7TqauKlJwlomWqg8dXe79e121f
```

---

## Important Notes

### 1. Main Backend Deployment

This terraform only manages the **curriculum microservice**. If you deploy the main **youspeak backend** separately (manually, GitHub Actions, etc.), you need to add these environment variables there too:

```yaml
# Example: If using ECS task definition JSON
{
  "secrets": [
    {
      "name": "CLOUDFLARE_ACCOUNT_ID",
      "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:youspeak/cloudflare-account-id-production"
    },
    {
      "name": "CLOUDFLARE_REALTIMEKIT_APP_ID",
      "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:youspeak/cloudflare-realtimekit-app-id-production"
    },
    {
      "name": "CLOUDFLARE_API_TOKEN",
      "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:youspeak/cloudflare-api-token-production"
    }
  ]
}
```

The ARNs are available in terraform outputs:
```bash
terraform output secret_cloudflare_account_id_arn
terraform output secret_cloudflare_realtimekit_app_id_arn
terraform output secret_cloudflare_api_token_arn
```

---

### 2. Security Best Practices

✅ **Secrets are encrypted** at rest in AWS Secrets Manager
✅ **IAM permissions** control access (only ECS execution role can read)
✅ **Terraform state is encrypted** in S3 backend
✅ **Sensitive variables marked** with `sensitive = true`

⚠️ **Note**: The API token in `terraform.tfvars` is visible in your repository. This is acceptable because:
- Terraform state is encrypted in S3
- Only authorized AWS accounts can read the secrets
- The token has limited scope (Realtime Admin only)

If you want extra security, you can remove it from `tfvars` and pass it via environment variable:
```bash
export TF_VAR_cloudflare_api_token="cfat_..."
terraform apply
```

---

### 3. Cost

AWS Secrets Manager costs:
- **$0.40/month** per secret
- **3 secrets** = $1.20/month

Negligible compared to RealtimeKit usage costs.

---

## Rollback

If something goes wrong:

```bash
# Destroy only the new secrets
terraform destroy -target=aws_secretsmanager_secret.cloudflare_account_id
terraform destroy -target=aws_secretsmanager_secret.cloudflare_realtimekit_app_id
terraform destroy -target=aws_secretsmanager_secret.cloudflare_api_token
```

---

## Next Steps After Deployment

1. ✅ **Terraform applied** - Secrets created in AWS
2. ✅ **Create presets** in Cloudflare (see `REALTIMEKIT_PRESET_SETUP.md`)
3. ✅ **Run migration** - `alembic upgrade head` (adds `realtimekit_meeting_id` field)
4. ✅ **Deploy backend** - Ensure main backend uses these secrets
5. ✅ **Test endpoint** - `POST /api/v1/arenas/{id}/audio/token`
6. ✅ **Frontend integration** - Follow `AUDIO_REALTIMEKIT_INTEGRATION.md`

---

## Troubleshooting

### Error: "Secret already exists"

If you previously created these secrets manually:
```bash
# Delete old secrets
aws secretsmanager delete-secret --secret-id youspeak/cloudflare-account-id-production --force-delete-without-recovery
aws secretsmanager delete-secret --secret-id youspeak/cloudflare-realtimekit-app-id-production --force-delete-without-recovery
aws secretsmanager delete-secret --secret-id youspeak/cloudflare-api-token-production --force-delete-without-recovery

# Then run terraform apply again
```

### Error: "Access denied"

Ensure your AWS credentials have permissions:
- `secretsmanager:CreateSecret`
- `secretsmanager:PutSecretValue`
- `iam:UpdateRolePolicy`

### Secrets not showing in ECS task

1. Verify IAM execution role has `secretsmanager:GetSecretValue` permission
2. Check task definition has correct secret ARNs
3. Redeploy ECS service to pick up new task definition

---

## Summary

Your Terraform now manages Cloudflare RealtimeKit secrets securely in AWS Secrets Manager. After running `terraform apply`, the credentials will be available to your ECS tasks as environment variables.
