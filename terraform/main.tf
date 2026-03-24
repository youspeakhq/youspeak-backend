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

variable "resend_api_key" {
  description = "Resend API key for transactional emails (teacher invites)"
  type        = string
  sensitive   = true
  default     = ""
}

# Cloudflare R2 (S3-compatible) storage – optional. Create API token in Cloudflare dashboard (R2 > Manage R2 API Tokens).
variable "r2_account_id" {
  description = "Cloudflare R2 account ID (e.g. from bucket S3 API URL)"
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
  description = "Public URL for stored objects (R2 dev URL or custom domain)"
  type        = string
  default     = "https://pub-2dc65d0e715b43b5ab0985e9c0eb514c.r2.dev"
}

# Cloudflare RealtimeKit (Audio Conferencing) - optional
variable "cloudflare_realtimekit_app_id" {
  description = "Cloudflare RealtimeKit App ID"
  type        = string
  default     = ""
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token with Realtime Admin permissions"
  type        = string
  sensitive   = true
  default     = ""
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
  idle_timeout       = 180 # allow long-running requests (e.g. curriculum generate / Bedrock)

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
  idle_timeout       = 180 # allow long-running requests (e.g. curriculum generate / Bedrock)
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

# Auto-scaling for staging: scale to 0-2 tasks based on CPU/memory
resource "aws_appautoscaling_target" "staging" {
  max_capacity       = 2
  min_capacity       = 0  # Scale to zero during low traffic
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.staging.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "staging_cpu" {
  name               = "${var.app_name}-staging-cpu-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.staging.resource_id
  scalable_dimension = aws_appautoscaling_target.staging.scalable_dimension
  service_namespace  = aws_appautoscaling_target.staging.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 30.0  # Scale down if CPU < 30%
    scale_in_cooldown  = 300   # Wait 5 min before scaling in
    scale_out_cooldown = 60    # Wait 1 min before scaling out
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

resource "aws_appautoscaling_policy" "staging_memory" {
  name               = "${var.app_name}-staging-memory-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.staging.resource_id
  scalable_dimension = aws_appautoscaling_target.staging.scalable_dimension
  service_namespace  = aws_appautoscaling_target.staging.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 30.0  # Scale down if memory < 30%
    scale_in_cooldown  = 300   # Wait 5 min before scaling in
    scale_out_cooldown = 60    # Wait 1 min before scaling out
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
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

# ECR Repository (curriculum microservice)
resource "aws_ecr_repository" "curriculum" {
  name                 = "${var.app_name}-curriculum-backend"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
}

# CloudWatch Log Group (curriculum)
resource "aws_cloudwatch_log_group" "curriculum" {
  name              = "/ecs/${var.app_name}-curriculum-api"
  retention_in_days = 14
}

# Security group for curriculum internal ALB (core API tasks reach this on 80)
resource "aws_security_group" "curriculum_alb_internal" {
  name        = "${var.app_name}-curriculum-alb-internal-${var.environment}"
  description = "Internal ALB for curriculum service"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ECS SG must allow outbound to curriculum ALB (already has egress 0.0.0.0/0)

# Internal ALB and TG for curriculum (production)
resource "aws_lb" "curriculum_internal_production" {
  name               = "${var.app_name}-curric-int-prod"
  internal           = true
  load_balancer_type = "application"
  security_groups    = [aws_security_group.curriculum_alb_internal.id]
  subnets            = aws_subnet.private[*].id
  idle_timeout       = 180 # allow long-running database queries and AI operations
}

resource "aws_lb_target_group" "curriculum_production" {
  name        = "${var.app_name}-curric-tg-prod"
  port        = 8001
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

resource "aws_lb_listener" "curriculum_internal_production" {
  load_balancer_arn = aws_lb.curriculum_internal_production.arn
  port              = "80"
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.curriculum_production.arn
  }
}

# Internal ALB and TG for curriculum (staging)
resource "aws_lb" "curriculum_internal_staging" {
  name               = "${var.app_name}-curric-int-stg"
  internal           = true
  load_balancer_type = "application"
  security_groups    = [aws_security_group.curriculum_alb_internal.id]
  subnets            = aws_subnet.private[*].id
  idle_timeout       = 180 # allow long-running database queries and AI operations
}

resource "aws_lb_target_group" "curriculum_staging" {
  name        = "${var.app_name}-curric-tg-stg"
  port        = 8001
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

resource "aws_lb_listener" "curriculum_internal_staging" {
  load_balancer_arn = aws_lb.curriculum_internal_staging.arn
  port              = "80"
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.curriculum_staging.arn
  }
}

# ECS service: curriculum production
resource "aws_ecs_service" "curriculum_production" {
  name            = "${var.app_name}-curriculum-service-production"
  cluster         = aws_ecs_cluster.main.id
  task_definition = "youspeak-curriculum-task"
  desired_count   = 1
  launch_type     = "FARGATE"
  platform_version = "LATEST"
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.curriculum_production.arn
    container_name   = "youspeak-curriculum"
    container_port   = 8001
  }
  health_check_grace_period_seconds = 90
  enable_execute_command           = true
  lifecycle {
    ignore_changes = [task_definition]
  }
}

# Curriculum microservice: ECS task definition for staging. Uses current env's secrets so staging
# can share DB/secrets when using a single state, or use staging secrets when applied with environment=staging.
resource "aws_ecs_task_definition" "curriculum_staging" {
  family                   = "youspeak-curriculum-task-staging"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  ephemeral_storage {
    size_in_gib = 50
  }
  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "youspeak-curriculum"
    image     = "${aws_ecr_repository.curriculum.repository_url}:latest"
    essential = true
    portMappings = [{ containerPort = 8001, protocol = "tcp" }]
    environment = [
      { name = "ENVIRONMENT", value = "staging" },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "BEDROCK_MODEL_ID", value = "amazon.nova-lite-v1:0" }
    ]
    secrets = concat(
      [{ name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn }],
      var.r2_access_key_id != "" ? [
        { name = "R2_ACCOUNT_ID", valueFrom = aws_secretsmanager_secret.r2_account_id[0].arn },
        { name = "R2_ACCESS_KEY_ID", valueFrom = aws_secretsmanager_secret.r2_access_key_id[0].arn },
        { name = "R2_SECRET_ACCESS_KEY", valueFrom = aws_secretsmanager_secret.r2_secret_access_key[0].arn },
        { name = "R2_BUCKET_NAME", valueFrom = aws_secretsmanager_secret.r2_bucket_name[0].arn }
      ] : [],
      var.cloudflare_api_token != "" ? [
        { name = "CLOUDFLARE_ACCOUNT_ID", valueFrom = aws_secretsmanager_secret.cloudflare_account_id[0].arn },
        { name = "CLOUDFLARE_REALTIMEKIT_APP_ID", valueFrom = aws_secretsmanager_secret.cloudflare_realtimekit_app_id[0].arn },
        { name = "CLOUDFLARE_API_TOKEN", valueFrom = aws_secretsmanager_secret.cloudflare_api_token[0].arn }
      ] : []
    )
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.curriculum.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
        "awslogs-create-group"  = "true"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "python3 -c \"import urllib.request; urllib.request.urlopen('http://localhost:8001/health')\" || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])
}

# ECS service: curriculum staging (microservice; uses Terraform task def above)
resource "aws_ecs_service" "curriculum_staging" {
  name            = "${var.app_name}-curriculum-service-staging"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.curriculum_staging.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  platform_version = "LATEST"
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.curriculum_staging.arn
    container_name   = "youspeak-curriculum"
    container_port   = 8001
  }
  health_check_grace_period_seconds = 90
  enable_execute_command           = true
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
# Note: Both staging and production share this log group (task definition uses same name)
# Setting to 14 days as compromise (could be optimized further with separate log groups)
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.app_name}-api"
  retention_in_days = 14  # Compromise: 14 days (was 30, saves ~$1/month)
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
      Resource = concat(
        [
          aws_secretsmanager_secret.database_url.arn,
          aws_secretsmanager_secret.redis_url.arn,
          aws_secretsmanager_secret.secret_key.arn
        ],
        var.resend_api_key != "" ? [aws_secretsmanager_secret.resend_api_key[0].arn] : [],
        var.r2_access_key_id != "" ? [
          aws_secretsmanager_secret.r2_account_id[0].arn,
          aws_secretsmanager_secret.r2_access_key_id[0].arn,
          aws_secretsmanager_secret.r2_secret_access_key[0].arn,
          aws_secretsmanager_secret.r2_bucket_name[0].arn
        ] : [],
        var.cloudflare_api_token != "" ? [
          aws_secretsmanager_secret.cloudflare_account_id[0].arn,
          aws_secretsmanager_secret.cloudflare_realtimekit_app_id[0].arn,
          aws_secretsmanager_secret.cloudflare_api_token[0].arn
        ] : []
      )
    }]
  })
}

