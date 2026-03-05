# Curriculum Service Fix - Complete Report

**Date:** March 5, 2026
**Issue:** Staging curriculum endpoints returning 504 Gateway Timeout
**Status:** ✅ **RESOLVED**

---

## Executive Summary

Successfully diagnosed and fixed the staging curriculum service that was returning 504 Gateway Timeout errors. The root cause was a **missing security group rule** that prevented the load balancer from reaching the curriculum service container on port 8001.

**Result:** All curriculum endpoints are now working correctly on staging.

---

## Problem Statement

When testing the curriculum GET endpoint on staging (`https://api-staging.youspeakhq.com/api/v1/curriculums`), the API was returning:

```json
{
  "success": false,
  "error": {
    "code": "UPSTREAM_ERROR",
    "message": "504 Gateway Time-out"
  }
}
```

### Initial Investigation

- ✅ Main API service: Running and healthy
- ✅ Curriculum microservice: Running and healthy (1/1 tasks)
- ✅ Application logs: Service responding to localhost health checks
- ❌ Load balancer target health: **UNHEALTHY (Target.Timeout)**

---

## Root Cause Analysis

### Discovery Process

1. **ECS Service Check**
   - Service: `youspeak-curriculum-service-staging`
   - Cluster: `youspeak-cluster`
   - Status: ACTIVE with 1 running task
   - Container health: HEALTHY

2. **Load Balancer Target Health**
   ```json
   {
     "State": "unhealthy",
     "Reason": "Target.Timeout",
     "Description": "Request timed out"
   }
   ```

3. **Security Group Analysis**
   - Task security group: `sg-0a564644a7af96dc0`
   - Load balancer security group: `sg-0df6225d7b57f86c2`
   - **Issue:** No inbound rule allowing port 8001 from LB security group

4. **Service Configuration**
   - Application listening on: `http://0.0.0.0:8001`
   - Health check endpoint: `/health`
   - Port mapping: Container port 8001 → Host port 8001

### Root Cause

**Missing security group rule:** The curriculum service security group did not allow inbound TCP traffic on port 8001 from the curriculum load balancer security group (`sg-0df6225d7b57f86c2`).

This prevented the load balancer from reaching the service for health checks and request forwarding, resulting in:
- Unhealthy targets
- 504 Gateway Timeout errors from the main API

---

## Solution Implemented

### Step 1: Add Security Group Rule

Added inbound rule to curriculum service security group:

```bash
aws ec2 authorize-security-group-ingress \
    --group-id sg-0a564644a7af96dc0 \
    --protocol tcp \
    --port 8001 \
    --source-group sg-0df6225d7b57f86c2 \
    --region us-east-1
```

**Result:**
```json
{
  "SecurityGroupRuleId": "sgr-05b422c98c4d9c80f",
  "GroupId": "sg-0a564644a7af96dc0",
  "FromPort": 8001,
  "ToPort": 8001,
  "ReferencedGroupInfo": {
    "GroupId": "sg-0df6225d7b57f86c2"
  }
}
```

### Step 2: Monitor Health Recovery

Monitored target health for 2 minutes:

1. Old task drained and deregistered
2. New task registered with updated security group
3. Health checks started passing
4. Target became healthy

**Final Status:**
```json
{
  "Target": {
    "Id": "10.0.10.190",
    "Port": 8001
  },
  "TargetHealth": {
    "State": "healthy"
  }
}
```

### Step 3: End-to-End Testing

Ran comprehensive test suite:

```bash
./test_staging_full_flow.sh
```

**Test Results:**
- ✅ School admin registration
- ✅ Authentication (login)
- ✅ List curriculums (empty for new school)
- ✅ GET curriculum by ID (404 for non-existent, as expected)
- ✅ Generate curriculum (AI service working)

---

## Verification

### Load Balancer Target Health
```
State: healthy
Health Check Port: 8001
Health Check Path: /health
```

### Application Logs
```
INFO:     Uvicorn running on http://0.0.0.0:8001
INFO:     127.0.0.1:47870 - "GET /health HTTP/1.1" 200 OK
```

