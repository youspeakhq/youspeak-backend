#!/usr/bin/env bash
# Run a DB connectivity check from inside a running ECS task (same network/secrets as the app).
# Usage: ./scripts/check-db-from-ecs.sh [production|staging]
# Requires: AWS CLI, same AWS profile/credentials that can describe ECS and use ECS Exec.

set -e

ENV="${1:-production}"
CLUSTER="${ECS_CLUSTER:-youspeak-cluster}"
SERVICE_NAME="youspeak-api-service-${ENV}"
CONTAINER="${CONTAINER_NAME:-youspeak-api}"

echo "Checking live DB connectivity via ECS (env=${ENV}, cluster=${CLUSTER}, service=${SERVICE_NAME})..."
echo ""

# Get a running task ARN
TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER" \
  --service-name "$SERVICE_NAME" \
  --desired-status RUNNING \
  --query 'taskArns[0]' \
  --output text 2>/dev/null)

if [ -z "$TASK_ARN" ] || [ "$TASK_ARN" = "None" ]; then
  echo "ERROR: No running task found for service ${SERVICE_NAME}. Is the service deployed and healthy?"
  exit 1
fi

echo "Using task: ${TASK_ARN##*/}"
echo "Running: psql \$DATABASE_URL -c 'SELECT 1' inside container..."
echo ""

# Run psql SELECT 1 inside the container (DATABASE_URL is set by ECS from Secrets Manager)
if aws ecs execute-command \
  --cluster "$CLUSTER" \
  --task "$TASK_ARN" \
  --container "$CONTAINER" \
  --command "/bin/sh" "-c" "/usr/bin/psql \"\$DATABASE_URL\" -t -c 'SELECT 1 AS one' && echo 'DB_OK'" \
  --interactive false \
  --output text 2>&1 | tee /tmp/ecs-db-check.out; then
  if grep -q "DB_OK" /tmp/ecs-db-check.out 2>/dev/null; then
    echo ""
    echo "SUCCESS: Live DB connection from ECS is working."
    exit 0
  fi
fi

echo ""
echo "FAILED: Could not confirm DB connectivity (execute-command or psql failed)."
echo "Check: (1) ECS Exec enabled on service, (2) Task IAM has ssm:StartSession, (3) DATABASE_URL secret is correct."
exit 1
