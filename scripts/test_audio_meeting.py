#!/usr/bin/env python3
"""
Test script for audio meeting creation on staging.
Creates test accounts (student, teacher, admin) and tests audio meeting functionality.
"""
import requests
import json
import sys
from datetime import datetime, timedelta

# Staging endpoint
BASE_URL = "https://youspeak-alb-staging-1068882573.eu-north-1.elb.amazonaws.com/api/v1"

class Color:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def log_success(msg):
    print(f"{Color.GREEN}✓ {msg}{Color.END}")

def log_error(msg):
    print(f"{Color.RED}✗ {msg}{Color.END}")

def log_info(msg):
    print(f"{Color.BLUE}ℹ {msg}{Color.END}")

def log_warning(msg):
    print(f"{Color.YELLOW}⚠ {msg}{Color.END}")

def make_request(method, endpoint, token=None, json_data=None, params=None):
    """Make HTTP request with error handling."""
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, params=params, timeout=10)
        elif method == "POST":
            resp = requests.post(url, headers=headers, json=json_data, timeout=10)
        elif method == "PUT":
            resp = requests.put(url, headers=headers, json=json_data, timeout=10)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return resp
    except requests.exceptions.RequestException as e:
        log_error(f"Request failed: {e}")
        return None

def create_test_user(email, name, role="student"):
    """Create a test user account."""
    log_info(f"Creating {role}: {email}")
    
    # In production, you'd use proper authentication flow
    # For now, we'll use direct API calls (adjust based on your auth system)
    payload = {
        "email": email,
        "name": name,
        "role": role
    }
    
    resp = make_request("POST", "/auth/register", json_data=payload)
    if resp and resp.status_code in [200, 201]:
        data = resp.json()
        log_success(f"Created {role}: {email}")
        return data
    else:
        log_error(f"Failed to create {role}: {resp.status_code if resp else 'No response'}")
        if resp:
            log_error(f"Response: {resp.text}")
        return None

def create_classroom(teacher_token, name, subject):
    """Create a test classroom."""
    log_info(f"Creating classroom: {name}")
    
    payload = {
        "name": name,
        "subject": subject,
        "description": f"Test classroom for {subject}"
    }
    
    resp = make_request("POST", "/classrooms", token=teacher_token, json_data=payload)
    if resp and resp.status_code in [200, 201]:
        data = resp.json()
        log_success(f"Created classroom: {data.get('id')}")
        return data
    else:
        log_error(f"Failed to create classroom: {resp.status_code if resp else 'No response'}")
        if resp:
            log_error(f"Response: {resp.text}")
        return None

def create_audio_meeting(token, classroom_id=None, title="Test Audio Meeting"):
    """Create an audio meeting."""
    log_info(f"Creating audio meeting: {title}")
    
    start_time = datetime.utcnow() + timedelta(minutes=5)
    payload = {
        "title": title,
        "start_time": start_time.isoformat() + "Z",
        "duration_minutes": 30
    }
    
    if classroom_id:
        payload["classroom_id"] = classroom_id
    
    resp = make_request("POST", "/audio/meetings", token=token, json_data=payload)
    if resp and resp.status_code in [200, 201]:
        data = resp.json()
        log_success(f"Created audio meeting: {data.get('id')}")
        log_info(f"Meeting URL: {data.get('meeting_url')}")
        return data
    else:
        log_error(f"Failed to create audio meeting: {resp.status_code if resp else 'No response'}")
        if resp:
            log_error(f"Response: {resp.text}")
            try:
                error_data = resp.json()
                log_error(f"Error details: {json.dumps(error_data, indent=2)}")
            except:
                pass
        return None

def test_audio_flow():
    """Run complete audio meeting test flow."""
    print("=" * 60)
    print("Audio Meeting Test - Staging Environment")
    print("=" * 60)
    print()
    
    # Step 1: Health check
    log_info("Step 1: Health check")
    resp = make_request("GET", "/health")
    if resp and resp.status_code == 200:
        log_success("API is healthy")
    else:
        log_error("API health check failed")
        return False
    print()
    
    # Step 2: Create test accounts
    log_info("Step 2: Creating test accounts")
    timestamp = int(datetime.now().timestamp())
    
    teacher_email = f"teacher_{timestamp}@test.youspeak.com"
    student_email = f"student_{timestamp}@test.youspeak.com"
    
    # Note: Adjust these calls based on your actual auth flow
    # You may need to use Privy auth or different endpoints
    teacher = create_test_user(teacher_email, "Test Teacher", "teacher")
    if not teacher:
        log_warning("Skipping user creation - may need manual setup or different auth flow")
    
    student = create_test_user(student_email, "Test Student", "student")
    print()
    
    # Step 3: Get auth tokens (adjust based on your auth system)
    log_info("Step 3: Authentication")
    log_warning("Using mock tokens - replace with real auth flow")
    # In real scenario, you'd authenticate and get JWT tokens
    teacher_token = "YOUR_TEACHER_TOKEN_HERE"
    student_token = "YOUR_STUDENT_TOKEN_HERE"
    print()
    
    # Step 4: Create classroom
    log_info("Step 4: Creating classroom")
    classroom = create_classroom(teacher_token, "Test Audio Classroom", "Physics")
    if not classroom:
        log_error("Failed to create classroom")
        return False
    classroom_id = classroom.get("id")
    print()
    
    # Step 5: Create audio meeting
    log_info("Step 5: Creating audio meeting")
    meeting = create_audio_meeting(teacher_token, classroom_id, "Test Physics Discussion")
    if not meeting:
        log_error("Failed to create audio meeting")
        return False
    print()
    
    # Step 6: Test meeting access
    log_info("Step 6: Testing meeting access")
    meeting_id = meeting.get("id")
    resp = make_request("GET", f"/audio/meetings/{meeting_id}", token=teacher_token)
    if resp and resp.status_code == 200:
        log_success("Meeting is accessible")
    else:
        log_error("Meeting access failed")
    print()
    
    log_success("All tests completed!")
    return True

if __name__ == "__main__":
    try:
        success = test_audio_flow()
        sys.exit(0 if success else 1)
    except Exception as e:
        log_error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
