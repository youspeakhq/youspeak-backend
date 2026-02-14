#!/usr/bin/env bash
# Set up AWS billing alerts via CloudWatch and SNS.
# Usage: ./scripts/setup-billing-alerts.sh [email]
# Example: ./scripts/setup-billing-alerts.sh admin@youspeak.com

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

EMAIL="${1:-}"
if [ -z "$EMAIL" ]; then
  echo "Usage: $0 <email-address>"
  echo "Example: $0 admin@youspeak.com"
  exit 1
fi

AWS_REGION="${AWS_REGION:-us-east-1}"
SNS_TOPIC_NAME="youspeak-billing-alerts"

echo "Setting up billing alerts for: $EMAIL"
echo ""

# Create SNS topic for billing alerts
echo "Creating SNS topic: $SNS_TOPIC_NAME"
TOPIC_ARN=$(aws sns create-topic --name "$SNS_TOPIC_NAME" --region "$AWS_REGION" --query 'TopicArn' --output text 2>/dev/null || \
  aws sns list-topics --region "$AWS_REGION" --query "Topics[?contains(TopicArn, '$SNS_TOPIC_NAME')].TopicArn" --output text | head -1)

if [ -z "$TOPIC_ARN" ]; then
  echo "Failed to create or find SNS topic"
  exit 1
fi

echo "Topic ARN: $TOPIC_ARN"
echo ""

# Subscribe email to topic
echo "Subscribing $EMAIL to topic..."
SUBSCRIPTION_ARN=$(aws sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol email \
  --notification-endpoint "$EMAIL" \
  --region "$AWS_REGION" \
  --query 'SubscriptionArn' --output text)

echo "Subscription ARN: $SUBSCRIPTION_ARN"
echo "⚠️  Check your email ($EMAIL) and confirm the subscription!"
echo ""

# Create CloudWatch alarm for monthly billing ($200 threshold)
echo "Creating CloudWatch billing alarm (threshold: \$200/month)..."
aws cloudwatch put-metric-alarm \
  --alarm-name "youspeak-monthly-billing-alert" \
  --alarm-description "Alert when monthly AWS bill exceeds $200" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 200 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=Currency,Value=USD \
  --alarm-actions "$TOPIC_ARN" \
  --region us-east-1 \
  --no-cli-pager

echo "✅ Billing alarm created"
echo ""

# Create additional alarm for $150 threshold (warning)
echo "Creating CloudWatch billing warning alarm (threshold: \$150/month)..."
aws cloudwatch put-metric-alarm \
  --alarm-name "youspeak-monthly-billing-warning" \
  --alarm-description "Warning when monthly AWS bill exceeds $150" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 150 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=Currency,Value=USD \
  --alarm-actions "$TOPIC_ARN" \
  --region us-east-1 \
  --no-cli-pager

echo "✅ Billing warning alarm created"
echo ""

echo "Done! Billing alerts configured:"
echo "  - Warning: \$150/month"
echo "  - Alert: \$200/month"
echo "  - Email: $EMAIL"
echo ""
echo "⚠️  IMPORTANT: Check your email and confirm the SNS subscription!"
echo "   Alarms won't send emails until you confirm."
