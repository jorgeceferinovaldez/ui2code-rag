# src/core/tw_validator.py
from __future__ import annotations
import re
from typing import List, Set

def strip_md_fences(code: str) -> str:
    code = code.strip()
    if "```html" in code:
        start = code.find("```html") + 7
        end = code.find("```", start)
        if end != -1:
            return code[start:end].strip()
    if "```" in code:
        start = code.find("```") + 3
        end = code.find("```", start)
        if end != -1:
            return code[start:end].strip()
    return code

def validate_classes(html: str, allowed: Set[str]) -> List[str]:
    bad = []
    for cls in re.findall(r'class="([^"]+)"', html):
        for tok in cls.split():
            if tok not in allowed:
                bad.append(tok)
    return sorted(set(bad))
