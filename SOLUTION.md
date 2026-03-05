# Staging Curriculum Service - Root Cause & Solution

## 🔍 Root Cause Found!

**Issue:** 504 Gateway Timeout when accessing curriculum endpoints
**Root Cause:** Load balancer target is **UNHEALTHY** due to **Target.Timeout**

## Diagnostic Results

### Service Status
```
✅ ECS Service: RUNNING (1/1 tasks)
✅ Container: HEALTHY
❌ Load Balancer Target: UNHEALTHY (Target.Timeout)
```

### Target Health
```json
{
  "Target": "10.0.10.124",
  "Port": 8001,
  "Health": "unhealthy",
  "Reason": "Target.Timeout"
}
```

The load balancer **cannot reach the service on port 8001** due to timeout.

## Possible Causes

### 1. Security Group Issue (Most Likely)
The security groups might not allow traffic from the load balancer to the service.

**Check:**
```bash
# Get curriculum service security group
TASK_SG=$(aws ecs describe-tasks \
  --cluster youspeak-cluster \
  --tasks $(aws ecs list-tasks --cluster youspeak-cluster --service-name youspeak-curriculum-service-staging --region us-east-1 --query 'taskArns[0]' --output text) \
  --region us-east-1 \
  --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' \
  --output text | xargs aws ec2 describe-network-interfaces --network-interface-ids --region us-east-1 --query 'NetworkInterfaces[0].Groups[0].GroupId' --output text)

# Check inbound rules
aws ec2 describe-security-groups --group-ids $TASK_SG --region us-east-1 --query 'SecurityGroups[0].IpPermissions'
```

**Fix:**
The security group needs to allow inbound TCP on port 8001 from the load balancer security group.

### 2. Service Not Listening on Port 8001
The container might be running but not listening on the expected port.

**Check logs:**
```bash
aws logs tail /ecs/youspeak-curriculum-api --follow --region us-east-1
```

Look for:
- Port binding messages (e.g., "Listening on :8001")
- Startup errors
- Health check failures

### 3. Health Check Configuration
The health check path or timeout might be misconfigured.

**Check target group health check:**
```bash
aws elbv2 describe-target-groups \
  --target-group-arns arn:aws:elasticloadbalancing:us-east-1:497068062563:targetgroup/youspeak-curric-tg-stg/fb119ff5cf07df94 \
  --region us-east-1 \
  --query 'TargetGroups[0].{HealthCheckPath:HealthCheckPath,HealthCheckPort:HealthCheckPort,HealthCheckProtocol:HealthCheckProtocol,HealthCheckTimeoutSeconds:HealthCheckTimeoutSeconds,UnhealthyThresholdCount:UnhealthyThresholdCount}' \
  --output json | jq '.'
```

## Quick Fix Options

### Option 1: Re-apply Terraform (Recommended)
This will ensure all security groups and configurations are correct:

```bash
cd terraform
terraform apply -var=environment=staging -auto-approve
```

### Option 2: Force Service Restart
Sometimes a restart can fix transient issues:

```bash
aws ecs update-service \
  --cluster youspeak-cluster \
  --service youspeak-curriculum-service-staging \
  --force-new-deployment \
  --region us-east-1
```

Wait 2-3 minutes, then check target health again:

```bash
aws elbv2 describe-target-health \
  --target-group-arn arn:aws:elasticloadbalancing:us-east-1:497068062563:targetgroup/youspeak-curric-tg-stg/fb119ff5cf07df94 \
  --region us-east-1
```

### Option 3: Manual Security Group Fix
If you identify the security group issue, you can add the rule manually:

```bash
# Get load balancer security group
LB_SG=$(aws elbv2 describe-load-balancers \
  --names internal-youspeak-curric-int-stg \
  --region us-east-1 \
  --query 'LoadBalancers[0].SecurityGroups[0]' \
  --output text)

# Add rule to allow traffic from LB to service
aws ec2 authorize-security-group-ingress \
  --group-id <SERVICE_SECURITY_GROUP_ID> \
  --protocol tcp \
  --port 8001 \
  --source-group $LB_SG \
  --region us-east-1
```

## Verification Steps

After applying fixes:

1. **Check target health:**
   ```bash
   watch 'aws elbv2 describe-target-health --target-group-arn arn:aws:elasticloadbalancing:us-east-1:497068062563:targetgroup/youspeak-curric-tg-stg/fb119ff5cf07df94 --region us-east-1 --query "TargetHealthDescriptions[0].TargetHealth.State" --output text'
   ```

   Wait for: `healthy`

2. **Test endpoint:**
   ```bash
   ./test_staging_full_flow.sh
   ```

3. **Expected result:**
   - ✅ School registration
   - ✅ Login
   - ✅ List curriculums (empty for new school)
   - ✅ GET curriculum (404 for non-existent ID, as expected)

## Summary

| Component | Status | Issue |
|-----------|--------|-------|
| ECS Service | ✅ Running | None |
| Container | ✅ Healthy | None |
| Load Balancer Target | ❌ Unhealthy | **Target.Timeout** |
| Root Cause | - | **Security group or network config** |

**Next Action:** Re-apply Terraform to fix security groups and network configuration.

## Scripts Available

1. `./check_curriculum_status.sh` - Quick status check
2. `./fix_curriculum_service.sh` - Interactive diagnostic and fix
3. `./test_staging_full_flow.sh` - End-to-end test after fix

## Test Account

A test account was created for verification:
- **Email:** `admin_20260304_174413_d476853e@test.com`
- **Password:** `TestPass123!`