### Security Group Configuration
```json
{
  "FromPort": 8001,
  "ToPort": 8001,
  "SourceSGs": [
    "sg-02e677288b2457262",  // Other service (not used)
    "sg-0df6225d7b57f86c2"   // Curriculum LB (correct)
  ]
}
```

---

## Test Account Created

For ongoing testing and verification:

- **Email:** `admin_20260305_101054_720d321d@test.com`
- **Password:** `TestPass123!`
- **School:** Test School 20260305_101054
- **Environment:** Staging

---

## Files Created During Investigation

1. **`test_staging_full_flow.sh`** - End-to-end test (registration → curriculum test)
2. **`test_staging_curriculum.sh`** - Curriculum endpoint test with existing account
3. **`check_curriculum_status.sh`** - Quick ECS service status check
4. **`fix_curriculum_service.sh`** - Interactive diagnostic and fix tool
5. **`check_sg_config.sh`** - Security group analysis tool
6. **`STAGING_CURRICULUM_DIAGNOSIS.md`** - Initial diagnostic report
7. **`SOLUTION.md`** - Root cause and solution documentation

---

## Lessons Learned

### What Went Wrong

1. **Security Group Misconfiguration**
   - Likely caused by manual changes or incomplete Terraform state
   - Load balancer SG was not authorized for port 8001 access

2. **Terraform State Issues**
   - Staging workspace had stale state with wrong region ARNs
   - Made Terraform-based fix impractical for immediate resolution

### Prevention Strategies

1. **Infrastructure as Code**
   - Ensure all security group rules are managed through Terraform
   - Regular state validation and cleanup

2. **Monitoring**
   - Set up CloudWatch alarms for unhealthy targets
   - Alert on 504 errors from main API to curriculum service

3. **Documentation**
   - Document security group relationships
   - Maintain network diagrams for service-to-service communication

4. **Testing**
   - Include health check tests in CI/CD pipeline
   - Verify service connectivity after deployments

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Internet Gateway                          │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
                   ┌──────────────────┐
                   │   Public ALB     │  (Main API)
                   │  api-staging     │
                   └────────┬─────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │  Main API Tasks  │  Port 8000
                   │  (ECS Fargate)   │  sg-xxx
                   └────────┬─────────┘
                            │
                  HTTP Proxy│ (Curriculum requests)
                            │
                            ▼
             ┌──────────────────────────────┐
             │ Internal ALB (Curriculum)    │
             │ youspeak-curric-int-stg      │
             │ sg-0df6225d7b57f86c2         │
             └──────────────┬───────────────┘
                            │
                   TCP:8001 │ ✅ FIXED
                            │
                            ▼
             ┌──────────────────────────────┐
             │  Curriculum Service Tasks    │
             │  (ECS Fargate)               │
             │  sg-0a564644a7af96dc0        │
             │  Port 8001                   │
             └──────────────────────────────┘
```

---

## Commands Reference

### Check Service Status
```bash
./check_curriculum_status.sh
```

### Run Full Test Suite
```bash
./test_staging_full_flow.sh
```

### Check Target Health
```bash
aws elbv2 describe-target-health \
  --target-group-arn arn:aws:elasticloadbalancing:us-east-1:497068062563:targetgroup/youspeak-curric-tg-stg/fb119ff5cf07df94 \
  --region us-east-1
```

### View Application Logs
```bash
aws logs tail /ecs/youspeak-curriculum-api --follow --region us-east-1
```

---

## Conclusion

The curriculum service on staging is now **fully operational**. The issue was successfully resolved by adding the correct security group rule to allow load balancer traffic on port 8001.

**Status:** ✅ **RESOLVED AND VERIFIED**

All endpoints tested and working:
- ✅ `GET /api/v1/curriculums` (list)
- ✅ `GET /api/v1/curriculums/{id}` (get by ID)
- ✅ `POST /api/v1/curriculums/generate` (AI generation)

The service is ready for use and further testing.

---

**Report Generated:** March 5, 2026, 10:12 AM
**Engineer:** Claude (Complex Problem-Solving Agent)
**Verification:** End-to-end tests passed ✅
