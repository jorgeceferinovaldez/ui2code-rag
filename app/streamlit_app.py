# app/streamlit_app.py
# add project src/ to import path
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

# Project agents & config (these come from your repo)
from src.agents.code_rag_agent import CodeRAGAgent
from src.agents.visual_agent import VisualAgent
from src.config import generated_code_dir, temp_images_dir, project_dir
# --- Session helpers & fallbacks ---

def build_visual_from_text(txt: str) -> dict:
    lower = (txt or "").lower()
    comps = []
    if any(k in lower for k in ["form", "contact"]): comps += ["form","input","button"]
    if any(k in lower for k in ["landing", "hero"]): comps += ["navbar","hero","button"]
    if any(k in lower for k in ["card", "dashboard"]): comps += ["card","grid"]
    return {
        "components": comps or ["section","button"],
        "layout": "single column" if "mobile" in lower else "grid/flex",
        "style": "clean",
        "color_scheme": "neutral",
        "style_tokens": {
            "colors": ["#0f172a","#1e293b","#e2e8f0","#14b8a6"],
            "font_category": "sans",
            "spacing_scale": [0,2,4,6,8,12,16,24,32],
            "radii": ["none","md","lg"],
            "shadows": ["sm","md"]
        },
        "analysis_text": txt or "text-only prompt"
    }

def analyze_fallback_from_image(visual_agent, image_path: str) -> dict:
    """Usa tu preprocess + tokens aunque el VLM falle (401, etc.)."""
    try:
        meta = visual_agent.preprocess_image(image_path)  # ya lo tenés
    except Exception as e:
        meta = {"error": str(e)}
    # tokens básicos desde preprocess (si no hay colores, usa defaults)
    dom_colors = meta.get("dominant_colors", []) if isinstance(meta, dict) else []
    def to_hex(c): return f"#{c['r']:02x}{c['g']:02x}{c['b']:02x}"
    colors = [to_hex(c) for c in dom_colors][:4] if dom_colors else ["#0f172a","#1e293b","#e2e8f0","#14b8a6"]
    return {
        "components": ["section","button","navbar"],  # estimación neutra
        "layout": meta.get("layout_hints", {}).get("complexity","medium"),
        "style": "clean",
        "color_scheme": "neutral",
        "style_tokens": {
            "colors": colors,
            "font_category": "sans",
            "spacing_scale": [0,2,4,6,8,12,16,24,32],
            "radii": ["none","md","lg"],
            "shadows": ["sm","md"]
        },
        "image_metadata": meta,
        "analysis_text": "fallback-from-image"
    }

def safe_generate(rag_agent, patterns, visual, extra=""):
    """Envuelve la generación y muestra errores legibles en Streamlit."""
    try:
        result = rag_agent.generate_code(patterns=patterns, visual_analysis=visual, custom_instructions=extra)
        if result.get("error"):
            st.error(result["error"])
            st.stop()
        return result
    except Exception as e:
        st.exception(e)
        st.stop()

# -----------------------------
# File helpers
# -----------------------------
def ensure_dirs():
    generated_code_dir().mkdir(parents=True, exist_ok=True)
    temp_images_dir().mkdir(parents=True, exist_ok=True)

def save_uploaded_image(uploaded_file) -> str:
    """Save uploaded image into temp folder and return path."""
    ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = Path(uploaded_file.name).suffix or ".png"
    out_path = temp_images_dir() / f"ui_{ts}{suffix}"
    out_path.write_bytes(uploaded_file.read())
    return str(out_path)

def save_html(content: str, fname: str | None = None) -> Path:
    ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = fname or f"generated_{ts}.html"
    if not name.endswith(".html"):
        name += ".html"
    p = generated_code_dir() / name
    p.write_text(content, encoding="utf-8")
    return p

def save_json(obj: dict, base: Path) -> Path:
    meta_path = base.with_suffix(".json")
    meta_path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta_path

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="🎨 UI→Code (RAG + Vision)", layout="wide")
st.title("🎨 Multi-Agent UI-to-Code System")
st.caption("Convert UI designs to clean HTML/Tailwind CSS code using AI Vision and RAG (with anti-hallucination style gating)")

