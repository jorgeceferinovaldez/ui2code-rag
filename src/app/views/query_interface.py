import streamlit as st
from app.services.agents import get_orchestrator, get_rag_agent
from app.ui.components.code_preview import html_preview

# 👇 Agregar esto arriba del archivo
import re

_HIDE_TOKENS = [
    r"hover:hidden", r"group-hover:hidden",
    r"hover:opacity-0", r"group-hover:opacity-0",
    r"hover:invisible", r"group-hover:invisible",
    r"hover:collapse", r"group-hover:collapse",
    r"hover:scale-0", r"group-hover:scale-0",
]
_TAG_RE = re.compile(r"<(div|section|main|article|header|footer|body)\b[^>]*>", re.I)

def neutralize_root_hover_hide(html: str) -> str:
    """Quita tokens 'hover:*' que ocultarían TODO el preview al pasar el mouse."""
    if not html:
        return html
    m = _TAG_RE.search(html)
    if not m:
        return html
    tag = m.group(0)

    def _fix_classes(mm: re.Match) -> str:
        classes = mm.group(1)
        for tok in _HIDE_TOKENS:
            classes = re.sub(rf"(?<!\S){tok}(?!\S)", "", classes, flags=re.I)
        classes = re.sub(r"\s+", " ", classes).strip()
        return f'class="{classes}"'

    new_tag = re.sub(r'class\s*=\s*"(.*?)"', _fix_classes, tag, count=1, flags=re.I)
    if new_tag == tag:
        return html

    start, end = m.span()
    return html[:start] + new_tag + html[end:]


import streamlit as st
import uuid

def stable_code_block(code: str, *, language: str = "html", key: str | None = None):
    """
    Renderiza un st.code y neutraliza cualquier regla CSS de :hover que intente
    ocultarlo (display:none, opacity:0, visibility:hidden, transform, etc.).
    No toca el resto de la app.
    """
    anchor = key or f"code_{uuid.uuid4().hex[:8]}"
    st.markdown(f'<div id="{anchor}"></div>', unsafe_allow_html=True)

    st.code(code, language=language)

    st.markdown(
                f"""
        <style>
        /* Selecciona el contenedor que Streamlit pone justo después del ancla */
        div#{anchor} + div, 
        div#{anchor} + div * {{
        /* aseguremos que esté visible por más que exista algún :hover global */
        visibility: visible !important;
        transform: none !important;
        }}
        div#{anchor} + div pre,
        div#{anchor} + div code,
        div#{anchor} + div [data-testid="stCodeBlock"] {{
        display: block !important;
        visibility: visible !important;
        }}
        /* cuando haya hover por cualquier ancestro o el propio bloque */
        div#{anchor} + div:hover,
        div#{anchor} + div:hover *,
        div#{anchor} + div *:hover {{
        opacity: 1 !important;
        visibility: visible !important;
        transform: none !important;
        filter: none !important;
        }}
        </style>
                """,
        unsafe_allow_html=True,
    )

def render():
    st.header("🔎 Query Interface")

    mode = st.radio(
        "Modo",
        ["RAG Search (HTML Patterns)", "Prompt → HTML"],
        horizontal=True
    )

    c1, c2 = st.columns([3,1])
    with c1:
        query = st.text_area(
            "Ingresá tu consulta o prompt de UI",
            placeholder="• RAG: 'dashboard con sidebar y cards'\n• Prompt → HTML: 'dark dashboard con sidebar, cards y header'",
            height=120
        )
    with c2:
        if mode == "RAG Search (HTML Patterns)":
            top_k = st.slider("Top resultados", 1, 10, 5)
            custom = ""
        else:
            custom = st.text_area("Instrucciones opcionales", height=120, placeholder="Tailwind, glassmorphism, mobile-first…")
            save = st.checkbox("Guardar código generado", value=True)

    if mode == "RAG Search (HTML Patterns)":
        if st.button("🚀 Buscar patrones", type="primary", disabled=not query.strip()):
            rag = get_rag_agent()
            if not rag:
                st.error("RAG agent no disponible.")
                return
            with st.spinner("Buscando patrones HTML/CSS…"):
                visual_analysis = {"analysis_text": query.strip(), "components": [], "layout": "unknown", "style": "modern"}
                patterns = rag.invoke(visual_analysis, top_k=top_k)

            if patterns:
                st.subheader(f"🔍 {len(patterns)} patrones similares")
                for i, (doc_id, chunk, meta, score) in enumerate(patterns, 1):
                    with st.expander(f"Pattern #{i} — {meta.get('filename', doc_id)} (score {score:.3f})"):
                        st.markdown(f"**Tipo:** {meta.get('doc_type','?')} — **Desc.:** {meta.get('description','—')}")
                        html_code = meta.get("html_code", chunk)
                        st.code(html_code[:1500] + ("..." if len(html_code)>1500 else ""), language="html")
                        with st.popover("👁️ Previsualizar"):
                             safe_html = neutralize_root_hover_hide(html_code)
                             html_preview(safe_html)
            else:
                st.warning("Sin resultados, probá otra descripción.")
    else:
        if st.button("🚀 Generar desde Prompt", type="primary", disabled=not query.strip()):
            orch = get_orchestrator()
            if not orch:
                st.error("Orchestrator no disponible.")
                return
            with st.spinner("Generando HTML/Tailwind…"):
                import asyncio
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(
                    orch.send_prompt_to_code_agent(prompt_text=query.strip(), patterns=[], custom_instructions=custom.strip())
                )
            if "error" in result and not result.get("html_code"):
                st.error(f"Falló la generación: {result['error']}")
                return
            html_code = result.get("html_code", "")
            from app.ui.theme import code_block_no_hover_hide

            st.subheader("💻 Código generado")
            render_code = html_code or "<!-- empty -->"
            code_block_no_hover_hide(render_code, language="html", key="gen_code_block")
            
            with st.expander("🛠️ Detalles"):
                st.json(result.get("generation_metadata", {}))
                st.json(result.get("visual_analysis_summary", {}))
            st.subheader("🌐 Preview")
            safe_html = neutralize_root_hover_hide(html_code)
            html_preview(safe_html)
            if html_code and st.checkbox("Guardar resultado (artifacts)"):
                from src.agents.orchestator_agent.utils import save_generated_code
                try:
                    p = save_generated_code(result)
                    st.success(f"Guardado en: {p}")
                except Exception as e:
                    st.warning(f"No se pudo guardar: {e}")
