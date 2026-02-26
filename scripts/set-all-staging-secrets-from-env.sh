#!/usr/bin/env bash
# Set all Terraform-managed staging secrets in AWS Secrets Manager from environment variables,
# then verify and optionally force ECS deploy. Use after exporting staging values or loading .env.
#
# Required env (for curriculum staging): DATABASE_URL, R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
#   R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME.
# Optional: REDIS_URL, SECRET_KEY (if missing, secret-key-staging is left as-is if it has a value).
#
# Usage:
#   export DATABASE_URL='...' R2_ACCOUNT_ID='...' ... && ./scripts/set-all-staging-secrets-from-env.sh
#   # Or from repo root with .env containing staging values:
#   ./scripts/set-all-staging-secrets-from-env.sh [--no-deploy]

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Optional: load only the vars we need from .env (avoids parsing errors from spaces in other values)
LOAD_VARS=( DATABASE_URL REDIS_URL SECRET_KEY R2_ACCOUNT_ID R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_BUCKET_NAME )
if [ -f "$REPO_ROOT/.env" ]; then
  for v in "${LOAD_VARS[@]}"; do
    line=$(grep -E "^${v}=" "$REPO_ROOT/.env" 2>/dev/null | head -1)
    [ -n "$line" ] && export "$line"
  done
fi

AWS_REGION="${AWS_REGION:-us-east-1}"
NO_DEPLOY=""
[ "${1:-}" = "--no-deploy" ] && NO_DEPLOY=1

has_current() {
  aws secretsmanager list-secret-version-ids --secret-id "$1" --region "$AWS_REGION" \
    --query "Versions[?contains(VersionStages, 'AWSCURRENT')].VersionId" --output text 2>/dev/null | grep -q .
}

put_if_missing() {
  local secret_name="$1"
  local env_var="$2"
  local val="${!env_var}"
  if [ -z "$val" ]; then
    return
  fi
  if has_current "$secret_name"; then
    echo "  skip $secret_name (already has AWSCURRENT)"
    return
  fi
  echo "  set  $secret_name"
  aws secretsmanager put-secret-value \
    --secret-id "$secret_name" \
    --secret-string "$val" \
    --region "$AWS_REGION" --no-cli-pager
}

echo "=== Setting staging secrets from environment ==="
put_if_missing "youspeak/database-url-staging" DATABASE_URL
put_if_missing "youspeak/redis-url-staging" REDIS_URL
put_if_missing "youspeak/secret-key-staging" SECRET_KEY
put_if_missing "youspeak/r2-account-id-staging" R2_ACCOUNT_ID
put_if_missing "youspeak/r2-access-key-id-staging" R2_ACCESS_KEY_ID
put_if_missing "youspeak/r2-secret-access-key-staging" R2_SECRET_ACCESS_KEY
put_if_missing "youspeak/r2-bucket-name-staging" R2_BUCKET_NAME

echo ""
echo "=== Verification (staging secrets used by ECS) ==="
REQUIRED=( "youspeak/database-url-staging" "youspeak/secret-key-staging"
  "youspeak/r2-account-id-staging" "youspeak/r2-access-key-id-staging"
  "youspeak/r2-secret-access-key-staging" "youspeak/r2-bucket-name-staging" )
MISSING=()
for name in "${REQUIRED[@]}"; do
  if has_current "$name"; then
    echo "  OK   $name"
  else
    echo "  MISS $name"
    MISSING+=("$name")
  fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
  echo ""
  echo "Missing values for: ${MISSING[*]}"
  echo "Export DATABASE_URL, SECRET_KEY, R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME and re-run."
  exit 1
fi

echo ""
echo "All required staging secrets have AWSCURRENT."

if [ -n "$NO_DEPLOY" ]; then
  echo "Skipping ECS deploy (--no-deploy). To deploy:"
  echo "  aws ecs update-service --cluster youspeak-cluster --service youspeak-curriculum-service-staging --force-new-deployment --region $AWS_REGION"
  exit 0
fi

echo "Forcing ECS deploy for youspeak-curriculum-service-staging..."
aws ecs update-service --cluster youspeak-cluster \
  --service youspeak-curriculum-service-staging \
  --force-new-deployment --region "$AWS_REGION" --no-cli-pager --output text \
  --query 'service.{serviceName:serviceName,desiredCount:desiredCount,runningCount:runningCount}'
echo "Deploy triggered. Check task status in ECS console or:"
echo "  aws ecs describe-services --cluster youspeak-cluster --services youspeak-curriculum-service-staging --region $AWS_REGION --query 'services[0].{runningCount:runningCount,events:events[0:3]}'"
