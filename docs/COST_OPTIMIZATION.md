# Cost Optimization Guide for YouSpeak Backend

## Current Infrastructure & Monthly Costs

| Resource | Configuration | Estimated Monthly Cost |
|----------|--------------|------------------------|
| **ECS Fargate** (2 tasks: staging + production) | 0.5 vCPU, 1GB RAM each | $30-40 |
| **RDS PostgreSQL** | db.t3.small, Multi-AZ, 20GB | $50-60 |
| **ElastiCache Redis** | cache.t3.micro | $12-15 |
| **Application Load Balancer** (2 ALBs) | Standard, 2 ALBs | $40 |
| **NAT Gateway** | Standard | $32 |
| **Data Transfer** | ~100GB/month | $9 |
| **ECR Storage** | ~5GB images | $0.50 |
| **CloudWatch Logs** | 7-day retention (staging), 30-day (production) | $1-3 |
| **Secrets Manager** | 3 secrets | $1.50 |
| **Total** | | **~$178-203/month** |

---

## Why ECS Fargate Instead of EC2?

### ✅ **ECS Fargate Advantages:**

1. **No Server Management**
   - No EC2 instances to patch, secure, or monitor
   - AWS handles OS updates, security patches, capacity planning
   - Reduces operational overhead significantly

2. **Cost Efficiency for Low-Medium Traffic**
   - **Fargate**: Pay only for running containers (0.5 vCPU + 1GB = ~$15/month per task)
   - **EC2**: Pay for entire instance 24/7 even if idle (t3.small = ~$15/month + EBS + you still need ECS)
   - For 2 tasks, Fargate is comparable or cheaper than EC2 + ECS

3. **Auto-Scaling Built-In**
   - Fargate scales containers up/down automatically
   - EC2 requires ASG setup, instance lifecycle management

4. **Better Security**
   - Containers run in isolated environments
   - No SSH access needed (reduces attack surface)
   - IAM roles per task, not per instance

5. **Faster Deployments**
   - No instance provisioning wait time
   - Containers start in seconds vs minutes for EC2

### ⚠️ **When EC2 Makes Sense:**

- **Very high traffic** (>1000 req/s sustained) where EC2 reserved instances save 30-60%
- **Specialized hardware** requirements (GPU, high-memory)
- **Strict compliance** requiring full OS control
- **Cost optimization** with Reserved Instances for predictable workloads

**For YouSpeak:** Fargate is the right choice unless you're processing >1M requests/day.

---

## Cost Optimization Strategies

### 1. **Immediate Savings (No Code Changes)**

#### A. Reduce RDS Multi-AZ (Save ~$25/month)
**Current:** Multi-AZ enabled (production)
**Change:** Disable Multi-AZ for staging, keep for production only
**Savings:** ~$25/month
**Risk:** Staging loses high availability (acceptable for non-production)

```hcl
# In terraform/main.tf, line 543:
multi_az = var.environment == "production" ? true : false
```
✅ **Already configured correctly**

#### B. Use Smaller RDS Instance for Staging (Save ~$20/month)
**Current:** db.t3.small for both environments
**Change:** Use db.t3.micro for staging
**Savings:** ~$20/month

```hcl
# Already configured:
instance_class = var.environment == "production" ? "db.t3.small" : "db.t3.micro"
```
✅ **Already configured correctly**

#### C. Auto-Scale Staging to Zero (Save ~$7-15/month)
**Current:** 1 task per environment (staging + production = 2 tasks)
**Change:** ✅ **IMPLEMENTED** - Auto-scaling configured to scale staging to 0-2 tasks based on CPU/memory
**Savings:** ~$7-15/month during low-traffic periods

**Implementation:** Terraform auto-scaling policies scale staging to 0 when CPU/memory < 30% for 5+ minutes.

#### D. Reduce CloudWatch Log Retention (Save ~$2/month)
**Current:** 30 days retention
**Change:** ✅ **IMPLEMENTED** - 7 days for staging, 30 for production
**Savings:** ~$2/month

**Implementation:** CloudWatch log group retention is now environment-aware in Terraform.

---

### 2. **Medium-Term Savings (Requires Changes)**

#### A. Use AWS Savings Plans (Save 20-30%)
**What:** Commit to 1-year or 3-year usage for ECS Fargate
**Savings:** 20% (1-year) or 30% (3-year)
**Monthly Savings:** ~$6-9/month
**Trade-off:** Less flexibility to change instance sizes

**How:** AWS Console → Cost Management → Savings Plans → Purchase

