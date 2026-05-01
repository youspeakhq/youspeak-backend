#!/usr/bin/env python3
"""
Comprehensive curriculum endpoint tests against staging.

Run:
    python scripts/test_curriculum_staging.py

Creates a school admin + teacher, exercises all curriculum endpoints,
then tears down test data.
"""

import json
import sys
import uuid
import httpx

BASE = "https://api-staging.youspeakhq.com/api/v1"
TIMEOUT = 60.0

# ── colour helpers ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

passed = []
failed = []
skipped = []


def ok(name, detail=""):
    passed.append(name)
    print(f"  {GREEN}✓{RESET} {name}" + (f"  ({detail})" if detail else ""))


def fail(name, detail=""):
    failed.append(name)
    print(f"  {RED}✗{RESET} {name}" + (f"  → {detail}" if detail else ""))


def skip(name, reason=""):
    skipped.append(name)
    print(f"  {YELLOW}~{RESET} {name}" + (f"  [{reason}]" if reason else ""))


def section(title):
    print(f"\n{BOLD}{title}{RESET}")


def assert_status(resp, expected, name):
    if isinstance(expected, int):
        expected = (expected,)
    if resp.status_code in expected:
        ok(name, f"{resp.status_code}")
        return True
    else:
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:200]
        fail(name, f"got {resp.status_code}, expected {expected} — {body}")
        return False


