#!/usr/bin/env bash
# Option A: Reset RDS master password to match the value in Secrets Manager.
# Use when the app gets "password authentication failed" - syncs RDS to the secret.
# Requires: AWS CLI configured, permissions for secretsmanager:GetSecretValue and rds:ModifyDBInstance.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# RDS identifier (from Terraform)
DB_ID="${DB_IDENTIFIER:-youspeak-db-production}"
SECRET_NAME="${SECRET_NAME:-youspeak/database-url-production}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "Fetching password from Secrets Manager secret: $SECRET_NAME"
SECRET_STR=$(aws secretsmanager get-secret-value --secret-id "$SECRET_NAME" --region "$AWS_REGION" --query SecretString --output text)
# Parse postgresql://user:password@host/... with Python (password may contain special chars)
# Use env var to avoid quoting issues when secret contains " or '
export SECRET_STR
DB_PASSWORD=$(python3 << 'PY'
import os, re
from urllib.parse import unquote_plus
s = os.environ.get("SECRET_STR", "")
s = s.split("?")[0]
m = re.match(r"postgresql://[^:]+:(.+)@[^/]+/", s)
if m:
    print(unquote_plus(m.group(1)))
else:
    exit(1)
PY
)

if [ -z "$DB_PASSWORD" ]; then
  echo "Failed to parse password from secret"
  exit 1
fi

echo "Setting RDS instance $DB_ID master password to match secret..."
aws rds modify-db-instance \
  --db-instance-identifier "$DB_ID" \
  --master-user-password "$DB_PASSWORD" \
  --apply-immediately \
  --region "$AWS_REGION" \
  --no-cli-pager

echo "Done. RDS password reset is in progress (apply-immediately). It may take a few minutes."
echo "Then force a new ECS deployment so tasks pick up connections with the (now matching) password."
echo "  ECS Console: Cluster -> youspeak-api-service-staging (or -production) -> Update -> Force new deployment"
