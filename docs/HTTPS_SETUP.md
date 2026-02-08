# Enabling HTTPS for the API

The ALB is reachable over HTTP by default. To get **HTTPS** (and remove the browser “Not secure” warning), you need a **custom domain** and to set one Terraform variable.

## Requirements

- A **domain you control** (e.g. `youspeak.com`).
- The domain’s **hosted zone in Route 53** in the same AWS account (so Terraform can create validation and alias records).

If the domain is registered elsewhere, create a **public hosted zone** in Route 53 for it and update your registrar’s nameservers to point to the Route 53 NS records.

## Steps

### 1. Create the Route 53 hosted zone (if needed)

In AWS Console: **Route 53** → **Hosted zones** → **Create hosted zone** → enter your domain (e.g. `youspeak.com`). Note the **Zone ID**. If the zone already exists, you can skip this.

### 2. Set the domain in Terraform

Pass the domain when applying (or add to `terraform.tfvars`):

```bash
cd terraform
terraform plan -var="domain_name=youspeak.com"
terraform apply -var="domain_name=youspeak.com"
```

Or create/update `terraform/terraform.tfvars` (do **not** commit if it contains other secrets):

```hcl
domain_name = "youspeak.com"
```

Then run:

```bash
terraform plan
terraform apply
```

### 3. What Terraform does

- Looks up the Route 53 zone for `domain_name`.
- Requests an **ACM certificate** for `api.<domain>` and `api-staging.<domain>`.
- Creates **DNS validation** records in the zone so ACM can issue the cert.
- Adds **HTTPS listeners (port 443)** on both ALBs and attaches the certificate.
- Changes **HTTP (80)** to **redirect** to HTTPS (301).
- Creates **A (alias) records**:
  - `api.<domain>` → production ALB  
  - `api-staging.<domain>` → staging ALB  

### 4. Use the secure URLs

After apply (and a few minutes for DNS/ACM):

- **Production:** `https://api.youspeak.com`
- **Staging:** `https://api-staging.youspeak.com`

HTTP requests to those hostnames (or the old ALB URLs) will redirect to HTTPS when `domain_name` is set.

## Disabling HTTPS

Leave `domain_name` unset (or remove it from tfvars). Terraform will keep only HTTP listeners and no certificate or Route 53 API/staging records.

## Security group

The ALB security group already allows inbound **443**; no extra change is needed for HTTPS.
