#!/usr/bin/env python3
"""
Complete test for audio meeting creation.
Creates school, admin, teacher, class, arena, and tests audio token generation.
"""
import requests
import json
import sys
from datetime import datetime
from uuid import uuid4

BASE_URL = "https://api-staging.youspeakhq.com/api/v1"

class TestRunner:
    def __init__(self):
        self.school_id = None
        self.admin_token = None
        self.teacher_token = None
        self.teacher_id = None
        self.class_id = None
        self.arena_id = None

    def log(self, emoji, message):
        print(f"{emoji} {message}")

    def make_request(self, method, endpoint, token=None, json_data=None, expect_success=True):
        """Make HTTP request with error handling."""
        url = f"{BASE_URL}{endpoint}"
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=10)
            elif method == "POST":
                resp = requests.post(url, headers=headers, json=json_data, timeout=10)
            elif method == "PUT":
                resp = requests.put(url, headers=headers, json=json_data, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if expect_success and resp.status_code not in [200, 201]:
                self.log("❌", f"Request failed: {resp.status_code}")
                self.log("📄", f"Response: {resp.text}")
                return None
                
            return resp
        except requests.exceptions.RequestException as e:
            self.log("❌", f"Request failed: {e}")
            return None

    def step_1_register_school(self):
        """Register a new school with admin."""
        self.log("🏫", "Step 1: Registering school...")
        
        timestamp = int(datetime.now().timestamp())
        payload = {
            "school_name": f"Test School {timestamp}",
            "email": f"admin_{timestamp}@test.youspeak.com",
            "password": "TestPassword123!",
            "school_type": "secondary",
            "program_type": "partnership",
            "address_country": "US",
            "address_state": "CA",
            "address_city": "San Francisco",
            "address_zip": "94102",
            "languages": ["spanish"]
        }
        
        resp = self.make_request("POST", "/auth/register/school", json_data=payload)
        if not resp:
            return False
            
        data = resp.json().get("data", {})
        self.school_id = data.get("school_id")
        self.log("✅", f"School created: {self.school_id}")
        
        # Login as admin
        login_resp = self.make_request("POST", "/auth/login", json_data={
            "email": payload["email"],
            "password": payload["password"]
        })
        
        if not login_resp:
            return False
            
        token_data = login_resp.json().get("data", {})
        self.admin_token = token_data.get("access_token")
        self.log("✅", "Admin logged in")
        return True

    def step_2_create_teacher(self):
        """Create a teacher account."""
        self.log("👨‍🏫", "Step 2: Creating teacher...")
        
        # Use admin token for testing (admin can do everything teacher can)
        self.teacher_token = self.admin_token
        self.log("✅", "Using admin token as teacher for testing")
        return True

    def step_3_create_class(self):
        """Create a class."""
        self.log("📚", "Step 3: Creating class...")

        payload = {
            "name": "Test Spanish Class",
            "language_id": 1,
            "level": "beginner"
        }

        resp = self.make_request("POST", "/my-classes", token=self.teacher_token, json_data=payload)
        if not resp:
            return False

        data = resp.json().get("data", {})
        self.class_id = data.get("id")
        self.log("✅", f"Class created: {self.class_id}")
        return True

    def step_4_create_arena(self):
        """Create an arena."""
        self.log("🎯", "Step 4: Creating arena...")
        
        payload = {
            "title": "Test Audio Arena",
            "class_id": self.class_id,
            "description": "Testing audio functionality",
            "challenge_type": "speaking",
            "difficulty_level": "beginner",
            "time_limit_seconds": 300
        }
        
        resp = self.make_request("POST", "/arenas", token=self.teacher_token, json_data=payload)
        if not resp:
            return False
            
        data = resp.json().get("data", {})
        self.arena_id = data.get("id")
        self.log("✅", f"Arena created: {self.arena_id}")
        return True

    def step_5_start_arena(self):
        """Start the arena session."""
        self.log("▶️", "Step 5: Starting arena...")
        
        resp = self.make_request("POST", f"/arenas/{self.arena_id}/start", token=self.teacher_token)
        if not resp:
            return False
            
        self.log("✅", "Arena started")
        return True

    def step_6_test_audio_token(self):
        """Test audio token generation."""
        self.log("🎙️", "Step 6: Generating audio token...")
        
        resp = self.make_request("POST", f"/arenas/{self.arena_id}/audio/token", token=self.teacher_token)
        if not resp:
            return False
            
        data = resp.json().get("data", {})
        token = data.get("token")
        meeting_id = data.get("meeting_id")
        
        if token:
            self.log("✅", f"Audio token generated!")
            self.log("🎫", f"Token: {token[:50]}...")
            self.log("📱", f"Meeting ID: {meeting_id}")
            return True
        else:
            self.log("❌", "No token in response")
            self.log("📄", f"Full response: {json.dumps(data, indent=2)}")
            return False

    def run(self):
        """Run all test steps."""
        print("=" * 60)
        print("🧪 Audio Meeting Test - Complete Flow")
        print("=" * 60)
        print()
        
        steps = [
            self.step_1_register_school,
            self.step_2_create_teacher,
            self.step_3_create_class,
            self.step_4_create_arena,
            self.step_5_start_arena,
            self.step_6_test_audio_token
        ]
        
        for i, step in enumerate(steps, 1):
            if not step():
                self.log("❌", f"Test failed at step {i}")
                return False
            print()
        
        print("=" * 60)
        self.log("🎉", "ALL TESTS PASSED!")
        print("=" * 60)
        print()
        print(f"📋 Summary:")
        print(f"   School ID: {self.school_id}")
        print(f"   Class ID: {self.class_id}")
        print(f"   Arena ID: {self.arena_id}")
        print()
        return True

if __name__ == "__main__":
    runner = TestRunner()
    success = runner.run()
    sys.exit(0 if success else 1)
