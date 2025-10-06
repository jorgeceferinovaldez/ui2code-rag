import streamlit as st
import sys, os, asyncio
from pathlib import Path
import nest_asyncio
from datetime import datetime
from typing import Optional, Any
from PIL import Image

from src.agents.orchestator_agent.utils import save_analysis_result, save_generated_code
from src.config import (
    corpus_dir,
    project_dir,
    temp_images_dir,
    pinecone_index,
    pinecone_model_name,
    pinecone_cloud,
    pinecone_region,
    pinecone_api_key,
    pinecone_namespace,
)
from src.agents.rag_agent.rag_agent import RAGAgent
from src.agents.orchestator_agent.orchestator_agent import OrchestratorAgent

st.write(
    """
# My first app
Hello *world!*
"""
)

nest_asyncio.apply()


@st.cache_resource
def get_rag_pipeline():
    """
    Initialize and cache the RAG pipeline.
    Returns the pipeline instance, initializing it if needed.
    """
    try:
        from src.agents.rag_agent.rag.adapters.pinecone_adapter import PineconeSearcher
        from src.agents.rag_agent.rag.core.rag_pipeline import RagPipeline
        from src.agents.rag_agent.rag.ingestion.pdf_loader import folder_pdfs_to_documents

        # Load documents from corpus
        docs = folder_pdfs_to_documents(corpus_dir(), recursive=True)
        if not docs:
            st.error("No documents found in corpus directory")
            return None

        # Initialize Pinecone searcher if configured
        pinecone_searcher = None
        pinecone_searcher = PineconeSearcher(
            index_name=pinecone_index,
            model_name=pinecone_model_name,
            cloud=pinecone_cloud,
            region=pinecone_region,
            api_key=pinecone_api_key,
            namespace=pinecone_namespace,
        )

        # Initialize pipeline
        pipeline = RagPipeline(
            docs=docs,
            pinecone_searcher=pinecone_searcher,
            max_tokens_chunk=300,
            overlap=80,
            ce_model="cross-encoder/ms-marco-MiniLM-L-6-v2",
        )
        return pipeline

    except Exception as e:
        st.error(f"Failed to initialize RAG pipeline: {str(e)}")
        return None


def query_rag_system(
    query: str,
    top_k: int = 5,
    top_retrieve: int = 30,
    use_reranking: bool = True,
    include_summary: bool = True,
    meta_filter: Optional[dict[str, Any]] = None,
    pipeline=None,
):
    """
    Query the RAG system with hybrid search and optional re-ranking.
    """
    if not pipeline:
        st.error("RAG pipeline is not available")
        return None

    try:
        # Retrieval + optional reranking
        if use_reranking:
            results = pipeline.retrieve_and_rerank(query, top_retrieve=top_retrieve, top_final=top_k)
        else:
            raw_results = pipeline.retrieve_with_metadata(query, top_k=top_k, meta_filter=meta_filter)
            results = [(doc_id, chunk, meta, 0.0) for doc_id, chunk, meta in raw_results]

        # Build contexts
        cited_context = pipeline.build_cited_context(results)
        summary_context = None
        if include_summary:
            try:
                summary_context = pipeline.build_summary_context(results)
            except Exception:
                # If summary fails (e.g., no OpenAI API key), continue without it
                pass

        # Format results for UI
        formatted_results = []
        for rank, (doc_id, chunk, meta, score) in enumerate(results, 1):
            formatted_results.append(
                {
                    "rank": rank,
                    "doc_id": doc_id,
                    "chunk": chunk,
                    "metadata": meta,
                    "score": score,
                    "citation": pipeline.format_citation(meta),
                }
            )

        return {
            "query": query,
            "results": formatted_results,
            "summary_context": summary_context,
            "cited_context": cited_context,
            "metadata": {
                "total_results": len(results),
                "retrieval_method": "hybrid" if pipeline.vec else "bm25_only",
                "reranking_used": use_reranking,
                "top_retrieve": top_retrieve,
                "top_k": top_k,
                "timestamp": datetime.now().isoformat(),
            },
        }

    except Exception as e:
        st.error(f"Error processing query: {str(e)}")
        return None


