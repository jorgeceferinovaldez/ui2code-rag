# TODO: Posibles mejoras
# - Tests
# - Los returns tendrían que ser objetos (de Pyndantic?), no dicts
import os
import textwrap
from typing import Any
from datetime import datetime
import openai
from src.config import settings
from src.texts.prompts import SYSTEM_PROMPT, GENERATION_PROMPT_TEMPLATE
from src.texts.html_examples import write_examples, FALLBACK_HTML


OPENROUTER_API_KEY = settings.openrouter_api_key
OPENROUTER_BASE_URL = settings.openrouter_base_url
CODE_MODEL = settings.openrouter_model
OPENAI_KEY = settings.openai_key
OPENAI_MODEL = settings.openai_model
MAX_TOKENS = settings.max_tokens
TEMPERATURE = settings.temperature


class CodeAgent:
    def __init__(self):
        if not (OPENROUTER_API_KEY or OPENAI_KEY):
            raise ValueError("No API key found for available providers. Please set one in the environment.")
        if OPENROUTER_API_KEY:
            self.client = openai.OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)
            self.code_model = CODE_MODEL
            self.use_openrouter = True
        else:
            if OPENAI_KEY:
                self.client = openai.OpenAI(api_key=OPENAI_KEY)
                self.code_model = OPENAI_MODEL
                self.use_openrouter = False

    def create_sample_examples(self, examples_dir):
        """Escribir ejemplos HTML/CSS de referencia"""
        write_examples(examples_dir)

    def invoke(
        self, patterns: list[tuple], visual_analysis: dict[str, Any], custom_instructions: str = ""
    ) -> dict[str, Any]:
        """Generate HTML/CSS code based on patterns and visual analysis"""
        try:
            pattern_context = self._format_patterns_for_generation(patterns)
            prompt = self._get_generation_prompt(visual_analysis, pattern_context, custom_instructions)

            response = self.client.chat.completions.create(
                model=self.code_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
            )

            generated_code = response.choices[0].message.content
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
        """Format retrieved patterns for inclusion in the generation prompt"""
        if not patterns:
            return "No similar patterns found."

        formatted_patterns = []
        for i, (doc_id, chunk, metadata, score) in enumerate(patterns, 1):
            source_name = "unknown"
            if isinstance(metadata, dict):
                source_name = metadata.get("filename", metadata.get("source", "unknown"))
            else:
                source_name = getattr(metadata, "filename", getattr(metadata, "source", "unknown"))

            block = textwrap.dedent(
                f"""\
                Example {i} (similarity: {score:.3f}):
                Source: {source_name}
                ```html
                {chunk}
                ```
            """
            )
            formatted_patterns.append(block.strip())

        return "\n".join(formatted_patterns)

    def _get_generation_prompt(
        self, visual_analysis: dict[str, Any], pattern_context: str, custom_instructions: str = ""
    ) -> str:
        """Construct the full prompt for code generation"""
        components = ", ".join(visual_analysis.get("components", []))
        layout = visual_analysis.get("layout", "modern layout")
        style = visual_analysis.get("style", "clean and modern")
        color_scheme = visual_analysis.get("color_scheme", "neutral colors")

        ci_text = (
            f"\n\nINSTRUCCIONES ADICIONALES DEL USUARIO:\n{custom_instructions.strip()}"
            if custom_instructions and custom_instructions.strip()
            else ""
        )

        return GENERATION_PROMPT_TEMPLATE.format(
            components=components,
            layout=layout,
            style=style,
            color_scheme=color_scheme,
            pattern_context=pattern_context,
            custom_instructions=ci_text,
        )

    def _clean_generated_code(self, code: str) -> str:
        """Clean the generated code by removing extraneous text and markdown formatting"""
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

        return code.strip()

    def _get_fallback_html(self) -> str:
        return FALLBACK_HTML
