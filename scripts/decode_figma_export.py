#!/usr/bin/env python3
"""Decode Figma get_screenshot JSON and save first export as PNG. Usage: python decode_figma_export.py < path/to/export.json"""
import json
import base64
import sys
import os

def main():
    data = json.load(sys.stdin)
    exports = data.get("exports", [])
    if not exports:
        print("No exports in JSON", file=sys.stderr)
        sys.exit(1)
    b64 = exports[0].get("base64", "")
    if not b64:
        print("No base64 in first export", file=sys.stderr)
        sys.exit(1)
    out_dir = os.path.join(os.path.dirname(__file__), "..", "docs", "figma-cache")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "logo.png")
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64))
    print("Saved", out_path)

if __name__ == "__main__":
    main()