def get_system_status(pipeline=None):
    """
    Get comprehensive system status including corpus and indices.
    """
    try:
        corpus_path = corpus_dir()
        corpus_exists = corpus_path.exists()

        documents = []
        total_docs = 0
        total_chunks = 0

        if corpus_exists:
            try:
                from src.agents.rag_agent.rag.ingestion.pdf_loader import folder_pdfs_to_documents

                docs = folder_pdfs_to_documents(corpus_path, recursive=True)
                total_docs = len(docs)

                # Build document info preview
                for doc in docs[:10]:  # limit preview
                    text_preview = doc.text[:200] + "..." if len(doc.text) > 200 else doc.text
                    chunk_count = 0
                    if pipeline and hasattr(pipeline, "chunks_per_doc") and doc.id in pipeline.chunks_per_doc:
                        chunk_count = len(pipeline.chunks_per_doc[doc.id])

                    documents.append(
                        {
                            "doc_id": doc.id,
                            "source": doc.source,
                            "page": doc.page,
                            "text_preview": text_preview,
                            "chunk_count": chunk_count,
                        }
                    )

                if pipeline and hasattr(pipeline, "chunks_per_doc"):
                    total_chunks = sum(len(chunks) for chunks in pipeline.chunks_per_doc.values())

            except Exception as e:
                st.warning(f"Error loading documents: {str(e)}")

        # Index status
        bm25_ready = pipeline is not None
        vector_ready = pipeline is not None and pipeline.vec is not None

        vector_info = {}
        if vector_ready:
            try:
                vector_info = {
                    "vector_index_name": getattr(pipeline.vec, "index_name", None),
                    "vector_namespace": getattr(pipeline.vec, "namespace", None),
                    "total_vectors": None,  # would need Pinecone API call to get actual count
                }
            except:
                pass

        return {
            "status": "healthy" if (corpus_exists and total_docs > 0) else "warning",
            "corpus": {
                "total_documents": total_docs,
                "total_chunks": total_chunks,
                "corpus_path": str(corpus_path),
                "documents": documents,
            },
            "indices": {"bm25_ready": bm25_ready, "vector_ready": vector_ready, **vector_info},
            "config": {
                "project_root": str(project_dir()),
                "corpus_dir": str(corpus_path),
                "pipeline_initialized": pipeline is not None,
            },
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        st.error(f"Error getting system status: {str(e)}")
        return None


@st.cache_resource
def initilize_orchestator_agent() -> OrchestratorAgent:
    """
    Initialize and cache the Orchestrator Agent.
    """
    try:
        orchestrator_agent: OrchestratorAgent = OrchestratorAgent()
        asyncio.run(orchestrator_agent.initialize())
        return orchestrator_agent
    except Exception as e:
        st.error(f"Failed to initilize Orchestrator agent: {str(e)}")
        return None


@st.cache_resource
def initilize_rag_agent():
    """
    Initialize and cache the RAG Agent.
    """
    try:
        rag_agent: RAGAgent = RAGAgent()
        return rag_agent
    except Exception as e:
        st.error(f"Failed to initilize RAG agent: {str(e)}")
        return None


def ui_to_code_page():
    """UI-to-Code page for converting UI designs (image) to HTML/Tailwind."""
    st.header("🎨 UI to Code Generator")
    st.markdown("Upload a UI design image and convert it to clean HTML/Tailwind CSS code.")

    # Initialize agents
    orchestrator_agent = initilize_orchestator_agent()
    if not orchestrator_agent:
        st.error("Orchestrator agent is not available. Please check your configuration.")
        return

    rag_agent = initilize_rag_agent()
    if not rag_agent:
        st.error("RAG agent is not available. Please check your configuration.")
        return

    # Upload
    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded_file = st.file_uploader(
            "Upload UI Design Image",
            type=["png", "jpg", "jpeg", "webp"],
            help="Upload an image of your UI design to analyze and convert to code",
        )

    with col2:
        st.markdown("### Settings")
        top_k = st.slider("Similar patterns to use", 1, 10, 5, help="Number of similar HTML/CSS examples to retrieve")
        save_results = st.checkbox("Save generated code", value=True, help="Save the generated code to files")

        # Extra instructions
        st.markdown("### 💬 Additional Instructions")
        example_instructions = [
            "Use dark theme with purple accents and hover effects",
            "Make it fully responsive with mobile-first design",
            "Add subtle glassmorphism effects",
            "Include form validation states with error colors",
            "Create a minimalist layout with ample whitespace",
            "Add accessibility features and ARIA labels",
            "Create a card-based layout with shadows and rounded corners",
            "Add gradient backgrounds and smooth animations",
            "Use a modern color palette with high contrast",
            "Include loading states and micro-interactions",
        ]
        selected_example = st.selectbox(
            "Quick examples (optional)",
            [""] + example_instructions,
            help="Select a predefined instruction or write your own below",
        )
        custom_instructions = st.text_area(
            "Custom requirements (optional)",
            value=selected_example if selected_example else "",
            placeholder="E.g., 'Use dark theme', 'Add hover effects', 'Make responsive', 'Include form validation'...",
            help="Additional context or specific requirements",
        )

    if uploaded_file is not None:
        # Show image
        st.markdown("### 📷 Uploaded Design")
        st.image(uploaded_file, caption="Uploaded UI Design", use_container_width=True)

        # Save temp
        temp_dir = temp_images_dir()
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file_path = temp_dir / f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Analyze and generate
        if st.button("🚀 Analyze Design & Generate Code", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            try:
                # Step 1: Visual Analysis
                status_text.text("Step 1/3: Analyzing UI design...")
                progress_bar.progress(10)
                loop = asyncio.get_event_loop()
                with st.spinner("Analyzing design with AI vision model..."):
                    analysis_result = loop.run_until_complete(
                        orchestrator_agent.send_message_to_visual_agent(temp_file_path)
                    )
                progress_bar.progress(30)

                if "error" in analysis_result:
                    st.error(f"Visual analysis failed: {analysis_result['error']}")
                    return

                # Display analysis
                st.markdown("### 🔍 Visual Analysis Results")
                col1, col2, col3 = st.columns(3)
                with col1:
                    components = analysis_result.get("components", [])
                    st.markdown(f"**Components Found:** {len(components)}")
                    with st.expander("View Components"):
                        st.write(components)
                with col2:
                    layout = analysis_result.get("layout", "Unknown")
                    st.markdown(f"**Layout:** {layout}")
                with col3:
                    style = analysis_result.get("style", "Unknown")
                    st.markdown(f"**Style:** {style}")
                with st.expander("📋 Detailed Analysis"):
                    st.json(analysis_result)

                # Step 2: Pattern Retrieval
                status_text.text("Step 2/3: Finding similar HTML/CSS patterns...")
                progress_bar.progress(50)
                with st.spinner("Searching for similar code patterns..."):
                    patterns = rag_agent.invoke(analysis_result, top_k=top_k)
                progress_bar.progress(70)

                if patterns:
                    st.markdown(f"### 🔗 Found {len(patterns)} Similar Patterns")
                    for i, (doc_id, chunk, metadata, score) in enumerate(patterns, 1):
                        with st.expander(f"Pattern #{i} - {metadata.get('filename', 'Unknown')} (Score: {score:.3f})"):
                            st.markdown(f"**Type:** {metadata.get('type', 'Unknown')}")
                            st.markdown(f"**Description:** {metadata.get('description', 'No description')}")
                            st.code(chunk[:500] + ("..." if len(chunk) > 500 else ""), language="html")
                else:
                    st.warning("No similar patterns found. Will generate code from scratch.")

                # Step 3: Code Generation
                status_text.text("Step 3/3: Generating HTML/Tailwind CSS code...")
                progress_bar.progress(80)
                with st.spinner("Generating clean HTML/Tailwind CSS code..."):
                    code_result = loop.run_until_complete(
                        orchestrator_agent.send_message_to_code_agent(
                            patterns, analysis_result, custom_instructions=custom_instructions
                        )
                    )
                progress_bar.progress(100)
                status_text.text("✅ Code generation complete!")

                # Show generated code
                generated_code = code_result.get("html_code", "")
                st.markdown("### 💻 Generated HTML/CSS Code")
                if generated_code:
                    st.code(generated_code, language="html")

                    # Save artifacts
                    if save_results and generated_code:
                        try:
                            saved_path = save_generated_code(code_result)
                            st.success(f"✅ Code saved to: {saved_path}")
                            analysis_path = save_analysis_result(analysis_result)
                            st.info(f"📊 Analysis saved to: {analysis_path}")
                        except Exception as e:
                            st.warning(f"Could not save files: {str(e)}")

                    if custom_instructions.strip():
                        with st.expander("💬 Custom Instructions Used"):
                            st.write(custom_instructions.strip())

                    with st.expander("🛠️ Generation Details"):
                        metadata = code_result.get("generation_metadata", {})
                        st.json(metadata)

                    st.markdown("### 🌐 Code Preview")
                    st.info("💡 Copy the code above and paste it into an HTML file to preview.")
                else:
                    st.error("No code was generated.")

            except Exception as e:
                st.error(f"An error occurred during processing: {str(e)}")
                st.info("Try again or check the uploaded image.")
                st.exception(e)
            finally:
                # Cleanup temp file
                try:
                    if temp_file_path.exists():
                        temp_file_path.unlink()
                except:
                    pass

    # RAG System Status (for UI-to-Code)
    with st.expander("🔧 UI-to-Code System Status"):
        rag_status = rag_agent.get_rag_status() if rag_agent else None
        if rag_status:
            st.json(rag_status)
        else:
            st.error("RAG agent not available")


# ------------------------------- MAIN APP ------------------------------- #


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Multi-Agent UI-to-Code System",
        page_icon="🎨",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("🎨 Multi-Agent UI-to-Code System")
    st.markdown("Convert UI designs to clean HTML/Tailwind CSS code using AI vision, RAG, and prompt-to-HTML.")

    # Initialize RAG pipeline (only needed for RAG search)
    pipeline = get_rag_pipeline()

    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page", ["Query Interface", "UI to Code", "System Status", "Corpus Information"]
    )

    # -------------------------- QUERY INTERFACE -------------------------- #
    if page == "Query Interface":
        st.header("🔎 Query Interface")

        # Choose mode
        mode = st.radio(
            "Mode",
            ["RAG Search", "Prompt → HTML"],
            horizontal=True,
            help="RAG Search = query your corpus. Prompt → HTML = generate UI code from a natural-language prompt.",
        )

        # Layout
        col1, col2 = st.columns([3, 1])
        with col1:
            query = st.text_area(
                "Enter your query or UI prompt:",
                placeholder="• RAG Search: ask about your documents.\n• Prompt → HTML: describe the UI you want (e.g., 'dark dashboard with sidebar, cards, and a header').",
                height=120,
            )

        with col2:
            st.markdown("### Settings")
            if mode == "RAG Search":
                top_k = st.slider("Top results to show", 1, 20, 5)
                top_retrieve = st.slider("Candidates to retrieve", 10, 100, 30)
                use_reranking = st.checkbox("Use re-ranking", value=True)
                include_summary = st.checkbox("Include summary", value=True)
                prompt_custom_instructions = ""  # keep var defined for later reference
                save_results_prompt = False
            else:
                # Prompt → HTML options
                prompt_custom_instructions = st.text_area(
                    "Custom instructions (optional)",
                    placeholder="e.g., Use Tailwind, glassmorphism, add hover states, mobile-first…",
                    height=120,
                )
                save_results_prompt = st.checkbox("Save generated code", value=True)

        btn_label = "🚀 Search" if mode == "RAG Search" else "🚀 Generate from Prompt"
        btn_disabled = (not query or not query.strip()) or (mode == "RAG Search" and not pipeline)

        if st.button(btn_label, disabled=btn_disabled):
            # --- RAG SEARCH MODE --- #
            if mode == "RAG Search":
                if not pipeline:
                    st.error("RAG pipeline is not available. Please check your configuration.")
                else:
                    with st.spinner("Searching..."):
                        response = query_rag_system(
                            query=query.strip(),
                            top_k=top_k,
                            top_retrieve=top_retrieve,
                            use_reranking=use_reranking,
                            include_summary=include_summary,
                            pipeline=pipeline,
                        )

                    if response:
                        st.markdown("### Query Information")
                        metadata = response["metadata"]
                        c1, c2, c3, c4 = st.columns(4)
                        with c1:
                            st.metric("Total Results", metadata["total_results"])
                        with c2:
                            st.metric("Retrieval Method", metadata["retrieval_method"])
                        with c3:
                            st.metric("Re-ranking", "Yes" if metadata["reranking_used"] else "No")
                        with c4:
                            st.metric("Retrieved Candidates", metadata["top_retrieve"])

                        if response["summary_context"]:
                            st.markdown("### 📝 Summary Context")
                            st.info(response["summary_context"])

                        st.markdown("### 📚 Cited Context")
                        st.text_area("", response["cited_context"], height=200)

                        st.markdown("### 🔍 Search Results")
                        for result in response["results"]:
                            with st.expander(
                                f"Result #{result['rank']} - {result['citation']} (Score: {result['score']:.4f})"
                            ):
                                st.markdown(f"**Document ID:** `{result['doc_id']}`")
                                st.markdown(f"**Source:** {result['metadata'].get('source', 'Unknown')}")
                                if result["metadata"].get("page"):
                                    st.markdown(f"**Page:** {result['metadata']['page']}")
                                st.markdown("**Content:**")
                                st.text(result["chunk"])
                                if result["metadata"]:
                                    with st.expander("Metadata"):
                                        st.json(result["metadata"])

            # --- PROMPT → HTML MODE --- #
            else:
                orchestrator_agent = initilize_orchestator_agent()
                if not orchestrator_agent:
                    st.error("Orchestrator agent is not available. Please check your configuration.")
                else:
                    with st.spinner("Generating clean HTML/Tailwind CSS from your prompt..."):
                        loop = asyncio.get_event_loop()
                        code_result = loop.run_until_complete(
                            orchestrator_agent.send_prompt_to_code_agent(
                                prompt_text=query.strip(),
                                patterns=[],  # optional: plug in RAG-derived patterns if desired
                                custom_instructions=prompt_custom_instructions.strip(),
                            )
                        )

                    if "error" in code_result and not code_result.get("html_code"):
                        st.error(f"Code generation failed: {code_result['error']}")
                    else:
                        html_code = code_result.get("html_code", "")
                        st.markdown("### 💻 Generated HTML/Tailwind Code")
                        st.code(html_code or "<!-- empty -->", language="html")

                        with st.expander("🛠️ Generation Details"):
                            st.json(code_result.get("generation_metadata", {}))
                            st.json(code_result.get("visual_analysis_summary", {}))

                        if html_code and save_results_prompt:
                            try:
                                saved_path = save_generated_code(code_result)
                                st.success(f"✅ Code saved to: {saved_path}")
                            except Exception as e:
                                st.warning(f"Could not save files: {e}")

                        st.markdown("### 🌐 Preview")
                        st.info("Copy the code above into an .html file to preview in your browser.")

    # ---------------------------- UI TO CODE PAGE ---------------------------- #
    elif page == "UI to Code":
        ui_to_code_page()

    # ------------------------------ SYSTEM STATUS --------------------------- #
    elif page == "System Status":
        st.header("⚙️ System Status")

        if st.button("🔄 Refresh Status"):
            st.cache_resource.clear()
            st.rerun()

        status = get_system_status(pipeline)
        if status:
            status_color = "🟢" if status["status"] == "healthy" else "🟡"
            st.markdown(f"## {status_color} System Status: {status['status'].upper()}")

            st.markdown("### 📚 Corpus Status")
            corpus = status["corpus"]
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Total Documents", corpus["total_documents"])
            with c2:
                st.metric("Total Chunks", corpus["total_chunks"])
            with c3:
                path_str = corpus["corpus_path"]
                st.metric(
                    "Corpus Path",
                    path_str if len(path_str) < 30 else f"...{path_str[-27:]}",
                )

            st.markdown("### 🔗 Index Status")
            indices = status["indices"]
            c1, c2 = st.columns(2)
            with c1:
                bm25_status = "🟢 Ready" if indices["bm25_ready"] else "🔴 Not Ready"
                st.markdown(f"**BM25 Index:** {bm25_status}")
            with c2:
                vector_status = "🟢 Ready" if indices["vector_ready"] else "🔴 Not Ready"
                st.markdown(f"**Vector Index:** {vector_status}")

            if indices.get("vector_index_name"):
                st.markdown(f"**Vector Index Name:** {indices['vector_index_name']}")
            if indices.get("vector_namespace"):
                st.markdown(f"**Vector Namespace:** {indices['vector_namespace']}")

            st.markdown("### ⚙️ Configuration")
            config = status["config"]
            st.json(config)

    # ---------------------------- CORPUS INFORMATION ------------------------ #
    elif page == "Corpus Information":
        st.header("📚 Corpus Information")

        status = get_system_status(pipeline)
        if status and status["corpus"]["documents"]:
            corpus = status["corpus"]

            st.markdown("### Summary")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Total Documents", corpus["total_documents"])
            with c2:
                st.metric("Total Chunks", corpus["total_chunks"])
            with c3:
                avg_chunks = corpus["total_chunks"] / corpus["total_documents"] if corpus["total_documents"] > 0 else 0
                st.metric("Avg Chunks per Doc", f"{avg_chunks:.1f}")

            st.markdown("### Document Details")
            for i, doc in enumerate(corpus["documents"]):
                with st.expander(f"Document {i+1}: {Path(doc['source']).name}"):
                    st.markdown(f"**Document ID:** `{doc['doc_id']}`")
                    st.markdown(f"**Source:** {doc['source']}")
                    if doc.get("page"):
                        st.markdown(f"**Page:** {doc['page']}")
                    st.markdown(f"**Chunks:** {doc['chunk_count']}")
                    st.markdown("**Preview:**")
                    st.text(doc["text_preview"])
        else:
            st.warning("No documents found in corpus or system not initialized.")
            if status:
                st.markdown(f"**Corpus Path:** {status['corpus']['corpus_path']}")


if __name__ == "__main__":
    main()
