# scripts/seed_ui_examples.py
from src.agents.code_rag_agent import CodeRAGAgent

if __name__ == "__main__":
    agent = CodeRAGAgent()
    st = agent.get_rag_status()
    print("RAG status:", st)
    if st.get("status") != "ready":
        # forzar reinicialización por si algo quedó colgado
        agent._initialize_rag_pipeline()
        print("RAG reinit:", agent.get_rag_status())
