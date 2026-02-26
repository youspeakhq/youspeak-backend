#!/usr/bin/env bash
# Build curriculum image for linux/amd64, push to ECR, and force new ECS deployment.
# Usage: ./scripts/build-and-deploy-curriculum.sh [staging|production|both]
# Default: staging. Requires: AWS CLI, Docker (buildx), jq. AWS credentials must allow ECR push and ECS update-service.

set -e
ENV="${1:-staging}"
AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REGISTRY="497068062563.dkr.ecr.us-east-1.amazonaws.com"
ECR_REPO="youspeak-curriculum-backend"
IMAGE="${ECR_REGISTRY}/${ECR_REPO}:latest"
CLUSTER="youspeak-cluster"
SERVICE_BASE="youspeak-curriculum-service"

echo "=== 1. ECR login ==="
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "=== 2. Build and push curriculum image (linux/amd64) ==="
docker buildx build \
  --platform linux/amd64 \
  -f services/curriculum/Dockerfile \
  -t "$IMAGE" \
  --push \
  .

echo "=== 3. Force new ECS deployment ==="
if [ "$ENV" = "both" ]; then
  for svc in staging production; do
    echo "Updating $SERVICE_BASE-$svc..."
    aws ecs update-service \
      --cluster "$CLUSTER" \
      --service "$SERVICE_BASE-$svc" \
      --force-new-deployment \
      --region "$AWS_REGION" \
      --no-cli-pager
  done
  echo "Waiting for both services to stabilize..."
  aws ecs wait services-stable --cluster "$CLUSTER" --services "$SERVICE_BASE-staging" "$SERVICE_BASE-production" --region "$AWS_REGION"
else
  aws ecs update-service \
    --cluster "$CLUSTER" \
    --service "$SERVICE_BASE-$ENV" \
    --force-new-deployment \
    --region "$AWS_REGION" \
    --no-cli-pager
  aws ecs wait services-stable --cluster "$CLUSTER" --services "$SERVICE_BASE-$ENV" --region "$AWS_REGION"
fi

echo "Done. Curriculum image pushed and ECS service(s) updated."
