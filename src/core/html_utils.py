# src/core/html_utils.py
from __future__ import annotations
import re
from typing import Set
from .style_tokens import inline_tailwind_config_js

def extract_tw_classes(html: str) -> Set[str]:
    classes = set()
    for m in re.findall(r'class="([^"]+)"', html):
        for tok in m.split():
            tok = tok.strip()
            if tok:
                classes.add(tok)
    return classes

def inject_tailwind_inline_config(html: str, style_tokens: dict) -> str:
    """
    Inserts <script>tailwind.config=...</script> in <head>.
    If there is no <head>, it adds before </html>.
    """
    js = inline_tailwind_config_js(style_tokens)
    if "<head" in html:
        return re.sub(r"(<head[^>]*>)", r"\1\n" + js + "\n", html, count=1, flags=re.IGNORECASE)
    if "</head>" in html:
        return html.replace("</head>", js + "\n</head>")
    if "</html>" in html:
        return html.replace("</html>", js + "\n</html>")
    # fallback
    return js + "\n" + html
