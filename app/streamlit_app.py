"""
Streamlit App for RAG System
Provides a web interface for RAG queries, corpus management, and system status
"""

import streamlit as st
import sys
from pathlib import Path
import os
import asyncio
import nest_asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from PIL import Image


# Add src to Python path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))


from src.agents import rag_agent
from src.agents.code_agent.code_agent_mock import CodeAgentMock
from src.agents.orchestator_agent.utils import save_analysis_result, save_generated_code
from src.config import corpus_dir, project_dir, temp_images_dir

from src.agents.code_agent.code_rag_agent import CodeAgent
from src.agents.rag_agent.rag_agent import RAGAgent
from src.agents.orchestator_agent.orchestator_agent import OrchestratorAgent

nest_asyncio.apply()


@st.cache_resource
def get_rag_pipeline():
    """
    Initialize and cache RAG pipeline
    Returns the pipeline instance, initializing it if needed
    """
    try:
        # Import here to avoid circular imports and load time issues
        from dotenv import load_dotenv
        from src.rag.core.rag_pipeline import RagPipeline
        from src.rag.ingestion.pdf_loader import folder_pdfs_to_documents
        from src.runtime.adapters.pinecone_adapter import PineconeSearcher

        # Load environment variables
        env_path = project_dir() / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)

        # Load documents from corpus
        docs = folder_pdfs_to_documents(corpus_dir(), recursive=True)
        if not docs:
            st.error("No documents found in corpus directory")
            return None

        # Initialize Pinecone searcher if configured
        pinecone_searcher = None
        if os.getenv("PINECONE_API_KEY"):
            pinecone_searcher = PineconeSearcher(
                index_name=os.getenv("PINECONE_INDEX", "rag-index"),
                model_name=os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
                cloud=os.getenv("PINECONE_CLOUD", "aws"),
                region=os.getenv("PINECONE_REGION", "us-east-1"),
                api_key=os.getenv("PINECONE_API_KEY"),
                namespace=os.getenv("PINECONE_NAMESPACE", "default"),
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
    meta_filter: Optional[Dict[str, Any]] = None,
    pipeline=None,
):
    """
    Query the RAG system with hybrid search and optional re-ranking
    """
    if not pipeline:
        st.error("RAG pipeline is not available")
        return None

    try:
        # Perform retrieval and re-ranking
        if use_reranking:
            results = pipeline.retrieve_and_rerank(query, top_retrieve=top_retrieve, top_final=top_k)
        else:
            # Get results without re-ranking
            raw_results = pipeline.retrieve_with_metadata(query, top_k=top_k, meta_filter=meta_filter)
            # Convert to expected format (add dummy score)
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

        # Format results for response
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
    Get comprehensive system status including corpus and indices
    """
    try:
        # Check corpus status
        corpus_path = corpus_dir()
        corpus_exists = corpus_path.exists()

        documents = []
        total_docs = 0
        total_chunks = 0

        if corpus_exists:
            try:
                from src.rag.ingestion.pdf_loader import folder_pdfs_to_documents

                docs = folder_pdfs_to_documents(corpus_path, recursive=True)
                total_docs = len(docs)

                # Create document info
                for doc in docs[:10]:  # Limit to first 10 for preview
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

                # Get total chunks if pipeline is available
                if pipeline and hasattr(pipeline, "chunks_per_doc"):
                    total_chunks = sum(len(chunks) for chunks in pipeline.chunks_per_doc.values())

            except Exception as e:
                st.warning(f"Error loading documents: {str(e)}")

        # Check index status
        bm25_ready = pipeline is not None
        vector_ready = pipeline is not None and pipeline.vec is not None

        vector_info = {}
        if vector_ready:
            try:
                vector_info = {
                    "vector_index_name": getattr(pipeline.vec, "index_name", None),
                    "vector_namespace": getattr(pipeline.vec, "namespace", None),
                    "total_vectors": None,  # Would need Pinecone API call to get actual count
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
    Initialize and cache UI-to-Code agents
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
    Initialize and cache RAG agent
    """
    try:
        rag_agent: RAGAgent = RAGAgent()
        return rag_agent

    except Exception as e:
        st.error(f"Failed to initilize RAG agent: {str(e)}")
        return None


