# Secrets Management Guide

**Date:** 2026-03-16
**Purpose:** Prevent credential leaks and follow security best practices

---

## Core Principle: Never Commit Secrets

**NEVER** commit the following to git:
- API keys (AWS, Resend, Cloudflare R2, etc.)
- Database passwords
- JWT secret keys
- OAuth client secrets
- Internal service secrets
- Any credentials, tokens, or sensitive data

---

## Proper Secrets Handling

### 1. Environment Variables (Recommended)

All secrets should be loaded from environment variables using `pydantic-settings`:

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str = ""
    DATABASE_URL: str = ""
    RESEND_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )
```

### 2. AWS Credentials (Boto3 Pattern)

For AWS services (Bedrock, S3, etc.), use boto3's automatic credential discovery:

**Do NOT do this:**
```python
# ❌ BAD: Hardcoded credentials
boto3.client('bedrock-runtime',
    aws_access_key_id='AKIAIOSFODNN7EXAMPLE',  # NEVER DO THIS!
    aws_secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'  # NEVER DO THIS!
)
```

**Do this instead:**
```python
# ✅ GOOD: Boto3 auto-discovers credentials
import boto3
boto3.client('bedrock-runtime')  # Uses environment or ~/.aws/credentials
```

Boto3 automatically looks for credentials in this order:
1. Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
2. AWS credentials file: `~/.aws/credentials`
3. IAM role (when running on AWS infrastructure)

### 3. Local Development

Create a `.env` file (never commit this!):

```bash
# .env (NEVER COMMIT THIS FILE)
SECRET_KEY=your-secret-key-min-32-chars
DATABASE_URL=postgresql://user:password@localhost:5432/db
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-access-key
RESEND_API_KEY=re_123456789
```

The `.gitignore` file already excludes `.env` files.

### 4. Production Deployment

**AWS ECS:**
- Use AWS Systems Manager Parameter Store or Secrets Manager
- Define secrets in task definition
- Use IAM roles for Bedrock access (no keys needed)

**Environment Variables:**
```json
{
  "containerDefinitions": [{
    "secrets": [
      {"name": "SECRET_KEY", "valueFrom": "arn:aws:ssm:region:account:parameter/youspeak/SECRET_KEY"},
      {"name": "DATABASE_URL", "valueFrom": "arn:aws:ssm:region:account:parameter/youspeak/DATABASE_URL"}
    ],
    "environment": [
      {"name": "AWS_REGION", "value": "us-east-1"}
    ]
  }]
}
```

---

## Testing with Credentials

### ❌ WRONG: Hardcode credentials in test files

```python
# test_bedrock_bearer.py - NEVER DO THIS
import boto3

def test_bedrock():
    client = boto3.client(
        'bedrock-runtime',
        aws_access_key_id='AKIAIOSFODNN7EXAMPLE',  # GitHub will block this!
        aws_secret_access_key='wJalrXUtnFEMI/K7MDENG/...'  # Security risk!
    )
```

### ✅ CORRECT: Use environment variables or AWS profiles

```python
# tests/integration/test_bedrock.py - DO THIS
import boto3
import pytest

@pytest.mark.requires_aws
def test_bedrock():
    # Boto3 auto-discovers credentials from:
    # 1. Environment: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
    # 2. ~/.aws/credentials
    # 3. IAM role (in CI/CD)
    client = boto3.client('bedrock-runtime')

    # Test code here...
```

Set credentials in shell before running tests:
```bash
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
pytest tests/integration/test_bedrock.py
```

Or use AWS profiles:
```bash
aws configure --profile youspeak
# Enter access key, secret key, region

AWS_PROFILE=youspeak pytest tests/integration/test_bedrock.py
```

---

## Security Checks

### GitHub Push Protection

GitHub will block pushes containing:
- AWS access keys
- Private keys
- OAuth tokens
- Database connection strings with passwords

If blocked:
1. Remove the secret from all commits (use `git filter-repo` or rewrite history)
2. **Immediately rotate the exposed credential** (assume it's compromised)
3. Update `.gitignore` to prevent future leaks

### Pre-commit Checks

Consider using [detect-secrets](https://github.com/Yelp/detect-secrets) or [gitleaks](https://github.com/gitleaks/gitleaks):

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Scan for secrets
pip install detect-secrets
detect-secrets scan
```

---

## Checklist for Developers

Before committing:
- [ ] No API keys, passwords, or tokens in code
- [ ] All secrets loaded from environment variables
- [ ] Test files use env vars, not hardcoded credentials
- [ ] `.env` file is in `.gitignore`
- [ ] `.env.example` has placeholder values, not real secrets
- [ ] AWS credentials use boto3 auto-discovery

Before deploying:
- [ ] Production secrets stored in AWS Secrets Manager or Parameter Store
- [ ] IAM roles configured for AWS service access
- [ ] Connection strings use least-privilege credentials
- [ ] Secrets rotated regularly (every 90 days)

---

## How Curriculum Service Does It

The curriculum service correctly handles Bedrock credentials:

```python
# services/curriculum/utils/ai.py
def _get_bedrock():
    import boto3
    from botocore.config import Config

    config = Config(
        region_name=settings.AWS_REGION,  # From environment
        max_pool_connections=100,
        # No explicit credentials - boto3 finds them automatically
    )
    _bedrock = boto3.client("bedrock-runtime", config=config)
    return _bedrock
```

```python
# services/curriculum/config.py
class Settings(BaseSettings):
    AWS_REGION: str = "us-east-1"  # From AWS_REGION env var
    BEDROCK_MODEL_ID: str = "amazon.nova-lite-v1:0"
    # AWS credentials auto-discovered by boto3
```

**This is the pattern to follow for all AWS services.**

---

## Resources

- [AWS Boto3 Credentials](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

---

**Updated:** 2026-03-16
**Reviewed:** Security Team
