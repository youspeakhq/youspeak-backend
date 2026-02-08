#!/bin/bash
# Run from repo root after Terraform apply. Outputs values to add as GitHub Actions secrets.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v terraform &>/dev/null; then
  echo "Terraform not found. Install it first."
  exit 1
fi
if ! aws sts get-caller-identity &>/dev/null; then
  echo "AWS CLI not configured. Run: aws configure"
  exit 1
fi

PRIVATE_SUBNETS=$(cd terraform && terraform output -raw private_subnet_ids 2>/dev/null) || true
ECS_SG=$(cd terraform && terraform output -raw ecs_security_group_id 2>/dev/null) || true

if [ -z "$PRIVATE_SUBNETS" ] || [ -z "$ECS_SG" ]; then
  PRIVATE_SUBNETS=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=youspeak-private-subnet-*-production" --query 'Subnets[*].SubnetId' --output text 2>/dev/null | tr '\t' ',')
  ECS_SG=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=youspeak-ecs-sg-production" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null)
fi
if [ -z "$PRIVATE_SUBNETS" ] || [ -z "$ECS_SG" ]; then
  echo "Run from repo root after: cd terraform && terraform apply"
  exit 1
fi

echo "Add these as GitHub repository secrets (Settings → Secrets and variables → Actions):"
echo ""
echo "Name: PRIVATE_SUBNET_IDS"
echo "Value: $PRIVATE_SUBNETS"
echo ""
echo "Name: ECS_SECURITY_GROUP"
echo "Value: $ECS_SG"
echo ""
echo "Also add (from IAM user with programmatic access):"
echo "  AWS_ACCESS_KEY_ID"
echo "  AWS_SECRET_ACCESS_KEY"
echo ""
echo "Then run: ./.aws/generate-task-definition.sh"
echo "Commit the updated .aws/task-definition.json so CI can deploy."
