# Email Setup (Resend)

To send emails to any recipient (e.g. teacher invites, notifications), you must **verify a domain** in Resend. The default `onboarding@resend.dev` only allows sending to your Resend account's verified email.

## Quick Steps

### 1. Add domain in Resend

1. Go to [resend.com/domains](https://resend.com/domains)
2. Click **Add Domain**
3. Enter a domain you own (e.g. `mail.youspeak.com` or `youspeak.com`)
   - **Recommended:** Use a subdomain like `mail.youspeak.com` to isolate sending reputation

### 2. Add DNS records

Resend will show the exact records. Add these at your DNS provider (Cloudflare, Route53, etc.):

**DKIM** (TXT record):
```
Name: resend._domainkey (or similar per Resend)
Value: [provided by Resend]
```

**SPF** (TXT record on `send` subdomain):
```
Name: send.yourdomain.com
Value: v=spf1 include:amazonses.com ~all
```

**MX** (for bounces):
```
Name: send.yourdomain.com
Value: [provided by Resend]
```

### 3. Verify domain

In Resend dashboard, click **Verify**. DNS propagation can take up to 48 hours (often minutes).

### 4. Update `.env`

```env
EMAIL_FROM=YouSpeak <noreply@mail.youspeak.com>
RESEND_API_KEY=re_xxxxxxxxx
```

Use an address at your **verified** domain. You can use any address (e.g. `noreply@`, `onboarding@`) — no need to create it elsewhere.

### 5. Test

```bash
python scripts/send_test_email.py
```

Update `TO_EMAIL` in the script to your target address, or use the teacher import flow.

## Troubleshooting

- **"You can only send to your own email"** → Domain not verified. Complete steps 1–4.
- **"Domain not verified"** → Wait for DNS propagation; double-check record names/values.
- **DNS guides:** [Resend Knowledge Base](https://resend.com/docs/knowledge-base/dns-providers)
