"""
Code RAG Agent for HTML/CSS Code Generation
Wraps the existing RAG pipeline to work with HTML/CSS examples and generates code
"""

import os
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import openai

from src.config import project_dir, generated_code_dir, ui_examples_dir
from src.rag.core.rag_pipeline import RagPipeline
from src.rag.core.documents import Document

from src.core.style_tokens import tokens_to_tailwind_config, build_allowed
from src.core.html_utils import extract_tw_classes, inject_tailwind_inline_config
from src.core.tw_validator import validate_classes, strip_md_fences


class CodeRAGAgent:
    """
    Agent responsible for retrieving similar HTML/CSS patterns and generating code
    """
    
    def __init__(self):
        """Initialize the Code RAG Agent"""
        # Load environment variables
        from dotenv import load_dotenv
        env_path = project_dir() / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
        
        # Configure OpenRouter client for code generation
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        
        if openrouter_api_key:
            self.client = openai.OpenAI(
                base_url=openrouter_base_url,
                api_key=openrouter_api_key
            )
            self.code_model = os.getenv("CODE_MODEL", "deepseek/deepseek-coder")
            self.use_openrouter = True
        else:
            # Fallback to OpenAI if available
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                self.client = openai.OpenAI(api_key=openai_key)
                self.code_model = "gpt-4"
                self.use_openrouter = False
            else:
                raise ValueError("Neither OPENROUTER_API_KEY nor OPENAI_API_KEY found in environment")
        
        # Initialize RAG pipeline
        self.rag_pipeline = None
        self._initialize_rag_pipeline()
    
    def _write_tailwind_config(self, style_tokens: dict):
        cfg = tokens_to_tailwind_config(style_tokens or {})
        out_dir = generated_code_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "tailwind.config.js").write_text(cfg, encoding="utf-8")

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
                        namespace="html-css-examples"  # Separate namespace for HTML/CSS
                    )
                except Exception as e:
                    print(f"Warning: Could not initialize Pinecone: {e}")
            
            # Initialize RAG pipeline
            self.rag_pipeline = RagPipeline(
                docs=html_examples,
                pinecone_searcher=pinecone_searcher,
                max_tokens_chunk=400,  # Slightly larger chunks for HTML/CSS
                overlap=100,
                ce_model="cross-encoder/ms-marco-MiniLM-L-6-v2"
            )
            
            print(f"RAG pipeline initialized with {len(html_examples)} HTML/CSS examples")
            
        except Exception as e:
            print(f"Error initializing RAG pipeline: {e}")
            self.rag_pipeline = None
    
    def _load_html_examples(self) -> List[Document]:
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
                    with open(html_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Create document (no metadata parameter in Document class)
                    doc = Document(
                        id=html_file.stem,  # Use filename without extension as ID
                        text=content,
                        source=str(html_file)
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
    
    def _create_sample_examples(self, examples_dir):
        """Create sample HTML/CSS examples for testing"""
        
        sample_examples = [
            {
                "filename": "landing_page.html",
                "content": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Modern Landing Page</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <header class="bg-white shadow-sm">
        <nav class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between items-center h-16">
                <div class="flex-shrink-0">
                    <h1 class="text-2xl font-bold text-gray-900">Brand</h1>
                </div>
                <div class="hidden md:flex space-x-8">
                    <a href="#" class="text-gray-600 hover:text-gray-900">Home</a>
                    <a href="#" class="text-gray-600 hover:text-gray-900">About</a>
                    <a href="#" class="text-gray-600 hover:text-gray-900">Services</a>
                    <a href="#" class="text-gray-600 hover:text-gray-900">Contact</a>
                </div>
                <button class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
                    Get Started
                </button>
            </div>
        </nav>
    </header>
    
    <main>
        <section class="bg-white">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24">
                <div class="text-center">
                    <h1 class="text-4xl font-extrabold text-gray-900 sm:text-5xl md:text-6xl">
                        Welcome to our platform
                    </h1>
                    <p class="mt-3 max-w-md mx-auto text-base text-gray-500 sm:text-lg md:mt-5 md:text-xl md:max-w-3xl">
                        Build amazing products with our modern tools and services
                    </p>
                    <div class="mt-5 max-w-md mx-auto sm:flex sm:justify-center md:mt-8">
                        <div class="rounded-md shadow">
                            <button class="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 md:py-4 md:text-lg md:px-10">
                                Start Free Trial
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    </main>
</body>
</html>"""
            },
            {
                "filename": "contact_form.html",
                "content": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contact Form</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100">
    <div class="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
        <div class="max-w-md w-full space-y-8">
            <div>
                <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900">
                    Contact Us
                </h2>
                <p class="mt-2 text-center text-sm text-gray-600">
                    Get in touch with our team
                </p>
            </div>
            <form class="mt-8 space-y-6">
                <div class="rounded-md shadow-sm -space-y-px">
                    <div>
                        <label for="name" class="sr-only">Name</label>
                        <input id="name" name="name" type="text" required 
                               class="relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-blue-500 focus:border-blue-500" 
                               placeholder="Your Name">
                    </div>
                    <div>
                        <label for="email" class="sr-only">Email</label>
                        <input id="email" name="email" type="email" required 
                               class="relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500" 
                               placeholder="Email Address">
                    </div>
                    <div>
                        <label for="message" class="sr-only">Message</label>
                        <textarea id="message" name="message" rows="4" required 
                                  class="relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-blue-500 focus:border-blue-500" 
                                  placeholder="Your Message"></textarea>
                    </div>
                </div>
                
                <div>
                    <button type="submit" 
                            class="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                        Send Message
                    </button>
                </div>
            </form>
        </div>
    </div>
</body>
</html>"""
            },
            {
                "filename": "dashboard_card.html",
                "content": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Cards</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <div class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            
            <!-- Stats Card -->
            <div class="bg-white overflow-hidden shadow rounded-lg">
                <div class="p-5">
                    <div class="flex items-center">
                        <div class="flex-shrink-0">
                            <div class="w-8 h-8 bg-blue-500 rounded-md flex items-center justify-center">
                                <span class="text-white text-sm font-medium">$</span>
                            </div>
                        </div>
                        <div class="ml-5 w-0 flex-1">
                            <dl>
                                <dt class="text-sm font-medium text-gray-500 truncate">
                                    Total Revenue
                                </dt>
                                <dd class="text-lg font-medium text-gray-900">
                                    $45,231
                                </dd>
                            </dl>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Users Card -->
            <div class="bg-white overflow-hidden shadow rounded-lg">
                <div class="p-5">
                    <div class="flex items-center">
                        <div class="flex-shrink-0">
                            <div class="w-8 h-8 bg-green-500 rounded-md flex items-center justify-center">
                                <span class="text-white text-sm font-medium">U</span>
                            </div>
                        </div>
                        <div class="ml-5 w-0 flex-1">
                            <dl>
                                <dt class="text-sm font-medium text-gray-500 truncate">
                                    Active Users
                                </dt>
                                <dd class="text-lg font-medium text-gray-900">
                                    1,234
                                </dd>
                            </dl>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Orders Card -->
            <div class="bg-white overflow-hidden shadow rounded-lg">
                <div class="p-5">
                    <div class="flex items-center">
                        <div class="flex-shrink-0">
                            <div class="w-8 h-8 bg-purple-500 rounded-md flex items-center justify-center">
                                <span class="text-white text-sm font-medium">O</span>
                            </div>
                        </div>
                        <div class="ml-5 w-0 flex-1">
                            <dl>
                                <dt class="text-sm font-medium text-gray-500 truncate">
                                    Orders
                                </dt>
                                <dd class="text-lg font-medium text-gray-900">
                                    567
                                </dd>
                            </dl>
                        </div>
                    </div>
                </div>
            </div>
            
        </div>
    </div>
</body>
</html>"""
            }
        ]
        
        for example in sample_examples:
            file_path = examples_dir / example["filename"]
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(example["content"])
    
    def retrieve_patterns(self, visual_analysis: Dict[str, Any], top_k: int = 5) -> List[Tuple]:
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
                top_final=top_k   # Return top_k final results
            )
            
            return results
            
        except Exception as e:
            print(f"Error retrieving patterns: {e}")
            return []
    
    def generate_code(self, patterns, visual_analysis, custom_instructions: str = "") -> Dict[str, Any]:
        try:
            # 1) contexto de patrones + clases observadas
            pattern_context = self._format_patterns_for_generation(patterns)
            retrieved_classes = set()
            for _, chunk, _, _ in (patterns or []):
                retrieved_classes |= extract_tw_classes(chunk)

            # 2) tokens y config Tailwind
            style_tokens = visual_analysis.get("style_tokens", {}) or {}
            self._write_tailwind_config(style_tokens)
            allowed = build_allowed(style_tokens, retrieved_classes)

            # 3) prompt con whitelist
            prompt = self._get_generation_prompt(
                visual_analysis, pattern_context, custom_instructions, allowed
            )

            # 4) generación estricta
            response = self.client.chat.completions.create(
                model=self.code_model,
                messages=[
                    {"role": "system", "content": "Eres un desarrollador experto en HTML con Tailwind. SOLO usas clases permitidas."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.0,
                top_p=0.2,
                **({"seed": 42} if self.use_openrouter else {})  # si el gateway soporta seed
            )

            generated_code = response.choices[0].message.content
            cleaned_code = strip_md_fences(generated_code).strip()

            # 5) validar clases
            bad = validate_classes(cleaned_code, allowed)
            if bad:
                cleaned_code = self._repair(cleaned_code, bad, allowed)
                bad = validate_classes(cleaned_code, allowed)  # segunda pasada

            # 6) (opcional CDN) inyectar tailwind.config inline en <head>
            cleaned_code = inject_tailwind_inline_config(cleaned_code, style_tokens)

            # 7) métrica simple
            total_classes = len(extract_tw_classes(cleaned_code)) or 1
            shr = round((len(bad) / total_classes) * 100, 2) if bad else 0.0

            return {
                "html_code": cleaned_code,
                "generation_metadata": {
                    "model_used": self.code_model,
                    "patterns_used": len(patterns or []),
                    "visual_components": visual_analysis.get("components", []),
                    "custom_instructions": custom_instructions.strip() if custom_instructions else "",
                    "style_hallucination_rate_pct": shr,
                    "timestamp": datetime.now().isoformat()
                },
                "visual_analysis_summary": {
                    "components": visual_analysis.get("components", []),
                    "layout": visual_analysis.get("layout", "unknown"),
                    "style": visual_analysis.get("style", "modern")
                }
            }

        except Exception as e:
            return {
                "error": f"Code generation failed: {str(e)}",
                "html_code": self._get_fallback_html(),
                "generation_metadata": {
                    "model_used": self.code_model,
                    "custom_instructions": custom_instructions.strip() if custom_instructions else "",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            }
    
    
    def _repair(self, html: str, bad: list[str], allowed: set[str]) -> str:
        repair_prompt = f"""
    Reemplaza únicamente estas clases inválidas {bad} por alternativas válidas de ESTA LISTA:
    {sorted(list(allowed))}
    No agregues clases nuevas. Devuelve SOLO el HTML reparado.
    ---
    HTML:
    {html}
    """
        r = self.client.chat.completions.create(
            model=self.code_model,
            messages=[
                {"role": "system", "content": "Reparador de Tailwind estricto."},
                {"role": "user", "content": repair_prompt}
            ],
            max_tokens=1800,
            temperature=0.0,
            top_p=0.2,
            **({"seed": 42} if self.use_openrouter else {})
        )
        fixed = strip_md_fences(r.choices[0].message.content).strip()
        return fixed


    def _format_patterns_for_generation(self, patterns: List[Tuple]) -> str:
        """Format retrieved patterns for code generation prompt"""
        if not patterns:
            return "No similar patterns found."
        
        formatted_patterns = []
        for i, (doc_id, chunk, metadata, score) in enumerate(patterns, 1):
            # Handle both dict metadata and document attributes
            source_name = "unknown"
            if isinstance(metadata, dict):
                source_name = metadata.get('filename', metadata.get('source', 'unknown'))
            else:
                source_name = getattr(metadata, 'filename', getattr(metadata, 'source', 'unknown'))
            
            formatted_patterns.append(f"""
Example {i} (similarity: {score:.3f}):
Source: {source_name}
```html
{chunk}
```
            """)
        
        return "\n".join(formatted_patterns)
    
    def _get_generation_prompt(self, visual_analysis: Dict[str, Any], pattern_context: str,
                           custom_instructions: str, allowed_classes: set) -> str:
        components = visual_analysis.get("components", [])
        layout = visual_analysis.get("layout", "modern layout")
        style = visual_analysis.get("style", "clean and modern")
        color_scheme = visual_analysis.get("color_scheme", "neutral colors")

        allowed_list = "\n".join(sorted(list(allowed_classes))[:600])  # cap to avoid long ctx

        base_prompt = f"""Basándote en este análisis visual:
    - Componentes identificados: {', '.join(components)}
    - Layout: {layout}
    - Estilo: {style}
    - Esquema de colores: {color_scheme}

    Y estos ejemplos similares encontrados:
    {pattern_context}

    REGLAS ESTRICTAS:
    - Usa EXCLUSIVAMENTE estas clases Tailwind (whitelist):
    {allowed_list}
    - No inventes clases ni CSS inline.
    - Si una clase no existe en la lista, reemplázala por la opción semánticamente más cercana de la lista.
    - HTML semántico, responsive (mobile-first), sin JavaScript, con accesibilidad básica (alt/labels).
    - Responde SOLO con el HTML (sin bloques markdown, ni explicaciones).
    """
        if custom_instructions and custom_instructions.strip():
            base_prompt += f"\nINSTRUCCIONES ADICIONALES:\n{custom_instructions.strip()}\n"
        return base_prompt

    def _clean_generated_code(self, code: str) -> str:
        """Clean up generated code"""
        # Remove markdown code blocks if present
        if "```html" in code:
            start = code.find("```html") + 7
            end = code.find("```", start)
            if end != -1:
                code = code[start:end]
        elif "```" in code:
            start = code.find("```") + 3
            end = code.find("```", start)
            if end != -1:
                code = code[start:end]
        
        # Basic cleanup
        code = code.strip()
        
        return code
    
    def _get_fallback_html(self) -> str:
        """Get fallback HTML when generation fails"""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated UI</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <div class="min-h-screen flex items-center justify-center">
        <div class="max-w-md mx-auto bg-white rounded-lg shadow-md p-6">
            <h1 class="text-2xl font-bold text-gray-900 mb-4">UI Component</h1>
            <p class="text-gray-600 mb-4">Generated based on your design analysis.</p>
            <button class="w-full bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
                Action Button
            </button>
        </div>
    </div>
</body>
</html>"""
    
    def save_generated_code(self, code_result: Dict[str, Any], filename: str = None) -> str:
        """
        Save generated code to file
        
        Args:
            code_result: Generated code result
            filename: Optional filename
            
        Returns:
            Path to saved file
        """
        try:
            # Ensure output directory exists
            output_dir = generated_code_dir()
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename if not provided
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"generated_{timestamp}.html"
            
            if not filename.endswith('.html'):
                filename += '.html'
            
            # Save HTML file
            output_path = output_dir / filename
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(code_result.get("html_code", ""))
            
            # Save metadata
            metadata_path = output_path.with_suffix('.json')
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "generation_metadata": code_result.get("generation_metadata", {}),
                    "visual_analysis_summary": code_result.get("visual_analysis_summary", {}),
                    "html_file": filename,
                    "created_at": datetime.now().isoformat()
                }, f, indent=2)
            
            return str(output_path)
            
        except Exception as e:
            raise ValueError(f"Failed to save generated code: {str(e)}")
    
    def get_rag_status(self) -> Dict[str, Any]:
        """Get status of the RAG pipeline"""
        if not self.rag_pipeline:
            return {
                "status": "not_initialized",
                "message": "RAG pipeline is not initialized"
            }
        
        try:
            total_docs = len(self.rag_pipeline.docs) if hasattr(self.rag_pipeline, 'docs') else 0
            total_chunks = sum(len(chunks) for chunks in self.rag_pipeline.chunks_per_doc.values()) if hasattr(self.rag_pipeline, 'chunks_per_doc') else 0
            
            return {
                "status": "ready",
                "total_documents": total_docs,
                "total_chunks": total_chunks,
                "vector_search_available": self.rag_pipeline.vec is not None,
                "bm25_search_available": self.rag_pipeline.bm25 is not None,
                "examples_directory": str(ui_examples_dir())
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error getting RAG status: {str(e)}"
            }