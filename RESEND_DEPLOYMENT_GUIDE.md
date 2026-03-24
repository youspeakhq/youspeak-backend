# Resend API Key Configuration & Email API Deployment Guide

## Overview

This guide walks you through configuring the Resend API key via Terraform and deploying the new email sending API to AWS.

---

## Step 1: Verify Domain on Resend (IMPORTANT)

Before deploying, you **MUST** verify your domain on Resend:

### 1.1 Log into Resend Dashboard
Visit: https://resend.com/domains

### 1.2 Add Your Domain
1. Click "Add Domain"
2. Enter: `youspeakhq.com`
3. Follow instructions to add DNS records:
   - **SPF Record** (TXT): `v=spf1 include:_spf.resend.com ~all`
   - **DKIM Record** (TXT): Provided by Resend
   - **DMARC Record** (TXT): `v=DMARC1; p=none`

### 1.3 Wait for Verification
- DNS propagation can take up to 24 hours
- Check status at https://resend.com/domains
- Status must be "Verified" before sending emails

### 1.4 Update EMAIL_FROM
Once verified, emails can be sent from:
- `noreply@youspeakhq.com` ✅ (already configured)
- `onboarding@youspeakhq.com` ✅
- `no-reply@youspeakhq.com` ✅
- Any address `@youspeakhq.com` ✅

**Note:** The task definition already uses `noreply@youspeakhq.com` which will work once the domain is verified.

---

## Step 2: Apply Terraform Configuration

The Resend API key has already been updated in `terraform/terraform.tfvars`.

### 2.1 Navigate to Terraform Directory
```bash
cd terraform
```

### 2.2 Initialize Terraform (if not already done)
```bash
terraform init
```

### 2.3 Review Changes
```bash
terraform plan
```

**Expected Output:**
```
~ aws_secretsmanager_secret_version.resend_api_key[0] will be updated in-place
  ~ secret_string = (sensitive value)
```

### 2.4 Apply Changes
```bash
terraform apply
```

When prompted, type `yes` to confirm.

**What This Does:**
- Updates the `youspeak/resend-api-key-staging` secret in AWS Secrets Manager
- ECS tasks will automatically use the new key on next deployment

---

## Step 3: Run Database Migration

The email API requires the new `email_logs` table.

### 3.1 Run Migration Locally (Optional - for testing)
```bash
# Set environment variables
export DATABASE_URL="your-database-url"
export SECRET_KEY="your-secret-key"

# Run migration
python3 -m alembic upgrade head
```

### 3.2 Migration Will Run Automatically in CI/CD
When you push to `main` or `live` branch:
- GitHub Actions runs migrations before deploying
- Migration task: `youspeak-migration`
- Check logs: `aws ecs describe-tasks` if needed

---

## Step 4: Deploy to AWS

### Option A: Deploy via Git (Recommended)

#### For Staging (main branch):
```bash
git add .
git commit -m "feat(emails): configure Resend API key and EMAIL_FROM

- Update Resend API key in terraform.tfvars
- Add EMAIL_FROM environment variable to task definition
- Ready for email sending API deployment"

git push origin main
```

GitHub Actions will:
1. Run tests
2. Build Docker image
3. Run database migrations (adds `email_logs` table)
4. Deploy to staging ECS service
5. URL: https://api-staging.youspeakhq.com

#### For Production (live branch):
```bash
git checkout live
git merge main
git push origin live
```

GitHub Actions will deploy to production:
- URL: https://api.youspeakhq.com

### Option B: Manual Deploy (Advanced)

If you need to deploy without pushing to Git:

