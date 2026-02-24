# Lessons (codebase-specific)

- **Never commit ECS/task definition files that contain hardcoded AWS resource identifiers** (account IDs, IAM role ARNs, Secrets Manager ARNs, internal ALB URLs). Either generate them dynamically in CI from a template + Terraform outputs or GitHub variables, or use placeholders and substitute at deploy time. Do not add environment-specific task definition files (e.g. staging) to version control with real credentials/ARNs.
