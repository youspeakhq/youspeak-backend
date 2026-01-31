#!/bin/bash
# Script to generate ECS task definition with actual AWS account ID and region

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Generating ECS Task Definition...${NC}"

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo "Error: Could not get AWS account ID. Make sure AWS CLI is configured."
    exit 1
fi

# Get AWS region (default to us-east-1)
AWS_REGION=${AWS_REGION:-us-east-1}

echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"

# Generate task definition from template
cat > .aws/task-definition.json <<EOF
{
  "family": "youspeak-api-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskRole",
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
          "valueFrom": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:youspeak/database-url-production"
        },
        {
          "name": "REDIS_URL",
          "valueFrom": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:youspeak/redis-url-production"
        },
        {
          "name": "SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:youspeak/secret-key-production"
        }
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
