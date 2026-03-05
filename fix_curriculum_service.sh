#!/bin/bash
# Check and fix curriculum service on staging

set -e

REGION="us-east-1"
CLUSTER="youspeak-cluster"
SERVICE="youspeak-curriculum-service-staging"

echo "======================================================================"
echo "Curriculum Service Diagnostic & Fix Script"
echo "======================================================================"
echo ""

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first:"
    echo "   brew install awscli  (macOS)"
    echo "   pip install awscli   (Python)"
    exit 1
fi

# Check AWS credentials
echo "[1/6] Checking AWS credentials..."
if aws sts get-caller-identity --region $REGION &>/dev/null; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region $REGION)
    echo "✅ AWS credentials valid"
    echo "   Account ID: ${ACCOUNT_ID}"
else
    echo "❌ AWS credentials not configured"
    echo "   Run: aws configure"
    exit 1
fi
echo ""

# Check if service exists
echo "[2/6] Checking if service exists..."
if aws ecs describe-services --cluster $CLUSTER --services $SERVICE --region $REGION &>/dev/null; then
    echo "✅ Service exists: ${SERVICE}"

    # Get service status
    SERVICE_STATUS=$(aws ecs describe-services \
        --cluster $CLUSTER \
        --services $SERVICE \
        --region $REGION \
        --query 'services[0].{status:status,desired:desiredCount,running:runningCount,pending:pendingCount}' \
        --output json)

    STATUS=$(echo "$SERVICE_STATUS" | jq -r '.status')
    DESIRED=$(echo "$SERVICE_STATUS" | jq -r '.desired')
    RUNNING=$(echo "$SERVICE_STATUS" | jq -r '.running')
    PENDING=$(echo "$SERVICE_STATUS" | jq -r '.pending')

    echo "   Status: ${STATUS}"
    echo "   Desired: ${DESIRED}"
    echo "   Running: ${RUNNING}"
    echo "   Pending: ${PENDING}"
else
    echo "❌ Service not found: ${SERVICE}"
    echo "   The service needs to be created via Terraform first"
    exit 1
fi
echo ""

# List tasks
echo "[3/6] Checking for running tasks..."
TASKS=$(aws ecs list-tasks \
    --cluster $CLUSTER \
    --service-name $SERVICE \
    --region $REGION \
    --query 'taskArns[*]' \
    --output json)

TASK_COUNT=$(echo "$TASKS" | jq 'length')
echo "   Found ${TASK_COUNT} task(s)"

if [ "$TASK_COUNT" -gt 0 ]; then
    echo ""
    echo "   Task details:"
    TASK_ARN=$(echo "$TASKS" | jq -r '.[0]')

    TASK_INFO=$(aws ecs describe-tasks \
        --cluster $CLUSTER \
        --tasks "$TASK_ARN" \
        --region $REGION \
        --query 'tasks[0].{lastStatus:lastStatus,desiredStatus:desiredStatus,healthStatus:healthStatus,createdAt:createdAt}' \
        --output json)

    echo "$TASK_INFO" | jq '.'

    TASK_STATUS=$(echo "$TASK_INFO" | jq -r '.lastStatus')

    if [ "$TASK_STATUS" = "PENDING" ]; then
        echo ""
        echo "   ⚠️  Task is PENDING (not running)"
        echo "   Common causes:"
        echo "   - IAM role issues"
        echo "   - Missing secrets"
        echo "   - Image pull errors"
        echo ""
        echo "   Checking stopped tasks for errors..."

        STOPPED_TASKS=$(aws ecs list-tasks \
            --cluster $CLUSTER \
            --service-name $SERVICE \
            --desired-status STOPPED \
            --region $REGION \
            --max-items 3 \
            --query 'taskArns[*]' \
            --output json)

        if [ "$(echo "$STOPPED_TASKS" | jq 'length')" -gt 0 ]; then
            STOPPED_ARN=$(echo "$STOPPED_TASKS" | jq -r '.[0]')
            echo "   Latest stopped task reason:"
            aws ecs describe-tasks \
                --cluster $CLUSTER \
                --tasks "$STOPPED_ARN" \
                --region $REGION \
                --query 'tasks[0].{stoppedReason:stoppedReason,stopCode:stopCode}' \
                --output json | jq '.'
        fi
    fi
