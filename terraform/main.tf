# AWS Infrastructure for YouSpeak Backend
# This Terraform configuration sets up:
# - VPC with public/private subnets
# - ECS Fargate cluster
# - Application Load Balancer (Main and Staging)
# - RDS PostgreSQL database
# - ElastiCache Redis
# - ECR repository
# - CloudWatch logs
# - Secrets Manager
# - Route53 and ACM (optional)

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket  = "youspeak-terraform-state-497068062563"
    key     = "backend/terraform.tfstate"
    region  = "us-east-1"
    encrypt = true
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "YouSpeak"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

locals {
  # Safety check: ensure the active terraform workspace matches the environment variable
  # This prevents accidentally applying 'production' settings in a 'staging' workspace or vice versa.
  environment_validation = (var.environment == terraform.workspace) ? 0 : tonumber("ERROR: Environment variable ('${var.environment}') does not match active workspace ('${terraform.workspace}'). Please use -var-file=${terraform.workspace}.tfvars")
  
  enable_https = var.domain_name != ""
  api_fqdn     = local.enable_https ? "api.${var.domain_name}" : ""
  staging_fqdn = local.enable_https ? "api-staging.${var.domain_name}" : ""
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (staging or production)"
  type        = string
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "youspeak"
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "Application secret key"
  type        = string
  sensitive   = true
}

variable "resend_api_key" {
  description = "Resend API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "r2_account_id" {
  description = "Cloudflare R2 account ID"
  type        = string
  default     = ""
}

variable "r2_access_key_id" {
  description = "Cloudflare R2 API token access key ID"
  type        = string
  sensitive   = true
  default     = ""
}

variable "r2_secret_access_key" {
  description = "Cloudflare R2 API token secret access key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "r2_bucket_name" {
  description = "Cloudflare R2 bucket name"
  type        = string
  default     = "youspeakweb"
}

variable "storage_public_base_url" {
  description = "Public URL for R2 objects"
  type        = string
  default     = "https://pub-2dc65d0e715b43b5ab0985e9c0eb514c.r2.dev"
}

variable "cloudflare_realtimekit_app_id" {
  description = "Cloudflare RealtimeKit App ID"
  type        = string
  default     = ""
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token"
  type        = string
  sensitive   = true
  default     = ""
}

variable "cloudflare_account_id" {
  description = "Cloudflare Account ID for RealtimeKit"
  type        = string
  default     = ""
}

variable "azure_speech_key" {
  description = "Azure Speech Services subscription key for pronunciation assessment"
  type        = string
  sensitive   = true
  default     = ""
}

variable "azure_speech_region" {
  description = "Azure Speech Services region"
  type        = string
  default     = "eastus"
}

variable "domain_name" {
  description = "Root domain for API"
  type        = string
  default     = ""
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "${var.app_name}-vpc-${var.environment}" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.app_name}-igw-${var.environment}" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.${count.index + 1}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  tags = { Name = "${var.app_name}-public-subnet-${count.index + 1}-${var.environment}" }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 10}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags = { Name = "${var.app_name}-private-subnet-${count.index + 1}-${var.environment}" }
}

resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = { Name = "${var.app_name}-nat-eip-${var.environment}" }
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  tags          = { Name = "${var.app_name}-nat-${var.environment}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "${var.app_name}-public-rt-${var.environment}" }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }
  tags = { Name = "${var.app_name}-private-rt-${var.environment}" }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# Security Groups
resource "aws_security_group" "alb" {
  name        = "${var.app_name}-alb-sg-${var.environment}"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs" {
  name        = "${var.app_name}-ecs-sg-${var.environment}"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "rds" {
  name        = "${var.app_name}-rds-sg-${var.environment}"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }
}

resource "aws_security_group" "redis" {
  name        = "${var.app_name}-redis-sg-${var.environment}"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }
}

# Application Load Balancers
resource "aws_lb" "main" {
  name               = "${var.app_name}-alb-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  idle_timeout       = 180
  enable_deletion_protection = var.environment == "production"
  
  lifecycle { prevent_destroy = true }
}