# ECS Task Role (for Bedrock and other runtime AWS services)
resource "aws_iam_role" "ecs_task" {
  name = "${var.app_name}-ecs-task-role-${var.environment}"
  
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

resource "aws_iam_role_policy_attachment" "bedrock" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
}

# AWS Marketplace permissions required for Bedrock to auto-enable foundation model access on first
# invocation (see https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html).
# Without these, first-time model use can fail with 403. If the account is a "channel program
# account", AWS may still block access until the Solution Provider/Distributor enables it;
# Terraform cannot override that restriction.
resource "aws_iam_role_policy" "bedrock_marketplace_model_access" {
  name   = "${var.app_name}-bedrock-marketplace-model-access-${var.environment}"
  role   = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "BedrockFoundationModelSubscription"
      Effect = "Allow"
      Action = [
        "aws-marketplace:Subscribe",
        "aws-marketplace:Unsubscribe",
        "aws-marketplace:ViewSubscriptions"
      ]
      Resource = "*"
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
  secret_string = "postgresql://${aws_db_instance.postgres.username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/${aws_db_instance.postgres.db_name}?sslmode=require"
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

resource "aws_secretsmanager_secret" "resend_api_key" {
  count = var.resend_api_key != "" ? 1 : 0
  name  = "${var.app_name}/resend-api-key-${var.environment}"
}

resource "aws_secretsmanager_secret_version" "resend_api_key" {
  count         = var.resend_api_key != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.resend_api_key[0].id
  secret_string = var.resend_api_key
}

# R2 storage secrets (optional – set r2_access_key_id to enable)
resource "aws_secretsmanager_secret" "r2_account_id" {
  count  = var.r2_access_key_id != "" ? 1 : 0
  name   = "${var.app_name}/r2-account-id-${var.environment}"
}

resource "aws_secretsmanager_secret_version" "r2_account_id" {
  count         = var.r2_access_key_id != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.r2_account_id[0].id
  secret_string = var.r2_account_id
}

resource "aws_secretsmanager_secret" "r2_access_key_id" {
  count  = var.r2_access_key_id != "" ? 1 : 0
  name   = "${var.app_name}/r2-access-key-id-${var.environment}"
}

resource "aws_secretsmanager_secret_version" "r2_access_key_id" {
  count         = var.r2_access_key_id != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.r2_access_key_id[0].id
  secret_string = var.r2_access_key_id
}

resource "aws_secretsmanager_secret" "r2_secret_access_key" {
  count  = var.r2_access_key_id != "" ? 1 : 0
  name   = "${var.app_name}/r2-secret-access-key-${var.environment}"
}

resource "aws_secretsmanager_secret_version" "r2_secret_access_key" {
  count         = var.r2_access_key_id != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.r2_secret_access_key[0].id
  secret_string = var.r2_secret_access_key
}

resource "aws_secretsmanager_secret" "r2_bucket_name" {
  count  = var.r2_access_key_id != "" ? 1 : 0
  name   = "${var.app_name}/r2-bucket-name-${var.environment}"
}

resource "aws_secretsmanager_secret_version" "r2_bucket_name" {
  count         = var.r2_access_key_id != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.r2_bucket_name[0].id
  secret_string = var.r2_bucket_name
}

# Cloudflare RealtimeKit secrets (optional - set cloudflare_api_token to enable)
resource "aws_secretsmanager_secret" "cloudflare_account_id" {
  count = var.cloudflare_api_token != "" ? 1 : 0
  name  = "${var.app_name}/cloudflare-account-id-${var.environment}"
}

resource "aws_secretsmanager_secret_version" "cloudflare_account_id" {
  count         = var.cloudflare_api_token != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.cloudflare_account_id[0].id
  secret_string = var.r2_account_id  # Same as R2 account ID
}

resource "aws_secretsmanager_secret" "cloudflare_realtimekit_app_id" {
  count = var.cloudflare_api_token != "" ? 1 : 0
  name  = "${var.app_name}/cloudflare-realtimekit-app-id-${var.environment}"
}

resource "aws_secretsmanager_secret_version" "cloudflare_realtimekit_app_id" {
  count         = var.cloudflare_api_token != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.cloudflare_realtimekit_app_id[0].id
  secret_string = var.cloudflare_realtimekit_app_id
}

resource "aws_secretsmanager_secret" "cloudflare_api_token" {
  count = var.cloudflare_api_token != "" ? 1 : 0
  name  = "${var.app_name}/cloudflare-api-token-${var.environment}"
}

resource "aws_secretsmanager_secret_version" "cloudflare_api_token" {
  count         = var.cloudflare_api_token != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.cloudflare_api_token[0].id
  secret_string = var.cloudflare_api_token
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

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role (for Bedrock access)"
  value       = aws_iam_role.ecs_task.arn
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

output "secret_resend_api_key_arn" {
  description = "ARN of the Resend API key secret (empty if not configured)"
  value       = var.resend_api_key != "" ? aws_secretsmanager_secret.resend_api_key[0].arn : ""
}

output "secret_r2_account_id_arn" {
  description = "ARN of the R2 account ID secret (empty if R2 not configured)"
  value       = var.r2_access_key_id != "" ? aws_secretsmanager_secret.r2_account_id[0].arn : ""
}

output "secret_r2_access_key_id_arn" {
  description = "ARN of the R2 access key ID secret (empty if R2 not configured)"
  value       = var.r2_access_key_id != "" ? aws_secretsmanager_secret.r2_access_key_id[0].arn : ""
}

output "secret_r2_secret_access_key_arn" {
  description = "ARN of the R2 secret access key secret (empty if R2 not configured)"
  value       = var.r2_access_key_id != "" ? aws_secretsmanager_secret.r2_secret_access_key[0].arn : ""
}

output "secret_r2_bucket_name_arn" {
  description = "ARN of the R2 bucket name secret (empty if R2 not configured)"
  value       = var.r2_access_key_id != "" ? aws_secretsmanager_secret.r2_bucket_name[0].arn : ""
}

output "secret_cloudflare_account_id_arn" {
  description = "ARN of the Cloudflare account ID secret (empty if RealtimeKit not configured)"
  value       = var.cloudflare_api_token != "" ? aws_secretsmanager_secret.cloudflare_account_id[0].arn : ""
}

output "secret_cloudflare_realtimekit_app_id_arn" {
  description = "ARN of the Cloudflare RealtimeKit app ID secret (empty if RealtimeKit not configured)"
  value       = var.cloudflare_api_token != "" ? aws_secretsmanager_secret.cloudflare_realtimekit_app_id[0].arn : ""
}

output "secret_cloudflare_api_token_arn" {
  description = "ARN of the Cloudflare API token secret (empty if RealtimeKit not configured)"
  value       = var.cloudflare_api_token != "" ? aws_secretsmanager_secret.cloudflare_api_token[0].arn : ""
}

output "storage_public_base_url" {
  description = "Public base URL for R2 objects (for ECS task environment)"
  value       = var.storage_public_base_url
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

output "curriculum_service_url_production" {
  description = "Internal URL for curriculum service (production). Use as CURRICULUM_SERVICE_URL for core API production task."
  value       = "http://${aws_lb.curriculum_internal_production.dns_name}"
}

output "curriculum_service_url_staging" {
  description = "Internal URL for curriculum service (staging). Use as CURRICULUM_SERVICE_URL for core API staging task."
  value       = "http://${aws_lb.curriculum_internal_staging.dns_name}"
}

output "ecr_curriculum_repository_url" {
  description = "ECR repository URL for curriculum service image"
  value       = aws_ecr_repository.curriculum.repository_url
}