else
    echo "   ⚠️  No tasks found. Service might be scaled to 0 or failing to start."
fi
echo ""

# Check recent service events
echo "[4/6] Checking recent service events..."
aws ecs describe-services \
    --cluster $CLUSTER \
    --services $SERVICE \
    --region $REGION \
    --query 'services[0].events[:5]' \
    --output json | jq '.[] | {createdAt, message}'
echo ""

# Check CloudWatch logs
echo "[5/6] Checking CloudWatch logs (last 50 lines)..."
LOG_GROUP="/ecs/youspeak-curriculum-api"

if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --region $REGION &>/dev/null; then
    echo "   Log group exists: ${LOG_GROUP}"

    # Get latest log stream
    LATEST_STREAM=$(aws logs describe-log-streams \
        --log-group-name "$LOG_GROUP" \
        --order-by LastEventTime \
        --descending \
        --max-items 1 \
        --region $REGION \
        --query 'logStreams[0].logStreamName' \
        --output text 2>/dev/null || echo "")

    if [ -n "$LATEST_STREAM" ] && [ "$LATEST_STREAM" != "None" ]; then
        echo "   Latest log stream: ${LATEST_STREAM}"
        echo ""
        echo "   Recent logs:"
        aws logs get-log-events \
            --log-group-name "$LOG_GROUP" \
            --log-stream-name "$LATEST_STREAM" \
            --limit 50 \
            --region $REGION \
            --query 'events[*].message' \
            --output text | tail -20
    else
        echo "   ⚠️  No log streams found (container never started)"
    fi
else
    echo "   ⚠️  Log group not found: ${LOG_GROUP}"
fi
echo ""

# Ask to restart
echo "[6/6] Restart options:"
echo "======================================================================"
echo ""

if [ "$RUNNING" -eq 0 ]; then
    echo "⚠️  Service has 0 running tasks!"
    echo ""
    echo "Options:"
    echo "  1. Force new deployment (will try to start tasks)"
    echo "  2. Check task definition and IAM roles"
    echo "  3. Exit"
    echo ""
    read -p "Select option (1-3): " OPTION

    case $OPTION in
        1)
            echo ""
            echo "🔄 Forcing new deployment..."
            aws ecs update-service \
                --cluster $CLUSTER \
                --service $SERVICE \
                --force-new-deployment \
                --region $REGION \
                --output json | jq '.service.{serviceName,desiredCount,runningCount,status}'

            echo ""
            echo "✅ Deployment triggered"
            echo "   Monitor progress with:"
            echo "   watch 'aws ecs describe-services --cluster ${CLUSTER} --services ${SERVICE} --region ${REGION} --query \"services[0].{running:runningCount,pending:pendingCount}\"'"
            ;;
        2)
            echo ""
            echo "📋 Task Definition Check:"
            TASK_DEF=$(aws ecs describe-services \
                --cluster $CLUSTER \
                --services $SERVICE \
                --region $REGION \
                --query 'services[0].taskDefinition' \
                --output text)

            echo "   Current task definition: ${TASK_DEF}"
            echo ""
            echo "   To view full task definition:"
            echo "   aws ecs describe-task-definition --task-definition ${TASK_DEF} --region ${REGION}"
            echo ""
            echo "   To fix IAM role issues, run from terraform directory:"
            echo "   terraform apply -var=environment=staging -target=aws_iam_role.ecs_task_role"
            echo "   terraform apply -var=environment=staging -target=aws_iam_role.ecs_execution_role"
            ;;
        *)
            echo "Exiting..."
            exit 0
            ;;
    esac
else
    echo "Service has ${RUNNING} running task(s)"
    echo ""
    read -p "Force restart anyway? (y/n): " CONFIRM

    if [ "$CONFIRM" = "y" ] || [ "$CONFIRM" = "Y" ]; then
        echo ""
        echo "🔄 Forcing new deployment..."
        aws ecs update-service \
            --cluster $CLUSTER \
            --service $SERVICE \
            --force-new-deployment \
            --region $REGION \
            --output json | jq '.service.{serviceName,desiredCount,runningCount,status}'

        echo ""
        echo "✅ Deployment triggered"
    else
        echo "Skipping restart"
    fi
fi

echo ""
echo "======================================================================"
echo "Done!"
echo "======================================================================"
