# Complete Setup Guide for YouSpeak Backend

This comprehensive guide covers everything from local development to production deployment on AWS ECS with live PostgreSQL and Redis databases.

---

## 📑 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [AWS Account Setup](#aws-account-setup)
4. [Terraform Infrastructure Deployment](#terraform-infrastructure-deployment)
5. [Database & Redis Configuration](#database--redis-configuration)
6. [ECS Deployment Setup](#ecs-deployment-setup)
7. [GitHub Actions CI/CD Setup](#github-actions-cicd-setup)
8. [Production Deployment](#production-deployment)
9. [Monitoring & Maintenance](#monitoring--maintenance)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

```bash
# macOS
brew install --cask docker
brew install awscli terraform git python@3.9

# Linux (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y docker.io awscli terraform git python3.9 python3.9-venv
```

### Required Accounts

- ✅ AWS Account with admin access
- ✅ GitHub account with repository access
- ✅ Domain name (optional, for custom domain)

### Verify Installations

```bash
docker --version          # Should show 29.0.1 or higher
aws --version            # Should show aws-cli/2.x
terraform --version      # Should show Terraform v1.0+
python3.9 --version      # Should show Python 3.9.x
```

---

## Local Development Setup

### Step 1: Clone Repository

```bash
git clone https://github.com/YOUR_ORG/youspeak_backend.git
cd youspeak_backend
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3.9 -m venv venv

# Activate it
source venv/bin/activate  # macOS/Linux
# or
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Step 3: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your local settings
nano .env
```

**Minimum required variables for local development:**
```bash
# Application
APP_NAME=YouSpeak Backend
ENVIRONMENT=development
DEBUG=True

# Database (matches docker-compose.yml)
DATABASE_URL=postgresql://youspeak_user:youspeak_password@localhost:5455/youspeak_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=local-dev-secret-key-change-in-production-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
```

### Step 4: Start Docker Compose Services

```bash
# Start all services in background
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api
```

**Expected Output:**
```
NAME                IMAGE                  STATUS
youspeak_api        youspeak_backend-api   Up (healthy)
youspeak_postgres   postgres:15-alpine     Up (healthy)
youspeak_redis      redis:7-alpine         Up (healthy)
youspeak_adminer    adminer:latest         Up
```

### Step 5: Run Database Migrations

```bash
# Inside the API container
docker exec youspeak_api alembic upgrade head

# Or locally (if running outside Docker)
alembic upgrade head
```

### Step 6: Verify Local Setup

```bash
# Test health endpoint
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "app_name": "YouSpeak Backend",
#   "version": "1.0.0",
#   "environment": "development"
# }

# Access Swagger UI
open http://localhost:8000/docs

# Access database UI (Adminer)
open http://localhost:8080
# Server: postgres
# Username: youspeak_user
# Password: youspeak_password
# Database: youspeak_db
```

✅ **Local development is now ready!**

---

## AWS Account Setup

### Step 1: Configure AWS CLI

```bash
# Configure AWS credentials
aws configure

# Enter when prompted:
# AWS Access Key ID: YOUR_ACCESS_KEY
# AWS Secret Access Key: YOUR_SECRET_KEY
# Default region name: us-east-1
# Default output format: json
```

### Step 2: Verify AWS Access

```bash
# Get your AWS account ID
aws sts get-caller-identity

# Expected output:
# {
#     "UserId": "AIDAXXXXXXXXXXXXXXXXX",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/your-username"
# }

# Save your account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo $AWS_ACCOUNT_ID
```

### Step 3: Create IAM User for GitHub Actions

```bash
# Create IAM policy for GitHub Actions
cat > /tmp/github-actions-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecs:DescribeServices",
        "ecs:DescribeTaskDefinition",
        "ecs:DescribeTasks",
        "ecs:ListTasks",
        "ecs:RegisterTaskDefinition",
        "ecs:UpdateService",
        "ecs:RunTask",
        "iam:PassRole",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Create the policy
aws iam create-policy \
  --policy-name GitHubActionsYouSpeakPolicy \
  --policy-document file:///tmp/github-actions-policy.json

# Create IAM user
aws iam create-user --user-name github-actions-youspeak

# Attach policy to user
aws iam attach-user-policy \
  --user-name github-actions-youspeak \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/GitHubActionsYouSpeakPolicy

# Create access keys (SAVE THESE!)
aws iam create-access-key --user-name github-actions-youspeak

# Output will show:
# {
#     "AccessKey": {
#         "AccessKeyId": "AKIAXXXXXXXXXX",
#         "SecretAccessKey": "xxxxxxxxxxxxxxxxxxxxx",
#         ...
#     }
# }
```

**⚠️ IMPORTANT:** Save the `AccessKeyId` and `SecretAccessKey` - you'll need them for GitHub secrets!

---

## Terraform Infrastructure Deployment

### Step 1: Prepare Terraform Backend

```bash
# Create S3 bucket for Terraform state
aws s3 mb s3://youspeak-terraform-state-${AWS_ACCOUNT_ID} --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket youspeak-terraform-state-${AWS_ACCOUNT_ID} \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket youspeak-terraform-state-${AWS_ACCOUNT_ID} \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Block public access
aws s3api put-public-access-block \
  --bucket youspeak-terraform-state-${AWS_ACCOUNT_ID} \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

### Step 2: Update Terraform Backend Configuration

```bash
cd terraform

# Update backend bucket name in main.tf
sed -i '' "s/youspeak-terraform-state/youspeak-terraform-state-${AWS_ACCOUNT_ID}/g" main.tf
```

### Step 3: Create Terraform Variables File

```bash
# Generate secure passwords
DB_PASSWORD=$(openssl rand -base64 32)
SECRET_KEY=$(openssl rand -base64 48)

# Create terraform.tfvars
cat > terraform.tfvars <<EOF
# Environment Configuration
environment = "production"
aws_region  = "us-east-1"
app_name    = "youspeak"

# Sensitive Variables (DO NOT COMMIT!)
db_password = "${DB_PASSWORD}"
secret_key  = "${SECRET_KEY}"
EOF

# Save these credentials securely!
echo "Database Password: ${DB_PASSWORD}" >> ../credentials.txt
echo "Secret Key: ${SECRET_KEY}" >> ../credentials.txt
chmod 600 ../credentials.txt

echo "✅ Credentials saved to credentials.txt - KEEP THIS SAFE!"
```

### Step 4: Initialize Terraform

```bash
# Initialize Terraform
terraform init

# Expected output:
# Terraform has been successfully initialized!
```

### Step 5: Review Terraform Plan

```bash
# Create execution plan
terraform plan -out=tfplan

# Review the plan carefully
# This will create:
# - 1 VPC
# - 4 Subnets (2 public, 2 private)
# - 1 Internet Gateway
# - 1 NAT Gateway
# - 1 Application Load Balancer
# - 1 ECS Cluster
# - 1 RDS PostgreSQL instance
# - 1 ElastiCache Redis cluster
# - 1 ECR repository
# - Multiple security groups
# - IAM roles and policies
# - Secrets in AWS Secrets Manager
```

### Step 6: Apply Terraform Configuration

```bash
# Apply the plan (this takes 10-15 minutes)
terraform apply tfplan

# Type 'yes' when prompted

# Wait for completion...
# Apply complete! Resources: XX added, 0 changed, 0 destroyed.
```

### Step 7: Save Terraform Outputs

```bash
# Save all outputs to a file
terraform output > ../terraform-outputs.txt

# Display important outputs
echo "=== Important Infrastructure Details ==="
echo "ALB DNS Name: $(terraform output -raw alb_dns_name)"
echo "ECR Repository: $(terraform output -raw ecr_repository_url)"
echo "ECS Cluster: $(terraform output -raw ecs_cluster_name)"
echo "Database Endpoint: $(terraform output -raw database_endpoint)"
echo "Redis Endpoint: $(terraform output -raw redis_endpoint)"

# Go back to project root
cd ..
```

**⚠️ SAVE THESE VALUES!** You'll need them for the next steps.

---

## Database & Redis Configuration

### Understanding Your Live Database

After Terraform completes, you have:

**PostgreSQL Database (RDS):**
- Instance Type: `db.t3.small` (2 vCPU, 2 GB RAM)
- Engine: PostgreSQL 15.4
- Storage: 20 GB (encrypted)
- Multi-AZ: Yes (production) / No (staging)
- Backup Retention: 7 days (production) / 1 day (staging)
- Endpoint: `youspeak-db-production.xxxxx.us-east-1.rds.amazonaws.com:5432`

**Redis Cache (ElastiCache):**
- Node Type: `cache.t3.micro` (2 vCPU, 0.5 GB RAM)
- Engine: Redis 7.0
- Endpoint: `youspeak-redis-production.xxxxx.cache.amazonaws.com:6379`

### Step 1: Verify Database Connectivity

```bash
# Get database endpoint from Terraform
DB_ENDPOINT=$(cd terraform && terraform output -raw database_endpoint)
DB_PASSWORD=$(grep "db_password" terraform/terraform.tfvars | cut -d'"' -f2)

# Test connection using psql (install if needed: brew install postgresql)
psql "postgresql://youspeak_user:${DB_PASSWORD}@${DB_ENDPOINT}/youspeak_db" -c "SELECT version();"

# Expected output:
# PostgreSQL 15.4 on x86_64-pc-linux-gnu...
```

### Step 2: Verify Redis Connectivity

```bash
# Get Redis endpoint
REDIS_ENDPOINT=$(cd terraform && terraform output -raw redis_endpoint)

# Test connection using redis-cli (install if needed: brew install redis)
redis-cli -h $(echo $REDIS_ENDPOINT | cut -d':' -f1) -p $(echo $REDIS_ENDPOINT | cut -d':' -f2) ping

# Expected output:
# PONG
```

### Step 3: Configure Database Connection from Local Machine

For direct database access from your local machine:

```bash
# Option 1: SSH Tunnel through EC2 bastion (if you have one)
# ssh -i your-key.pem -L 5432:RDS_ENDPOINT:5432 ec2-user@BASTION_IP

# Option 2: Temporarily allow your IP in security group
MY_IP=$(curl -s https://checkip.amazonaws.com)
DB_SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=youspeak-rds-sg-production" \
  --query 'SecurityGroups[0].GroupId' --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $DB_SG_ID \
  --protocol tcp \
  --port 5432 \
  --cidr ${MY_IP}/32

echo " Your IP ($MY_IP) can now access the database"
echo " Remember to revoke this rule when done!"
```

### Step 4: Run Database Migrations on Production

```bash
# Set production database URL
export DATABASE_URL="postgresql://youspeak_user:${DB_PASSWORD}@${DB_ENDPOINT}/youspeak_db"

# Run migrations
alembic upgrade head

# Verify tables were created
psql "$DATABASE_URL" -c "\dt"

# Expected output: List of tables
```

### Step 5: Create Initial Data (Optional)

```bash
# Connect to database
psql "$DATABASE_URL"

# Create initial admin user, seed data, etc.
-- Example:
-- INSERT INTO users (email, password_hash, role) VALUES (...);

# Exit
\q
```

---

## ECS Deployment Setup

### Step 1: Create ECR Repository (if not created by Terraform)

```bash
# Check if ECR repository exists
aws ecr describe-repositories --repository-names youspeak-backend 2>/dev/null

# If not, create it
aws ecr create-repository \
  --repository-name youspeak-backend \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=AES256
```

### Step 2: Build and Push Docker Image to ECR

```bash
# Get ECR repository URL
ECR_URL=$(cd terraform && terraform output -raw ecr_repository_url)

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin ${ECR_URL}

# Build Docker image
docker build -t youspeak-backend:latest .

# Tag for ECR
docker tag youspeak-backend:latest ${ECR_URL}:latest
docker tag youspeak-backend:latest ${ECR_URL}:v1.0.0

# Push to ECR
docker push ${ECR_URL}:latest
docker push ${ECR_URL}:v1.0.0

echo "✅ Docker image pushed to ECR"
```

### Step 3: Generate ECS Task Definition

```bash
# Run the generator script
./.aws/generate-task-definition.sh

# This creates .aws/task-definition.json with your AWS account ID

# Verify the file
cat .aws/task-definition.json | jq .
```

### Step 4: Register Task Definition

```bash
# Register the task definition with ECS
aws ecs register-task-definition \
  --cli-input-json file://.aws/task-definition.json

# Verify registration
aws ecs list-task-definitions --family-prefix youspeak-api-task
```

### Step 5: Get Network Configuration Details

```bash
# Get private subnet IDs
PRIVATE_SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=tag:Name,Values=youspeak-private-subnet-*-production" \
  --query 'Subnets[*].SubnetId' --output text | tr '\t' ',')

# Get ECS security group ID
ECS_SG=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=youspeak-ecs-sg-production" \
  --query 'SecurityGroups[0].GroupId' --output text)

# Get target group ARN
TG_ARN=$(aws elbv2 describe-target-groups \
  --names youspeak-api-tg-production \
  --query 'TargetGroups[0].TargetGroupArn' --output text)

echo "Private Subnets: $PRIVATE_SUBNETS"
echo "ECS Security Group: $ECS_SG"
echo "Target Group ARN: $TG_ARN"
```

### Step 6: Create ECS Service

```bash
# Create production ECS service
aws ecs create-service \
  --cluster youspeak-cluster \
  --service-name youspeak-api-service-production \
  --task-definition youspeak-api-task \
  --desired-count 2 \
  --launch-type FARGATE \
  --platform-version LATEST \
  --network-configuration "awsvpcConfiguration={subnets=[${PRIVATE_SUBNETS}],securityGroups=[${ECS_SG}],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=${TG_ARN},containerName=youspeak-api,containerPort=8000" \
  --health-check-grace-period-seconds 60 \
  --deployment-configuration "maximumPercent=200,minimumHealthyPercent=100" \
  --enable-execute-command

echo "✅ ECS service created"

# Wait for service to stabilize
aws ecs wait services-stable \
  --cluster youspeak-cluster \
  --services youspeak-api-service-production

echo "✅ Service is stable and running"
```

### Step 7: Verify ECS Deployment

```bash
# Check service status
aws ecs describe-services \
  --cluster youspeak-cluster \
  --services youspeak-api-service-production \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}' \
  --output table

# Get running tasks
aws ecs list-tasks \
  --cluster youspeak-cluster \
  --service-name youspeak-api-service-production

# View task logs
TASK_ARN=$(aws ecs list-tasks \
  --cluster youspeak-cluster \
  --service-name youspeak-api-service-production \
  --query 'taskArns[0]' --output text)

aws logs tail /ecs/youspeak-api --follow
```

### Step 8: Test Production API

```bash
# Get ALB DNS name
ALB_DNS=$(cd terraform && terraform output -raw alb_dns_name)

# Test health endpoint
curl http://${ALB_DNS}/health

# Expected response:
# {
#   "status": "healthy",
#   "app_name": "YouSpeak Backend",
#   "version": "1.0.0",
#   "environment": "production"
# }

# Access Swagger UI
echo "API Documentation: http://${ALB_DNS}/docs"
```

✅ **ECS deployment is complete!**

---

## GitHub Actions CI/CD Setup

### Step 1: Configure GitHub Repository Secrets

Go to your GitHub repository:
1. Click **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**

Add the following secrets:

| Secret Name | Value | Where to Get It |
|-------------|-------|-----------------|
| `AWS_ACCESS_KEY_ID` | `AKIAXXXXXXXXXX` | From IAM user creation step |
| `AWS_SECRET_ACCESS_KEY` | `xxxxxxxxxxxxxxxx` | From IAM user creation step |
| `PRIVATE_SUBNET_IDS` | `subnet-xxx,subnet-yyy` | From `echo $PRIVATE_SUBNETS` |
| `ECS_SECURITY_GROUP` | `sg-xxxxxxxxx` | From `echo $ECS_SG` |

### Step 2: Update GitHub Workflow (if needed)

The workflow is already configured in `.github/workflows/ci-cd.yml`. Verify it matches your setup:

```bash
# Check workflow file
cat .github/workflows/ci-cd.yml

# Key variables to verify:
# - AWS_REGION: us-east-1
# - ECR_REPOSITORY: youspeak-backend
# - ECS_SERVICE: youspeak-api-service
# - ECS_CLUSTER: youspeak-cluster
```

### Step 3: Create Staging Environment (Optional)

If you want a staging environment:

```bash
# Create staging ECS service
aws ecs create-service \
  --cluster youspeak-cluster \
  --service-name youspeak-api-service-staging \
  --task-definition youspeak-api-task \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[${PRIVATE_SUBNETS}],securityGroups=[${ECS_SG}],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=${TG_ARN},containerName=youspeak-api,containerPort=8000"
```

### Step 4: Test GitHub Actions Workflow

```bash
# Create a test branch
git checkout -b test-cicd

# Make a small change
echo "# Test CI/CD" >> README.md

# Commit and push
git add README.md
git commit -m "test: Trigger CI/CD pipeline"
git push origin test-cicd

# Create pull request on GitHub
# The workflow will run automatically
```

### Step 5: Monitor Workflow Execution

1. Go to GitHub repository → **Actions** tab
2. Click on the running workflow
3. Monitor each job:
   - ✅ Test job should pass
   - ✅ Build job should build and push Docker image
   - ⏸️ Deploy job waits for manual approval (if configured)

### Step 6: Deploy to Production

```bash
# Merge to main branch
git checkout main
git merge test-cicd
git push origin main

# GitHub Actions will automatically:
# 1. Run tests
# 2. Build Docker image
# 3. Push to ECR
# 4. Deploy to production ECS
# 5. Run database migrations
```

✅ **CI/CD is now fully automated!**

---

## Production Deployment

### Complete Production Checklist

Before going live, ensure:

#### Infrastructure
- [ ] Terraform applied successfully
- [ ] RDS database is running and accessible
- [ ] Redis cache is running
- [ ] ECS service is healthy
- [ ] Load balancer is routing traffic
- [ ] Security groups are properly configured

#### Application
- [ ] Docker image built and pushed to ECR
- [ ] Database migrations completed
- [ ] Environment variables configured in Secrets Manager
- [ ] Health checks passing
- [ ] API endpoints responding correctly

#### Security
- [ ] Secrets stored in AWS Secrets Manager (not hardcoded)
- [ ] IAM roles follow least privilege principle
- [ ] Security groups restrict access appropriately
- [ ] Database password is strong and secure
- [ ] SSL/TLS certificate configured (if using custom domain)

#### Monitoring
- [ ] CloudWatch logs configured
- [ ] CloudWatch alarms set up
- [ ] Log retention policies configured
- [ ] Monitoring dashboard created

### Post-Deployment Steps

#### 1. Set Up Custom Domain (Optional)

```bash
# Create Route 53 hosted zone
aws route53 create-hosted-zone \
  --name api.youspeak.com \
  --caller-reference $(date +%s)

# Create A record pointing to ALB
# (Use AWS Console or CLI to create alias record)
```

#### 2. Configure SSL/TLS Certificate

```bash
# Request certificate from ACM
aws acm request-certificate \
  --domain-name api.youspeak.com \
  --validation-method DNS \
  --region us-east-1

# Add HTTPS listener to ALB
# (Configure in AWS Console or update Terraform)
```

#### 3. Set Up CloudWatch Alarms

```bash
# CPU utilization alarm
aws cloudwatch put-metric-alarm \
  --alarm-name youspeak-high-cpu-production \
  --alarm-description "Alert when CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=ClusterName,Value=youspeak-cluster Name=ServiceName,Value=youspeak-api-service-production

# Memory utilization alarm
aws cloudwatch put-metric-alarm \
  --alarm-name youspeak-high-memory-production \
  --alarm-description "Alert when memory exceeds 80%" \
  --metric-name MemoryUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=ClusterName,Value=youspeak-cluster Name=ServiceName,Value=youspeak-api-service-production

# Database connections alarm
aws cloudwatch put-metric-alarm \
  --alarm-name youspeak-high-db-connections \
  --alarm-description "Alert when DB connections exceed 80" \
  --metric-name DatabaseConnections \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=DBInstanceIdentifier,Value=youspeak-db-production
```

#### 4. Configure Backup Strategy

```bash
# RDS automated backups are already configured by Terraform
# Verify backup settings
aws rds describe-db-instances \
  --db-instance-identifier youspeak-db-production \
  --query 'DBInstances[0].{BackupRetention:BackupRetentionPeriod,Window:PreferredBackupWindow}' \
  --output table

# Create manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier youspeak-db-production \
  --db-snapshot-identifier youspeak-db-production-$(date +%Y%m%d)
```

---

## Monitoring & Maintenance

### Viewing Logs

```bash
# View ECS task logs
aws logs tail /ecs/youspeak-api --follow

# View logs for specific time range
aws logs tail /ecs/youspeak-api \
  --since 1h \
  --format short

# Search logs for errors
aws logs filter-log-events \
  --log-group-name /ecs/youspeak-api \
  --filter-pattern "ERROR"
```

### Scaling ECS Service

```bash
# Scale up to 4 tasks
aws ecs update-service \
  --cluster youspeak-cluster \
  --service youspeak-api-service-production \
  --desired-count 4

# Enable auto-scaling (optional)
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/youspeak-cluster/youspeak-api-service-production \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10
```

### Database Maintenance

```bash
# Create manual backup
aws rds create-db-snapshot \
  --db-instance-identifier youspeak-db-production \
  --db-snapshot-identifier manual-backup-$(date +%Y%m%d-%H%M)

# List snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier youspeak-db-production

# Restore from snapshot (if needed)
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier youspeak-db-restored \
  --db-snapshot-identifier SNAPSHOT_ID
```

### Updating Application

```bash
# Method 1: Push to GitHub (automated via CI/CD)
git add .
git commit -m "feat: New feature"
git push origin main
# GitHub Actions will automatically deploy

# Method 2: Manual deployment
# Build new image
docker build -t youspeak-backend:v1.1.0 .

# Push to ECR
docker tag youspeak-backend:v1.1.0 ${ECR_URL}:v1.1.0
docker push ${ECR_URL}:v1.1.0

# Update task definition with new image
# Register new task definition
# Update ECS service to use new task definition
aws ecs update-service \
  --cluster youspeak-cluster \
  --service youspeak-api-service-production \
  --task-definition youspeak-api-task:NEW_REVISION \
  --force-new-deployment
```

---

## Troubleshooting

### Common Issues

#### 1. ECS Tasks Keep Restarting

```bash
# Check task stopped reason
aws ecs describe-tasks \
  --cluster youspeak-cluster \
  --tasks TASK_ARN \
  --query 'tasks[0].stoppedReason'

# Common causes:
# - Database connection failed → Check security groups
# - Missing secrets → Verify Secrets Manager
# - Health check failing → Check /health endpoint
# - Out of memory → Increase task memory
```

#### 2. Database Connection Timeout

```bash
# Verify security group allows ECS → RDS
aws ec2 describe-security-groups \
  --group-ids $DB_SG_ID \
  --query 'SecurityGroups[0].IpPermissions'

# Should show ingress from ECS security group on port 5432

# Test connection from ECS task
aws ecs execute-command \
  --cluster youspeak-cluster \
  --task TASK_ARN \
  --container youspeak-api \
  --interactive \
  --command "/bin/sh"

# Inside container:
# python -c "import psycopg2; conn = psycopg2.connect('$DATABASE_URL'); print('OK')"
```

#### 3. Load Balancer Returns 502/503

```bash
# Check target health
aws elbv2 describe-target-health \
  --target-group-arn $TG_ARN

# Common causes:
# - Tasks not registered with target group
# - Health check path incorrect
# - Security group blocking ALB → ECS traffic
# - Tasks not running
```

#### 4. GitHub Actions Deployment Fails

```bash
# Common issues:
# 1. AWS credentials expired → Update GitHub secrets
# 2. ECR repository doesn't exist → Create it
# 3. ECS service doesn't exist → Create it
# 4. Insufficient IAM permissions → Update policy

# Check GitHub Actions logs for specific error
```

#### 5. High Database CPU Usage

```bash
# Check slow queries
psql "$DATABASE_URL" -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
ORDER BY duration DESC;
"

# Create indexes if needed
# Upgrade instance size if necessary
```

### Getting Help

**CloudWatch Logs:**
```bash
aws logs tail /ecs/youspeak-api --follow
```

**ECS Service Events:**
```bash
aws ecs describe-services \
  --cluster youspeak-cluster \
  --services youspeak-api-service-production \
  --query 'services[0].events[0:10]'
```

**Database Logs:**
```bash
aws rds describe-db-log-files \
  --db-instance-identifier youspeak-db-production

aws rds download-db-log-file-portion \
  --db-instance-identifier youspeak-db-production \
  --log-file-name error/postgresql.log.2024-01-31-12
```

---

## Cost Optimization Tips

### Current Monthly Costs

| Resource | Configuration | Estimated Cost |
|----------|--------------|----------------|
| ECS Fargate (2 tasks) | 0.5 vCPU, 1GB each | $30-40 |
| RDS PostgreSQL | db.t3.small | $50 |
| ElastiCache Redis | cache.t3.micro | $12 |
| Application Load Balancer | Standard | $20 |
| NAT Gateway | Standard | $32 |
| Data Transfer | ~100GB | $9 |
| **Total** | | **~$153-163/month** |

### Ways to Reduce Costs

1. **Use Savings Plans** (20-50% savings on ECS Fargate)
2. **Use Reserved Instances** for RDS (30-60% savings)
3. **Remove NAT Gateway** if not needed (saves $32/month)
4. **Use smaller instance types** for dev/staging
5. **Enable auto-scaling** to scale down during low traffic
6. **Use S3 for static assets** instead of serving from API

---

## Summary

You now have a complete production-ready setup with:

✅ **Local Development:**
- Docker Compose environment
- PostgreSQL database
- Redis cache
- Hot-reload development server

✅ **AWS Production Infrastructure:**
- VPC with public/private subnets
- ECS Fargate cluster
- RDS PostgreSQL database (live, production-ready)
- ElastiCache Redis (live, production-ready)
- Application Load Balancer
- ECR container registry
- CloudWatch logging

✅ **CI/CD Pipeline:**
- Automated testing
- Docker image building
- Security scanning
- Automated deployment to staging/production
- Database migrations

✅ **Monitoring & Operations:**
- CloudWatch logs and metrics
- Automated backups
- Health checks
- Scaling capabilities

**Next Steps:**
1. Test your production API
2. Set up custom domain (optional)
3. Configure SSL/TLS
4. Set up monitoring alerts
5. Create runbook for common operations

**Need Help?**
- Check CloudWatch logs: `/ecs/youspeak-api`
- Review ECS service events
- Check database logs in RDS console
- Review GitHub Actions logs for deployment issues

🎉 **Congratulations! Your YouSpeak backend is production-ready!**
