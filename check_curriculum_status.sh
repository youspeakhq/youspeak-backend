#!/bin/bash
# Quick status check for curriculum service (read-only, no changes)

REGION="us-east-1"
CLUSTER="youspeak-cluster"
SERVICE="youspeak-curriculum-service-staging"

echo "======================================================================"
echo "Curriculum Service Status Check (Staging)"
echo "======================================================================"
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not installed"
    echo ""
    echo "Install with:"
    echo "  macOS: brew install awscli"
    echo "  Python: pip install awscli"
    echo ""
    echo "Then configure:"
    echo "  aws configure"
    exit 1
fi

# Check credentials
echo "Checking AWS credentials..."
if ! aws sts get-caller-identity --region $REGION &>/dev/null; then
    echo "❌ AWS credentials not configured"
    echo ""
    echo "Run: aws configure"
    echo ""
    echo "You'll need:"
    echo "  - AWS Access Key ID"
    echo "  - AWS Secret Access Key"
    echo "  - Default region: us-east-1"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region $REGION)
echo "✅ Connected to AWS account: ${ACCOUNT_ID}"
echo ""

# Service status
echo "Service Status:"
echo "---------------"
SERVICE_INFO=$(aws ecs describe-services \
    --cluster $CLUSTER \
    --services $SERVICE \
    --region $REGION \
    --query 'services[0].{status:status,desired:desiredCount,running:runningCount,pending:pendingCount}' \
    --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "$SERVICE_INFO" | jq -r '"  Status: " + .status, "  Desired tasks: " + (.desired|tostring), "  Running tasks: " + (.running|tostring), "  Pending tasks: " + (.pending|tostring)'

    RUNNING=$(echo "$SERVICE_INFO" | jq -r '.running')
    PENDING=$(echo "$SERVICE_INFO" | jq -r '.pending')

    echo ""
    if [ "$RUNNING" -gt 0 ]; then
        echo "✅ Service is running with ${RUNNING} task(s)"
    elif [ "$PENDING" -gt 0 ]; then
        echo "⚠️  Service has ${PENDING} task(s) pending (not started yet)"
    else
        echo "❌ Service has NO running or pending tasks"
    fi
else
    echo "❌ Service not found or access denied"
    echo "   Service: ${SERVICE}"
    echo "   Cluster: ${CLUSTER}"
fi

echo ""
echo "Recent Events:"
echo "--------------"
aws ecs describe-services \
    --cluster $CLUSTER \
    --services $SERVICE \
    --region $REGION \
    --query 'services[0].events[:3]' \
    --output json 2>/dev/null | jq -r '.[] | "  " + .createdAt + ": " + .message' || echo "  No events found"

echo ""
echo "======================================================================"
echo ""
echo "Next steps:"
if [ "$RUNNING" -eq 0 ]; then
    echo "  Run: ./fix_curriculum_service.sh   (to diagnose and fix)"
else
    echo "  Service appears healthy"
    echo "  If still seeing 504 errors, check:"
    echo "    1. Main API has correct CURRICULUM_SERVICE_URL env var"
    echo "    2. Security groups allow traffic between services"
    echo "    3. Curriculum service is responding on correct port"
fi
echo ""
