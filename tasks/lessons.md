# Lessons Learned - YouSpeak Backend

## Git Commits
- ❌ Never include `Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>` in commit messages
- ✅ Keep commit messages clean and professional

## Infrastructure & Secrets
- Always verify secrets have AWSCURRENT version after restoration
- IAM policies need wildcard matching for secret suffixes (e.g., `secret-name-*`)
- Both execution role AND task role need proper permissions

## Deployment
- Force new ECS deployment after fixing secrets (they cache metadata)
- Check both staging AND production when deploying infrastructure changes

