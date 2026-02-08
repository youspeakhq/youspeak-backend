# Get YouSpeak Backend Live — Step-by-Step

This guide gets your backend to a **live public URL** using AWS (ECS + ALB). You do **not** launch EC2 instances manually; Terraform creates an ECS Fargate cluster, RDS, Redis, and a load balancer. The **public URL** is the Application Load Balancer (ALB) DNS name.

---

## How deployment works (Terraform vs Docker vs keys)

- **Terraform does not deploy through Docker.** Terraform only provisions AWS resources: VPC, ALB, ECS cluster and services, RDS, ElastiCache, ECR, Secrets Manager, IAM. It does not build or push images.
- **Docker is used by GitHub Actions.** When you push to `main` or `live`, the CI/CD pipeline builds the image, pushes it to ECR, then updates the ECS service so new tasks use that image. So the *app* is deployed by CI/CD, not by Terraform.
- **Terraform sets your keys (secrets) correctly.** It creates three secrets in AWS Secrets Manager and stores the right values:
  - **DATABASE_URL** — `postgresql://user:password@<rds-endpoint>/youspeak_db` (from RDS + your `db_password` variable).
  - **REDIS_URL** — `redis://<elasticache-host>:6379/0`.
  - **SECRET_KEY** — your `secret_key` variable.
  The ECS execution role has permission to read these secrets. The task definition (`.aws/task-definition.json`) references their ARNs in `secrets[].valueFrom`, so when ECS starts a task it injects `DATABASE_URL`, `REDIS_URL`, and `SECRET_KEY` into the container. After `terraform apply`, run `./.aws/generate-task-definition.sh` so the task definition uses the current secret ARNs, then commit the updated file for CI/CD.

---

## Prerequisites (one-time)

