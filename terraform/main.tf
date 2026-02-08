# AWS Infrastructure for YouSpeak Backend
# This Terraform configuration sets up:
# - VPC with public/private subnets
# - ECS Fargate cluster
# - Application Load Balancer
# - RDS PostgreSQL database
# - ElastiCache Redis
# - ECR repository
# - CloudWatch logs
# - Secrets Manager

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket = "youspeak-terraform-state-497068062563"
    key    = "backend/terraform.tfstate"
    region = "us-east-1"
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

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
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

# Optional: enable HTTPS with a custom domain (e.g. youspeak.com).
# Requires a Route53 hosted zone for the domain in this AWS account.
variable "domain_name" {
  description = "Root domain for API (e.g. youspeak.com). Leave empty to keep HTTP only."
  type        = string
  default     = ""
}

locals {
  enable_https = var.domain_name != ""
  api_fqdn     = local.enable_https ? "api.${var.domain_name}" : ""
  staging_fqdn = local.enable_https ? "api-staging.${var.domain_name}" : ""
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = {
    Name = "${var.app_name}-vpc-${var.environment}"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  
  tags = {
    Name = "${var.app_name}-igw-${var.environment}"
  }
}

# Public Subnets
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.${count.index + 1}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  
  tags = {
    Name = "${var.app_name}-public-subnet-${count.index + 1}-${var.environment}"
  }
}

# Private Subnets
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 10}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  
  tags = {
    Name = "${var.app_name}-private-subnet-${count.index + 1}-${var.environment}"
  }
}

# NAT Gateway
resource "aws_eip" "nat" {
  domain = "vpc"
  
  tags = {
    Name = "${var.app_name}-nat-eip-${var.environment}"
  }
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  
  tags = {
    Name = "${var.app_name}-nat-${var.environment}"
  }
}

# Route Tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  
  tags = {
    Name = "${var.app_name}-public-rt-${var.environment}"
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }
  
  tags = {
    Name = "${var.app_name}-private-rt-${var.environment}"
  }
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
  description = "Security group for ALB"
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
  description = "Security group for ECS tasks"
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
  description = "Security group for RDS"
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
  description = "Security group for Redis"
  vpc_id      = aws_vpc.main.id
  
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${var.app_name}-alb-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  
  enable_deletion_protection = var.environment == "production" ? true : false
}

resource "aws_lb_target_group" "api" {
  name        = "${var.app_name}-api-tg-${var.environment}"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 3
  }
}

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

# Staging ALB and target group (for main branch deploys)
resource "aws_lb" "staging" {
  name               = "${var.app_name}-alb-staging"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
}

resource "aws_lb_target_group" "api_staging" {
  name        = "${var.app_name}-api-tg-staging"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "staging" {
  count             = local.enable_https ? 0 : 1
  load_balancer_arn = aws_lb.staging.arn
  port              = "80"
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api_staging.arn
  }
}

resource "aws_lb_listener" "staging_http_redirect" {
  count             = local.enable_https ? 1 : 0
  load_balancer_arn = aws_lb.staging.arn
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

resource "aws_lb_listener" "staging_https" {
  count             = local.enable_https ? 1 : 0
  load_balancer_arn = aws_lb.staging.arn
  port              = "443"
  protocol          = "HTTPS"
  certificate_arn   = aws_acm_certificate_validation.api[0].certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api_staging.arn
  }
}

resource "aws_ecs_service" "production" {
  name            = "${var.app_name}-api-service-production"
  cluster         = aws_ecs_cluster.main.id
  task_definition = "youspeak-api-task"
  desired_count   = 1
  launch_type     = "FARGATE"
  platform_version = "LATEST"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "youspeak-api"
    container_port   = 8000
  }

  health_check_grace_period_seconds = 90
  enable_execute_command           = true

  lifecycle {
    ignore_changes = [task_definition]
  }
}

resource "aws_ecs_service" "staging" {
  name            = "${var.app_name}-api-service-staging"
  cluster         = aws_ecs_cluster.main.id
  task_definition = "youspeak-api-task"
  desired_count   = 1
  launch_type     = "FARGATE"
  platform_version = "LATEST"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api_staging.arn
    container_name   = "youspeak-api"
    container_port   = 8000
  }

  health_check_grace_period_seconds = 90
  enable_execute_command           = true

  lifecycle {
    ignore_changes = [task_definition]
  }
}

# ECR Repository
resource "aws_ecr_repository" "app" {
  name                 = "${var.app_name}-backend"
  image_tag_mutability = "MUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.app_name}-cluster"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.app_name}-api"
  retention_in_days = 30
}

# IAM Roles
resource "aws_iam_role" "ecs_execution" {
  name = "${var.app_name}-ecs-execution-role-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "secrets-access"
  role = aws_iam_role.ecs_execution.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = [
        aws_secretsmanager_secret.database_url.arn,
        aws_secretsmanager_secret.redis_url.arn,
        aws_secretsmanager_secret.secret_key.arn
      ]
    }]
  })
}

