import re
import streamlit as st
import streamlit.components.v1 as components

# Clases de Tailwind que esconden el root al hacer hover
_HIDE_TOKENS = [
    r"hover:hidden", r"group-hover:hidden",
    r"hover:opacity-0", r"group-hover:opacity-0",
    r"hover:invisible", r"group-hover:invisible",
    r"hover:collapse", r"group-hover:collapse",
    r"hover:scale-0", r"group-hover:scale-0",
]

_TAG_RE = re.compile(r"<(div|section|main|article|header|footer|body)\b[^>]*>", re.I)

def _neutralize_root_hover_hide(html: str) -> str:
    """Quita tokens 'hover:*' que ocultan el PRIMER contenedor (root)."""
    if not html:
        return html

    m = _TAG_RE.search(html)
    if not m:
        return html

    tag = m.group(0)

    def _fix_classes(match: re.Match) -> str:
        classes = match.group(1)
        for tok in _HIDE_TOKENS:
            classes = re.sub(rf"(?<!\S){tok}(?!\S)", "", classes, flags=re.I)
        classes = re.sub(r"\s+", " ", classes).strip()
        return f'class="{classes}"'

    # sólo tocamos la primera class="" del primer tag contenedor encontrado
    new_tag = re.sub(r'class\s*=\s*"(.*?)"', _fix_classes, tag, count=1, flags=re.I)
    if new_tag == tag:
        return html  # no tenía class o no había tokens a quitar

    start, end = m.span()
    return html[:start] + new_tag + html[end:]

def html_preview(html_code: str, height: int = 520):
    safe_html = _neutralize_root_hover_hide(html_code)
    components.html(
        html=safe_html,
        height=height,
        scrolling=True
    )