with st.sidebar:
    st.header("⚙️ Environment (example)")
    st.code(
        "OPENROUTER_API_KEY=...\n"
        "OPENROUTER_BASE_URL=https://openrouter.ai/api/v1\n"
        "VISUAL_MODEL=google/gemini-flash-1.5\n"
        "CODE_MODEL=deepseek/deepseek-coder",
        language="bash",
    )
    if st.button("📁 Show output folder"):
        st.write(str(generated_code_dir()))

# Initialize agents (show clear errors if something fails)
rag_agent = None
visual_agent = None
rag_error = None
visual_error = None

try:
    rag_agent = CodeRAGAgent()
except Exception as e:
    rag_error = str(e)

try:
    visual_agent = VisualAgent()
except Exception as e:
    visual_error = str(e)

col1, col2 = st.columns([1, 1])
with col1:
    st.subheader("📚 RAG Status")
    if rag_agent:
        status = rag_agent.get_rag_status()
        st.json(status)
        if status.get("status") != "ready":
            st.warning("No documents found in the corpus. The app will fall back to generation without RAG (whitelisted Tailwind classes from tokens).")
    else:
        st.error(f"Could not initialize CodeRAGAgent: {rag_error}")

with col2:
    st.subheader("🧪 OpenRouter Health Check")
    if visual_agent:
        def healthcheck():
            try:
                r = visual_agent.client.chat.completions.create(
                    model=os.getenv("VISUAL_MODEL", "google/gemini-flash-1.5"),
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=4
                )
                return {"ok": True, "response": r.choices[0].message.content}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        if st.button("Run health check"):
            st.json(healthcheck())
    else:
        st.error(f"Could not initialize VisualAgent: {visual_error}")

st.markdown("---")

tab_img, tab_text, tab_diag = st.tabs(["🖼️ From Image", "⌨️ From Text", "🔧 Diagnostics"])

# --------------------------------------
# TAB: From Image
# --------------------------------------
with tab_img:
    st.subheader("🖼️ Upload a wireframe / mockup")
    up = st.file_uploader("Drop a PNG/JPG of your UI", type=["png","jpg","jpeg"], key="img_uploader")

    if up and visual_agent and rag_agent:
        img_path = save_uploaded_image(up)
        st.image(img_path, caption="Uploaded image", use_column_width=True)

        colA, colB = st.columns(2)
        with colA:
            if st.button("Analyze (vision model)", key="btn_analyze_model"):
                analysis = visual_agent.analyze_image(img_path)
                if analysis and not analysis.get("error"):
                    st.success("Vision analysis OK")
                    st.session_state["last_analysis"] = analysis
                    st.json(analysis)
                else:
                    st.error(f"Vision analysis failed: {analysis.get('error') if isinstance(analysis, dict) else analysis}")
                    if isinstance(analysis, dict) and analysis.get("hint"):
                        st.info(analysis["hint"])

        with colB:
            if st.button("Analyze (fallback, no model)", key="btn_analyze_fallback"):
                analysis = analyze_fallback_from_image(visual_agent, img_path)
                st.success("Fallback analysis OK")
                st.session_state["last_analysis"] = analysis
                st.json(analysis)

        st.markdown("### ⚒️ Generate HTML/Tailwind (CodeRAGAgent)")
        extra = st.text_area("Optional instructions", "", key="img_extra")

        # 👉 botón SIEMPRE habilitado: genera con último análisis válido o con fallback directo
        if st.button("Generate from current analysis (force)", key="btn_generate_force"):
            analysis = st.session_state.get("last_analysis")
            if not analysis:
                # si no analizaste, usa fallback al vuelo
                analysis = analyze_fallback_from_image(visual_agent, img_path)
            # retrieval opcional
            patterns = rag_agent.retrieve_patterns(analysis, top_k=5) if rag_agent and rag_agent.rag_pipeline else []
            result = safe_generate(rag_agent, patterns, analysis, extra=extra)
            html = result["html_code"]
            meta = result["generation_metadata"]
            st.success("✅ Generated from image")
            st.json(meta)
            out_path = save_html(html)
            save_json({"generation_metadata": meta, "visual_analysis_summary": result.get("visual_analysis_summary", {})}, out_path)
            st.download_button("⬇️ Download HTML", html, file_name=out_path.name)
            st.markdown("### 👀 Preview")
            st.components.v1.html(html, height=900, scrolling=True)

    elif not up:
        st.info("Upload an image to enable the image workflow.")
    elif not (visual_agent and rag_agent):
        st.error("Agents not initialized. Check errors above.")

