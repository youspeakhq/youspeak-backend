#!/bin/bash
# Set GitHub Actions secrets via CLI. Run from repo root.
# You must be logged in: gh auth login (do NOT share tokens with anyone).
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Require gh and auth
if ! command -v gh &>/dev/null; then
  echo "GitHub CLI not found. Install: brew install gh"
  exit 1
fi
if ! gh auth status &>/dev/null; then
  echo "Not logged in to GitHub. Run: gh auth login"
  exit 1
fi

# Repo (current by default)
REPO="${GH_REPO:-}"
[ -n "$REPO" ] || REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null) || true
[ -n "$REPO" ] && REPO_FLAG="-R $REPO" || REPO_FLAG=""

# Terraform outputs
if command -v terraform &>/dev/null && [ -d terraform ]; then
  PRIVATE_SUBNETS=$(cd terraform && terraform output -raw private_subnet_ids 2>/dev/null) || true
  ECS_SG=$(cd terraform && terraform output -raw ecs_security_group_id 2>/dev/null) || true
fi
if [ -z "$PRIVATE_SUBNETS" ] || [ -z "$ECS_SG" ]; then
  if command -v aws &>/dev/null; then
    PRIVATE_SUBNETS=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=youspeak-private-subnet-*-production" --query 'Subnets[*].SubnetId' --output text 2>/dev/null | tr '\t' ',')
    ECS_SG=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=youspeak-ecs-sg-production" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null)
  fi
fi
if [ -z "$PRIVATE_SUBNETS" ] || [ -z "$ECS_SG" ]; then
  echo "Could not get PRIVATE_SUBNET_IDS or ECS_SECURITY_GROUP. Run terraform apply first or set them manually."
  exit 1
fi

# AWS keys: use env or prompt (never echo)
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}"
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}"
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
  echo "AWS keys not in environment. Enter them (or export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and re-run)."
  [ -z "$AWS_ACCESS_KEY_ID" ] && read -r -p "AWS_ACCESS_KEY_ID: " AWS_ACCESS_KEY_ID
  [ -z "$AWS_SECRET_ACCESS_KEY" ] && read -r -sp "AWS_SECRET_ACCESS_KEY: " AWS_SECRET_ACCESS_KEY && echo
fi
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
  echo "Both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required."
  exit 1
fi

echo "Setting repository secrets (repo: ${REPO:-current})..."
echo -n "$PRIVATE_SUBNETS" | gh secret set PRIVATE_SUBNET_IDS $REPO_FLAG
echo -n "$ECS_SG" | gh secret set ECS_SECURITY_GROUP $REPO_FLAG
echo -n "$AWS_ACCESS_KEY_ID" | gh secret set AWS_ACCESS_KEY_ID $REPO_FLAG
echo -n "$AWS_SECRET_ACCESS_KEY" | gh secret set AWS_SECRET_ACCESS_KEY $REPO_FLAG
echo "Done. Run: ./.aws/generate-task-definition.sh && commit .aws/task-definition.json"