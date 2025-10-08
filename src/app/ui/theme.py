import streamlit as st

_DEFAULTS = {
    "primary": "#8B5CF6", 
    "bg":      "#0B0B10",
    "bg2":     "#151621",
    "text":    "#EDEAF5",
    "accent":  "#7C3AED",
    "font":    "montserrat",  
}

def set_theme_globals(**overrides):
    if "_theme_defaults" not in st.session_state:
        st.session_state["_theme_defaults"] = dict(_DEFAULTS)
    st.session_state["_theme_defaults"].update({k: v for k, v in overrides.items() if v})

def _cfg():
    cfg = st.session_state.get("_theme_defaults", dict(_DEFAULTS))
    f = (cfg.get("font") or "montserrat").lower()
    if f not in ("montserrat", "roboto"):
        f = "montserrat"
    cfg["font"] = f
    return cfg

import streamlit as st

def violet_button(label, key, *, on_click=None, disabled=False, help=None, full_width=False, color="var(--primary, #8B5CF6)"):
    """
    Renderiza un st.button y lo fuerza a violeta (mismo del theme),
    usando CSS "scoped" al botón recién pintado.
    """
    anchor_id = f"{key}__anchor"
    st.markdown(f'<div id="{anchor_id}"></div>', unsafe_allow_html=True)

    clicked = st.button(
        label=label,
        key=key,
        disabled=disabled,
        on_click=on_click,
        help=help,
        use_container_width=full_width,
        type="primary",  # aunque Streamlit lo ignore, lo forzamos con CSS
    )

    st.markdown(f"""
    <style>
    /* botón hermano inmediato y también general (por si hay wrappers) */
    div#{anchor_id} + div button,
    div#{anchor_id} + div [data-testid^="baseButton"],
    div#{anchor_id} ~ div button,
    div#{anchor_id} ~ div [data-testid^="baseButton"],
    /* variantes más específicas que suelen ganar al naranja */
    div#{anchor_id} + div div[data-testid="stButton"] > button,
    div#{anchor_id} ~ div div[data-testid="stButton"] > button,
    div#{anchor_id} + div div[data-testid="baseButton-primary"] > button,
    div#{anchor_id} ~ div div[data-testid="baseButton-primary"] > button {{
      background: {color} !important;
      background-color: {color} !important;
      color: #fff !important;
      border-radius: 12px !important;
      border: 1px solid rgba(255,255,255,0.10) !important;
      box-shadow: 0 6px 18px rgba(139, 92, 246, .25) !important; /* 8B5CF6 */
      padding: .6rem 1rem !important;
      font-weight: 600 !important;
      font-family: 'Montserrat','Roboto',sans-serif !important;
      transition: transform .08s ease, filter .08s ease;
    }}
    div#{anchor_id} + div button:hover,
    div#{anchor_id} + div [data-testid^="baseButton"]:hover,
    div#{anchor_id} ~ div button:hover,
    div#{anchor_id} ~ div [data-testid^="baseButton"]:hover {{
      filter: brightness(1.08) !important;
      transform: translateY(-0.5px) !important;
    }}
    div#{anchor_id} + div button:disabled,
    div#{anchor_id} + div [data-testid^="baseButton"][disabled],
    div#{anchor_id} ~ div button:disabled,
    div#{anchor_id} ~ div [data-testid^="baseButton"][disabled] {{
      opacity: .55 !important;
      cursor: not-allowed !important;
      box-shadow: none !important;
    }}
    </style>
    """, unsafe_allow_html=True)
    return clicked


def apply_theme():
    cfg = _cfg()
    primary, bg, bg2, text, accent, font = (
        cfg["primary"], cfg["bg"], cfg["bg2"], cfg["text"], cfg["accent"], cfg["font"]
    )
    from app.ui.header import render_global_header
    render_global_header(
        title="🧠 Multi-Agent UI-to-Code System",
        subtitle="Vision + RAG + Prompt-to-HTML (Tailwind)"
    )
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {
    text-transform: capitalize; /* capitaliza cada palabra del link */
    }
    </style>
