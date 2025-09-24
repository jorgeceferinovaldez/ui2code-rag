"""
Code RAG Agent for HTML/CSS Code Generation
Wraps the existing RAG pipeline to work with HTML/CSS examples and generates code
"""

import os
from typing import Any
from datetime import datetime
import openai
from src.config import project_dir, ui_examples_dir


class CodeAgent:
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
            self.client = openai.OpenAI(base_url=openrouter_base_url, api_key=openrouter_api_key)
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
</html>""",
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
</html>""",
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
</html>""",
            },
        ]

        for example in sample_examples:
            file_path = examples_dir / example["filename"]
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(example["content"])

    def invoke(
        self, patterns: list[tuple], visual_analysis: dict[str, Any], custom_instructions: str = ""
    ) -> dict[str, Any]:
        """
        Generate HTML/CSS code based on patterns and visual analysis

        Args:
            patterns: Retrieved similar patterns
            visual_analysis: Visual analysis from VisualAgent
            custom_instructions: Additional user requirements and customizations

        Returns:
            Generated code and metadata
        """
        try:
            # Prepare context from retrieved patterns
            pattern_context = self._format_patterns_for_generation(patterns)

            # Create generation prompt
            prompt = self._get_generation_prompt(visual_analysis, pattern_context, custom_instructions)

            # Generate code using language model
            response = self.client.chat.completions.create(
                model=self.code_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert HTML/CSS developer specializing in modern, clean, artisanal web design.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
                temperature=0.1,
            )

            generated_code = response.choices[0].message.content

            # Clean up the generated code
            cleaned_code = self._clean_generated_code(generated_code)

            return {
                "html_code": cleaned_code,
                "generation_metadata": {
                    "model_used": self.code_model,
                    "patterns_used": len(patterns),
                    "visual_components": visual_analysis.get("components", []),
                    "custom_instructions": custom_instructions.strip() if custom_instructions else "",
                    "timestamp": datetime.now().isoformat(),
                },
                "visual_analysis_summary": {
                    "components": visual_analysis.get("components", []),
                    "layout": visual_analysis.get("layout", "unknown"),
                    "style": visual_analysis.get("style", "modern"),
                },
            }

        except Exception as e:
            return {
                "error": f"Code generation failed: {str(e)}",
                "html_code": self._get_fallback_html(),
                "generation_metadata": {
                    "model_used": self.code_model,
                    "custom_instructions": custom_instructions.strip() if custom_instructions else "",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                },
            }

    def _format_patterns_for_generation(self, patterns: list[tuple]) -> str:
        """Format retrieved patterns for code generation prompt"""
        if not patterns:
            return "No similar patterns found."

        formatted_patterns = []
        for i, (doc_id, chunk, metadata, score) in enumerate(patterns, 1):
            # Handle both dict metadata and document attributes
            source_name = "unknown"
            if isinstance(metadata, dict):
                source_name = metadata.get("filename", metadata.get("source", "unknown"))
            else:
                source_name = getattr(metadata, "filename", getattr(metadata, "source", "unknown"))

            formatted_patterns.append(
                f"""
Example {i} (similarity: {score:.3f}):
Source: {source_name}
```html
{chunk}
```
            """
            )

        return "\n".join(formatted_patterns)

    def _get_generation_prompt(
        self, visual_analysis: dict[str, Any], pattern_context: str, custom_instructions: str = ""
    ) -> str:
        """Create the code generation prompt"""

        components = visual_analysis.get("components", [])
        layout = visual_analysis.get("layout", "modern layout")
        style = visual_analysis.get("style", "clean and modern")
        color_scheme = visual_analysis.get("color_scheme", "neutral colors")

        # Build the prompt with custom instructions
        base_prompt = f"""Basándote en este análisis visual:
- Componentes identificados: {', '.join(components)}
- Layout: {layout}
- Estilo: {style}
- Esquema de colores: {color_scheme}

Y estos ejemplos similares encontrados:
{pattern_context}"""

        # Add custom instructions if provided
        if custom_instructions and custom_instructions.strip():
            base_prompt += f"""

INSTRUCCIONES ADICIONALES DEL USUARIO:
{custom_instructions.strip()}"""

        # Complete the prompt
        full_prompt = (
            base_prompt
            + """

Genera código HTML limpio y moderno con Tailwind CSS que implemente el diseño analizado.

ESTILO ARTESANAL - INSTRUCCIONES ESPECÍFICAS:
- EVITAR completamente íconos de librerías externas (FontAwesome, Heroicons, etc.)
- NO usar símbolos Unicode decorativos (→, ★, ✓, etc.)
- EVITAR gradientes muy llamativos y efectos "AI-looking"
- PREFERIR elementos geométricos simples creados con CSS/Tailwind
- USAR texto descriptivo plano en lugar de íconos
- MANTENER diseño limpio y profesional
- APLICAR principios de tipografía como elemento de diseño

REQUISITOS TÉCNICOS:
- Solo HTML y clases Tailwind CSS
- Sin JavaScript
- Responsive design (mobile-first)
- Estructura semántica correcta
- Accesibilidad básica (alt texts, labels apropiados)

ESTRUCTURA ESPERADA:
- DOCTYPE html completo
- Head con meta tags apropiados
- CDN de Tailwind CSS incluido
- Estructura de body organizada

IMPORTANTE: Si el usuario proporcionó instrucciones adicionales, asegúrate de incorporarlas en el código generado.

Responde SOLO con el código HTML, sin explicaciones adicionales."""
        )

        return full_prompt

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
