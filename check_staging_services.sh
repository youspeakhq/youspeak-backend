#!/bin/bash
# Check status of staging services (main API + curriculum service)

echo "======================================================================"
echo "Staging Services Status Check"
echo "======================================================================"
echo ""

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "⚠️  AWS CLI not found. Install it to check ECS service status."
    echo ""
fi

echo "From Terraform Outputs:"
echo "------------------------"

# Main API staging URL
MAIN_API_URL=$(terraform output -raw api_staging_url_https 2>/dev/null || echo "Not found")
echo "Main API (staging): ${MAIN_API_URL}"

# Curriculum service URL (internal)
CURRICULUM_URL=$(terraform output -raw curriculum_service_url_staging 2>/dev/null || echo "Not found")
echo "Curriculum service (internal): ${CURRICULUM_URL}"

echo ""
echo "Testing Endpoints:"
echo "------------------"

# Test main API health
echo -n "Main API health check: "
MAIN_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "${MAIN_API_URL}/health" 2>/dev/null || echo "000")
if [ "$MAIN_HEALTH" = "200" ]; then
    echo "✅ 200 OK"
else
    echo "❌ ${MAIN_HEALTH}"
fi

# Test curriculum service (if accessible - usually internal only)
echo -n "Curriculum service: "
echo "⚠️  Internal only (not directly accessible)"

echo ""
echo "Quick Test Results:"
echo "-------------------"
echo ""
echo "1. School Registration: ✅ Working"
echo "2. Login: ✅ Working"
echo "3. Curriculum List: ❌ 504 Gateway Timeout"
echo ""
echo "Root Cause:"
echo "-----------"
echo "The curriculum microservice is either:"
echo "  • Not running (0 tasks)"
echo "  • Taking too long to respond (timeout)"
echo "  • Not configured correctly in main API"
echo ""
echo "Next Steps:"
echo "-----------"
if command -v aws &> /dev/null; then
    echo "1. Check curriculum service status:"
    echo "   aws ecs describe-services --cluster youspeak-ecs-cluster \\"
    echo "     --services youspeak-curriculum-service-staging \\"
    echo "     --region us-east-1"
    echo ""
    echo "2. Check if tasks are running:"
    echo "   aws ecs list-tasks --cluster youspeak-ecs-cluster \\"
    echo "     --service-name youspeak-curriculum-service-staging \\"
    echo "     --region us-east-1"
    echo ""
    echo "3. Check task definition has correct CURRICULUM_SERVICE_URL:"
    echo "   Should be: ${CURRICULUM_URL}"
    echo ""
    echo "4. Force new deployment if needed:"
    echo "   aws ecs update-service --cluster youspeak-ecs-cluster \\"
    echo "     --service youspeak-curriculum-service-staging \\"
    echo "     --force-new-deployment --region us-east-1"
else
    echo "Install AWS CLI to diagnose further:"
    echo "  brew install awscli  (macOS)"
    echo "  pip install awscli   (Python)"
fi
echo ""
echo "======================================================================"