```bash
# 1. Build and push Docker image
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 497068062563.dkr.ecr.us-east-1.amazonaws.com

docker build -t youspeak-backend .
docker tag youspeak-backend:latest 497068062563.dkr.ecr.us-east-1.amazonaws.com/youspeak-backend:latest
docker push 497068062563.dkr.ecr.us-east-1.amazonaws.com/youspeak-backend:latest

# 2. Update ECS service (staging)
aws ecs update-service \
  --cluster youspeak-cluster \
  --service youspeak-api-service-staging \
  --force-new-deployment

# 3. Update ECS service (production)
aws ecs update-service \
  --cluster youspeak-cluster \
  --service youspeak-api-service-production \
  --force-new-deployment
```

---

## Step 5: Verify Deployment

### 5.1 Check ECS Service Status
```bash
# Staging
aws ecs describe-services \
  --cluster youspeak-cluster \
  --services youspeak-api-service-staging \
  --query 'services[0].deployments' \
  --output table

# Production
aws ecs describe-services \
  --cluster youspeak-cluster \
  --services youspeak-api-service-production \
  --query 'services[0].deployments' \
  --output table
```

### 5.2 Check Application Logs
```bash
# Staging logs
aws logs tail /ecs/youspeak-api \
  --follow \
  --filter-pattern "Email" \
  --region us-east-1

# Production logs
aws logs tail /ecs/youspeak-api \
  --follow \
  --filter-pattern "Email" \
  --region us-east-1
```

### 5.3 Test Email Endpoint (Staging)

Get JWT token from frontend, then:

```bash
TOKEN="your-jwt-token"

curl -X POST https://api-staging.youspeakhq.com/api/v1/emails/send \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "recipients": ["your-email@example.com"],
    "subject": "Test Email from YouSpeak Staging",
    "html_body": "<html><body><h1>Test Email</h1><p>This email was sent from the YouSpeak staging API.</p></body></html>"
  }'
```

**Expected Response (200):**
```json
{
  "success": true,
  "data": {
    "total_recipients": 1,
    "successful_sends": 1,
    "failed_sends": 0,
    "results": [
      {
        "recipient": "your-email@example.com",
        "status": "sent",
        "error": null
      }
    ],
    "email_log_id": "uuid-here"
  },
  "message": "Email sent to 1/1 recipients"
}
```

### 5.4 Verify Database Migration
```bash
# Connect to database
psql $DATABASE_URL

# Check email_logs table exists
\d email_logs

# Check for email logs
SELECT id, sender_id, recipients, subject, send_status, sent_at
FROM email_logs
ORDER BY created_at DESC
LIMIT 10;
```

### 5.5 Check API Documentation
Visit: https://api-staging.youspeakhq.com/docs

Look for "Emails" section - should show:
- `POST /api/v1/emails/send`

---

## Step 6: Monitor Email Sending

### 6.1 Application Logs
```bash
# Filter for email-related logs
aws logs filter-log-events \
  --log-group-name /ecs/youspeak-api \
  --filter-pattern "Bulk email sent" \
  --start-time $(date -u -d '1 hour ago' +%s)000 \
  --region us-east-1
```

### 6.2 Database Queries

**Daily email volume:**
```sql
SELECT DATE(sent_at) as date, COUNT(*) as emails_sent
FROM email_logs
WHERE sent_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(sent_at)
ORDER BY date DESC;
```

**Failed sends:**
```sql
SELECT * FROM email_logs
WHERE send_status = 'failed'
AND sent_at > NOW() - INTERVAL '1 day'
ORDER BY sent_at DESC;
```

**Top senders:**
```sql
SELECT u.email, u.first_name, u.last_name, COUNT(*) as emails_sent
FROM email_logs el
JOIN users u ON el.sender_id = u.id
WHERE el.sent_at > NOW() - INTERVAL '7 days'
GROUP BY u.id, u.email, u.first_name, u.last_name
ORDER BY emails_sent DESC
LIMIT 10;
```

### 6.3 Resend Dashboard
Monitor sends at: https://resend.com/emails

---

## Troubleshooting

### Issue: "Email service returned false"

**Cause:** Resend API key is invalid or domain not verified

