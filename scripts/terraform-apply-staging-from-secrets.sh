#!/usr/bin/env bash
# Fetch required secrets from AWS Secrets Manager and run Terraform apply for staging.
# Uses: youspeak/secret-key-staging, and youspeak/db-password-staging (or youspeak/database-url-staging to parse password).
# Usage: ./scripts/terraform-apply-staging-from-secrets.sh [--plan-only]

set -e

AWS_REGION="${AWS_REGION:-us-east-1}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLAN_ONLY=""
[[ "${1:-}" == "--plan-only" ]] && PLAN_ONLY="true"

export TF_VAR_environment="staging"

# Secret key (required for app) – must exist and have AWSCURRENT
echo "Fetching youspeak/secret-key-staging..."
TF_VAR_secret_key=$(aws secretsmanager get-secret-value --secret-id "youspeak/secret-key-staging" --region "$AWS_REGION" --query SecretString --output text 2>/dev/null) || {
  echo "Error: Could not read youspeak/secret-key-staging (no value or no access)."
  exit 1
}
export TF_VAR_secret_key

# DB password – from youspeak/db-password-staging, or parse from youspeak/database-url-staging
TF_VAR_db_password=""
TF_VAR_db_password=$(aws secretsmanager get-secret-value --secret-id "youspeak/db-password-staging" --region "$AWS_REGION" --query SecretString --output text 2>/dev/null) || true
if [ -z "$TF_VAR_db_password" ]; then
  DB_URL=$(aws secretsmanager get-secret-value --secret-id "youspeak/database-url-staging" --region "$AWS_REGION" --query SecretString --output text 2>/dev/null) || true
  if [ -n "$DB_URL" ]; then
    export DB_URL
    TF_VAR_db_password=$(python3 -c "
import os, re
from urllib.parse import unquote_plus
s = os.environ.get('DB_URL', '').split('?')[0]
m = re.match(r'postgresql://[^:]+:(.+)@[^/]+/', s)
print(unquote_plus(m.group(1))) if m else exit(1)
")
  fi
fi
if [ -z "$TF_VAR_db_password" ]; then
  echo "Error: DB password not found. Either:"
  echo "  1. Create secret youspeak/db-password-staging with the staging RDS password, or"
  echo "  2. Set youspeak/database-url-staging to a full postgres URL (then we parse the password), or"
  echo "  3. Export TF_VAR_db_password and run: cd terraform && terraform apply -var=environment=staging"
  exit 1
fi
export TF_VAR_db_password

cd "$REPO_ROOT/terraform"
if [[ -n "$PLAN_ONLY" ]]; then
  terraform plan -var="environment=staging" "$@"
else
  terraform apply -var="environment=staging" "$@"
fi
