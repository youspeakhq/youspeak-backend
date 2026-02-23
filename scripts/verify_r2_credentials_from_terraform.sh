#!/usr/bin/env bash
# Fetch R2 credentials from AWS Secrets Manager using Terraform outputs (for the environment
# in current Terraform state), then run the R2 connection test to confirm they work.
# Requires: terraform, aws CLI, and Python/app deps. Run from repo root.
# Usage: ./scripts/verify_r2_credentials_from_terraform.sh [terraform-dir]

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TERRAFORM_DIR="${1:-$REPO_ROOT/terraform}"

if [ ! -d "$TERRAFORM_DIR" ]; then
  echo "Terraform dir not found: $TERRAFORM_DIR"
  exit 1
fi

echo "=== 1. Terraform outputs (R2 secret ARNs and storage URL) ==="
cd "$TERRAFORM_DIR"
ARN_ACCOUNT="$(terraform output -raw secret_r2_account_id_arn 2>/dev/null)" || true
ARN_ACCESS_KEY="$(terraform output -raw secret_r2_access_key_id_arn 2>/dev/null)" || true
ARN_SECRET_KEY="$(terraform output -raw secret_r2_secret_access_key_arn 2>/dev/null)" || true
ARN_BUCKET="$(terraform output -raw secret_r2_bucket_name_arn 2>/dev/null)" || true
STORAGE_BASE="$(terraform output -raw storage_public_base_url 2>/dev/null)" || true

if [ -z "$ARN_ACCOUNT" ] || [ "$ARN_ACCOUNT" = "null" ]; then
  echo "R2 is not configured in Terraform (secret_r2_account_id_arn empty). Set r2_access_key_id (and related) in tfvars and apply."
  exit 1
fi
if [ -z "$ARN_ACCESS_KEY" ] || [ -z "$ARN_SECRET_KEY" ] || [ -z "$ARN_BUCKET" ]; then
  echo "One or more R2 secret ARNs are missing. Check Terraform outputs."
  exit 1
fi

echo "OK Terraform outputs present"
echo ""

echo "=== 2. Fetch secret values from AWS Secrets Manager ==="
R2_ACCOUNT_ID="$(aws secretsmanager get-secret-value --secret-id "$ARN_ACCOUNT" --query SecretString --output text 2>/dev/null)" || {
  echo "FAIL could not fetch R2 account ID from Secrets Manager. Check AWS CLI and IAM."
  exit 1
}
R2_ACCESS_KEY_ID="$(aws secretsmanager get-secret-value --secret-id "$ARN_ACCESS_KEY" --query SecretString --output text 2>/dev/null)" || {
  echo "FAIL could not fetch R2 access key ID from Secrets Manager."
  exit 1
}
R2_SECRET_ACCESS_KEY="$(aws secretsmanager get-secret-value --secret-id "$ARN_SECRET_KEY" --query SecretString --output text 2>/dev/null)" || {
  echo "FAIL could not fetch R2 secret access key from Secrets Manager."
  exit 1
}
R2_BUCKET_NAME="$(aws secretsmanager get-secret-value --secret-id "$ARN_BUCKET" --query SecretString --output text 2>/dev/null)" || {
  echo "FAIL could not fetch R2 bucket name from Secrets Manager."
  exit 1
}

echo "OK Fetched R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME"
[ -n "$STORAGE_BASE" ] && [ "$STORAGE_BASE" != "null" ] && echo "   STORAGE_PUBLIC_BASE_URL=$STORAGE_BASE" || true
echo ""

echo "=== 3. Run R2 connection test (head_bucket, put_object, public URL, delete) ==="
export R2_ACCOUNT_ID R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_BUCKET_NAME
[ -n "$STORAGE_BASE" ] && [ "$STORAGE_BASE" != "null" ] && export STORAGE_PUBLIC_BASE_URL="$STORAGE_BASE" || true

cd "$REPO_ROOT"
python3 scripts/test_r2_connection.py

echo ""
echo "Done. Credentials from Terraform/Secrets Manager are valid and R2 is reachable."
