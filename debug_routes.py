"""Debug script to check registered routes"""
import sys
from app.main import app

print("=" * 80)
print("REGISTERED ROUTES IN APP")
print("=" * 80)

email_routes_found = False

for route in app.routes:
    if hasattr(route, 'path'):
        path = route.path
        if 'email' in path.lower():
            email_routes_found = True
            print(f"✅ FOUND EMAIL ROUTE: {path}")
            if hasattr(route, 'methods'):
                print(f"   Methods: {route.methods}")
        elif '/api/v1/' in path:
            print(f"   {path}")

print("=" * 80)

if email_routes_found:
    print("✅ Email routes are registered!")
else:
    print("❌ NO EMAIL ROUTES FOUND!")
    print("\nAll routes:")
    for route in app.routes:
        if hasattr(route, 'path'):
            print(f"  - {route.path}")

print("=" * 80)

# Check the API router specifically
from app.api.v1.router import api_router

print("\nAPI V1 ROUTER ROUTES:")
print("=" * 80)
for route in api_router.routes:
    if hasattr(route, 'path'):
        path = route.path
        methods = getattr(route, 'methods', set())
        print(f"  {path} - {methods}")
        if 'email' in path.lower():
            print(f"    ✅ EMAIL ROUTE FOUND IN API ROUTER")

print("=" * 80)
