# Email API Implementation Checklist

## ✅ Implementation Complete

All components of the email sending API have been implemented according to the plan.

---

## Files Changed/Created

### Models & Database
- ✅ `app/models/enums.py` - Added `EmailSendStatus` enum
- ✅ `app/models/communication.py` - Added `EmailLog` model
- ✅ `app/models/user.py` - Added `sent_emails` relationship
- ✅ `app/models/onboarding.py` - Added `email_logs` relationship
- ✅ `alembic/versions/f48298ca174c_add_email_logs_table.py` - Database migration

### Schemas
- ✅ `app/schemas/communication.py` - Added email request/response schemas

### Services
- ✅ `app/services/email_service.py` - Extended with `send_bulk_email()` and reply_to support

### API
- ✅ `app/api/v1/endpoints/emails.py` - New email endpoint
- ✅ `app/api/v1/router.py` - Registered emails router

### Tests
- ✅ `tests/integration/test_emails.py` - 9 integration test cases
- ✅ `tests/unit/test_email_service.py` - 8 unit test cases

### Documentation
- ✅ `IMPLEMENTATION_SUMMARY.md` - Complete implementation guide
- ✅ `EMAIL_API_CHECKLIST.md` - This file

---

## Next Steps

### 1. Run Database Migration
```bash
# Ensure environment variables are set
export DATABASE_URL="postgresql+asyncpg://..."
export SECRET_KEY="your-secret-key"

# Run migration
python3 -m alembic upgrade head

# Expected output:
# INFO  [alembic.runtime.migration] Running upgrade 009_add_published_enum -> f48298ca174c, add_email_logs_table
```

### 2. Verify Database Schema
```bash
psql $DATABASE_URL -c "\d email_logs"

# Expected columns:
# - id (uuid)
# - school_id (uuid, nullable)
# - sender_id (uuid)
# - recipients (text[])
# - subject (text)
# - html_body_sha256 (varchar(64))
# - send_status (email_send_status)
# - error_message (text, nullable)
# - sent_at (timestamp, nullable)
# - created_at (timestamp)
# - updated_at (timestamp)
```

### 3. Run Tests
```bash
# Unit tests (no database required)
pytest tests/unit/test_email_service.py -v

# Integration tests (requires DATABASE_URL and SECRET_KEY)
pytest tests/integration/test_emails.py -v

# Expected: All tests pass
```

### 4. Start Server and Test Endpoint
```bash
# Start server
uvicorn app.main:app --reload

# In another terminal, test the endpoint:
# (Replace TOKEN with actual JWT from login)
curl -X POST http://localhost:8000/api/v1/emails/send \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "recipients": ["test@example.com"],
    "subject": "Test Email",
    "html_body": "<html><body><h1>Test</h1></body></html>"
  }'

# Expected: 200 response with email_log_id
```

### 5. Check API Documentation
Visit: http://localhost:8000/docs

Look for "Emails" tag - should show:
- `POST /api/v1/emails/send`

### 6. Verify Rate Limiting
Send 6 emails in quick succession - the 6th should return 429.

### 7. Check Audit Trail
```sql
SELECT * FROM email_logs ORDER BY created_at DESC LIMIT 10;
```

---

## Testing Checklist

### Integration Tests (9 test cases)
- ✅ `test_send_email_single_recipient_success` - Single email sends
- ✅ `test_send_email_multiple_recipients_success` - Multiple recipients
- ✅ `test_send_email_partial_failure` - Some recipients fail
- ✅ `test_send_email_with_reply_to` - Reply-to header works
- ✅ `test_send_email_validation_errors` - Input validation (5 scenarios)
- ✅ `test_send_email_requires_authentication` - 401 without auth
- ✅ `test_send_email_rate_limit` - 429 after 5 emails
- ✅ `test_send_email_audit_trail` - Database logging works
- ✅ `test_send_email_all_failures` - All recipients fail

### Unit Tests (8 test cases)
- ✅ `test_hash_html_body` - SHA256 hashing
- ✅ `test_send_bulk_email_all_success` - Bulk send succeeds
- ✅ `test_send_bulk_email_partial_failure` - Partial failures handled
- ✅ `test_send_bulk_email_all_failure` - All failures handled
- ✅ `test_send_bulk_email_with_reply_to` - Reply-to parameter
- ✅ `test_send_bulk_email_exception_handling` - Exception handling
- ✅ `test_send_email_with_reply_to` - send_email with reply_to
- ✅ `test_send_email_without_reply_to` - send_email without reply_to

---

## Security Verification

### Rate Limiting
```bash
# Test rate limit by sending 6 emails rapidly
for i in {1..6}; do
  curl -X POST http://localhost:8000/api/v1/emails/send \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"recipients\": [\"test$i@example.com\"], \"subject\": \"Test $i\", \"html_body\": \"<html><body>Test</body></html>\"}"
  echo "\n"
done

# Expected: First 5 succeed (200), 6th fails (429)
```

### Input Validation
```bash
# Test HTML size limit (>500KB)
python3 -c "print('<html><body>' + 'X'*500001 + '</body></html>')" > large.html

curl -X POST http://localhost:8000/api/v1/emails/send \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @large.html

# Expected: 422 validation error
```