""", unsafe_allow_html=True)
    st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet"/>
""", unsafe_allow_html=True)

    font_stack = (
        "'Montserrat','Roboto',-apple-system,BlinkMacSystemFont,'Segoe UI','Helvetica Neue',Arial,sans-serif"
        if font == "montserrat"
        else "'Roboto',-apple-system,BlinkMacSystemFont,'Segoe UI','Helvetica Neue',Arial,sans-serif"
    )

    st.markdown(f"""
<style>
  /* ===== Root tokens (para todas las versiones de Streamlit) ===== */
  :root,
  .stApp,
  [data-testid="stAppViewContainer"] {{
    /* tokens nuevos */
    --primary: {primary};
    --accent:  {accent};
    --bg:      {bg};
    --bg2:     {bg2};
    --text:    {text};
    --font-sans: {font_stack};

    /* tokens legacy de Streamlit (¡clave para el naranja!) */
    --primary-color: {primary} !important;
    --secondary-background-color: {bg2} !important;
    --background-color: {bg} !important;
    --text-color: {text} !important;

    /* variantes camelCase usadas en builds recientes */
    --secondaryBackgroundColor: {bg2} !important;
    --backgroundColor: {bg} !important;
    --primaryColor: {primary} !important;
    --textColor: {text} !important;

    /* botones (algunos temas los leen de acá) */
    --button-primary-background-color: {primary} !important;
    --button-primary-text-color: #ffffff !important;
  }}

  /* ===== Tipografía global (incluye widgets) ===== */
  html, body, [class*="css"], .stApp, .main,
  button, input, textarea, select,
  .stButton > button, .stDownloadButton > button, [data-testid^="baseButton"] {{
    font-family: var(--font-sans) !important;
    color: var(--text) !important;
  }}

  /* ===== Fondos ===== */
  .stApp, [data-testid="stAppViewContainer"], .main {{ background: var(--bg) !important; }}
  [data-testid="stHeader"] {{
    background: linear-gradient(180deg, rgba(0,0,0,.35), rgba(0,0,0,0)) !important;
  }}
  section[data-testid="stSidebar"] {{ background: var(--bg2) !important; }}

  /* ===== Menú de Pages en sidebar ===== */
  section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a,
  section[data-testid="stSidebar"] nav[aria-label="Main"] a {{
    display: block !important;
    color: var(--text) !important;
    text-decoration: none !important;
    border-radius: 12px !important;
    padding: .55rem .75rem !important;
    margin: 2px 4px !important;
    border: 1px solid transparent !important;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover,
  section[data-testid="stSidebar"] nav[aria-label="Main"] a:hover {{
    background: color-mix(in srgb, {primary} 18%, transparent) !important;
    border-color: color-mix(in srgb, {primary} 45%, transparent) !important;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"],
  section[data-testid="stSidebar"] nav[aria-label="Main"] a[aria-current="page"] {{
    background: color-mix(in srgb, {primary} 28%, transparent) !important;
    border-color: color-mix(in srgb, {primary} 55%, transparent) !important;
    box-shadow: 0 0 0 1px color-mix(in srgb, {primary} 35%, transparent) inset !important;
  }}

  /* ===== BOTONES (todas las variantes) ===== */
  /* 1) Clásicos */
  .stButton > button,
  .stDownloadButton > button,
  [data-testid="stFormSubmitButton"] > button,
  .stForm button[type="submit"] {{
    background: {primary} !important;
    background-color: {primary} !important;  /* por si el build usa background-color */
    color: #fff !important;
    border-radius: 12px !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    box-shadow: 0 6px 18px color-mix(in srgb, {primary} 25%, transparent) !important;
    padding: .6rem 1rem !important;
    font-weight: 600 !important;
    transition: transform .08s ease, filter .08s ease;
  }}
  .stButton > button:hover,
  .stDownloadButton > button:hover,
  [data-testid="stFormSubmitButton"] > button:hover,
  .stForm button[type="submit"]:hover {{
    filter: brightness(1.08) !important;
    transform: translateY(-0.5px) !important;
  }}

  /* 2) DOM moderno (1.33+): baseButton */
  [data-testid^="baseButton"],
  div[role="button"][data-testid^="baseButton"] {{
    background: {primary} !important;
    background-color: {primary} !important;
    color: #fff !important;
    border-radius: 12px !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    box-shadow: 0 6px 18px color-mix(in srgb, {primary} 25%, transparent) !important;
    padding: .6rem 1rem !important;
    font-weight: 600 !important;
  }}
  [data-testid^="baseButton"]:hover {{
    filter: brightness(1.08) !important;
    transform: translateY(-0.5px) !important;
  }}

  /* Secondary */
  .stButton > button[kind="secondary"],
  [data-testid="baseButton-secondary"] {{
    background: transparent !important;
    color: var(--text) !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
    box-shadow: none !important;
  }}
  .stButton > button[kind="secondary"]:hover,
  [data-testid="baseButton-secondary"]:hover {{
    background: color-mix(in srgb, {primary} 16%, transparent) !important;
    border-color: color-mix(in srgb, {primary} 55%, transparent) !important;
    color: #fff !important;
  }}

  /* ===== Inputs / slider / code ===== */
  .stTextInput input, .stTextArea textarea, .stNumberInput input,
  .stSelectbox > div > div {{
    background: rgba(255,255,255,0.06) !important;
    color: var(--text) !important;
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
  }}
  .stSlider [data-baseweb="slider"] > div > div > div {{ background: {primary} !important; }}
  pre, code, .stCode > div {{
    background: #0f0f17 !important;
    color: #eae9f1 !important;
    border-radius: 12px !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
  }}
</style>
""", unsafe_allow_html=True)
