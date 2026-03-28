#!/bin/bash
# Simple health check and config verification

BASE_URL="http://youspeak-alb-staging-1068882573.eu-north-1.elb.amazonaws.com"

echo "=== Testing Staging API ==="
echo ""

echo "1. Health Check:"
curl -s "$BASE_URL/api/v1/health" | jq '.' || echo "Health check failed"
echo ""

echo "2. API Info (to check if Cloudflare is configured):"
curl -s "$BASE_URL/api/v1/health" | jq '.environment' || echo "API not responding"
echo ""

echo "To test audio, you'll need:"
echo "  - Valid auth token (from Privy)"
echo "  - Active arena ID"
echo "  - Arena in 'initialized' or 'live' state"
echo ""
