import streamlit as st
import pandas as pd
from io import StringIO
from app.services.agents import get_rag_agent
from src.config import project_dir
from loguru import logger

def _run_eval(docs_path: str, qrels_path: str, ks: tuple[int,...], top_retrieve: int, top_final: int, device: str | None):
    """
    Ejecuta la lógica de evaluate_retrieval.py pero desde Streamlit.
    """
    from src.agents.rag_agent.rag.adapters.pinecone_adapter import PineconeSearcher
    from src.agents.rag_agent.rag.core.io_utils import load_docs_jsonl, load_qrels_csv
    from src.agents.rag_agent.rag.core.rag_pipeline import RagPipeline
    from src.agents.rag_agent.rag.evaluators.evaluate_retrieval import evaluate

    docs = load_docs_jsonl(project_dir()/docs_path if not docs_path.startswith("/") else docs_path)
    qrels = load_qrels_csv(project_dir()/qrels_path if not qrels_path.startswith("/") else qrels_path)

    import os
    from src.config import pinecone_index as cfg_pinecone_index, pinecone_api_key as cfg_pinecone_api_key

    index_name = os.getenv("PINECONE_INDEX") or (cfg_pinecone_index if cfg_pinecone_index else "pln3-index")
    api_key = os.getenv("PINECONE_API_KEY") or cfg_pinecone_api_key

    if not api_key:
        st.error("PINECONE_API_KEY no configurada. Seteala como variable de entorno o en src.config.")
        st.stop()

    searcher = PineconeSearcher(index_name=index_name, namespace="eval-metrics")
    try:
        searcher.clear_namespace()
    except Exception:
        pass

    pipeline = RagPipeline(
        docs=docs,
        pinecone_searcher=searcher,
        max_tokens_chunk=120,
        overlap=30,
        ce_model="cross-encoder/ms-marco-MiniLM-L-6-v2",
        device=device,
    )

    df, agg = evaluate(pipeline, qrels, ks=ks, top_retrieve=top_retrieve, top_final=top_final)
    return df, agg

def _download_btn(df: pd.DataFrame, label: str, filename: str):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(label=label, data=csv, file_name=filename, mime="text/csv", type="primary")

def render():
    st.header("📏 Evaluaciones de Retrieval")
    st.markdown("Corre métricas **MRR, nDCG, Precision@k, Recall@k** sobre tu set de evaluación.")

    with st.expander("⚙️ Parámetros", expanded=True):
        c1,c2 = st.columns([2,2])
        with c1:
            docs = st.text_input("Ruta Docs JSONL", value="data/evaluate/docs_ui_code_en.jsonl")
            qrels = st.text_input("Ruta Qrels CSV", value="data/evaluate/qrels_ui_code_en.csv")
        with c2:
            ks_str = st.text_input("K's (coma)", value="3,5")
            ks = tuple(int(x) for x in ks_str.split(",") if x.strip().isdigit())
            top_ret = st.slider("top_retrieve", 5, 200, 10, step=5)
            top_fin = st.slider("top_final", 1, 50, 5, step=1)
        device = st.selectbox("Device (opcional)", ["auto","cpu","cuda","mps"], index=0)

    run = st.button("🚀 Ejecutar evaluación", type="primary")
    if run:
        with st.spinner("Indexando y evaluando…"):
            try:
                df, agg = _run_eval(docs, qrels, ks=ks, top_retrieve=top_ret, top_final=top_fin, device=None if device=="auto" else device)
            except FileNotFoundError as e:
                st.error(f"No se encontraron archivos: {e}")
                return
            except Exception as e:
                st.error(f"Error durante la evaluación: {e}")
                st.exception(e)
                return

        st.subheader("📊 Métricas por query y K")
        st.dataframe(df, use_container_width=True)
        _download_btn(df, "⬇️ Descargar per-query", "eval_retrieval_per_query.csv")

        st.subheader("✅ Promedios (macro) por K")
        st.dataframe(agg, use_container_width=True)
        _download_btn(agg, "⬇️ Descargar agregados", "eval_retrieval_aggregated.csv")

        with st.expander("📈 Tips de lectura"):
            st.markdown(
                "- **MRR** resalta si el doc relevante aparece muy arriba.\n"
                "- **nDCG** captura ganancias por posición, útil si hay múltiples relevantes.\n"
                "- **Precision@k/Recall@k**: micro-claros para comparar pre/post reranking."
            )