def ui_to_code_page():
    """UI-to-Code page for converting UI designs to HTML/CSS"""
    st.header("🎨 UI to Code Generator")
    st.markdown("Upload a UI design image and convert it to clean HTML/Tailwind CSS code")

    # Initialize agents
    orchestrator_agent = initilize_orchestator_agent()
    if not orchestrator_agent:
        st.error("Orchestrator agent is not available. Please check your configuration.")
        return
    rag_agent = initilize_rag_agent()
    if not rag_agent:
        st.error("RAG agent is not available. Please check your configuration.")
        return

    # File upload section
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

        # Additional text input for customization
        st.markdown("### 💬 Additional Instructions")

        # Quick examples (bilingual)
        example_instructions = [
            # Spanish examples
            "Usar tema oscuro con acentos púrpura y efectos hover",
            "Hacer completamente responsive con diseño mobile-first",
            "Agregar efectos glassmorphism con desenfoques sutiles",
            "Incluir estados de validación para formularios con colores de error",
            "Crear diseño minimalista con mucho espacio en blanco",
            "Añadir características de accesibilidad y etiquetas ARIA",
            # English examples
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
            placeholder="Ej: 'Usar tema oscuro', 'Agregar efectos hover', 'Hacer responsive', 'Incluir validación de formularios'...",
            help="Proporciona contexto adicional o requerimientos específicos para la generación de código (español o inglés)",
        )

    if uploaded_file is not None:
        # Display uploaded image
        st.markdown("### 📷 Uploaded Design")
        st.image(uploaded_file, caption="Uploaded UI Design", use_container_width=True)

        # Save uploaded file temporarily
        temp_dir = temp_images_dir()
        temp_dir.mkdir(parents=True, exist_ok=True)

        temp_file_path = temp_dir / f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"

        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Analysis button
        if st.button("🚀 Analyze Design & Generate Code", type="primary"):

            # Progress tracking
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

                # Display analysis results
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

                # Show full analysis in expandable section
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
                status_text.text("Step 3/3: Generating HTML/CSS code...")
                progress_bar.progress(80)

                loop = asyncio.get_event_loop()
                with st.spinner("Generating clean HTML/Tailwind CSS code..."):
                    code_result = loop.run_until_complete(
                        orchestrator_agent.send_message_to_code_agent(
                            patterns, analysis_result, custom_instructions=custom_instructions
                        )
                    )

                progress_bar.progress(100)
                status_text.text("✅ Code generation complete!")

                if "error" in code_result:
                    st.error(f"Code generation failed: {code_result['error']}")
                    generated_code = code_result.get("html_code", "")
                else:
                    generated_code = code_result.get("html_code", "")

                # Display generated code
                st.markdown("### 💻 Generated HTML/CSS Code")

                if generated_code:
                    # Code display with copy button
                    st.code(generated_code, language="html")

                    # Save results if requested
                    if save_results and generated_code:
                        try:
                            saved_path = save_generated_code(code_result)
                            st.success(f"✅ Code saved to: {saved_path}")

                            # Also save analysis
                            analysis_path = save_analysis_result(analysis_result)
                            st.info(f"📊 Analysis saved to: {analysis_path}")

                        except Exception as e:
                            st.warning(f"Could not save files: {str(e)}")

                    # Show custom instructions used if any
                    if custom_instructions.strip():
                        with st.expander("💬 Custom Instructions Used"):
                            st.write(custom_instructions.strip())

                    # Generation metadata
                    with st.expander("🛠️ Generation Details"):
                        metadata = code_result.get("generation_metadata", {})
                        st.json(metadata)

                    # Preview section (if we want to add HTML rendering)
                    st.markdown("### 🌐 Code Preview")
                    st.info("💡 Copy the code above and paste it into an HTML file to see the result!")

                else:
                    st.error("No code was generated.")

            except Exception as e:
                st.error(f"An error occurred during processing: {str(e)}")
                st.exception(e)
            finally:
                # Cleanup temp file
                try:
                    if temp_file_path.exists():
                        temp_file_path.unlink()
                except:
                    pass

    # RAG System Status for UI-to-Code
    with st.expander("🔧 UI-to-Code System Status"):
        if rag_agent:
            rag_status = rag_agent.get_rag_status()
            st.json(rag_status)
        else:
            st.error("RAG agent not available")


