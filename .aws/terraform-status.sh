#!/usr/bin/env bash
# Confirm Terraform state and outputs (run from repo root).
# Use this to verify infrastructure before deploying and to get values for GitHub secrets.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v terraform &>/dev/null; then
  echo "Terraform not found. Install: https://developer.hashicorp.com/terraform/install"
  exit 1
fi

echo "=== Terraform status (terraform/ from repo root) ==="
cd terraform
terraform init -input=false -backend=true 2>/dev/null || true
terraform validate
echo ""

echo "=== Key outputs (for CI/CD and migration task) ==="
echo "private_subnet_ids:    $(terraform output -raw private_subnet_ids 2>/dev/null || echo 'N/A')"
echo "ecs_security_group_id: $(terraform output -raw ecs_security_group_id 2>/dev/null || echo 'N/A')"
echo "ecs_cluster_name:      $(terraform output -raw ecs_cluster_name 2>/dev/null || echo 'N/A')"
echo "alb_staging_dns_name:  $(terraform output -raw alb_staging_dns_name 2>/dev/null || echo 'N/A')"
echo "ecr_repository_url:    $(terraform output -raw ecr_repository_url 2>/dev/null || echo 'N/A')"
echo ""

echo "=== GitHub Actions secrets (set these for migration task to reach RDS) ==="
echo "  PRIVATE_SUBNET_IDS   = (terraform output -raw private_subnet_ids)"
echo "  ECS_SECURITY_GROUP   = (terraform output -raw ecs_security_group_id)"
echo ""
echo "To set from this machine: ./.aws/set-github-secrets.sh"
echo ""

echo "=== Plan (no changes applied) ==="
terraform plan -input=false -no-color || true
echo "Done."
