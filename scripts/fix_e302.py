#!/usr/bin/env python3
"""Ensure two blank lines before top-level def/class (PEP 8 E302)."""
import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
PAT = re.compile(r"^(\s*)(def |class )")


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    out = []
    i = 0
    changed = False
    while i < len(lines):
        line = lines[i]
        # Top-level def/class only: 2 blank lines before (PEP 8 E302)
        m = PAT.match(line)
        if m and not m.group(1):
            blanks = 0
            j = len(out) - 1
            while j >= 0 and out[j].strip() == "":
                blanks += 1
                j -= 1
            if 0 <= blanks < 2:
                out.extend([""] * (2 - blanks))
                changed = True
        out.append(line)
        i += 1
    if changed:
        path.write_text("\n".join(out) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")
    return changed


def main():
    for py in APP.rglob("*.py"):
        if fix_file(py):
            print(py)


if __name__ == "__main__":
    main()
