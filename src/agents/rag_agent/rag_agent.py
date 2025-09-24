"""RAG Agent for retrieving HTML/CSS examples based on visual analysis."""

import os
from typing import Any
from src.config import ui_examples_dir
from src.rag.core.rag_pipeline import RagPipeline
from src.rag.core.documents import Document


class RAGAgent:
    def __init__(self):
        self.rag_pipeline = None
        self._initialize_rag_pipeline()

    def _initialize_rag_pipeline(self):
        """Initialize RAG pipeline with HTML/CSS examples"""
        try:
            # Load HTML/CSS examples
            html_examples = self._load_html_examples()

            if not html_examples:
                print("Warning: No HTML/CSS examples found. RAG pipeline will not be available.")
                return

            # Initialize Pinecone searcher if configured (optional)
            pinecone_searcher = None
            if os.getenv("PINECONE_API_KEY"):
                try:
                    from src.runtime.adapters.pinecone_adapter import PineconeSearcher

                    pinecone_searcher = PineconeSearcher(
                        index_name=os.getenv("PINECONE_INDEX", "rag-index"),
                        model_name=os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
                        cloud=os.getenv("PINECONE_CLOUD", "aws"),
                        region=os.getenv("PINECONE_REGION", "us-east-1"),
                        api_key=os.getenv("PINECONE_API_KEY"),
                        namespace="html-css-examples",  # Separate namespace for HTML/CSS
                    )
                except Exception as e:
                    print(f"Warning: Could not initialize Pinecone: {e}")

            # Initialize RAG pipeline
            self.rag_pipeline = RagPipeline(
                docs=html_examples,
                pinecone_searcher=pinecone_searcher,
                max_tokens_chunk=400,  # Slightly larger chunks for HTML/CSS
                overlap=100,
                ce_model="cross-encoder/ms-marco-MiniLM-L-6-v2",
            )

            print(f"RAG pipeline initialized with {len(html_examples)} HTML/CSS examples")

        except Exception as e:
            print(f"Error initializing RAG pipeline: {e}")
            self.rag_pipeline = None

    def _load_html_examples(self) -> list[Document]:
        """
        Load HTML/CSS examples from the ui_examples directory
        This will be expanded to load from WebSight dataset
        """
        documents = []

        try:
            examples_dir = ui_examples_dir()

            # Check if examples directory exists
            if not examples_dir.exists():
                print(f"Creating examples directory: {examples_dir}")
                examples_dir.mkdir(parents=True, exist_ok=True)

                # Create some sample HTML/CSS examples
                self._create_sample_examples(examples_dir)

            # Load HTML files
            html_files = list(examples_dir.glob("**/*.html"))

            for html_file in html_files:
                try:
                    with open(html_file, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Create document (no metadata parameter in Document class)
                    doc = Document(
                        id=html_file.stem, text=content, source=str(html_file)  # Use filename without extension as ID
                    )

                    # Add additional attributes
                    doc.doc_type = "html_example"
                    doc.filename = html_file.name
                    doc.html_code = content
                    doc.file_size = len(content)
                    documents.append(doc)

                except Exception as e:
                    print(f"Error loading {html_file}: {e}")

            print(f"Loaded {len(documents)} HTML examples")
            return documents

        except Exception as e:
            print(f"Error loading HTML examples: {e}")
            return []

    def invoke(self, visual_analysis: dict[str, Any], top_k: int = 5) -> list[tuple]:
        """
        Retrieve similar HTML/CSS patterns based on visual analysis

        Args:
            visual_analysis: Analysis result from VisualAgent
            top_k: Number of top patterns to retrieve

        Returns:
            List of tuples (doc_id, chunk, metadata, score)
        """
        if not self.rag_pipeline:
            return []

        try:
            # Extract analysis text for RAG search
            analysis_text = visual_analysis.get("analysis_text", "")

            if not analysis_text:
                # Fallback: construct analysis text from components
                components = visual_analysis.get("components", [])
                layout = visual_analysis.get("layout", "")
                style = visual_analysis.get("style", "")

                analysis_text = f"UI components: {', '.join(components)}. Layout: {layout}. Style: {style}"

            # Use RAG pipeline to retrieve similar patterns
            results = self.rag_pipeline.retrieve_and_rerank(
                query=analysis_text,
                top_retrieve=20,  # Retrieve more candidates
                top_final=top_k,  # Return top_k final results
            )

            return results

        except Exception as e:
            print(f"Error retrieving patterns: {e}")
            return []

    def get_rag_status(self) -> dict[str, Any]:
        """Get status of the RAG pipeline"""
        if not self.rag_pipeline:
            return {"status": "not_initialized", "message": "RAG pipeline is not initialized"}

        try:
            total_docs = len(self.rag_pipeline.docs) if hasattr(self.rag_pipeline, "docs") else 0
            total_chunks = (
                sum(len(chunks) for chunks in self.rag_pipeline.chunks_per_doc.values())
                if hasattr(self.rag_pipeline, "chunks_per_doc")
                else 0
            )

            return {
                "status": "ready",
                "total_documents": total_docs,
                "total_chunks": total_chunks,
                "vector_search_available": self.rag_pipeline.vec is not None,
                "bm25_search_available": self.rag_pipeline.bm25 is not None,
                "examples_directory": str(ui_examples_dir()),
            }

        except Exception as e:
            return {"status": "error", "message": f"Error getting RAG status: {str(e)}"}
