#!/usr/bin/env bash
# Run database migrations on staging ECS task
# Usage: ./scripts/run-migrations-staging.sh
# Requires: AWS CLI with proper credentials and ECS Exec enabled

set -e

ENV="staging"
CLUSTER="${ECS_CLUSTER:-youspeak-cluster}"
SERVICE_NAME="youspeak-api-service-${ENV}"
CONTAINER="${CONTAINER_NAME:-youspeak-api}"

echo "=========================================="
echo "Running database migrations on ${ENV}"
echo "Cluster: ${CLUSTER}"
echo "Service: ${SERVICE_NAME}"
echo "=========================================="
echo ""

# Get a running task ARN
echo "1. Finding running ECS task..."
TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER" \
  --service-name "$SERVICE_NAME" \
  --desired-status RUNNING \
  --query 'taskArns[0]' \
  --output text 2>/dev/null)

if [ -z "$TASK_ARN" ] || [ "$TASK_ARN" = "None" ]; then
  echo "ERROR: No running task found for service ${SERVICE_NAME}"
  echo "Is the service deployed and healthy?"
  exit 1
fi

TASK_ID="${TASK_ARN##*/}"
echo "✓ Found task: ${TASK_ID}"
echo ""

# Run alembic upgrade head
echo "2. Running 'alembic upgrade head'..."
echo ""

aws ecs execute-command \
  --cluster "$CLUSTER" \
  --task "$TASK_ARN" \
  --container "$CONTAINER" \
  --command "/bin/sh -c 'cd /app && alembic upgrade head'" \
  --interactive

echo ""
echo "3. Verifying migration status..."
echo ""

# Check current migration version
aws ecs execute-command \
  --cluster "$CLUSTER" \
  --task "$TASK_ARN" \
  --container "$CONTAINER" \
  --command "/bin/sh -c 'cd /app && alembic current'" \
  --interactive

echo ""
echo "=========================================="
echo "✓ Migration complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Test the endpoint: ./test_assessment_endpoint.sh"
echo "2. Check logs if there are any issues:"
echo "   aws logs tail /ecs/youspeak-api --follow --filter-pattern 'ERROR'"