def main():
    """Main Streamlit application"""

    # Page configuration
    st.set_page_config(
        page_title="Multi-Agent UI-to-Code System", page_icon="🎨", layout="wide", initial_sidebar_state="expanded"
    )

    # Title and description
    st.title("🎨 Multi-Agent UI-to-Code System")
    st.markdown("Convert UI designs to clean HTML/Tailwind CSS code using AI vision and RAG technology")

    # Initialize pipeline
    pipeline = get_rag_pipeline()

    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page", ["Query Interface", "UI to Code", "System Status", "Corpus Information"]
    )

    if page == "Query Interface":
        st.header("🔎 Query Interface")

        # Query input section
        col1, col2 = st.columns([3, 1])

        with col1:
            query = st.text_area(
                "Enter your query:", placeholder="Ask a question about the documents in your corpus...", height=100
            )

        with col2:
            st.markdown("### Settings")
            top_k = st.slider("Top results to show", 1, 20, 5)
            top_retrieve = st.slider("Candidates to retrieve", 10, 100, 30)
            use_reranking = st.checkbox("Use re-ranking", value=True)
            include_summary = st.checkbox("Include summary", value=True)

        # Query button
        if st.button("🚀 Search", disabled=not query or not pipeline):
            if not pipeline:
                st.error("RAG pipeline is not available. Please check your configuration.")
            elif not query.strip():
                st.warning("Please enter a query.")
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
                        # Display query metadata
                        st.markdown("### Query Information")
                        metadata = response["metadata"]
                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            st.metric("Total Results", metadata["total_results"])
                        with col2:
                            st.metric("Retrieval Method", metadata["retrieval_method"])
                        with col3:
                            st.metric("Re-ranking", "Yes" if metadata["reranking_used"] else "No")
                        with col4:
                            st.metric("Retrieved Candidates", metadata["top_retrieve"])

                        # Display summary context if available
                        if response["summary_context"]:
                            st.markdown("### 📝 Summary Context")
                            st.info(response["summary_context"])

                        # Display cited context
                        st.markdown("### 📚 Cited Context")
                        st.text_area("", response["cited_context"], height=200)

                        # Display individual results
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

                                # Show metadata if available
                                if result["metadata"]:
                                    with st.expander("Metadata"):
                                        st.json(result["metadata"])

    elif page == "UI to Code":
        ui_to_code_page()

    elif page == "System Status":
        st.header("⚙️ System Status")

        if st.button("🔄 Refresh Status"):
            st.cache_resource.clear()
            st.rerun()

        status = get_system_status(pipeline)

        if status:
            # Overall status
            status_color = "🟢" if status["status"] == "healthy" else "🟡"
            st.markdown(f"## {status_color} System Status: {status['status'].upper()}")

            # Corpus information
            st.markdown("### 📚 Corpus Status")
            corpus = status["corpus"]

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Documents", corpus["total_documents"])
            with col2:
                st.metric("Total Chunks", corpus["total_chunks"])
            with col3:
                st.metric(
                    "Corpus Path",
                    corpus["corpus_path"] if len(corpus["corpus_path"]) < 30 else f"...{corpus['corpus_path'][-27:]}",
                )

            # Index status
            st.markdown("### 🔗 Index Status")
            indices = status["indices"]

            col1, col2 = st.columns(2)
            with col1:
                bm25_status = "🟢 Ready" if indices["bm25_ready"] else "🔴 Not Ready"
                st.markdown(f"**BM25 Index:** {bm25_status}")
            with col2:
                vector_status = "🟢 Ready" if indices["vector_ready"] else "🔴 Not Ready"
                st.markdown(f"**Vector Index:** {vector_status}")

            if indices.get("vector_index_name"):
                st.markdown(f"**Vector Index Name:** {indices['vector_index_name']}")
            if indices.get("vector_namespace"):
                st.markdown(f"**Vector Namespace:** {indices['vector_namespace']}")

            # Configuration
            st.markdown("### ⚙️ Configuration")
            config = status["config"]
            st.json(config)

    elif page == "Corpus Information":
        st.header("📚 Corpus Information")

        status = get_system_status(pipeline)

        if status and status["corpus"]["documents"]:
            corpus = status["corpus"]

            # Summary metrics
            st.markdown("### Summary")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Documents", corpus["total_documents"])
            with col2:
                st.metric("Total Chunks", corpus["total_chunks"])
            with col3:
                avg_chunks = corpus["total_chunks"] / corpus["total_documents"] if corpus["total_documents"] > 0 else 0
                st.metric("Avg Chunks per Doc", f"{avg_chunks:.1f}")

            # Document list
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
