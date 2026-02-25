# Settings Screen API Endpoints

All paths are relative to **`/api/v1`**. Use **Bearer token** (admin or current user) where noted.

---

## 1. School Information tab

| Action | Method | Path | Auth | Request | Response |
|--------|--------|------|------|---------|----------|
| Load school profile (bio data, location, logo, languages) | `GET` | `/schools/profile` | Admin | — | `{ "data": SchoolResponse, "message": "..." }` |
| Save bio data & location | `PUT` | `/schools/profile` | Admin | `SchoolUpdate` (JSON) | `{ "data": SchoolResponse, "message": "Profile updated successfully" }` |
| Change logo | `POST` | `/schools/logo` | Admin | `multipart/form-data`: `file` (image/jpeg or image/png) | `{ "data": SchoolResponse, "message": "Logo uploaded successfully" }` |

**SchoolUpdate** (all optional):  
`name`, `address_country`, `address_state`, `address_city`, `address_zip`, `phone`, `email`, `logo_url`

**SchoolResponse** (in `data`):  
`id`, `name`, `school_type`, `program_type`, `email`, `phone`, `address_country`, `address_state`, `address_city`, `address_zip`, `logo_url`, `languages` (list of language codes), `is_active`, `created_at`

---

## 2. Language Offered tab

| Action | Method | Path | Auth | Request | Response |
|--------|--------|------|------|---------|----------|
| Get available languages (for "Add Language" dropdown) | `GET` | `/references/languages` | Any (optional) | — | `{ "data": [ { "id", "name", "code" }, ... ] }` |
| Load current school languages | — | Use `GET /schools/profile` | Admin | — | `data.languages` is the list of codes |
| Save languages offered | `PUT` | `/schools/program` | Admin | `{ "languages": ["en", "es", "fr"] }` | `{ "data": { "languages": ["en", "es", "fr"] }, "message": "..." }` |
| Remove a language | `DELETE` | `/schools/program/{language_code}` | Admin | — (code in path, e.g. `fr`) | `{ "data": { "languages": [...] }, "message": "Language removed successfully" }` |

---

## 3. Account tab

| Action | Method | Path | Auth | Request | Response |
|--------|--------|------|------|---------|----------|
| Change password | `POST` | `/users/change-password` | Current user | `{ "current_password": "...", "new_password": "..." }` | User object (or 400 if current password wrong) |
| Delete my account | `DELETE` | `/users/me` | Current user | `{ "password": "current_password" }` | `{ "data": null, "message": "Account deleted successfully" }` |

**Change password**: `new_password` min 8 chars. Returns 400 with `"Incorrect current password"` if wrong.

**Delete account**: Returns 400 with `"Incorrect password"` if wrong. After success, token is invalid.

---

## 4. Billing tab (school management)

| Action | Method | Path | Auth | Request | Response |
|--------|--------|------|------|---------|----------|
| List billing history | `GET` | `/schools/bills` | Admin | Query: `page`, `page_size` (optional) | Paginated list of bills (Date, Amount, Status; frontend can add View Receipt when receipt URL is available) |

**Query:** `page` (default 1), `page_size` (default 20, max 100).

**Bill item (in `data`):** `id`, `amount`, `status` (`pending` \| `paid` \| `failed`), `due_date`, `created_at`.

---

## 5. Auth (for "Log out" and general access)

| Action | Method | Path | Auth | Request | Response |
|--------|--------|------|------|---------|----------|
| Login (get token) | `POST` | `/auth/login` | — | `{ "email", "password" }` | `{ "data": { "access_token", "refresh_token", "role", "user_id", "school_id" }, ... }` |
| Log out | Client-only | — | — | Discard token / clear storage | — |

Log out is handled on the client (clear token and redirect); no backend endpoint required.

---

## Quick reference: full URLs (base `/api/v1`)

```
GET    /schools/profile           → load settings (School Information + languages)
PUT    /schools/profile           → save bio data & location
POST   /schools/logo              → upload logo (multipart)
GET    /references/languages      → list all languages (for dropdown)
PUT    /schools/program           → save languages offered
DELETE /schools/program/{code}    → remove one language (e.g. /schools/program/fr)
GET    /schools/bills             → list billing history (paginated; admin only)
POST   /users/change-password     → change password
DELETE /users/me                  → delete account (body: { "password": "..." })
POST   /auth/login                → login (for token)
```

All school and user endpoints above require `Authorization: Bearer <access_token>`.
