#!/usr/bin/env bash
# Confirm Terraform-managed staging secrets have AWSCURRENT in Secrets Manager.
# Optionally set youspeak/database-url-staging from DATABASE_URL if missing.
# Usage: ./scripts/confirm-and-set-staging-secrets.sh [--set-db]

set -e

SET_DB="${1:-}"
AWS_REGION="${AWS_REGION:-us-east-1}"
SECRETS=( "youspeak/database-url-staging" "youspeak/redis-url-staging" "youspeak/secret-key-staging" )

has_current() {
  aws secretsmanager list-secret-version-ids --secret-id "$1" --region "$AWS_REGION" \
    --query "Versions[?contains(VersionStages, 'AWSCURRENT')].VersionId" --output text 2>/dev/null | grep -q .
}

echo "=== Staging secrets in Secrets Manager ==="
MISSING=()
for name in "${SECRETS[@]}"; do
  if has_current "$name"; then
    echo "  OK   $name (has AWSCURRENT)"
  else
    echo "  MISS $name (no AWSCURRENT)"
    MISSING+=("$name")
  fi
done

if [ ${#MISSING[@]} -eq 0 ]; then
  echo ""
  echo "All required staging secrets have a value. Force ECS deploy:"
  echo "  aws ecs update-service --cluster youspeak-cluster --service youspeak-curriculum-service-staging --force-new-deployment --region $AWS_REGION"
  exit 0
fi

echo ""
if [[ "$SET_DB" == "--set-db" ]]; then
  if [[ " ${MISSING[*]} " =~ " youspeak/database-url-staging " ]]; then
    if [ -z "${DATABASE_URL:-}" ]; then
      echo "Error: DATABASE_URL is not set. Export it and re-run with --set-db."
      echo "  Example: export DATABASE_URL='postgresql://user:pass@host:5432/dbname?sslmode=require'"
      exit 1
    fi
    echo "Setting youspeak/database-url-staging from DATABASE_URL..."
    aws secretsmanager put-secret-value \
      --secret-id "youspeak/database-url-staging" \
      --secret-string "$DATABASE_URL" \
      --region "$AWS_REGION" --no-cli-pager
    echo "  Done. Re-run without --set-db to confirm; then force ECS deploy."
  fi
else
  echo "Terraform: cd terraform && terraform apply -var=environment=staging (needs db_password; DB must be in state for secret value)."
  echo "Manual: export DATABASE_URL='postgresql://...' then ./scripts/confirm-and-set-staging-secrets.sh --set-db"
  echo "Then: aws ecs update-service --cluster youspeak-cluster --service youspeak-curriculum-service-staging --force-new-deployment --region $AWS_REGION"
  exit 1
fi
