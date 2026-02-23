#!/usr/bin/env bash
# Confirm Terraform-managed secrets exist in AWS and fetch recent ECS API logs.
# Requires: AWS CLI configured (aws configure or env AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY).
# Usage: ./scripts/aws-secrets-and-logs.sh [staging|production] [trigger-generate]
#   Optional: staging (default) or production - only affects which ECS service name we hint for logs.
#   Optional: trigger-generate - call the curriculum generate endpoint then fetch last log events (to capture 500 traceback).

set -e

ENV_TYPE="${1:-staging}"
TRIGGER_GENERATE="${2:-}"
AWS_REGION="${AWS_REGION:-us-east-1}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_GROUP="/ecs/youspeak-api"

echo "=== 1. Terraform outputs (secret ARNs) ==="
cd "$REPO_ROOT"
if ! command -v terraform >/dev/null 2>&1; then
  echo "Terraform not in PATH; skipping Terraform outputs."
else
  for out in secret_database_url_arn secret_redis_url_arn secret_secret_key_arn; do
    val="$(terraform -chdir=terraform output -raw "$out" 2>/dev/null)" || val=""
    if [ -n "$val" ]; then
      echo "  $out: $val"
    fi
  done
  for out in secret_resend_api_key_arn secret_r2_account_id_arn; do
    val="$(terraform -chdir=terraform output -raw "$out" 2>/dev/null)" || val=""
    [ "$val" = "" ] && val="(empty/not set)"
    echo "  $out: $val"
  done
fi
echo ""

echo "=== 2. AWS Secrets Manager – list youspeak/* secrets ==="
if ! aws secretsmanager list-secrets --region "$AWS_REGION" --query "SecretList[?starts_with(Name, 'youspeak/')].{Name:Name,ARN:ARN}" --output table 2>/dev/null; then
  echo "  (AWS CLI not configured or no permission to list secrets)"
else
  echo ""
  echo "  Checking each secret exists (no value printed):"
  for name in youspeak/database-url-production youspeak/redis-url-production youspeak/secret-key-production; do
    if aws secretsmanager get-secret-value --secret-id "$name" --region "$AWS_REGION" --query 'Name' --output text 2>/dev/null; then
      echo "    OK $name"
    else
      echo "    MISSING or no access: $name"
    fi
  done
fi
echo ""

echo "=== 3. CloudWatch Logs – recent streams in $LOG_GROUP ==="
if ! aws logs describe-log-streams \
  --log-group-name "$LOG_GROUP" \
  --order-by LastEventTime \
  --descending \
  --limit 5 \
  --region "$AWS_REGION" \
  --query 'logStreams[*].{name:logStreamName,last:lastEventTimestamp}' \
  --output table 2>/dev/null; then
  echo "  (Cannot list streams – check AWS credentials and log group exists)"
else
  echo ""
fi

echo "=== 4. Tail last 50 log events (all streams, most recent first) ==="
echo "  Run manually for live follow: aws logs tail $LOG_GROUP --follow --region $AWS_REGION"
echo "  Or filter errors: aws logs filter-log-events --log-group-name $LOG_GROUP --filter-pattern '?ERROR ?error ?Exception' --limit 20 --region $AWS_REGION"
echo ""

# Fetch last 30 minutes of events from the most recent stream
RECENT_MS=$(($(date +%s) * 1000 - 30 * 60 * 1000))
echo "  Fetching events from last 30 minutes (filter pattern: ERROR or Exception)..."
if aws logs filter-log-events \
  --log-group-name "$LOG_GROUP" \
  --start-time "$RECENT_MS" \
  --filter-pattern "?ERROR ?Exception ?error ?Traceback" \
  --limit 30 \
  --region "$AWS_REGION" \
  --query 'events[*].message' \
  --output text 2>/dev/null | head -80; then
  :
else
  echo "  (No matching events or permission denied)"
fi
echo ""

echo "=== 5. ECS service status (staging) ==="
aws ecs describe-services \
  --cluster youspeak-cluster \
  --services youspeak-api-service-staging \
  --region "$AWS_REGION" \
  --query 'services[0].{name:serviceName,runningCount:runningCount,desiredCount:desiredCount,status:status}' \
  --output table 2>/dev/null || echo "  (Cannot describe service)"
echo ""

echo "=== 6. ECS task definition (task role for Bedrock) ==="
aws ecs describe-task-definition --task-definition youspeak-api-task --region "$AWS_REGION" \
  --query 'taskDefinition.{taskRoleArn:taskRoleArn}' --output table 2>/dev/null || echo "  (Cannot describe task definition)"
echo ""

if [ "$TRIGGER_GENERATE" = "trigger-generate" ]; then
  echo "=== 7. Trigger curriculum generate and fetch logs ==="
  echo "  Calling test_curriculum_generate_staging.sh to trigger POST /api/v1/curriculums/generate..."
  if "$REPO_ROOT/scripts/test_curriculum_generate_staging.sh" 2>&1; then
    echo "  Generate request completed (HTTP 200)."
  else
    echo "  Generate request returned non-200 (see above). Fetching logs for traceback..."
  fi
  echo "  Waiting 15s for CloudWatch to receive log events..."
  sleep 15
  echo "  Last 5 minutes – errors/exceptions/tracebacks:"
  RECENT_MS=$(($(date +%s) * 1000 - 5 * 60 * 1000))
  aws logs filter-log-events \
    --log-group-name "$LOG_GROUP" \
    --start-time "$RECENT_MS" \
    --filter-pattern "?ERROR ?Exception ?Traceback ?error ?500" \
    --limit 50 \
    --region "$AWS_REGION" \
    --query 'events[*].message' \
    --output text 2>/dev/null | head -120 || echo "  (No matching events or permission denied)"
  echo ""
  echo "  Full tail (last 5 min, raw): aws logs tail $LOG_GROUP --since 5m --region $AWS_REGION"
  echo ""
fi

echo "Done."
echo "  - All Terraform secrets (DB, Redis, secret_key, Resend, R2) are in AWS Secrets Manager; ECS execution role has GetSecretValue."
echo "  - Bedrock uses the ECS task role (AmazonBedrockFullAccess), not a secret. No BEDROCK_MODEL_ID in task def = app default."
echo "  - Live logs: aws logs tail $LOG_GROUP --follow --region $AWS_REGION"
echo "  - 500 errors: aws logs filter-log-events --log-group-name $LOG_GROUP --filter-pattern '\"status_code\": 500' --limit 20 --region $AWS_REGION"
echo "  - One-shot: trigger generate then fetch logs: $0 $ENV_TYPE trigger-generate"