resource "aws_lb_target_group" "api" {
  name        = "${var.app_name}-api-tg-${var.environment}"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check {
    path = "/health"
    matcher = "200"
  }
}

# Listeners for main ALB
resource "aws_lb_listener" "http" {
  count             = local.enable_https ? 0 : 1
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener" "http_redirect" {
  count             = local.enable_https ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"
  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  count             = local.enable_https ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  certificate_arn   = aws_acm_certificate_validation.api[0].certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# Staging ALB (Only if environment is staging or we want parallel LB)
resource "aws_lb" "staging" {
  name               = "${var.app_name}-alb-staging"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  idle_timeout       = 180
  lifecycle { prevent_destroy = true }
}

resource "aws_lb_target_group" "api_staging" {
  name        = "${var.app_name}-api-tg-staging"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check {
    path    = "/health"
    matcher = "200"
  }
}

resource "aws_lb_listener" "staging_http" {
  count             = local.enable_https ? 0 : 1
  load_balancer_arn = aws_lb.staging.arn
  port              = "80"
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api_staging.arn
  }
}

# ECS Services
resource "aws_ecs_service" "production" {
  name            = "${var.app_name}-api-service-production"
  cluster         = aws_ecs_cluster.main.id
  task_definition = "youspeak-api-task" # Managed by CI/CD
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "youspeak-api"
    container_port   = 8000
  }
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [task_definition]
  }
}

resource "aws_ecs_service" "staging" {
  name            = "${var.app_name}-api-service-staging"
  cluster         = aws_ecs_cluster.main.id
  task_definition = "youspeak-api-task"
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs.id]
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api_staging.arn
    container_name   = "youspeak-api"
    container_port   = 8000
  }
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [task_definition]
  }
}

# ECR
resource "aws_ecr_repository" "app" {
  name                 = "${var.app_name}-backend"
  image_tag_mutability = "MUTABLE"
  lifecycle { prevent_destroy = true }
}

resource "aws_ecr_repository" "curriculum" {
  name                 = "${var.app_name}-curriculum-backend"
  image_tag_mutability = "MUTABLE"
  lifecycle { prevent_destroy = true }
}

# RDS
resource "aws_db_subnet_group" "main" {
  name       = "${var.app_name}-db-subnet-${var.environment}"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "postgres" {
  identifier             = "${var.app_name}-db-${var.environment}"
  engine                 = "postgres"
  engine_version         = "15.7"
  instance_class         = var.environment == "production" ? "db.t3.small" : "db.t3.micro"
  allocated_storage      = 20
  db_name                = "youspeak_db"
  username               = "youspeak_user"
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  skip_final_snapshot    = var.environment != "production"
  
  lifecycle { prevent_destroy = true }
}

# Redis
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.app_name}-redis-subnet-${var.environment}"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.app_name}-redis-${var.environment}"
  engine               = "redis"
  node_type            = var.environment == "production" ? "cache.t3.small" : "cache.t3.micro"
  num_cache_nodes      = 1
  engine_version       = "7.0"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]
}

# Secrets
resource "aws_secretsmanager_secret" "database_url" {
  name = "${var.app_name}/database-url-${var.environment}"
  lifecycle { prevent_destroy = true }
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id     = aws_secretsmanager_secret.database_url.id
  secret_string = "postgresql://${aws_db_instance.postgres.username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/${aws_db_instance.postgres.db_name}?sslmode=require"
}

resource "aws_secretsmanager_secret" "redis_url" {
  name = "${var.app_name}/redis-url-${var.environment}"
  lifecycle { prevent_destroy = true }
}

resource "aws_secretsmanager_secret_version" "redis_url" {
  secret_id     = aws_secretsmanager_secret.redis_url.id
  secret_string = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.cache_nodes[0].port}/0"
}

resource "aws_secretsmanager_secret" "secret_key" {
  name = "${var.app_name}/secret-key-${var.environment}"
  lifecycle { prevent_destroy = true }
}

