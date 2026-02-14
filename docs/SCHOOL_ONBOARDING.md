# School Onboarding API

This document maps the frontend onboarding screens to backend endpoints.

## Flow Overview

| Screen | Endpoint | Purpose |
|--------|----------|---------|
| Tell us about your school | `POST /api/v1/auth/contact-inquiry` | Optional pre-onboarding inquiry (can Skip) |
| Set Up Your Login Details | — | Collects data for register (see below) |
| Set up your school profile | — | Collects data for register |
| Enrollment Program Setup | — | Collects data for register |
| **Final submit** | `POST /api/v1/auth/register/school` | Creates school + admin in one request |

The frontend collects data across steps 2–4 and sends a single `POST /api/v1/auth/register/school` with all fields.

---

## 1. Contact Inquiry (Optional)

**Endpoint:** `POST /api/v1/auth/contact-inquiry`

For the "Tell us about your school" screen when the user does **not** skip.

**Request body:**
```json
{
  "school_name": "Hill High Int",
  "email": "school@example.com",
  "inquiry_type": "program_selection_guidance" | "billing" | "demo_request" | "new_onboarding",
  "message": "Optional message text"
}
```

**Inquiry types** (match frontend dropdown):
- `program_selection_guidance` — Program selection guidance
- `billing` — Billing/pricing inquiry
- `demo_request` — Demo request
- `new_onboarding` — New School Onboarding

---

## 2. School Registration

**Endpoint:** `POST /api/v1/auth/register/school`

**Required:**
- `email` — School admin email (used for login)
- `password` — Admin password
- `school_name` — School name

**Optional (defaults applied if omitted):**
- `school_type` — `"primary"` | `"secondary"` | `"tertiary"` (default: `"secondary"`)
- `program_type` — `"pioneer"` | `"partnership"` (default: `"partnership"`)
- `address_country`, `address_state`, `address_city`, `address_zip`
- `languages` — Array of language codes, e.g. `["es", "fr"]`

**Example (minimal):**
```json
{
  "email": "admin@hillschool.edu",
  "password": "SecurePass123!",
  "school_name": "Hill High Int"
}
```

**Example (full onboarding):**
```json
{
  "email": "admin@hillschool.edu",
  "password": "SecurePass123!",
  "school_name": "Hill High Int",
  "school_type": "secondary",
  "program_type": "pioneer",
  "address_country": "United States",
  "address_state": "California",
  "address_city": "Los Angeles",
  "address_zip": "90001",
  "languages": ["es", "fr"]
}
```

**Response:** `{ "data": { "school_id": "uuid" }, "message": "School registered successfully" }`

---

## Frontend Recommendations

1. **Single submit:** Accumulate data from steps 2–4 and send one `register/school` request at the end.
2. **Language codes:** Use lowercase codes (e.g. `es`, `fr`) matching the `languages` table.