#### B. Use RDS Reserved Instances (Save 30-60%)
**What:** Commit to 1-year or 3-year RDS instance
**Savings:** 30% (1-year) or 60% (3-year)
**Monthly Savings:** ~$15-30/month
**Trade-off:** Locked into db.t3.small for the term

**How:** AWS Console → RDS → Reserved Instances → Purchase

#### C. Remove NAT Gateway (Save $32/month)
**Current:** NAT Gateway allows private subnets to reach internet
**Change:** Use VPC endpoints for AWS services (S3, ECR, Secrets Manager)
**Savings:** $32/month
**Trade-off:** More complex setup, VPC endpoints cost ~$7/month each

**VPC Endpoints needed:**
- `com.amazonaws.us-east-1.s3` (for ECR image pulls)
- `com.amazonaws.us-east-1.ecr.dkr` (for ECR API)
- `com.amazonaws.us-east-1.secretsmanager` (for Secrets Manager)

**Net Savings:** ~$11/month (after endpoint costs)

---

### 3. **Advanced Optimizations**

#### A. Auto-Scaling Based on Traffic
**Current:** Fixed 1 task per environment
**Change:** Scale to 0-2 tasks based on CPU/memory/request count
**Savings:** ~$7-15/month during low-traffic periods

**ECS Auto-Scaling Setup:**
```hcl
resource "aws_appautoscaling_target" "ecs_target" {
  max_capacity       = 2
  min_capacity       = 0  # Scale to zero for staging
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.staging.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "ecs_policy" {
  name               = "scale-down-on-low-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 30.0  # Scale down if CPU < 30%
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}
```

#### B. Use Spot Instances for Non-Critical Workloads
**Not applicable for Fargate** (Fargate doesn't support Spot). Would require switching to EC2.

#### C. Consolidate ALBs (Save ~$20/month)
**Current:** 2 ALBs (staging + production)
**Change:** Use path-based routing on single ALB
**Savings:** ~$20/month
**Trade-off:** More complex routing rules, shared ALB limits

---

## Recommended Immediate Actions

### Priority 1: Quick Wins (No Code Changes)
1. ✅ **Already optimized:** RDS instance sizes (micro for staging, small for production)
2. ✅ **Already optimized:** Multi-AZ only for production
3. ✅ **IMPLEMENTED:** Auto-scaling for staging (scales to 0 during low traffic)
4. ✅ **IMPLEMENTED:** Reduced CloudWatch log retention for staging (7 days)

**Estimated Savings:** ~$9-17/month (depends on traffic patterns)

### Priority 2: Commit to Savings Plans (If Usage is Stable)
1. **Purchase:** 1-year ECS Fargate Savings Plan (20% discount)
2. **Purchase:** 1-year RDS Reserved Instance (30% discount)

**Estimated Savings:** ~$21/month

### Priority 3: Advanced (If Traffic is Low)
1. **Add:** Auto-scaling to scale staging to 0 during low traffic
2. **Consider:** VPC endpoints instead of NAT Gateway (if endpoints < $32/month)

**Estimated Savings:** ~$11-15/month

---

## Cost Monitoring

### Set Up Billing Alerts

✅ **IMPLEMENTED** - Use the setup script:

```bash
./scripts/setup-billing-alerts.sh your-email@example.com
```

This creates:
- SNS topic for billing notifications
- Email subscription (you must confirm via email)
- CloudWatch alarm at $150/month (warning)
- CloudWatch alarm at $200/month (alert)

**Manual setup** (if you prefer):
```bash
# Create SNS topic for billing alerts
aws sns create-topic --name billing-alerts

# Create CloudWatch alarm for monthly spend
aws cloudwatch put-metric-alarm \
  --alarm-name monthly-billing-alert \
  --alarm-description "Alert when monthly AWS bill exceeds $200" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 200 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=Currency,Value=USD
```

### View Current Costs

```bash
# Get cost breakdown by service
aws ce get-cost-and-usage \
  --time-period Start=2026-02-01,End=2026-02-09 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=SERVICE
```

---

## Summary

**Current Monthly Cost:** ~$178-203/month

**After Quick Wins:** ✅ **~$161-194/month** (save ~$9-17/month, depending on traffic)

**After Savings Plans:** ~$140-165/month (save ~$38/month)

**After All Optimizations:** ~$120-145/month (save ~$58/month)

**Best Value:** Use Savings Plans + scale staging to 0 during off-hours = **~$140/month** (30% reduction)
