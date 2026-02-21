#!/bin/bash
# Script to generate ECS task definition with Terraform outputs (run from repo root after terraform apply)

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Generating ECS Task Definition...${NC}"

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo -e "${RED}Error: Could not get AWS account ID. Make sure AWS CLI is configured (aws configure).${NC}"
    exit 1
fi

# Get AWS region (default to us-east-1)
AWS_REGION=${AWS_REGION:-us-east-1}

# Require Terraform outputs (run from repo root after terraform apply)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
EXEC_ROLE_ARN=$(terraform -chdir=terraform output -raw ecs_execution_role_arn 2>/dev/null)
TASK_ROLE_ARN=$(terraform -chdir=terraform output -raw ecs_task_role_arn 2>/dev/null)
SECRET_DB_ARN=$(terraform -chdir=terraform output -raw secret_database_url_arn 2>/dev/null)
SECRET_REDIS_ARN=$(terraform -chdir=terraform output -raw secret_redis_url_arn 2>/dev/null)
SECRET_KEY_ARN=$(terraform -chdir=terraform output -raw secret_secret_key_arn 2>/dev/null)
SECRET_RESEND_ARN=$(terraform -chdir=terraform output -raw secret_resend_api_key_arn 2>/dev/null || true)

if [ -z "$EXEC_ROLE_ARN" ] || [ -z "$SECRET_DB_ARN" ]; then
    echo -e "${RED}Error: Terraform outputs not found. Run from repo root after: cd terraform && terraform init && terraform apply${NC}"
    exit 1
fi

echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"
echo "Execution Role: $EXEC_ROLE_ARN"
echo "Task Role: $TASK_ROLE_ARN"

RESEND_SECRET_JSON=""
if [ -n "$SECRET_RESEND_ARN" ]; then
  RESEND_SECRET_JSON=",
        {
          \"name\": \"RESEND_API_KEY\",
          \"valueFrom\": \"${SECRET_RESEND_ARN}\"
        }"
fi

# Generate task definition from template (use execution role for task role as well)
cat > .aws/task-definition.json <<EOF
{
  "family": "youspeak-api-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "${EXEC_ROLE_ARN}",
  "taskRoleArn": "${TASK_ROLE_ARN}",
  "containerDefinitions": [
    {
      "name": "youspeak-api",
      "image": "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/youspeak-backend:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        },
        {
          "name": "API_V1_PREFIX",
          "value": "/api/v1"
        },
        {
          "name": "LOG_LEVEL",
          "value": "INFO"
        },
        {
          "name": "LOG_FORMAT",
          "value": "json"
        }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "${SECRET_DB_ARN}"
        },
        {
          "name": "REDIS_URL",
          "valueFrom": "${SECRET_REDIS_ARN}"
        },
        {
          "name": "SECRET_KEY",
          "valueFrom": "${SECRET_KEY_ARN}"
        }${RESEND_SECRET_JSON}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/youspeak-api",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "ecs",
          "awslogs-create-group": "true"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "python -c 'import urllib.request; urllib.request.urlopen(\"http://localhost:8000/health\")' || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
EOF

echo -e "${GREEN}✓ Task definition generated at .aws/task-definition.json${NC}"
echo ""
echo "Next steps:"
echo "1. Review the generated file"
echo "2. Register it with: aws ecs register-task-definition --cli-input-json file://.aws/task-definition.json"