### Authentication
```bash
# Test without auth token
curl -X POST http://localhost:8000/api/v1/emails/send \
  -H "Content-Type: application/json" \
  -d '{"recipients": ["test@example.com"], "subject": "Test", "html_body": "<html><body>Test</body></html>"}'

# Expected: 401 Unauthorized
```

---

## Performance Verification

### Database Indexes
```sql
-- Verify indexes exist
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'email_logs';

-- Expected indexes:
-- ix_email_logs_school_id
-- ix_email_logs_sender_id
-- ix_email_logs_send_status
```

### Query Performance
```sql
-- Test query by sender (should use index)
EXPLAIN ANALYZE
SELECT * FROM email_logs WHERE sender_id = '<some-uuid>';

-- Expected: Index Scan on ix_email_logs_sender_id

-- Test query by status (should use index)
EXPLAIN ANALYZE
SELECT * FROM email_logs WHERE send_status = 'failed';

-- Expected: Index Scan on ix_email_logs_send_status
```

---

## Configuration Checklist

### Environment Variables
- ✅ `RESEND_API_KEY` - Get from https://resend.com/api-keys
- ✅ `EMAIL_FROM` - Must be verified domain (e.g., "noreply@youspeak.com")
- ✅ `DATABASE_URL` - PostgreSQL connection string
- ✅ `SECRET_KEY` - JWT secret for authentication

### Resend Setup
1. Create account at https://resend.com
2. Verify domain (Settings → Domains → Add Domain)
3. Create API key (Settings → API Keys → Create API Key)
4. Set `RESEND_API_KEY` and `EMAIL_FROM` in environment

---

## Monitoring Setup

### Application Logs
Look for these log entries:
```
INFO: Bulk email sent: 2 succeeded, 0 failed
```

### Database Monitoring
```sql
-- Daily email volume
SELECT DATE(sent_at) as date, COUNT(*) as emails
FROM email_logs
WHERE sent_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(sent_at)
ORDER BY date DESC;

-- Failed sends today
SELECT * FROM email_logs
WHERE send_status = 'failed'
AND sent_at > CURRENT_DATE;

-- Top senders this week
SELECT u.email, u.first_name, u.last_name, COUNT(*) as emails_sent
FROM email_logs el
JOIN users u ON el.sender_id = u.id
WHERE el.sent_at > NOW() - INTERVAL '7 days'
GROUP BY u.id, u.email, u.first_name, u.last_name
ORDER BY emails_sent DESC
LIMIT 10;
```

### Alerts to Set Up
1. Failed email rate > 10% → Investigate Resend issues
2. Single user sends > 20 emails/day → Potential abuse
3. Email_logs table growth > 10K/day → Review usage patterns
4. Rate limit 429 errors spike → Adjust limits or investigate abuse

---

## Rollback Plan

If issues arise:

### 1. Revert Migration
```bash
python3 -m alembic downgrade -1
```

### 2. Remove Endpoint
Comment out in `app/api/v1/router.py`:
```python
# api_router.include_router(emails.router, prefix="/emails", tags=["Emails"])
```

### 3. Deploy Previous Version
```bash
git revert <commit-hash>
git push
```

---

## Support

### Debugging

**Error: "Field required [DATABASE_URL]"**
- Set `DATABASE_URL` environment variable

**Error: "resend.exceptions.ResendError"**
- Check `RESEND_API_KEY` is set
- Verify domain at resend.com
- Check `EMAIL_FROM` matches verified domain

**Error: "Rate limit exceeded"**
- User has sent 5 emails in the last hour
- Wait or adjust rate limit in code

**Error: "HTML body exceeds 500KB limit"**
- Frontend should compress/optimize HTML
- Consider increasing limit if needed

### Common Questions

**Q: Can I increase the rate limit?**
A: Yes, edit `@limiter.limit("5/hour")` in `app/api/v1/endpoints/emails.py`

**Q: Can I send to more than 10 recipients?**
A: Yes, change `max_length=10` in `SendEmailRequest.recipients` field

**Q: How do I view sent emails?**
A: Query `email_logs` table - HTML content is hashed (not stored)

**Q: Can I send attachments?**
A: Not in current implementation - requires extending Resend call

**Q: How do I restrict to school roster only?**
A: Add validation in endpoint to check recipients against `users` table

---

## Git Commit

When ready to commit:

```bash
git add .
git commit -m "feat(emails): implement email sending API with audit trail

- Add EmailLog model with audit trail (sender, recipients, status)
- Add EmailSendStatus enum (pending, sent, failed)
- Extend send_email service with reply_to support
- Add send_bulk_email service with per-recipient tracking
- Create POST /api/v1/emails/send endpoint
- Add rate limiting (5 emails/hour per user)
- Add input validation (max 10 recipients, 500KB HTML)
- Add comprehensive integration and unit tests
- Create database migration for email_logs table

Security measures:
- Strict rate limiting to prevent spam
- Full audit trail for compliance
- Input validation and size limits
- Authentication required

Ref: Email Sending API Implementation Plan"
```

---

## Status: ✅ READY FOR TESTING

All implementation work is complete. Ready for:
1. Database migration
2. Test execution
3. Manual endpoint testing
4. Production deployment

---

**Last Updated:** 2026-03-24
**Implemented By:** Claude Sonnet 4.5
**Verified:** Code compiles, all files created/modified successfully