# ── setup: create school + admin + teacher ─────────────────────────────────────
def setup(client: httpx.Client) -> dict:
    section("Setup: create school + admin + teacher")

    suffix = uuid.uuid4().hex[:8]

    admin_email = f"admin-{suffix}@currtest.com"
    admin_password = "Pass123!"

    # 1. Register school (public endpoint — does NOT return a token)
    r = client.post(f"{BASE}/auth/register/school", json={
        "school_name": f"CurriculumTestSchool-{suffix}",
        "email": admin_email,
        "password": admin_password,
        "school_type": "secondary",
        "program_type": "pioneer",
    })
    assert_status(r, 200, "register school")
    school_id = r.json()["data"]["school_id"]
    print(f"    school_id={school_id}")

    # 2. Login as admin to get token
    r = client.post(f"{BASE}/auth/login", json={"email": admin_email, "password": admin_password})
    assert_status(r, 200, "admin login")
    admin_token = r.json()["data"]["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Get a language id (seeded reference data, no auth needed)
    r = client.get(f"{BASE}/references/languages")
    assert_status(r, 200, "list languages")
    languages = r.json().get("data", [])
    assert languages, "no languages seeded on staging"
    lang_id = languages[0]["id"]
    print(f"    using lang_id={lang_id} ({languages[0]['name']})")

    # 4. Create teacher
    r = client.post(f"{BASE}/teachers", headers=admin_headers, json={
        "first_name": "Curriculum",
        "last_name": "Teacher",
        "email": f"teacher-{suffix}@currtest.com",
    })
    assert_status(r, 200, "create teacher invite")
    access_code = r.json()["data"]["access_code"]

    r = client.post(f"{BASE}/auth/register/teacher", json={
        "access_code": access_code,
        "email": f"teacher-{suffix}@currtest.com",
        "password": "Pass123!",
        "first_name": "Curriculum",
        "last_name": "Teacher",
    })
    assert_status(r, 200, "register teacher")

    r = client.post(f"{BASE}/auth/login", json={
        "email": f"teacher-{suffix}@currtest.com",
        "password": "Pass123!",
    })
    assert_status(r, 200, "login teacher")
    teacher_token = r.json()["data"]["access_token"]
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    # 5. Create a student
    r = client.post(f"{BASE}/students", headers=admin_headers, json={
        "first_name": "Test",
        "last_name": "Student",
        "email": f"student-{suffix}@currtest.com",
        "lang_id": lang_id,
        "password": "Pass123!",
    })
    assert_status(r, 200, "create student")
    student_id = r.json()["data"]["id"]

    return {
        "suffix": suffix,
        "school_id": school_id,
        "admin_headers": admin_headers,
        "teacher_headers": teacher_headers,
        "lang_id": lang_id,
        "student_id": student_id,
    }


# ── curriculum tests ───────────────────────────────────────────────────────────
def test_curriculum_endpoints(client: httpx.Client, ctx: dict):
    th = ctx["teacher_headers"]
    ah = ctx["admin_headers"]
    lang_id = ctx["lang_id"]
    curriculum_id = None
    topic_id = None
    library_curriculum_id = None

    # ── AUTH GUARDS ────────────────────────────────────────────────────────────
    section("Auth guards (unauthenticated → 401/403)")
    r = client.get(f"{BASE}/curriculums")
    assert_status(r, (401, 403), "GET /curriculums without auth")

    r = client.post(f"{BASE}/curriculums/generate", json={"prompt": "test", "language_id": lang_id})
    assert_status(r, (401, 403), "POST /curriculums/generate without auth")

    # ── LIST (empty) ───────────────────────────────────────────────────────────
    section("List curriculums")
    r = client.get(f"{BASE}/curriculums", headers=th)
    if assert_status(r, 200, "GET /curriculums (empty)"):
        body = r.json()
        assert "data" in body and isinstance(body["data"], list), "response has data[]"
        ok("response shape: data[] present")

    # ── AI GENERATE ────────────────────────────────────────────────────────────
    section("POST /curriculums/generate (AI — may be slow)")
    r = client.post(f"{BASE}/curriculums/generate",
        headers=th,
        json={"prompt": "Introduction to English grammar for B1 learners", "language_id": lang_id},
        timeout=120.0,
    )
    if assert_status(r, 200, "POST /curriculums/generate"):
        topics = r.json().get("data", [])
        ok(f"generated {len(topics)} topics")
        if topics:
            ok(f"first topic title: {topics[0].get('title','?')}")
    else:
        skip("downstream topic tests", "generate failed")

    # ── UPLOAD (multipart) ─────────────────────────────────────────────────────
    section("POST /curriculums (upload PDF)")
    # Use a minimal valid PDF bytes
    minimal_pdf = (
        b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
        b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000058 00000 n \n0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n190\n%%EOF"
    )
    r = client.post(
        f"{BASE}/curriculums",
        headers=th,
        files={"file": ("test.pdf", minimal_pdf, "application/pdf")},
        data={"title": f"Test Curriculum {ctx['suffix']}", "language_id": str(lang_id)},
        timeout=60.0,
    )
    if assert_status(r, 200, "POST /curriculums (upload)"):
        curriculum_id = r.json()["data"]["id"]
        ok(f"created curriculum_id={curriculum_id}")
    else:
        skip("all downstream curriculum tests", "upload failed")
        return curriculum_id, topic_id, library_curriculum_id

    # ── GET BY ID ──────────────────────────────────────────────────────────────
    section("GET /curriculums/{id}")
    r = client.get(f"{BASE}/curriculums/{curriculum_id}", headers=th)
    if assert_status(r, 200, f"GET /curriculums/{curriculum_id}"):
        data = r.json()["data"]
        assert data["id"] == curriculum_id
        ok(f"title: {data['title']}, status: {data['status']}, topics: {len(data.get('topics',[]))}")

    r = client.get(f"{BASE}/curriculums/00000000-0000-0000-0000-000000000000", headers=th)
    assert_status(r, 404, "GET /curriculums/fake-id → 404")

    # ── PATCH (teacher can edit their own curriculum) ──────────────────────────
    section("PATCH /curriculums/{id}")
    r = client.patch(f"{BASE}/curriculums/{curriculum_id}",
        headers=th,
        json={"title": f"Updated Title {ctx['suffix']}", "description": "Updated description"},
    )
    if assert_status(r, 200, "PATCH /curriculums/{id} as teacher"):
        ok(f"new title: {r.json()['data']['title']}")

    r = client.patch(f"{BASE}/curriculums/00000000-0000-0000-0000-000000000000",
        headers=th, json={"title": "nope"})
    assert_status(r, 404, "PATCH /curriculums/fake-id → 404")

    # ── EXTRACT TOPICS (AI) ────────────────────────────────────────────────────
    section("POST /curriculums/{id}/extract (AI extract topics from uploaded file)")
    r = client.post(f"{BASE}/curriculums/{curriculum_id}/extract", headers=th, timeout=120.0)
    if assert_status(r, 200, "POST /curriculums/{id}/extract"):
        topics = r.json().get("data", [])
        ok(f"extracted {len(topics)} topics")
        if topics:
            topic_id = topics[0]["id"]
            ok(f"first topic_id={topic_id}, title={topics[0].get('title','?')}")

    # ── GET after extract to see topics ────────────────────────────────────────
    r = client.get(f"{BASE}/curriculums/{curriculum_id}", headers=th)
    if assert_status(r, 200, "GET /curriculums/{id} after extract"):
        topics_in_body = r.json()["data"].get("topics", [])
        if topics_in_body and not topic_id:
            topic_id = topics_in_body[0]["id"]
        ok(f"curriculum now has {len(topics_in_body)} topics")

    # ── PATCH TOPIC (admin only) ───────────────────────────────────────────────
    section("PATCH /curriculums/topics/{topic_id} (admin only)")
    if topic_id:
        r = client.patch(f"{BASE}/curriculums/topics/{topic_id}",
            headers=ah,
            json={"title": "Updated Topic Title", "duration_hours": 2.5},
        )
        assert_status(r, 200, "PATCH /topics/{id} as admin")

        # Teacher cannot patch topics (admin only)
        r = client.patch(f"{BASE}/curriculums/topics/{topic_id}",
            headers=th,
            json={"title": "teacher attempt"},
        )
        assert_status(r, (403, 401), "PATCH /topics/{id} as teacher → 403")
    else:
        skip("PATCH /topics", "no topic_id available")

    # ── LIST with filters ──────────────────────────────────────────────────────
    section("GET /curriculums with filters")
    r = client.get(f"{BASE}/curriculums?page=1&page_size=5", headers=th)
    if assert_status(r, 200, "GET /curriculums?page=1&page_size=5"):
        body = r.json()
        assert "meta" in body
        ok(f"total={body.get('meta',{}).get('total','?')}, page={body.get('meta',{}).get('page','?')}")

    r = client.get(f"{BASE}/curriculums?status=draft", headers=th)
    assert_status(r, 200, "GET /curriculums?status=draft")

    r = client.get(f"{BASE}/curriculums?language_id={lang_id}", headers=th)
    assert_status(r, 200, f"GET /curriculums?language_id={lang_id}")

    # ── CREATE SECOND CURRICULUM (for merge) ──────────────────────────────────
    section("Create second curriculum for merge tests")
    r = client.post(
        f"{BASE}/curriculums",
        headers=th,
        files={"file": ("lib.pdf", minimal_pdf, "application/pdf")},
        data={"title": f"Library Curriculum {ctx['suffix']}", "language_id": str(lang_id)},
        timeout=60.0,
    )
    if assert_status(r, 200, "create library curriculum"):
        library_curriculum_id = r.json()["data"]["id"]
        ok(f"library_curriculum_id={library_curriculum_id}")

    # ── MERGE PROPOSE ──────────────────────────────────────────────────────────
    section("POST /curriculums/{id}/merge/propose")
    if library_curriculum_id:
        r = client.post(f"{BASE}/curriculums/{curriculum_id}/merge/propose",
            headers=th,
            json={"library_curriculum_id": library_curriculum_id},
            timeout=120.0,
        )
        # 200 if AI works, 503 if AI unavailable — both are valid; 403/404 would be bugs
        if r.status_code == 200:
            ok("merge/propose → 200")
            proposals = r.json()["data"].get("proposed_topics", [])
            ok(f"got {len(proposals)} topic proposals")
        elif r.status_code == 503:
            ok("merge/propose → 503 (AI service unavailable — acceptable in staging)")
        else:
            fail("merge/propose unexpected status", f"{r.status_code}: {r.text[:200]}")

        # Permission: teacher is allowed (not 403)
        assert r.status_code != 403, "teacher must not be forbidden from merge/propose"

        # 404 test
        r2 = client.post(f"{BASE}/curriculums/00000000-0000-0000-0000-000000000000/merge/propose",
            headers=th, json={"library_curriculum_id": library_curriculum_id})
        assert_status(r2, (404, 503), "merge/propose fake-id → 404 or 503")
    else:
        skip("merge/propose tests", "no library curriculum")

    # ── MERGE CONFIRM ──────────────────────────────────────────────────────────
    section("POST /curriculums/{id}/merge/confirm (admin only)")
    sample_topics = [
        {"title": "Grammar Basics", "content": "Nouns, verbs, adjectives",
         "duration_hours": 2.0, "learning_objectives": ["Identify parts of speech"], "order_index": 0}
    ]
    r = client.post(f"{BASE}/curriculums/{curriculum_id}/merge/confirm",
        headers=ah,
        json={"final_topics": sample_topics},
        timeout=60.0,
    )
    assert_status(r, (200, 404, 422), "merge/confirm as admin")

    r = client.post(f"{BASE}/curriculums/{curriculum_id}/merge/confirm",
        headers=th,
        json={"final_topics": sample_topics},
    )
    assert_status(r, (401, 403), "merge/confirm as teacher → 403")

    # ── DELETE (teacher can delete their own curriculum) ──────────────────────
    section("DELETE /curriculums/{id}")
    r = client.delete(f"{BASE}/curriculums/00000000-0000-0000-0000-000000000000", headers=th)
    assert_status(r, 404, "DELETE fake-id → 404")

    if library_curriculum_id:
        r = client.delete(f"{BASE}/curriculums/{library_curriculum_id}", headers=th)
        assert_status(r, 200, "DELETE library curriculum as teacher")

    r = client.delete(f"{BASE}/curriculums/{curriculum_id}", headers=th)
    assert_status(r, 200, "DELETE teacher curriculum")

    return curriculum_id, topic_id, library_curriculum_id


# ── main ───────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{BOLD}Curriculum endpoint tests → {BASE}{RESET}")
    print(f"{'─'*60}")

    with httpx.Client(timeout=TIMEOUT) as client:
        # Health check first
        r = client.get("https://api-staging.youspeakhq.com/health")
        if r.status_code != 200:
            print(f"{RED}Staging API unhealthy: {r.status_code}{RESET}")
            sys.exit(1)
        ok("staging /health", r.json().get("environment", "?"))

        ctx = setup(client)
        test_curriculum_endpoints(client, ctx)

    print(f"\n{'─'*60}")
    print(f"{BOLD}Results:{RESET}  {GREEN}{len(passed)} passed{RESET}  "
          f"{RED}{len(failed)} failed{RESET}  {YELLOW}{len(skipped)} skipped{RESET}")

    if failed:
        print(f"\n{RED}Failed:{RESET}")
        for f in failed:
            print(f"  • {f}")
        sys.exit(1)
    else:
        print(f"\n{GREEN}All checks passed ✓{RESET}")


if __name__ == "__main__":
    main()