# RDS PostgreSQL
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
  storage_encrypted      = true
  db_name                = "youspeak_db"
  username               = "youspeak_user"
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  skip_final_snapshot    = var.environment != "production"
  backup_retention_period = var.environment == "production" ? 7 : 1
  multi_az               = var.environment == "production" ? true : false
}

# ElastiCache Redis
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.app_name}-redis-subnet-${var.environment}"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.app_name}-redis-${var.environment}"
  engine               = "redis"
  node_type            = var.environment == "production" ? "cache.t3.small" : "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]
}

# Secrets Manager
resource "aws_secretsmanager_secret" "database_url" {
  name = "${var.app_name}/database-url-${var.environment}"
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id     = aws_secretsmanager_secret.database_url.id
  secret_string = "postgresql://${aws_db_instance.postgres.username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/${aws_db_instance.postgres.db_name}"
}

resource "aws_secretsmanager_secret" "redis_url" {
  name = "${var.app_name}/redis-url-${var.environment}"
}

resource "aws_secretsmanager_secret_version" "redis_url" {
  secret_id     = aws_secretsmanager_secret.redis_url.id
  secret_string = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.cache_nodes[0].port}/0"
}

resource "aws_secretsmanager_secret" "secret_key" {
  name = "${var.app_name}/secret-key-${var.environment}"
}

resource "aws_secretsmanager_secret_version" "secret_key" {
  secret_id     = aws_secretsmanager_secret.secret_key.id
  secret_string = var.secret_key
}

# Data Sources
data "aws_availability_zones" "available" {
  state = "available"
}

# Route53 zone for domain (required when domain_name is set)
data "aws_route53_zone" "main" {
  count = local.enable_https ? 1 : 0
  name  = "${var.domain_name}."
}

# ACM certificate for api and api-staging
resource "aws_acm_certificate" "api" {
  count             = local.enable_https ? 1 : 0
  domain_name       = local.api_fqdn
  validation_method = "DNS"
  subject_alternative_names = [local.staging_fqdn]
  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cert_validation" {
  for_each = local.enable_https ? {
    for dvo in aws_acm_certificate.api[0].domain_validation_options : dvo.domain_name => dvo
  } : {}
  zone_id = data.aws_route53_zone.main[0].zone_id
  name    = each.value.resource_record_name
  type    = each.value.resource_record_type
  records = [each.value.resource_record_value]
  ttl     = 60
}

resource "aws_acm_certificate_validation" "api" {
  count                   = local.enable_https ? 1 : 0
  certificate_arn         = aws_acm_certificate.api[0].arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}

# Route53 A records (alias to ALB) for api and api-staging
resource "aws_route53_record" "api" {
  count   = local.enable_https ? 1 : 0
  zone_id = data.aws_route53_zone.main[0].zone_id
  name    = local.api_fqdn
  type    = "A"
  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health  = true
  }
}

resource "aws_route53_record" "api_staging" {
  count   = local.enable_https ? 1 : 0
  zone_id = data.aws_route53_zone.main[0].zone_id
  name    = local.staging_fqdn
  type    = "A"
  alias {
    name                   = aws_lb.staging.dns_name
    zone_id                = aws_lb.staging.zone_id
    evaluate_target_health = true
  }
}

# Outputs
output "alb_dns_name" {
  description = "DNS name of the load balancer"
  value       = aws_lb.main.dns_name
}

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.app.repository_url
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "database_endpoint" {
  description = "RDS database endpoint"
  value       = aws_db_instance.postgres.endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = "${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.cache_nodes[0].port}"
  sensitive   = true
}

output "ecs_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  value       = aws_iam_role.ecs_execution.arn
}

output "secret_database_url_arn" {
  description = "ARN of the database URL secret"
  value       = aws_secretsmanager_secret.database_url.arn
}

output "secret_redis_url_arn" {
  description = "ARN of the Redis URL secret"
  value       = aws_secretsmanager_secret.redis_url.arn
}

output "secret_secret_key_arn" {
  description = "ARN of the secret key secret"
  value       = aws_secretsmanager_secret.secret_key.arn
}

output "private_subnet_ids" {
  description = "Private subnet IDs for ECS (comma-separated, for GitHub Actions)"
  value       = join(",", aws_subnet.private[*].id)
}

output "ecs_security_group_id" {
  description = "ECS tasks security group ID (for GitHub Actions)"
  value       = aws_security_group.ecs.id
}

output "alb_staging_dns_name" {
  description = "Staging ALB DNS name (main branch deploys here)"
  value       = aws_lb.staging.dns_name
}

output "api_url_https" {
  description = "Production API URL (HTTPS). Set when domain_name is configured."
  value       = local.enable_https ? "https://${local.api_fqdn}" : null
}

output "api_staging_url_https" {
  description = "Staging API URL (HTTPS). Set when domain_name is configured."
  value       = local.enable_https ? "https://${local.staging_fqdn}" : null
}