**Solution:**
1. Check domain verification status at https://resend.com/domains
2. Verify API key is correct in Secrets Manager:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id youspeak/resend-api-key-staging \
     --query SecretString \
     --output text
   ```
3. If key is wrong, update terraform.tfvars and run `terraform apply` again

### Issue: "Rate limit exceeded"

**Cause:** User has reached their role-based rate limit

**Current Limits:**
- Students: 3 emails per hour
- Teachers: 10 emails per hour
- Admins: 50 emails per hour

**Solution:**
- This is expected behavior (role-based rate limiting)
- Wait for rate limit window to reset (1 hour)
- Or adjust rate limits in `app/api/v1/endpoints/emails.py` (get_email_rate_limit function)
- Check user role in JWT token to verify correct limit is applied

### Issue: "HTML body exceeds 500KB limit"

**Cause:** Email HTML is too large

**Solution:**
- Optimize HTML (remove inline images, compress CSS)
- Or increase limit in `app/schemas/communication.py` (line 554)

### Issue: "Domain not verified" error from Resend

**Cause:** Domain verification not complete

**Solution:**
1. Check DNS records are correct at https://resend.com/domains
2. Wait for DNS propagation (can take 24 hours)
3. Use `dig` to verify DNS records:
   ```bash
   dig TXT _resend._domainkey.youspeakhq.com
   dig TXT youspeakhq.com
   ```

### Issue: Migration fails in CI/CD

**Cause:** Migration task cannot reach RDS

**Solution:**
1. Check GitHub Secrets are set:
   - `PRIVATE_SUBNET_IDS`
   - `ECS_SECURITY_GROUP`
2. Get values from Terraform:
   ```bash
   cd terraform
   terraform output private_subnet_ids
   terraform output ecs_security_group_id
   ```
3. Set in GitHub: Settings → Secrets → Actions → New repository secret

### Issue: ECS tasks not picking up new secret

**Cause:** Tasks use old secret version

**Solution:**
1. Force new deployment to pick up new secrets:
   ```bash
   aws ecs update-service \
     --cluster youspeak-cluster \
     --service youspeak-api-service-staging \
     --force-new-deployment
   ```
2. Wait for tasks to restart (2-3 minutes)

---

## Configuration Summary

**Updated Files:**
- ✅ `terraform/terraform.tfvars` - New Resend API key
- ✅ `.aws/task-definition.json` - Added EMAIL_FROM environment variable

**Infrastructure:**
- ✅ Secrets Manager: `youspeak/resend-api-key-staging`
- ✅ ECS Task Definition: References Resend secret
- ✅ IAM Role: Has permission to read Resend secret

**Database:**
- ✅ Migration: `f48298ca174c_add_email_logs_table.py`
- ✅ Table: `email_logs` with audit trail
- ✅ Indexes: On sender_id, school_id, send_status

**API Endpoint:**
- ✅ Route: `POST /api/v1/emails/send`
- ✅ Rate Limits (role-based per hour):
  - Students: 3 emails
  - Teachers: 10 emails
  - Admins: 50 emails
- ✅ Max Recipients: 10 per request
- ✅ Max HTML Size: 500KB

---

## Next Steps

1. **Verify domain on Resend** (MUST DO FIRST)
2. **Apply Terraform** to update secret: `cd terraform && terraform apply`
3. **Push to main branch** to deploy to staging
4. **Test the endpoint** with curl (see Step 5.3)
5. **Monitor logs** for any issues
6. **Merge to live branch** to deploy to production

---

## Support

- **Resend Docs:** https://resend.com/docs
- **API Documentation:** https://api-staging.youspeakhq.com/docs
- **Implementation Guide:** See `IMPLEMENTATION_SUMMARY.md`
- **Checklist:** See `EMAIL_API_CHECKLIST.md`

---

**Last Updated:** 2026-03-24
**Status:** ✅ Ready for deployment (pending domain verification)