- **AWS CLI** configured (`aws configure`) with a user that can create VPC, ECS, RDS, ElastiCache, ECR, IAM, Secrets Manager.
- **Docker** running locally (for building and pushing the image).
- **Terraform** installed (`brew install terraform` or [terraform.io](https://www.terraform.io/downloads)).

Verify:

```bash
aws sts get-caller-identity
docker info
terraform version
```

---

## Step 1: Terraform backend (S3 bucket)

From the **project root**:

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export TF_BUCKET="youspeak-terraform-state-${AWS_ACCOUNT_ID}"

aws s3 mb "s3://${TF_BUCKET}" --region us-east-1
aws s3api put-bucket-versioning --bucket "$TF_BUCKET" --versioning-configuration Status=Enabled
```

Point Terraform at this bucket (run from project root; replace the bucket name in `terraform/main.tf`):

```bash
# From project root
sed -i.bak "s/youspeak-terraform-state\"/youspeak-terraform-state-${AWS_ACCOUNT_ID}\"/" terraform/main.tf
```

On macOS, if `sed -i` behaves differently, edit `terraform/main.tf` and set the backend `bucket` to `youspeak-terraform-state-<YOUR_ACCOUNT_ID>`.

---

## Step 2: Terraform variables and apply

```bash
cd terraform

# Generate and store credentials (do not commit terraform.tfvars)
DB_PASSWORD=$(openssl rand -base64 32)
SECRET_KEY=$(openssl rand -base64 48)

cat > terraform.tfvars <<EOF
environment = "production"
aws_region  = "us-east-1"
app_name    = "youspeak"
db_password = "${DB_PASSWORD}"
secret_key  = "${SECRET_KEY}"
EOF

# Save for later (migrations, debugging)
echo "DB_PASSWORD=${DB_PASSWORD}" >> ../.env.production.local
echo "SECRET_KEY=${SECRET_KEY}" >> ../.env.production.local
chmod 600 ../.env.production.local ../terraform.tfvars

terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Apply takes about 10–15 minutes. When it finishes, you’ll have: VPC, ALB, ECS cluster, RDS PostgreSQL, ElastiCache Redis, ECR repo, Secrets Manager secrets.

---

## Step 3: Save the public URL (ALB) and other outputs

```bash
terraform output > ../terraform-outputs.txt
cd ..

# Your live public URL (save this)
export ALB_DNS=$(cd terraform && terraform output -raw alb_dns_name)
echo "Public URL: http://${ALB_DNS}"
```

**Share this with others:** `http://<alb_dns_name>`  
Example: `http://youspeak-alb-production-1234567890.us-east-1.elb.amazonaws.com`

**Optional — HTTPS (secure):** To serve over HTTPS and remove the browser “Not secure” warning, use a custom domain and set `domain_name` in Terraform. See [docs/HTTPS_SETUP.md](docs/HTTPS_SETUP.md).

---

## Step 4: Run database migrations on production

```bash
source .env.production.local  # or export DB_PASSWORD=...
export DB_ENDPOINT=$(cd terraform && terraform output -raw database_endpoint)
export DATABASE_URL="postgresql://youspeak_user:${DB_PASSWORD}@${DB_ENDPOINT}/youspeak_db"

# From project root (with venv activated or deps installed)
alembic upgrade head
```

If RDS is not reachable from your machine (private subnets), run migrations from an ECS task or a one-off task that can reach RDS (same VPC/security groups).

---

## Step 5: Build and push Docker image to ECR

```bash
export ECR_URL=$(cd terraform && terraform output -raw ecr_repository_url)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "$ECR_URL"

docker build -t youspeak-backend:latest .
docker tag youspeak-backend:latest "${ECR_URL}:latest"
docker push "${ECR_URL}:latest"
```

---

## Step 6: ECS task definition and service

Generate the task definition (uses Terraform outputs for role and secrets):

```bash
./.aws/generate-task-definition.sh
```

Register it and create the ECS service:

```bash
aws ecs register-task-definition --cli-input-json file://.aws/task-definition.json

# Get network config from Terraform-created resources
PRIVATE_SUBNETS=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=youspeak-private-subnet-*-production" --query 'Subnets[*].SubnetId' --output text | tr '\t' ',')
ECS_SG=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=youspeak-ecs-sg-production" --query 'SecurityGroups[0].GroupId' --output text)
TG_ARN=$(aws elbv2 describe-target-groups --names youspeak-api-tg-production --query 'TargetGroups[0].TargetGroupArn' --output text)

aws ecs create-service \
  --cluster youspeak-cluster \
  --service-name youspeak-api-service-production \
  --task-definition youspeak-api-task \
  --desired-count 1 \
  --launch-type FARGATE \
  --platform-version LATEST \
  --network-configuration "awsvpcConfiguration={subnets=[${PRIVATE_SUBNETS}],securityGroups=[${ECS_SG}],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=${TG_ARN},containerName=youspeak-api,containerPort=8000" \
  --health-check-grace-period-seconds 90 \
  --enable-execute-command
```

Wait for the service to become stable (2–5 minutes):

```bash
aws ecs wait services-stable --cluster youspeak-cluster --services youspeak-api-service-production
```

---

## Step 7: Verify and share the live URL

```bash
curl "http://${ALB_DNS}/health"
# Expect: {"status":"healthy", ...}

# API docs (share with team)
echo "API docs: http://${ALB_DNS}/docs"
```

**Live public URL:** `http://<alb_dns_name>`  
Use it for:

- Health: `http://<alb_dns_name>/health`
- Swagger: `http://<alb_dns_name>/docs`
- API base: `http://<alb_dns_name>/api/v1/...`

---

## Verify live DB connection

- **After deploying new code:** `GET /health/ready` returns 200 if the app can run `SELECT 1` against the live DB; 503 if not. Example: `curl -s http://<alb_dns_name>/health/ready`
- **From inside AWS (same network as the app):** Run `./scripts/check-db-from-ecs.sh production` (or `staging`). This uses ECS Exec to run `psql $DATABASE_URL -c 'SELECT 1'` in a running task. Requires AWS CLI and ECS Exec enabled on the service.

---

## Quick reference

| What            | Where |
|-----------------|--------|
| Public URL      | `terraform output alb_dns_name` → `http://<value>` |
| API docs        | `http://<alb_dns_name>/docs` |
| ECR image       | `terraform output ecr_repository_url` |
| ECS cluster     | `youspeak-cluster` |
| Service         | `youspeak-api-service-production` |
| Logs            | `aws logs tail /ecs/youspeak-api --follow` |

---

## If something fails

- **502/503 on ALB:** Wait a few minutes for tasks to pass health checks; then check `aws elbv2 describe-target-health --target-group-arn $TG_ARN` and ECS service events.
- **Tasks not starting:** Check CloudWatch log group `/ecs/youspeak-api` and ECS service events for errors (secrets, image pull, health check).
- **DB connection errors:** Ensure migrations ran and that the ECS security group can reach the RDS security group on port 5432 (Terraform sets this).

For more detail, see **SETUP_GUIDE.md** (Terraform, DB/Redis, ECS, CI/CD, troubleshooting).
