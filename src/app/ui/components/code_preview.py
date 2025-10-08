import streamlit as st
import streamlit.components.v1 as components

def html_preview(html_code: str, height: int = 520):
    components.html(
        html=html_code,
        height=height,
        scrolling=True
    )
