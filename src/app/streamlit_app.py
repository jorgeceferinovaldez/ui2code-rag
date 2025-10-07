import streamlit as st
import sys, os, asyncio
from pathlib import Path
import nest_asyncio
from datetime import datetime
from typing import Optional, Any
from PIL import Image
from loguru import logger

from src.agents.orchestator_agent.utils import save_analysis_result, save_generated_code
from src.config import (
    corpus_dir,
    project_dir,
    temp_images_dir,
    pinecone_index,
    pinecone_cloud,
    pinecone_region,
    pinecone_api_key,
    pinecone_namespace,
    st_model_name,
)
from src.agents.rag_agent.rag_agent import RAGAgent
from src.agents.orchestator_agent.orchestator_agent import OrchestratorAgent

nest_asyncio.apply()


@st.cache_resource
def get_rag_pipeline():
    """
    Initialize and cache the RAG pipeline for PDF corpus (if available).
    Note: This is for general document search. HTML/CSS patterns use RAGAgent instead.
    Returns the pipeline instance, initializing it if needed, or None if no PDFs found.
    """
    try:
        from src.agents.rag_agent.rag.adapters.pinecone_adapter import PineconeSearcher
        from src.agents.rag_agent.rag.core.rag_pipeline import RagPipeline
        from src.agents.rag_agent.rag.ingestion.pdf_loader import folder_pdfs_to_documents

        # Load documents from corpus
        docs = folder_pdfs_to_documents(corpus_dir(), recursive=True)
        if not docs:
            # This is OK - HTML patterns are handled by RAGAgent separately
            return None

        # Initialize Pinecone searcher if configured
        pinecone_searcher = None
        if pinecone_api_key:
            pinecone_searcher = PineconeSearcher(
                index_name=pinecone_index,
                model_name=st_model_name,
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
        logger.warning(f"RAG pipeline initialization error: {str(e)}")
        # Don't show error - PDF corpus is optional
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

    # Show corpus status
    rag_agent_test = initilize_rag_agent()
    if rag_agent_test:
        rag_status = rag_agent_test.get_rag_status()
        if rag_status.get('status') == 'ready':
            total_docs = rag_status.get('total_documents', 0)
            total_chunks = rag_status.get('total_chunks', 0)
            st.success(f"✅ HTML/CSS Pattern Corpus: {total_docs} documents ({total_chunks} code patterns) ready from WebSight dataset")
        else:
            st.warning("⚠️ HTML/CSS pattern corpus not fully initialized. Some features may be limited.")
    else:
        st.warning("⚠️ RAG Agent not available. Pattern-based code generation may be limited.")

    # Initialize RAG pipeline (only needed for PDF RAG search - optional)
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
            ["RAG Search (HTML Patterns)", "Prompt → HTML"],
            ["RAG Search (HTML Patterns)", "Prompt → HTML"],
            horizontal=True,
            help="RAG Search = query HTML/CSS patterns from WebSight. Prompt → HTML = generate UI code from a natural-language prompt.",
            help="RAG Search = query HTML/CSS patterns from WebSight. Prompt → HTML = generate UI code from a natural-language prompt.",
        )

        # Layout
        col1, col2 = st.columns([3, 1])
        with col1:
            query = st.text_area(
                "Enter your query or UI prompt:",
                placeholder="• RAG Search: describe UI components (e.g., 'dashboard with sidebar and cards').\n• Prompt → HTML: describe the UI you want (e.g., 'dark dashboard with sidebar, cards, and a header').",
                placeholder="• RAG Search: describe UI components (e.g., 'dashboard with sidebar and cards').\n• Prompt → HTML: describe the UI you want (e.g., 'dark dashboard with sidebar, cards, and a header').",
                height=120,
            )

        with col2:
            st.markdown("### Settings")
            if mode == "RAG Search (HTML Patterns)":
                top_k = st.slider("Top results to show", 1, 10, 5)
            if mode == "RAG Search (HTML Patterns)":
                top_k = st.slider("Top results to show", 1, 10, 5)
                prompt_custom_instructions = ""   # keep var defined for later reference
                save_results_prompt = False
            else:
                # Prompt → HTML options
                prompt_custom_instructions = st.text_area(
                    "Custom instructions (optional)",
                    placeholder="e.g., Use Tailwind, glassmorphism, add hover states, mobile-first…",
                    height=120,
                )
                save_results_prompt = st.checkbox("Save generated code", value=True)

        btn_label = "🚀 Search HTML Patterns" if mode == "RAG Search (HTML Patterns)" else "🚀 Generate from Prompt"
        btn_disabled = (not query or not query.strip())
        btn_label = "🚀 Search HTML Patterns" if mode == "RAG Search (HTML Patterns)" else "🚀 Generate from Prompt"
        btn_disabled = (not query or not query.strip())

        if st.button(btn_label, disabled=btn_disabled):
            # --- RAG SEARCH MODE (HTML PATTERNS) --- #
            if mode == "RAG Search (HTML Patterns)":
                # Initialize RAG agent for HTML patterns
                rag_agent = initilize_rag_agent()
                if not rag_agent:
                    st.error("RAG agent is not available. Please check your configuration.")
            # --- RAG SEARCH MODE (HTML PATTERNS) --- #
            if mode == "RAG Search (HTML Patterns)":
                # Initialize RAG agent for HTML patterns
                rag_agent = initilize_rag_agent()
                if not rag_agent:
                    st.error("RAG agent is not available. Please check your configuration.")
                else:
                    with st.spinner("Searching HTML/CSS patterns..."):
                        # Create a simple visual analysis from the query
                        visual_analysis = {
                            'analysis_text': query.strip(),
                            'components': [],
                            'layout': 'unknown',
                            'style': 'modern'
                        }

                        # Use RAG agent to search patterns
                        patterns = rag_agent.invoke(visual_analysis, top_k=top_k)

                    if patterns:
                        st.markdown(f"### 🔍 Found {len(patterns)} Similar HTML/CSS Patterns")

                        for i, (doc_id, chunk, metadata, score) in enumerate(patterns, 1):
                    with st.spinner("Searching HTML/CSS patterns..."):
                        # Create a simple visual analysis from the query
                        visual_analysis = {
                            'analysis_text': query.strip(),
                            'components': [],
                            'layout': 'unknown',
                            'style': 'modern'
                        }

                        # Use RAG agent to search patterns
                        patterns = rag_agent.invoke(visual_analysis, top_k=top_k)

                    if patterns:
                        st.markdown(f"### 🔍 Found {len(patterns)} Similar HTML/CSS Patterns")

                        for i, (doc_id, chunk, metadata, score) in enumerate(patterns, 1):
                            with st.expander(
                                f"Pattern #{i} - {metadata.get('filename', doc_id)} (Relevance: {score:.3f})"
                                f"Pattern #{i} - {metadata.get('filename', doc_id)} (Relevance: {score:.3f})"
                            ):
                                st.markdown(f"**Document ID:** `{doc_id}`")
                                st.markdown(f"**Type:** {metadata.get('doc_type', 'Unknown')}")
                                st.markdown(f"**Description:** {metadata.get('description', 'No description')}")

                                # Show HTML code if available
                                html_code = metadata.get('html_code', chunk)
                                if html_code:
                                    st.markdown("**HTML Code:**")
                                    st.code(html_code[:1500] + ("..." if len(html_code) > 1500 else ""), language="html")
                                else:
                                    st.markdown("**Content:**")
                                    st.text(chunk)

                                if metadata:
                                    with st.expander("📋 Full Metadata"):
                                        # Don't show html_code in JSON (too long)
                                        meta_display = {k: v for k, v in metadata.items() if k != 'html_code'}
                                        meta_display['html_code_length'] = len(html_code) if html_code else 0
                                        st.json(meta_display)
                    else:
                        st.warning("No patterns found. Try a different query.")
                                st.markdown(f"**Document ID:** `{doc_id}`")
                                st.markdown(f"**Type:** {metadata.get('doc_type', 'Unknown')}")
                                st.markdown(f"**Description:** {metadata.get('description', 'No description')}")

                                # Show HTML code if available
                                html_code = metadata.get('html_code', chunk)
                                if html_code:
                                    st.markdown("**HTML Code:**")
                                    st.code(html_code[:1500] + ("..." if len(html_code) > 1500 else ""), language="html")
                                else:
                                    st.markdown("**Content:**")
                                    st.text(chunk)

                                if metadata:
                                    with st.expander("📋 Full Metadata"):
                                        # Don't show html_code in JSON (too long)
                                        meta_display = {k: v for k, v in metadata.items() if k != 'html_code'}
                                        meta_display['html_code_length'] = len(html_code) if html_code else 0
                                        st.json(meta_display)
                    else:
                        st.warning("No patterns found. Try a different query.")

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

        # Get RAG Agent status (HTML/CSS patterns - the actual corpus)
        rag_agent = initilize_rag_agent()
        if rag_agent:
            rag_status = rag_agent.get_rag_status()

            # Determine overall system status
            is_healthy = (rag_status.get('status') == 'ready' and
                         rag_status.get('total_documents', 0) > 0)
            status_color = "🟢" if is_healthy else "🟡"
            status_text = "HEALTHY" if is_healthy else "WARNING"

            st.markdown(f"## {status_color} System Status: {status_text}")
        # Get RAG Agent status (HTML/CSS patterns - the actual corpus)
        rag_agent = initilize_rag_agent()
        if rag_agent:
            rag_status = rag_agent.get_rag_status()

            # Determine overall system status
            is_healthy = (rag_status.get('status') == 'ready' and
                         rag_status.get('total_documents', 0) > 0)
            status_color = "🟢" if is_healthy else "🟡"
            status_text = "HEALTHY" if is_healthy else "WARNING"

            st.markdown(f"## {status_color} System Status: {status_text}")

            # HTML/CSS Pattern Corpus Status
            st.markdown("### 📚 HTML/CSS Pattern Corpus Status")
            c1, c2, c3, c4 = st.columns(4)
            # HTML/CSS Pattern Corpus Status
            st.markdown("### 📚 HTML/CSS Pattern Corpus Status")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("HTML Documents", rag_status.get('total_documents', 0))
                st.metric("HTML Documents", rag_status.get('total_documents', 0))
            with c2:
                st.metric("Code Patterns", rag_status.get('total_chunks', 0))
                st.metric("Code Patterns", rag_status.get('total_chunks', 0))
            with c3:
                vector_status = "🟢 Ready" if rag_status.get('vector_search_available') else "🔴 Not Ready"
                st.metric("Vector Search", vector_status)
            with c4:
                bm25_status = "🟢 Ready" if rag_status.get('bm25_search_available') else "🔴 Not Ready"
                st.metric("BM25 Search", bm25_status)

            # Corpus location
            examples_dir = rag_status.get('examples_directory', 'Unknown')
            st.code(f"Corpus Path: {examples_dir}", language="bash")

            # Index Details
            st.markdown("### 🔗 Search Index Details")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**BM25 Index (Keyword Search)**")
                if rag_status.get('bm25_search_available'):
                    st.success("✅ Active - Fast keyword-based retrieval")
                    st.info(f"📊 Indexed: {rag_status.get('total_chunks', 0)} code patterns")
                else:
                    st.error("❌ Not available")

            with col2:
                st.markdown("**Vector Index (Semantic Search)**")
                if rag_status.get('vector_search_available'):
                    st.success("✅ Active - Pinecone semantic search")
                    import os
                    pinecone_index = os.getenv("PINECONE_INDEX", "rag-index")
                    st.info(f"📦 Index: `{pinecone_index}`")
                    st.info(f"🏷️ Namespace: `html-css-examples`")
                    st.info(f"🔢 Vectors: {rag_status.get('total_chunks', 0)}")
                else:
                    st.error("❌ Not available - Check PINECONE_API_KEY")

            # Agents Status
            st.markdown("### 🤖 Agents Status")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("**Visual Agent**")
                try:
                    # Check if visual agent is accessible via A2A agent-card endpoint
                    import httpx
                    from src.config import visual_agent_url
                    try:
                        response = httpx.get(f"{visual_agent_url}/.well-known/agent-card.json", timeout=2.0)
                        if response.status_code == 200:
                            st.success("✅ Running")
                            st.info(f"🌐 URL: {visual_agent_url}")
                        else:
                            st.warning(f"⚠️ Response: {response.status_code}")
                    except:
                        st.error("❌ Not reachable")
                        st.info(f"🌐 URL: {visual_agent_url}")
                except Exception as e:
                    st.error("❌ Error checking status")

            with col2:
                st.markdown("**Code Agent**")
                try:
                    from src.config import code_agent_url
                    try:
                        response = httpx.get(f"{code_agent_url}/.well-known/agent-card.json", timeout=2.0)
                        if response.status_code == 200:
                            st.success("✅ Running")
                            st.info(f"🌐 URL: {code_agent_url}")
                        else:
                            st.warning(f"⚠️ Response: {response.status_code}")
                    except:
                        st.error("❌ Not reachable")
                        st.info(f"🌐 URL: {code_agent_url}")
                except Exception as e:
                    st.error("❌ Error checking status")

            with col3:
                st.markdown("**RAG Agent**")
                if rag_agent and rag_status.get('status') == 'ready':
                    st.success("✅ Ready")
                    st.info(f"📚 {rag_status.get('total_documents', 0)} docs loaded")
                else:
                    st.error("❌ Not initialized")

            # Configuration
                vector_status = "🟢 Ready" if rag_status.get('vector_search_available') else "🔴 Not Ready"
                st.metric("Vector Search", vector_status)
            with c4:
                bm25_status = "🟢 Ready" if rag_status.get('bm25_search_available') else "🔴 Not Ready"
                st.metric("BM25 Search", bm25_status)

            # Corpus location
            examples_dir = rag_status.get('examples_directory', 'Unknown')
            st.code(f"Corpus Path: {examples_dir}", language="bash")

            # Index Details
            st.markdown("### 🔗 Search Index Details")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**BM25 Index (Keyword Search)**")
                if rag_status.get('bm25_search_available'):
                    st.success("✅ Active - Fast keyword-based retrieval")
                    st.info(f"📊 Indexed: {rag_status.get('total_chunks', 0)} code patterns")
                else:
                    st.error("❌ Not available")

            with col2:
                st.markdown("**Vector Index (Semantic Search)**")
                if rag_status.get('vector_search_available'):
                    st.success("✅ Active - Pinecone semantic search")
                    import os
                    pinecone_index = os.getenv("PINECONE_INDEX", "rag-index")
                    st.info(f"📦 Index: `{pinecone_index}`")
                    st.info(f"🏷️ Namespace: `html-css-examples`")
                    st.info(f"🔢 Vectors: {rag_status.get('total_chunks', 0)}")
                else:
                    st.error("❌ Not available - Check PINECONE_API_KEY")

            # Agents Status
            st.markdown("### 🤖 Agents Status")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("**Visual Agent**")
                try:
                    # Check if visual agent is accessible via A2A agent-card endpoint
                    import httpx
                    from src.config import visual_agent_url
                    try:
                        response = httpx.get(f"{visual_agent_url}/.well-known/agent-card.json", timeout=2.0)
                        if response.status_code == 200:
                            st.success("✅ Running")
                            st.info(f"🌐 URL: {visual_agent_url}")
                        else:
                            st.warning(f"⚠️ Response: {response.status_code}")
                    except:
                        st.error("❌ Not reachable")
                        st.info(f"🌐 URL: {visual_agent_url}")
                except Exception as e:
                    st.error("❌ Error checking status")

            with col2:
                st.markdown("**Code Agent**")
                try:
                    from src.config import code_agent_url
                    try:
                        response = httpx.get(f"{code_agent_url}/.well-known/agent-card.json", timeout=2.0)
                        if response.status_code == 200:
                            st.success("✅ Running")
                            st.info(f"🌐 URL: {code_agent_url}")
                        else:
                            st.warning(f"⚠️ Response: {response.status_code}")
                    except:
                        st.error("❌ Not reachable")
                        st.info(f"🌐 URL: {code_agent_url}")
                except Exception as e:
                    st.error("❌ Error checking status")

            with col3:
                st.markdown("**RAG Agent**")
                if rag_agent and rag_status.get('status') == 'ready':
                    st.success("✅ Ready")
                    st.info(f"📚 {rag_status.get('total_documents', 0)} docs loaded")
                else:
                    st.error("❌ Not initialized")

            # Configuration
            st.markdown("### ⚙️ Configuration")
            config_info = {
                "project_root": str(project_dir()),
                "websight_data_dir": str(project_dir() / "data" / "websight"),
                "html_patterns_dir": examples_dir,
                "rag_agent_initialized": rag_agent is not None,
                "total_html_patterns": rag_status.get('total_documents', 0),
                "pinecone_configured": rag_status.get('vector_search_available', False),
            }
            st.json(config_info)

            # Optional: Show PDF corpus status if available
            status = get_system_status(pipeline)
            if status and status["corpus"]["total_documents"] > 0:
                st.markdown("---")
                st.markdown("### 📄 Additional PDF Corpus (Optional)")
                st.info("Legacy PDF corpus for general knowledge retrieval (not used for HTML generation)")
                corpus = status["corpus"]
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("PDF Documents", corpus["total_documents"])
                with col2:
                    st.metric("PDF Chunks", corpus["total_chunks"])
        else:
            st.error("❌ RAG Agent not available. Please restart the application.")
            config_info = {
                "project_root": str(project_dir()),
                "websight_data_dir": str(project_dir() / "data" / "websight"),
                "html_patterns_dir": examples_dir,
                "rag_agent_initialized": rag_agent is not None,
                "total_html_patterns": rag_status.get('total_documents', 0),
                "pinecone_configured": rag_status.get('vector_search_available', False),
            }
            st.json(config_info)

            # Optional: Show PDF corpus status if available
            status = get_system_status(pipeline)
            if status and status["corpus"]["total_documents"] > 0:
                st.markdown("---")
                st.markdown("### 📄 Additional PDF Corpus (Optional)")
                st.info("Legacy PDF corpus for general knowledge retrieval (not used for HTML generation)")
                corpus = status["corpus"]
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("PDF Documents", corpus["total_documents"])
                with col2:
                    st.metric("PDF Chunks", corpus["total_chunks"])
        else:
            st.error("❌ RAG Agent not available. Please restart the application.")

    # ---------------------------- CORPUS INFORMATION ------------------------ #
    elif page == "Corpus Information":
        st.header("📚 HTML/CSS Pattern Corpus Information")
        st.markdown("Information about the WebSight dataset used for pattern-based code generation.")

        # Add refresh button to clear cache
        if st.button("🔄 Refresh Corpus Information"):
            st.cache_resource.clear()
            st.rerun()

        # Get RAG Agent status (HTML patterns)
        rag_agent = initilize_rag_agent()
        if rag_agent:
            rag_status = rag_agent.get_rag_status()

            if rag_status.get('status') == 'ready':
                st.markdown("### 📊 Corpus Summary")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("HTML Documents", rag_status.get('total_documents', 0))
                with c2:
                    st.metric("Code Patterns", rag_status.get('total_chunks', 0))
                with c3:
                    vector_available = "✅ Yes" if rag_status.get('vector_search_available') else "❌ No"
                    st.metric("Vector Search (Pinecone)", vector_available)
                with c4:
                    bm25_available = "✅ Yes" if rag_status.get('bm25_search_available') else "❌ No"
                    st.metric("BM25 Search", bm25_available)

                # Show Pinecone details if available
                if rag_status.get('vector_search_available'):
                    st.markdown("### 🔗 Vector Search Details")
                    import os
                    pinecone_index = os.getenv("PINECONE_INDEX", "rag-index")
                    pinecone_namespace = "html-css-examples"

                    col1, col2 = st.columns(2)
                    with col1:
                        st.code(f"Index: {pinecone_index}", language="text")
                        st.code(f"Namespace: {pinecone_namespace}", language="text")
                    with col2:
                        st.code(f"Vectors: {rag_status.get('total_chunks', 0)}", language="text")
                        st.code(f"Model: sentence-transformers/all-MiniLM-L6-v2", language="text")

                    st.info("💡 Vector search uses Pinecone for fast semantic similarity search across all HTML patterns.")

                st.markdown("### 📁 Corpus Location")
                st.code(rag_status.get('examples_directory', 'Unknown'), language="bash")

                st.markdown("### 🔍 Pattern Types")
                st.markdown("""
                The corpus contains HTML/CSS examples from the WebSight dataset covering:
                - **Landing pages** - Hero sections, CTAs, features
                - **Dashboards** - Sidebars, stat cards, data tables
                - **Navigation** - Headers, menus, breadcrumbs
                - **Forms** - Input fields, validation, layouts
                - **Cards & Components** - Reusable UI patterns
                - **Responsive layouts** - Mobile-first designs
                """)

                # Show WebSight data location
                st.markdown("### 📦 Source Data")
                websight_dir = project_dir() / "data" / "websight"
                st.markdown(f"**WebSight JSON files:** `{websight_dir}`")

                # Count JSON files
                try:
                    import json
                    json_files = list(websight_dir.glob("websight_*.json"))
                    total_rows = 0
                    valid_files = 0
                    for json_file in json_files:
                        try:
                            with open(json_file, 'r') as f:
                                data = json.load(f)
                                rows = len(data.get('rows', []))
                                if rows > 0:
                                    total_rows += rows
                                    valid_files += 1
                        except:
                            pass

                    st.markdown(f"- **JSON files:** {len(json_files)} total ({valid_files} valid)")
                    st.markdown(f"- **Total HTML examples:** ~{total_rows} available")
                    st.markdown(f"- **Currently loaded:** {rag_status.get('total_documents', 0)} documents")
                except Exception as e:
                    st.warning(f"Could not read WebSight directory: {e}")

                st.markdown("### 🎯 Usage")
                st.info("""
                This corpus is automatically used when:
                1. **UI to Code**: Upload an image → Visual analysis → RAG retrieves similar patterns → Code generated
                2. **RAG Search**: Search for HTML patterns by description
                3. **Prompt → HTML**: Describe UI → RAG finds similar examples → Code generated
                """)
            else:
                st.error("RAG system not ready. Please check system status.")
                st.json(rag_status)
        else:
            st.error("RAG Agent not available. Please restart the application.")

        # Optional: Show PDF corpus info if available
        st.header("📚 HTML/CSS Pattern Corpus Information")
        st.markdown("Information about the WebSight dataset used for pattern-based code generation.")

        # Add refresh button to clear cache
        if st.button("🔄 Refresh Corpus Information"):
            st.cache_resource.clear()
            st.rerun()

        # Get RAG Agent status (HTML patterns)
        rag_agent = initilize_rag_agent()
        if rag_agent:
            rag_status = rag_agent.get_rag_status()

            if rag_status.get('status') == 'ready':
                st.markdown("### 📊 Corpus Summary")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("HTML Documents", rag_status.get('total_documents', 0))
                with c2:
                    st.metric("Code Patterns", rag_status.get('total_chunks', 0))
                with c3:
                    vector_available = "✅ Yes" if rag_status.get('vector_search_available') else "❌ No"
                    st.metric("Vector Search (Pinecone)", vector_available)
                with c4:
                    bm25_available = "✅ Yes" if rag_status.get('bm25_search_available') else "❌ No"
                    st.metric("BM25 Search", bm25_available)

                # Show Pinecone details if available
                if rag_status.get('vector_search_available'):
                    st.markdown("### 🔗 Vector Search Details")
                    import os
                    pinecone_index = os.getenv("PINECONE_INDEX", "rag-index")
                    pinecone_namespace = "html-css-examples"

                    col1, col2 = st.columns(2)
                    with col1:
                        st.code(f"Index: {pinecone_index}", language="text")
                        st.code(f"Namespace: {pinecone_namespace}", language="text")
                    with col2:
                        st.code(f"Vectors: {rag_status.get('total_chunks', 0)}", language="text")
                        st.code(f"Model: sentence-transformers/all-MiniLM-L6-v2", language="text")

                    st.info("💡 Vector search uses Pinecone for fast semantic similarity search across all HTML patterns.")

                st.markdown("### 📁 Corpus Location")
                st.code(rag_status.get('examples_directory', 'Unknown'), language="bash")

                st.markdown("### 🔍 Pattern Types")
                st.markdown("""
                The corpus contains HTML/CSS examples from the WebSight dataset covering:
                - **Landing pages** - Hero sections, CTAs, features
                - **Dashboards** - Sidebars, stat cards, data tables
                - **Navigation** - Headers, menus, breadcrumbs
                - **Forms** - Input fields, validation, layouts
                - **Cards & Components** - Reusable UI patterns
                - **Responsive layouts** - Mobile-first designs
                """)

                # Show WebSight data location
                st.markdown("### 📦 Source Data")
                websight_dir = project_dir() / "data" / "websight"
                st.markdown(f"**WebSight JSON files:** `{websight_dir}`")

                # Count JSON files
                try:
                    import json
                    json_files = list(websight_dir.glob("websight_*.json"))
                    total_rows = 0
                    valid_files = 0
                    for json_file in json_files:
                        try:
                            with open(json_file, 'r') as f:
                                data = json.load(f)
                                rows = len(data.get('rows', []))
                                if rows > 0:
                                    total_rows += rows
                                    valid_files += 1
                        except:
                            pass

                    st.markdown(f"- **JSON files:** {len(json_files)} total ({valid_files} valid)")
                    st.markdown(f"- **Total HTML examples:** ~{total_rows} available")
                    st.markdown(f"- **Currently loaded:** {rag_status.get('total_documents', 0)} documents")
                except Exception as e:
                    st.warning(f"Could not read WebSight directory: {e}")

                st.markdown("### 🎯 Usage")
                st.info("""
                This corpus is automatically used when:
                1. **UI to Code**: Upload an image → Visual analysis → RAG retrieves similar patterns → Code generated
                2. **RAG Search**: Search for HTML patterns by description
                3. **Prompt → HTML**: Describe UI → RAG finds similar examples → Code generated
                """)
            else:
                st.error("RAG system not ready. Please check system status.")
                st.json(rag_status)
        else:
            st.error("RAG Agent not available. Please restart the application.")

        # Optional: Show PDF corpus info if available
        status = get_system_status(pipeline)
        if status and status["corpus"]["documents"]:
            st.markdown("---")
            st.markdown("### 📄 PDF Corpus (Optional)")
            st.info("Additional PDF documents can be added to the corpus for general knowledge retrieval.")
            st.markdown("---")
            st.markdown("### 📄 PDF Corpus (Optional)")
            st.info("Additional PDF documents can be added to the corpus for general knowledge retrieval.")
            corpus = status["corpus"]
            st.markdown(f"**PDF Documents:** {corpus['total_documents']}")
            st.markdown(f"**Total Chunks:** {corpus['total_chunks']}")
            st.markdown(f"**PDF Documents:** {corpus['total_documents']}")
            st.markdown(f"**Total Chunks:** {corpus['total_chunks']}")


if __name__ == "__main__":
    main()
