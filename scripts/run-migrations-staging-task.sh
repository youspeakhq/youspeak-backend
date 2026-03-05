#!/usr/bin/env bash
# Run database migrations on staging using a one-off ECS task
# Usage: ./scripts/run-migrations-staging-task.sh
# Requires: AWS CLI with proper credentials

set -e

CLUSTER="youspeak-cluster"
TASK_DEF="youspeak-api-task"
SUBNET1="subnet-081a85e40a0742115"  # Staging private subnet 1
SUBNET2="subnet-068d1cd04b2403cd9"  # Staging private subnet 2
SECURITY_GROUP="sg-0a564644a7af96dc0"  # Staging API security group

echo "=========================================="
echo "Running database migrations via one-off task"
echo "Cluster: ${CLUSTER}"
echo "Task Definition: ${TASK_DEF}"
echo "=========================================="
echo ""

echo "1. Starting migration task..."
echo ""

TASK_ARN=$(aws ecs run-task \
  --cluster "$CLUSTER" \
  --task-definition "$TASK_DEF" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET1,$SUBNET2],securityGroups=[$SECURITY_GROUP],assignPublicIp=DISABLED}" \
  --overrides '{
    "containerOverrides": [{
      "name": "youspeak-api",
      "command": ["sh", "-c", "alembic upgrade head && alembic current"]
    }]
  }' \
  --query 'tasks[0].taskArn' \
  --output text)

if [ -z "$TASK_ARN" ] || [ "$TASK_ARN" = "None" ]; then
  echo "ERROR: Failed to start migration task"
  exit 1
fi

TASK_ID="${TASK_ARN##*/}"
echo "✓ Task started: ${TASK_ID}"
echo ""

echo "2. Waiting for task to complete..."
echo "   (This may take 1-2 minutes)"
echo ""

# Wait for task to complete
aws ecs wait tasks-stopped \
  --cluster "$CLUSTER" \
  --tasks "$TASK_ARN"

echo "✓ Task completed"
echo ""

echo "3. Checking task exit code..."
echo ""

EXIT_CODE=$(aws ecs describe-tasks \
  --cluster "$CLUSTER" \
  --tasks "$TASK_ARN" \
  --query 'tasks[0].containers[0].exitCode' \
  --output text)

echo "Exit code: ${EXIT_CODE}"
echo ""

if [ "$EXIT_CODE" != "0" ]; then
  echo "ERROR: Migration task failed with exit code ${EXIT_CODE}"
  echo ""
  echo "Check logs:"
  echo "  aws logs tail /ecs/youspeak-api --follow --since 5m"
  exit 1
fi

echo "4. Fetching migration logs..."
echo ""

# Give logs a moment to flush
sleep 3

# Get logs from the last 5 minutes
aws logs tail /ecs/youspeak-api \
  --since 5m \
  --filter-pattern "{ \$.task_id = \"$TASK_ID\" }" \
  --format short 2>/dev/null || \
aws logs tail /ecs/youspeak-api \
  --since 5m \
  --format short | tail -20

echo ""
echo "=========================================="
echo "✓ Migration complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Test the endpoint: ./test_assessment_endpoint.sh"