# --------------------------------------
# TAB: From Text (fallback without image)
# --------------------------------------
with tab_text:
    st.subheader("⌨️ Describe your design in text")
    txt = st.text_area(
        "Example: 'Landing page with a navbar (Brand left, 3 links right) and a hero with a big title, paragraph, primary button. Clean style, cool colors.'",
        height=120,
        key="txt_prompt"
    )
    st.caption("Works even with an empty corpus (RAG). Uses a whitelist + default tokens.")

    # 👉 nunca grisamos el botón: lo dejamos SIEMPRE habilitado, chequeamos dentro
    if st.button("Generate from text (force)", key="btn_text_force"):
        if not txt.strip():
            st.warning("Type something first.")
        else:
            visual = build_visual_from_text(txt)
            patterns = rag_agent.retrieve_patterns(visual, top_k=5) if rag_agent and rag_agent.rag_pipeline else []
            result = safe_generate(rag_agent, patterns, visual, extra="")
            html = result["html_code"]
            meta = result["generation_metadata"]
            st.success("✅ Generated from text")
            st.json(meta)
            out_path = save_html(html, "generated_from_text.html")
            save_json({"generation_metadata": meta, "visual_analysis_summary": result.get("visual_analysis_summary", {})}, out_path)
            st.download_button("⬇️ Download HTML", html, file_name=out_path.name)
            st.markdown("### 👀 Preview")
            st.components.v1.html(html, height=900, scrolling=True)

# --------------------------------------
# TAB: Diagnostics / Utilities
# --------------------------------------
with tab_diag:
    st.subheader("🔧 Diagnostics")
    st.write("Quick tools to validate environment and pipeline.")

    colA, colB, colC = st.columns(3)

    with colA:
        st.markdown("**Paths**")
        st.write("Project:", str(project_dir()))
        st.write("Generated:", str(generated_code_dir()))
        st.write("Temp images:", str(temp_images_dir()))

    with colB:
        st.markdown("**Environment keys present**")
        st.write("OPENROUTER_API_KEY:", "✅" if os.getenv("OPENROUTER_API_KEY") else "❌")
        st.write("OPENROUTER_BASE_URL:", os.getenv("OPENROUTER_BASE_URL", "❌"))
        st.write("VISUAL_MODEL:", os.getenv("VISUAL_MODEL", "❌"))
        st.write("CODE_MODEL:", os.getenv("CODE_MODEL", "❌"))

    with colC:
        st.markdown("**Actions**")
        if st.button("List RAG status again"):
            if rag_agent:
                st.json(rag_agent.get_rag_status())
            else:
                st.error("CodeRAGAgent not initialized.")
        if st.button("Create seed examples (if missing)"):
            try:
                # Re-run the RAG initialization (your agent creates sample examples if none exist)
                rag_agent._initialize_rag_pipeline()
                st.success("Reinitialized RAG pipeline.")
                st.json(rag_agent.get_rag_status())
            except Exception as e:
                st.error(f"Failed to reinitialize RAG: {e}")

    st.markdown("---")
    st.markdown("**Troubleshooting**")
    st.markdown(
        "- 401 errors on image analysis: check `OPENROUTER_API_KEY` and `OPENROUTER_BASE_URL`, then restart the app.\n"
        "- Disabled buttons when typing a query: this app keeps the text-generation button enabled as long as the text box is not empty.\n"
        "- Empty corpus: you can still generate from text; use the 'Create seed examples' button to (re)populate sample HTML patterns."
    )