resource "aws_secretsmanager_secret_version" "secret_key" {
  secret_id     = aws_secretsmanager_secret.secret_key.id
  secret_string = var.secret_key
}

resource "aws_secretsmanager_secret" "cloudflare_realtimekit_app_id" {
  name = "${var.app_name}/cloudflare-realtimekit-app-id-${var.environment}"
  lifecycle { prevent_destroy = true }
}

resource "aws_secretsmanager_secret_version" "cloudflare_realtimekit_app_id" {
  secret_id     = aws_secretsmanager_secret.cloudflare_realtimekit_app_id.id
  secret_string = var.cloudflare_realtimekit_app_id
}

resource "aws_secretsmanager_secret" "cloudflare_api_token" {
  name = "${var.app_name}/cloudflare-api-token-${var.environment}"
  lifecycle { prevent_destroy = true }
}

resource "aws_secretsmanager_secret_version" "cloudflare_api_token" {
  secret_id     = aws_secretsmanager_secret.cloudflare_api_token.id
  secret_string = var.cloudflare_api_token
}

resource "aws_secretsmanager_secret" "cloudflare_account_id" {
  name = "${var.app_name}/cloudflare-account-id-${var.environment}"
  lifecycle { prevent_destroy = true }
}

resource "aws_secretsmanager_secret_version" "cloudflare_account_id" {
  secret_id     = aws_secretsmanager_secret.cloudflare_account_id.id
  secret_string = var.cloudflare_account_id
}

resource "aws_secretsmanager_secret" "azure_speech_key" {
  name = "${var.app_name}/azure-speech-key-${var.environment}"
  lifecycle { prevent_destroy = true }
}

resource "aws_secretsmanager_secret_version" "azure_speech_key" {
  secret_id     = aws_secretsmanager_secret.azure_speech_key.id
  secret_string = var.azure_speech_key
}

resource "aws_secretsmanager_secret" "azure_speech_region" {
  name = "${var.app_name}/azure-speech-region-${var.environment}"
  lifecycle { prevent_destroy = true }
}

resource "aws_secretsmanager_secret_version" "azure_speech_region" {
  secret_id     = aws_secretsmanager_secret.azure_speech_region.id
  secret_string = var.azure_speech_region
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.app_name}-cluster"
}

# Data
data "aws_availability_zones" "available" { state = "available" }
data "aws_route53_zone" "main" {
  count = local.enable_https ? 1 : 0
  name  = "${var.domain_name}."
}

# SSL
resource "aws_acm_certificate" "api" {
  count             = local.enable_https ? 1 : 0
  domain_name       = local.api_fqdn
  validation_method = "DNS"
  subject_alternative_names = [local.staging_fqdn]
  lifecycle { create_before_destroy = true }
}

resource "aws_acm_certificate_validation" "api" {
  count           = local.enable_https ? 1 : 0
  certificate_arn = aws_acm_certificate.api[0].arn
}

# Outputs
output "alb_dns_name" { value = aws_lb.main.dns_name }
output "ecr_repository_url" { value = aws_ecr_repository.app.repository_url }
output "database_endpoint" {
  value     = aws_db_instance.postgres.endpoint
  sensitive = true
}

output "secret_cloudflare_realtimekit_app_id_arn" {
  value = aws_secretsmanager_secret.cloudflare_realtimekit_app_id.arn
  sensitive = true
}

output "secret_cloudflare_api_token_arn" {
  value = aws_secretsmanager_secret.cloudflare_api_token.arn
  sensitive = true
}

output "secret_cloudflare_account_id_arn" {
  value = aws_secretsmanager_secret.cloudflare_account_id.arn
  sensitive = true
}

output "secret_azure_speech_key_arn" {
  value = aws_secretsmanager_secret.azure_speech_key.arn
  sensitive = true
}

output "secret_azure_speech_region_arn" {
  value = aws_secretsmanager_secret.azure_speech_region.arn
  sensitive = true
}