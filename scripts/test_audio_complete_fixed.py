#!/usr/bin/env python3
"""
Complete test for audio meeting creation - WORKING VERSION
Creates school, admin, class, arena, and tests audio token generation.
"""
import requests
import json
import sys
from datetime import datetime

BASE_URL = "https://api-staging.youspeakhq.com/api/v1"

class TestRunner:
    def __init__(self):
        self.school_id = None
        self.admin_token = None
        self.class_id = None
        self.arena_id = None
        self.meeting_id = None
        self.audio_token = None

    def log(self, emoji, message):
        print(f"{emoji} {message}")

    def make_request(self, method, endpoint, token=None, json_data=None):
        """Make HTTP request with error handling."""
        url = f"{BASE_URL}{endpoint}"
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=15)
            elif method == "POST":
                resp = requests.post(url, headers=headers, json=json_data, timeout=15)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            return resp
        except requests.exceptions.RequestException as e:
            self.log("❌", f"Request failed: {e}")
            return None

    def step_1_register_school(self):
        """Register a new school with admin."""
        self.log("🏫", "Step 1: Registering school...")
        
        timestamp = int(datetime.now().timestamp())
        payload = {
            "school_name": f"Test Audio School {timestamp}",
            "email": f"audio_test_{timestamp}@youspeak.test",
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
        if not resp or resp.status_code not in [200, 201]:
            self.log("❌", f"Failed: {resp.text if resp else 'No response'}")
            return False
            
        data = resp.json().get("data", {})
        self.school_id = data.get("school_id")
        self.log("✅", f"School created: {self.school_id}")
        
        # Login
        login_resp = self.make_request("POST", "/auth/login", json_data={
            "email": payload["email"],
            "password": payload["password"]
        })
        
        if not login_resp or login_resp.status_code != 200:
            self.log("❌", f"Login failed: {login_resp.text if login_resp else 'No response'}")
            return False
            
        token_data = login_resp.json().get("data", {})
        self.admin_token = token_data.get("access_token")
        self.log("✅", "Admin logged in successfully")
        return True

    def step_2_create_class(self):
        """Create a class."""
        self.log("📚", "Step 2: Creating class...")

        payload = {
            "name": "Audio Test Class",
            "language_id": 2,  # Spanish
            "level": "beginner"
        }

        resp = self.make_request("POST", "/my-classes", token=self.admin_token, json_data=payload)
        if not resp or resp.status_code not in [200, 201]:
            self.log("❌", f"Failed: {resp.text if resp else 'No response'}")
            return False

        data = resp.json().get("data", {})
        self.class_id = data.get("id")
        self.log("✅", f"Class created: {self.class_id}")
        return True

    def step_3_create_arena(self):
        """Create an arena."""
        self.log("🎯", "Step 3: Creating arena...")
        
        payload = {
            "title": "Audio Meeting Test Arena",
            "class_id": self.class_id,
            "description": "Testing Cloudflare RealtimeKit audio",
            "challenge_type": "speaking",
            "difficulty_level": "beginner",
            "time_limit_seconds": 600
        }
        
        resp = self.make_request("POST", "/arenas", token=self.admin_token, json_data=payload)
        if not resp or resp.status_code not in [200, 201]:
            self.log("❌", f"Failed: {resp.text if resp else 'No response'}")
            return False
            
        data = resp.json().get("data", {})
        self.arena_id = data.get("id")
        self.log("✅", f"Arena created: {self.arena_id}")
        return True

    def step_4_start_arena(self):
        """Start the arena session."""
        self.log("▶️", "Step 4: Starting arena session...")
        
        resp = self.make_request("POST", f"/arenas/{self.arena_id}/start", token=self.admin_token)
        if not resp or resp.status_code not in [200, 201]:
            self.log("❌", f"Failed: {resp.text if resp else 'No response'}")
            return False
            
        self.log("✅", "Arena session started (state: initialized/live)")
        return True

    def step_5_generate_audio_token(self):
        """🎙️ THE KEY TEST: Generate audio token via Cloudflare RealtimeKit."""
        self.log("🎙️", "Step 5: Generating Cloudflare RealtimeKit audio token...")
        
        resp = self.make_request("POST", f"/arenas/{self.arena_id}/audio/token", token=self.admin_token)
        
        if not resp:
            self.log("❌", "No response from server")
            return False
            
        if resp.status_code != 200:
            self.log("❌", f"HTTP {resp.status_code}: {resp.text}")
            return False
            
        data = resp.json().get("data", {})
        self.audio_token = data.get("token")
        self.meeting_id = data.get("meeting_id")
        
        if self.audio_token:
            self.log("✅", "SUCCESS! Audio token generated!")
            self.log("🎫", f"Token preview: {self.audio_token[:60]}...")
            self.log("📱", f"Meeting ID: {self.meeting_id}")
            self.log("🌐", f"Preset: {data.get('preset_name', 'N/A')}")
            return True
        else:
            self.log("❌", "Token missing in response")
            self.log("📄", json.dumps(data, indent=2))
            return False

    def run(self):
        """Run all test steps."""
        print("\n" + "="*70)
        print("🎙️  CLOUDFLARE REALTIMEKIT AUDIO TEST")
        print("="*70 + "\n")
        
        steps = [
            ("Register School & Admin", self.step_1_register_school),
            ("Create Class", self.step_2_create_class),
            ("Create Arena", self.step_3_create_arena),
            ("Start Arena Session", self.step_4_start_arena),
            ("🎯 Generate Audio Token (RealtimeKit)", self.step_5_generate_audio_token)
        ]
        
        for i, (name, step) in enumerate(steps, 1):
            if not step():
                print(f"\n❌ TEST FAILED at step {i}: {name}\n")
                return False
            print()
        
        print("="*70)
        print("🎉  ALL TESTS PASSED!")
        print("="*70)
        print(f"\n📋 Test Results:")
        print(f"   School ID:    {self.school_id}")
        print(f"   Class ID:     {self.class_id}")
        print(f"   Arena ID:     {self.arena_id}")
        print(f"   Meeting ID:   {self.meeting_id}")
        print(f"   Audio Token:  {self.audio_token[:40]}...")
        print(f"\n✅ Cloudflare RealtimeKit is working correctly!")
        print(f"✅ Audio credentials are properly configured!\n")
        return True

if __name__ == "__main__":
    runner = TestRunner()
    success = runner.run()
    sys.exit(0 if success else 1)
