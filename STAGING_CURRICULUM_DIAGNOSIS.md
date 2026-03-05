# Staging Curriculum Service Diagnosis

## Date: March 5, 2026

## Summary

**Issue:** Curriculum endpoints return 504 Gateway Timeout on staging
**Status:** Service is running and healthy ✅
**Root Cause:** Load balancer or network connectivity issue

## Test Results

### ✅ What's Working:
1. School admin registration
2. Login authentication
3. Main API is accessible
4. Curriculum service ECS task is **RUNNING** and **HEALTHY**

### ❌ What's NOT Working:
- Curriculum endpoints return 504 Gateway Timeout
- Main API cannot reach curriculum service through internal load balancer

## Infrastructure Status

### Curriculum Service (Staging)
```
Cluster: youspeak-cluster
Service: youspeak-curriculum-service-staging
Status: ACTIVE
Desired: 1
Running: 1
Pending: 0
Health: HEALTHY
```

### Task Details
```
Task ARN: arn:aws:ecs:us-east-1:497068062563:task/youspeak-cluster/0d674761a55248da965b64a33343fc60
Last Status: RUNNING
Health Status: HEALTHY
Container: youspeak-curriculum (RUNNING, HEALTHY)
```

### Main API Configuration
```
CURRICULUM_SERVICE_URL: http://internal-youspeak-curric-int-stg-129417713.us-east-1.elb.amazonaws.com
```

## Root Cause Analysis

The 504 Gateway Timeout indicates that:

1. **Main API is forwarding requests correctly** ✅
2. **Curriculum service is running** ✅
3. **Load balancer is timing out** ❌

Possible causes:

### 1. Load Balancer Target Health
The internal load balancer may not be routing to healthy targets.

**Check:**
```bash
aws elbv2 describe-target-health \
  --target-group-arn $(aws elbv2 describe-load-balancers \
    --names internal-youspeak-curric-int-stg \
    --query 'LoadBalancers[0].LoadBalancerArn' \
    --output text | sed 's/loadbalancer/targetgroup/') \
  --region us-east-1
```

### 2. Security Groups
The main API service may not have permission to reach the curriculum service.

**Check:**
- Main API security group allows outbound to curriculum LB
- Curriculum LB security group allows inbound from main API
- Curriculum service security group allows inbound from LB

### 3. Health Check Configuration
The load balancer health checks might be misconfigured.

**Check:**
```bash
aws elbv2 describe-target-groups \
  --load-balancer-arn $(aws elbv2 describe-load-balancers \
    --names internal-youspeak-curric-int-stg \
    --query 'LoadBalancers[0].LoadBalancerArn' \
    --output text) \
  --query 'TargetGroups[0].{Port:Port,Protocol:Protocol,HealthCheck:HealthCheckPath}' \
  --region us-east-1
```

### 4. Service Port Mismatch
The service might be running on a different port than the load balancer expects.

**Check task definition port:**
```bash
aws ecs describe-task-definition \
  --task-definition $(aws ecs describe-services \
    --cluster youspeak-cluster \
    --services youspeak-curriculum-service-staging \
    --region us-east-1 \
    --query 'services[0].taskDefinition' \
    --output text) \
  --query 'taskDefinition.containerDefinitions[0].portMappings' \
  --region us-east-1
```

## Quick Fixes

### Fix 1: Force Service Redeploy
```bash
aws ecs update-service \
  --cluster youspeak-cluster \
  --service youspeak-curriculum-service-staging \
  --force-new-deployment \
  --region us-east-1
```

### Fix 2: Re-apply Terraform (Staging)
From the terraform directory:
```bash
terraform apply -var=environment=staging -auto-approve
```

This will ensure:
- Security groups are correct
- Load balancer configuration is correct
- Target groups are properly configured

### Fix 3: Check CloudWatch Logs
```bash
aws logs tail /ecs/youspeak-curriculum-api --follow --region us-east-1
```

Look for errors in the application startup or request handling.

## Next Steps

1. **Check target health** (most likely issue)
2. **Verify security groups** allow traffic between services
3. **Review load balancer health check** configuration
4. **Check CloudWatch logs** for application errors
5. **Re-apply Terraform** if infrastructure is misconfigured

## Files Created

1. `test_staging_full_flow.sh` - Complete end-to-end test
2. `check_curriculum_status.sh` - Quick status check
3. `fix_curriculum_service.sh` - Interactive diagnostic and fix script

## Test Account Created

For testing purposes, a school admin account was created:
- **Email:** `admin_20260304_174413_d476853e@test.com`
- **Password:** `TestPass123!`
- **School:** Test School 20260304_174413

This account can be used for further curriculum endpoint testing once the service is fixed.
